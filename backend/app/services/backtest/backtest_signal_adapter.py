"""
As-of-T signal assembly for the backtester (Phase 2) — the no-look-ahead core.

Mirrors ``ledger_signal_adapter.signal_for_ledger`` but takes an explicit price
DataFrame truncated at the as-of date T (``df_T``) and rebuilds each engine's
inputs FROM PRICE only:

  - chart / candlestick patterns: recomputed by the pure detectors on ``df_T``
  - technical indicators: recomputed fresh by ``calculate_all_indicators``
  - market regime: ``backtest_regime.detect_regime_from_df`` on ``df_T``
  - strategy consensus (engine_2): the pure ``StrategyManager.compute_strategy_consensus``

Unavailable at price-technical fidelity (passed as None / neutral, which the pure
signal functions already handle): news sentiment, ML predictions, dividend/split.

INVARIANT (AST-enforced by ``tests/test_backtest_no_lookahead.py``): this module
NEVER reads wall-clock time (``datetime.now`` / ``date.today`` / ``utcnow`` /
``time.time``), NEVER imports or uses ``IndicatorCacheService``, and NEVER opens
a DB session / queries ``StockPrice``/``ChartPattern``/``CandlestickPattern``/
``News``/``Prediction``. Everything derives from ``df_T`` — so the as-of-T signal
is a pure function of data <= T, with zero look-ahead by construction.

NOTE on causality vs. the candlestick +1 follow-through peek: the candlestick
detector checks the *next* bar for follow-through volume. Because the caller
truncates at T, the as-of-T bar has no "next" bar in ``df_T`` → the check is
skipped for it. That is the correct causal behaviour (we do not know T+1 yet);
the recorded as-of-T signal is stable regardless of future data.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.services.signal.types import SignalResult
from app.services.backtest.backtest_regime import detect_direction_from_df, detect_regime_from_df

logger = logging.getLogger(__name__)

ENGINE1_MIN_BARS = 60
ENGINE2_MIN_BARS = 50

# Bars fed to the (pure) pattern detectors. Patterns of interest form within the
# 30/90-day windows, so feeding the detector the recent N bars — not the whole
# multi-year warmup series — is a speedup and still fully causal (the tail of
# df_T is still <= T). The CHART detector needs >= ~300 bars for its pivot/peak
# logic (fewer raises an internal out-of-bounds); candlestick is per-candle so 60
# suffices.
CHART_PATTERN_LOOKBACK = 300
CANDLE_LOOKBACK = 60

# Cached pure strategy manager (auto-discovery is expensive; build once).
_STRATEGY_MANAGER = None


def _strategy_manager():
    global _STRATEGY_MANAGER
    if _STRATEGY_MANAGER is None:
        from app.services.strategies.registry import StrategyManager
        _STRATEGY_MANAGER = StrategyManager()
    return _STRATEGY_MANAGER


def signal_as_of(
    engine: str,
    df_T: pd.DataFrame,
    weights: Optional[Dict[str, float]] = None,
    bundle: Optional[Dict] = None,
    overlay_strength: float = 0.0,
) -> SignalResult:
    """Compute an engine's signal as-of the last bar of ``df_T`` (no look-ahead).

    Args:
        engine: ``'engine_1'`` (systematic) or ``'engine_2'`` (swing).
        df_T: daily OHLCV DataFrame WITH a ``timestamp`` column, chronological,
            truncated at the as-of date T (rows with timestamp > T must already
            be excluded by the caller — the replay engine owns that cursor).
        weights: optional signal-weight override (Phase 3 GA candidates). ``None``
            uses each engine's module defaults. Threaded straight through to
            ``signal_systematic`` / ``signal_swing`` — no look-ahead is introduced
            (weights only re-scale already-computed as-of-T component scores).
        bundle: optional PRE-ASSEMBLED weight-independent inputs (Phase 3 input
            cache). When given, the expensive assembly (indicators / patterns /
            regime / tech-recommendation) is skipped and only weights are applied —
            the path the GA uses to reuse ONE assembly across many candidates.
            ``None`` => assemble fresh from ``df_T`` (the Phase-2 per-bar path).
        overlay_strength: regime de-risk overlay strength in ``[0,1]`` (Phase 2.5).
            ``0.0`` (default) => overlay OFF, byte-identical to every prior call.
            Threaded into ``signal_systematic`` / ``signal_swing`` — no look-ahead
            (it only scales already-computed as-of-T scores / a sizing factor).

    Returns:
        SignalResult. On insufficient history a neutral HOLD carries the engine's
        config_version so the stock is logged-but-not-traded (mirrors the live
        engine_2 path).
    """
    if bundle is None:
        bundle = assemble_inputs(engine, df_T)
    # Phase 3 #3: if the bundle carries precomputed weight-independent components
    # (the GA input cache), skip the expensive component derivation (~99% of
    # signal cost) and only re-apply weights via ``assemble``. Identical to
    # signal_from_bundle by construction (signal_X == compose(compute, assemble)).
    # Single backtests don't enrich bundles, so they take the per-call path below.
    components = bundle.get("_components") if isinstance(bundle, dict) else None
    if components is not None:
        return assemble(engine, components, weights, overlay_strength)
    return signal_from_bundle(engine, bundle, weights, overlay_strength)


def assemble_inputs(engine: str, df_T: pd.DataFrame) -> Optional[Dict]:
    """Assemble the weight-independent signal inputs for one as-of-T frame.

    Returns a bundle dict (the kwargs for ``signal_systematic`` / ``signal_swing``,
    minus ``weights``), or ``None`` when there is insufficient history (the caller
    maps ``None`` -> a neutral HOLD). This is the EXPENSIVE part (indicators /
    patterns / regime / tech-recommendation) and is exactly what the Phase-3 input
    cache memoizes per (stock, T) so the GA reuses it across every weight
    candidate. Computed over ``df_T`` with T as the LAST bar => no look-ahead
    (the ``*_signal`` indicator columns are last-bar-broadcast, so they MUST be
    computed on a frame whose last bar IS T — full-series slicing would leak).
    """
    if engine == "engine_1":
        return _engine1_assemble(df_T)
    if engine == "engine_2":
        return _engine2_assemble(df_T)
    raise ValueError(f"Unknown engine {engine!r}; expected 'engine_1' or 'engine_2'.")


def signal_from_bundle(engine: str, bundle: Optional[Dict], weights: Optional[Dict[str, float]] = None,
                       overlay_strength: float = 0.0) -> SignalResult:
    """Apply ``weights`` to a pre-assembled bundle -> SignalResult (cheap; no
    indicator recompute). ``bundle=None`` => a neutral HOLD (insufficient history),
    carrying the engine's config_version so the stock is logged-but-not-traded."""
    if bundle is None:
        return _hold_signal(engine)
    # ``pattern_levels`` + ``_components`` are backtest-only siblings of the signal
    # kwargs (order-calc SL/TP reuses the bundle's chart detection; ``_components``
    # is the Phase-3 #3 cached weight-independent stage). Strip BOTH before
    # splatting so the pure signal functions never see an unexpected kwarg — an
    # enriched bundle passed here directly (e.g. a no-look-ahead cache test, or any
    # future caller) must not leak ``_components`` into signal_swing/systematic.
    kwargs = {k: v for k, v in bundle.items() if k not in ("pattern_levels", "_components")}
    if engine == "engine_1":
        from app.services.signal.systematic import signal_systematic
        return signal_systematic(**kwargs, weights=weights, overlay_strength=overlay_strength)
    from app.services.signal.swing import signal_swing
    return signal_swing(**kwargs, weights=weights, overlay_strength=overlay_strength)


