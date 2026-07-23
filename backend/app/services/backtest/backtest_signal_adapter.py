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
from app.services.backtest.backtest_regime import detect_regime_from_df

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


def signal_as_of(engine: str, df_T: pd.DataFrame) -> SignalResult:
    """Compute an engine's signal as-of the last bar of ``df_T`` (no look-ahead).

    Args:
        engine: ``'engine_1'`` (systematic) or ``'engine_2'`` (swing).
        df_T: daily OHLCV DataFrame WITH a ``timestamp`` column, chronological,
            truncated at the as-of date T (rows with timestamp > T must already
            be excluded by the caller — the replay engine owns that cursor).

    Returns:
        SignalResult. On insufficient history a neutral HOLD carries the engine's
        config_version so the stock is logged-but-not-traded (mirrors the live
        engine_2 path).
    """
    if engine == "engine_1":
        return _engine1_as_of(df_T)
    if engine == "engine_2":
        return _engine2_as_of(df_T)
    raise ValueError(f"Unknown engine {engine!r}; expected 'engine_1' or 'engine_2'.")


# ── Engine #1 (systematic) ───────────────────────────────────────────────────
def _engine1_as_of(df_T: pd.DataFrame) -> SignalResult:
    from app.services.signal.systematic import signal_systematic, _SYSTEMATIC_CONFIG_VERSION

    n = 0 if df_T is None else len(df_T)
    if n < ENGINE1_MIN_BARS:
        return SignalResult(
            signal="HOLD", confidence=0.5, weighted_score=0.0,
            component_scores={}, config_version=_SYSTEMATIC_CONFIG_VERSION,
            reasoning=[f"insufficient daily bars ({n} < {ENGINE1_MIN_BARS})"],
        )

    return signal_systematic(
        df_prices=df_T.tail(60).copy(),
        chart_patterns=_chart_patterns_as_of(df_T, window_days=30),
        candlestick_patterns=_candlestick_as_of(df_T, window_days=7, simple=True),
        sentiment_score=None,
        regime=detect_regime_from_df(df_T, lookback=100),
        dividend_split_signal=None,
    )


# ── Engine #2 (swing) ────────────────────────────────────────────────────────
def _engine2_as_of(df_T: pd.DataFrame) -> SignalResult:
    from app.services.signal.swing import signal_swing, _SWING_CONFIG_VERSION
    from app.services.technical_indicators import TechnicalIndicators

    n = 0 if df_T is None else len(df_T)
    if n < ENGINE2_MIN_BARS:
        return SignalResult(
            signal="HOLD", confidence=0.5, weighted_score=0.0,
            component_scores={}, config_version=_SWING_CONFIG_VERSION,
            reasoning=[f"insufficient daily bars ({n} < {ENGINE2_MIN_BARS})"],
        )

    df = _to_datetime_index(df_T.tail(250).copy())
    df = TechnicalIndicators.calculate_all_indicators(df)
    tech_recommendation = TechnicalIndicators.generate_recommendation(df)

    return signal_swing(
        df=df,
        tech_recommendation=tech_recommendation,
        chart_patterns_raw=_chart_patterns_as_of(df_T, window_days=90),
        candlestick_patterns_raw=_candlestick_as_of(df_T, window_days=30, simple=False),
        sentiment_scores=None,
        ml=(None, None, None),
        dividend_split_signal=None,
        strategy_consensus=_strategy_consensus_as_of(df, tech_recommendation),
    )


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


def _chart_patterns_as_of(df_T: pd.DataFrame, window_days: int) -> List[Dict[str, Any]]:
    """Recompute chart patterns on ``df_T`` (pure detector), keep those whose
    ``end_date`` is within ``window_days`` of the last bar (mirrors the live
    "last N days chart patterns" window). confirmation_level is not produced by
    the detector -> None (signal_systematic treats it as 0)."""
    try:
        from app.services.chart_patterns import ChartPatternDetector

        last = _last_ts(df_T)
        if last is None:
            return []
        cutoff = last - pd.Timedelta(days=window_days)
        detected = ChartPatternDetector(df_T.tail(CHART_PATTERN_LOOKBACK).copy()).detect_all_patterns()
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