def compute_components(engine: str, bundle: Optional[Dict]) -> Optional[Dict]:
    """The weight-independent component stage (Phase 3 #3 cache). Derives the
    per-component votes / scores ONCE per (stock, T); :func:`assemble` then
    re-applies weights per candidate. This is the cacheable half of each engine's
    signal (``_systematic_scores`` / ``_swing_components``) and is exactly what the
    GA memoizes so hundreds of candidates skip the ~99%-of-cost derivation.

    ``bundle=None`` -> ``None`` (the caller maps that to a neutral HOLD). Strips
    ``pattern_levels`` (a backtest-only sibling, not a signal kwarg) exactly like
    :func:`signal_from_bundle`.
    """
    if bundle is None:
        return None
    kwargs = bundle if "pattern_levels" not in bundle else {
        k: v for k, v in bundle.items() if k != "pattern_levels"
    }
    if engine == "engine_1":
        from app.services.signal.systematic import _systematic_scores
        return _systematic_scores(**kwargs)
    from app.services.signal.swing import _swing_components
    return _swing_components(**kwargs)


def assemble(engine: str, components: Optional[Dict], weights: Optional[Dict[str, float]] = None,
             overlay_strength: float = 0.0) -> SignalResult:
    """Apply ``weights`` to a precomputed component dict -> SignalResult (cheap;
    the per-candidate path). ``components=None`` -> a neutral HOLD (insufficient
    history). Identical to :func:`signal_from_bundle` by construction, since each
    ``signal_X`` is ``compose(compute_components, assemble)``."""
    if components is None:
        return _hold_signal(engine)
    if engine == "engine_1":
        from app.services.signal.systematic import _decide_systematic
        return _decide_systematic(components, weights, overlay_strength)
    from app.services.signal.swing import _assemble_swing
    return _assemble_swing(components, weights, overlay_strength)


def _hold_signal(engine: str) -> SignalResult:
    try:
        if engine == "engine_1":
            from app.services.signal.systematic import _SYSTEMATIC_CONFIG_VERSION
            cv = _SYSTEMATIC_CONFIG_VERSION
        else:
            from app.services.signal.swing import _SWING_CONFIG_VERSION
            cv = _SWING_CONFIG_VERSION
    except Exception:
        cv = "unknown"
    return SignalResult(
        signal="HOLD", confidence=0.5, weighted_score=0.0,
        component_scores={}, config_version=cv, reasoning=["insufficient daily bars"],
    )


# ── Engine #1 (systematic) ───────────────────────────────────────────────────
def _engine1_assemble(df_T: pd.DataFrame) -> Optional[Dict]:
    """Assemble engine_1 inputs as-of T (bundle of signal_systematic kwargs)."""
    n = 0 if df_T is None else len(df_T)
    if n < ENGINE1_MIN_BARS:
        return None
    from app.services.technical_indicators import TechnicalIndicators

    df_prices = df_T.tail(60).copy()
    # Compute indicators ONCE here (the expensive part) so the cached bundle lets
    # every GA candidate skip it. Computed on df_T.tail(60) with T as last bar =>
    # the last-bar-broadcast *_signal columns reflect T, not the future. No leak.
    indicators = TechnicalIndicators.calculate_all_indicators(df_prices)
    # Detect chart patterns ONCE: the projection feeds the signal, and the raw
    # first-pattern (SL, TP) feeds order-calc (calculate_levels) so a fresh BUY
    # never re-runs this ~1.2s detector. Same df_T.tail(300) detection either way.
    detected = _detect_chart_patterns(df_T)
    return {
        "df_prices": df_prices,
        "chart_patterns": _chart_patterns_as_of(df_T, window_days=30, detected=detected),
        "candlestick_patterns": _candlestick_as_of(df_T, window_days=7, simple=True),
        "sentiment_score": None,
        "regime": detect_regime_from_df(df_T, lookback=100),
        # Phase 2.5: per-stock directional regime as-of T (sibling compute, pure)
        # — feeds the regime de-risk overlay's buy-score scaling. Inert unless the
        # caller passes a nonzero ``overlay_strength``.
        "regime_direction": detect_direction_from_df(df_T, lookback=100),
        "dividend_split_signal": None,
        "indicators": indicators,
        "pattern_levels": _pattern_levels_from_detected(detected),
    }


# ── Engine #2 (swing) ────────────────────────────────────────────────────────
def _engine2_assemble(df_T: pd.DataFrame) -> Optional[Dict]:
    """Assemble engine_2 inputs as-of T (bundle of signal_swing kwargs)."""
    n = 0 if df_T is None else len(df_T)
    if n < ENGINE2_MIN_BARS:
        return None
    from app.services.technical_indicators import TechnicalIndicators

    # Indicators + tech_recommendation computed ONCE here (the expensive parts) so
    # the cached bundle lets every GA candidate skip them. df_T.tail(250) with T as
    # last bar => no look-ahead (broadcast *_signal columns reflect T).
    df = _to_datetime_index(df_T.tail(250).copy())
    df = TechnicalIndicators.calculate_all_indicators(df)
    tech_recommendation = TechnicalIndicators.generate_recommendation(df)
    detected = _detect_chart_patterns(df_T)
    return {
        "df": df,
        "tech_recommendation": tech_recommendation,
        "chart_patterns_raw": _chart_patterns_as_of(df_T, window_days=90, detected=detected),
        "candlestick_patterns_raw": _candlestick_as_of(df_T, window_days=30, simple=False),
        "sentiment_scores": None,
        "ml": (None, None, None),
        "dividend_split_signal": None,
        "strategy_consensus": _strategy_consensus_as_of(df, tech_recommendation),
        "pattern_levels": _pattern_levels_from_detected(detected),
    }


# ── price-only input builders ────────────────────────────────────────────────
def _to_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure a DatetimeIndex (what calculate_all_indicators + signal_swing expect)."""
    if isinstance(df.index, pd.DatetimeIndex):
        return df
    if "timestamp" in df.columns:
        return df.set_index("timestamp")
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    return df


def _last_ts(df_T: pd.DataFrame) -> Optional[pd.Timestamp]:
    if df_T is None or len(df_T) == 0 or "timestamp" not in df_T.columns:
        return None
    return pd.Timestamp(df_T["timestamp"].iloc[-1])


def _detect_chart_patterns(df_T: pd.DataFrame) -> List[Dict[str, Any]]:
    """Run the pure chart detector ONCE on ``df_T.tail(CHART_PATTERN_LOOKBACK)``.

    Shared by the signal projection (``_chart_patterns_as_of``) and the order-calc
    pattern levels (``_pattern_levels_from_detected``) so a fresh BUY never re-runs
    this expensive (~1s) detection. Failure -> [] (neutral, no crash).
    """
    try:
        from app.services.chart_patterns import ChartPatternDetector
        return ChartPatternDetector(df_T.tail(CHART_PATTERN_LOOKBACK).copy()).detect_all_patterns()
    except Exception as e:  # noqa: BLE001 — detection failure -> neutral (no crash)
        logger.warning("[backtest] chart pattern detection failed: %s", e)
        return []


def _pattern_levels_from_detected(detected: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    """First detected chart pattern's ``(stop_loss, target_price)`` — exactly what
    ``backtest_order_calc._pattern_levels`` would recompute. Reuses the bundle's
    detection instead of re-running the detector."""
    try:
        for p in detected or []:
            sl, tp = p.get("stop_loss"), p.get("target_price")
            if sl is not None and tp is not None:
                return float(sl), float(tp)
    except Exception:  # noqa: BLE001
        pass
    return None, None


def _chart_patterns_as_of(df_T: pd.DataFrame, window_days: int, detected: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Recompute chart patterns on ``df_T`` (pure detector), keep those whose
    ``end_date`` is within ``window_days`` of the last bar (mirrors the live
    "last N days chart patterns" window). confirmation_level is not produced by
    the detector -> None (signal_systematic treats it as 0). Pass ``detected`` to
    reuse an existing detection (avoids re-running the ~1s detector)."""
    try:
        last = _last_ts(df_T)
        if last is None:
            return []
        cutoff = last - pd.Timedelta(days=window_days)
        if detected is None:
            detected = _detect_chart_patterns(df_T)
        out: List[Dict[str, Any]] = []
        for p in detected:
            end = p.get("end_date")
            if end is None or pd.Timestamp(end) < cutoff:
                continue
            out.append({
                "signal": p.get("signal"),
                "confidence_score": p.get("confidence_score"),
                "start_date": p.get("start_date"),
                "end_date": p.get("end_date"),
                "confirmation_level": None,
            })
        return out
    except Exception as e:  # noqa: BLE001 — detection failure -> neutral (no crash)
        logger.warning("[backtest] chart pattern detection failed: %s", e)
        return []


def _candlestick_as_of(df_T: pd.DataFrame, window_days: int, simple: bool) -> List[Dict[str, Any]]:
    """Recompute candlestick patterns on ``df_T`` (pure detector), keep those
    within ``window_days`` of the last bar. ``simple`` returns engine_1's shape
    (``{pattern_type, confidence_score}``); else engine_2's full shape."""
    try:
        from app.services.candlestick_patterns import CandlestickPatternDetector

        last = _last_ts(df_T)
        if last is None:
            return []
        cutoff = last - pd.Timedelta(days=window_days)
        detected = CandlestickPatternDetector(df_T.tail(CANDLE_LOOKBACK).copy()).detect_all_patterns()
        out: List[Dict[str, Any]] = []
        for p in detected:
            ts = p.get("timestamp")
            if ts is None or pd.Timestamp(ts) < cutoff:
                continue
            if simple:
                out.append({
                    "pattern_type": p.get("pattern_type"),
                    "confidence_score": p.get("confidence_score"),
                })
            else:
                out.append({
                    "pattern_name": p.get("pattern_name"),
                    "pattern_type": p.get("pattern_type"),
                    "timestamp": p.get("timestamp"),
                    "confidence_score": p.get("confidence_score"),
                })
        return out
    except Exception as e:  # noqa: BLE001 — detection failure -> neutral (no crash)
        logger.warning("[backtest] candlestick detection failed: %s", e)
        return []


def _strategy_consensus_as_of(df: pd.DataFrame, tech_recommendation: Dict[str, Any]) -> Optional[Tuple[Optional[str], Optional[float]]]:
    """Engine #2 strategy consensus via the PURE consensus helper (no DB/now)."""
    try:
        rec, conf, _breakdown = _strategy_manager().compute_strategy_consensus(
            df, tech_recommendation["indicators"]
        )
        return (rec, conf) if rec is not None else None
    except Exception as e:  # noqa: BLE001 — consensus failure -> None (neutral vote)
        logger.warning("[backtest] strategy consensus failed: %s", e)
        return None
