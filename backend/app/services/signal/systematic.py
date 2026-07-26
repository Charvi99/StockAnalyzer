"""
Engine #1 systematic pure signal function (Phase 0.4b).

Extracted verbatim from ``recommendation_engine.generate_final_recommendation`` —
the 6-factor weighted score (chart / candlestick / technical / sentiment / regime
/ dividend-split) that produces a BUY/SELL/HOLD. This is the DB-free core: it
takes DataFrames + plain dicts and returns a :class:`SignalResult`, so the
paper-trading ledger (Phase 1) and backtester (Phase 2) call exactly what the
live engine produces.

Behavior is identical to ``generate_final_recommendation`` as of this refactor —
including the per-component ``try/except`` that logs a warning and leaves the
score at 0.0 on failure (a deliberate behavior-preserving choice; "kill silent
failures" is a separate, later concern). The 0.4b baseline diff
(`/tmp/engine1_baseline.json`, 6 real stocks) is byte-identical before/after.

The DB→DataFrame adapter lives in ``recommendation_engine.py``.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from app.services.signal.regime_overlay import buy_score_factor
from app.services.signal.types import SignalResult, config_version
from app.services.technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

# ── Policy constants (locked by tests/test_collapse_targets.py) ──────────────
WEIGHTS: Dict[str, float] = {
    'chart_patterns': 0.28,
    'candlestick_patterns': 0.14,
    'technical_indicators': 0.23,
    'sentiment': 0.13,
    'market_regime': 0.12,
    'dividend_split_signals': 0.10,
}
BUY_SELL_THRESHOLD = 0.3
REGIME_SCORES: Dict[str, float] = {
    'trending_up': 0.8,
    'trend': 0.6,
    'accumulation': 0.5,
    'ranging': 0.0,
    'distribution': -0.5,
    'trending_down': -0.8,
    'volatile': -0.3,
}
SCHEMA = "systematic-v1"

_SYSTEMATIC_CONFIG_VERSION = config_version(
    WEIGHTS, {"buy_sell_threshold": BUY_SELL_THRESHOLD}, REGIME_SCORES, SCHEMA
)


def config_version_for(weights: Optional[Dict[str, float]] = None,
                       overlay_strength: float = 0.0) -> str:
    """Deterministic config_version for a weight set (``None`` => live defaults).

    Single source of truth shared by :func:`signal_systematic` and the backtester
    (replay engine), so a run's recorded ``config_version`` always matches its
    EFFECTIVE weights. Passing the exact defaults reproduces
    ``_SYSTEMATIC_CONFIG_VERSION``.

    ``overlay_strength`` is folded into the hash ONLY when nonzero, so the
    regime de-risk overlay (Phase 2.5) is attributable when active while the
    default (``0.0`` / OFF) stays byte-identical to every prior run.
    """
    eff = weights if weights is not None else WEIGHTS
    parts: list = [eff, {"buy_sell_threshold": BUY_SELL_THRESHOLD}, REGIME_SCORES, SCHEMA]
    if overlay_strength:
        parts.append({"regime_overlay": overlay_strength})
    return config_version(*parts)


def signal_systematic(
    df_prices: pd.DataFrame,
    chart_patterns: List[Dict[str, Any]],
    candlestick_patterns: List[Dict[str, Any]],
    sentiment_score: Optional[float],
    regime: str,
    dividend_split_signal: Optional[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
    indicators: Optional[pd.DataFrame] = None,
    regime_direction: Optional[str] = None,
    overlay_strength: float = 0.0,
) -> SignalResult:
    """
    Pure Engine #1 signal: 6-factor weighted score -> BUY/SELL/HOLD.

    Args:
        df_prices: daily OHLCV DataFrame (with a ``timestamp`` column, chronological).
            May be empty -> technical score stays 0.
        chart_patterns: list of ``{signal, confidence_score, confirmation_level}``
            dicts (last 30d). ``confirmation_level`` may be None.
        candlestick_patterns: list of ``{pattern_type, confidence_score}`` dicts
            (last 7d).
        sentiment_score: average news sentiment in [-1, 1], or None.
        regime: MarketRegimeService regime label (e.g. ``'trending_up'``).
        dividend_split_signal: DividendSplitDetector signal dict, or None.
        weights: optional override for the 6 component WEIGHTS (Phase 3 GA /
            backtest candidates). ``None`` (default) uses the module WEIGHTS —
            behaviour-identical to every existing caller. Passing the exact
            defaults yields the same ``config_version`` + signal.
        indicators: optional precomputed indicator DataFrame (Phase 3 precompute).
        regime_direction: optional per-stock directional regime
            (``'bearish'`` / ``'bearish_weak'`` / ...) from
            ``MarketRegimeService.detect_tcr_regime``. Consumed only by the
            regime de-risk overlay (Phase 2.5); ``None`` => no direction-based
            suppression (overlay inactive even at nonzero strength).
        overlay_strength: regime de-risk overlay strength in ``[0, 1]``.
            ``0.0`` (default) => overlay OFF, byte-identical to every prior call.

    Returns:
        SignalResult. ``component_scores`` are RAW (unrounded); the adapter rounds
        for the legacy dict shape. ``weighted_score``/``confidence`` are also raw.
    """
    # Phase 3 #3: behaviour-preserving factor. The per-component ``scores`` are
    # weight-independent (cached per (stock,T) by the GA); only the weighted sum +
    # threshold depend on weights. signal_systematic = compose(compute, decide) so
    # the live path and the backtest share ONE implementation (no divergence).
    return _decide_systematic(
        _systematic_scores(
            df_prices, chart_patterns, candlestick_patterns, sentiment_score,
            regime, dividend_split_signal, indicators, regime_direction,
        ),
        weights, overlay_strength,
    )


def _systematic_scores(
    df_prices: pd.DataFrame,
    chart_patterns: List[Dict[str, Any]],
    candlestick_patterns: List[Dict[str, Any]],
    sentiment_score: Optional[float],
    regime: str,
    dividend_split_signal: Optional[Dict[str, Any]],
    indicators: Optional[pd.DataFrame] = None,
    regime_direction: Optional[str] = None,
) -> Dict[str, Any]:
    """Weight-independent Engine #1 per-component scores as-of T — the cacheable
    half of :func:`signal_systematic`. Returns
    ``{scores, regime, sentiment_score, direction}``; ``scores`` is the 6-component
    dict in [-1,1]. The per-component ``try/except`` (0.0 on failure) is preserved
    verbatim. No weights are read here. ``direction`` (the per-stock directional
    regime) is carried through untouched for the regime overlay (Phase 2.5) — it
    does not affect the per-component scores, only the later buy-score scaling."""
    scores: Dict[str, float] = {k: 0.0 for k in WEIGHTS}

    # ============================================
    # 1. CHART PATTERNS (weight 0.28)
    # ============================================
    try:
        if chart_patterns:
            bullish_count = sum(1 for p in chart_patterns if p.get('signal') == 'bullish')
            bearish_count = sum(1 for p in chart_patterns if p.get('signal') == 'bearish')

            # Weight by confidence and multi-timeframe confirmation
            bullish_score = sum(
                float(p.get('confidence_score')) * (1 + float(p.get('confirmation_level') or 0) * 0.2)
                for p in chart_patterns if p.get('signal') == 'bullish'
            )
            bearish_score = sum(
                float(p.get('confidence_score')) * (1 + float(p.get('confirmation_level') or 0) * 0.2)
                for p in chart_patterns if p.get('signal') == 'bearish'
            )

            if bullish_count + bearish_count > 0:
                scores['chart_patterns'] = (bullish_score - bearish_score) / (bullish_count + bearish_count)
                scores['chart_patterns'] = max(-1.0, min(1.0, scores['chart_patterns']))

    except Exception as e:
        logger.warning(f"Chart pattern scoring failed: {e}")

    # ============================================
    # 2. CANDLESTICK PATTERNS (weight 0.14)
    # ============================================
    try:
        if candlestick_patterns:
            bullish_cs = sum(float(p.get('confidence_score')) for p in candlestick_patterns if p.get('pattern_type') == 'bullish')
            bearish_cs = sum(float(p.get('confidence_score')) for p in candlestick_patterns if p.get('pattern_type') == 'bearish')

            total_cs = bullish_cs + bearish_cs
            if total_cs > 0:
                scores['candlestick_patterns'] = (bullish_cs - bearish_cs) / total_cs
                scores['candlestick_patterns'] = max(-1.0, min(1.0, scores['candlestick_patterns']))

    except Exception as e:
        logger.warning(f"Candlestick pattern scoring failed: {e}")

    # ============================================
    # 3. TECHNICAL INDICATORS (weight 0.23)
    # ============================================
    try:
        # `indicators` may be supplied precomputed (Phase 3 backtest precompute);
        # otherwise compute from df_prices. The rest of this block reads the local
        # `indicators`, so either source is transparent (and byte-identical: the
        # precompute is a causal slice — see backtest/precompute.py).
        if indicators is None and not (df_prices is None or df_prices.empty):
            indicators = TechnicalIndicators.calculate_all_indicators(df_prices)

        if indicators is not None and not indicators.empty:
            # Advanced scoring with Phase 1 + Phase 2 indicators
            tech_score = 0.0
            indicator_count = 0

            # NOTE: `indicators` is a DataFrame. Values read via .iloc[-1], NOT
            # dict-style ['value'] — the old access raised KeyError and was silently
            # swallowed, so RSI/MACD/SMA never contributed. (BU1 audit)

            # RSI
            if 'rsi' in indicators.columns:
                rsi = indicators['rsi'].iloc[-1]
                if pd.notna(rsi):
                    if rsi < 30:
                        tech_score += 1.0  # Oversold - bullish
                    elif rsi > 70:
                        tech_score -= 1.0  # Overbought - bearish
                    indicator_count += 1

            # MACD — 'macd_trend' is the bullish/bearish signal column
            # (do NOT confuse with 'macd_signal', which is the signal LINE)
            if 'macd_trend' in indicators.columns:
                macd_signal = indicators['macd_trend'].iloc[-1]
                if pd.notna(macd_signal):
                    if macd_signal == 'bullish':
                        tech_score += 1.0
                    elif macd_signal == 'bearish':
                        tech_score -= 1.0
                    indicator_count += 1

            # Moving Average Trend (golden / death cross)
            if 'sma_50' in indicators.columns and 'sma_200' in indicators.columns:
                sma_50 = indicators['sma_50'].iloc[-1]
                sma_200 = indicators['sma_200'].iloc[-1]
                if pd.notna(sma_50) and pd.notna(sma_200):
                    if sma_50 > sma_200:
                        tech_score += 0.5  # Golden cross zone
                    else:
                        tech_score -= 0.5  # Death cross zone
                    indicator_count += 1

            # Check market regime first (PHASE 3B: HT_TRENDMODE)
            market_regime = 'TREND'  # Default
            if 'ht_trendmode' in indicators.columns:
                regime_mode = indicators['ht_trendmode'].iloc[-1]
                market_regime = 'TREND' if regime_mode == 1 else 'CYCLE'

            # Advanced Trend Indicators (KAMA, TEMA, T3, HT_Trendline, AROON, TRIX, MAMA, APO, PPO)
            trend_signals = []
            if 'kama_signal' in indicators.columns:
                trend_signals.append(indicators['kama_signal'].iloc[-1])
            if 'tema_signal' in indicators.columns:
                trend_signals.append(indicators['tema_signal'].iloc[-1])
            if 't3_signal' in indicators.columns:
                trend_signals.append(indicators['t3_signal'].iloc[-1])
            if 'ht_signal' in indicators.columns:
                trend_signals.append(indicators['ht_signal'].iloc[-1])
            if 'aroon_signal' in indicators.columns:
                trend_signals.append(indicators['aroon_signal'].iloc[-1])
            if 'trix_signal' in indicators.columns:
                trend_signals.append(indicators['trix_signal'].iloc[-1])
            if 'mama_signal' in indicators.columns:
                trend_signals.append(indicators['mama_signal'].iloc[-1])
            if 'apo_signal' in indicators.columns:
                trend_signals.append(indicators['apo_signal'].iloc[-1])
            if 'ppo_signal' in indicators.columns:
                trend_signals.append(indicators['ppo_signal'].iloc[-1])

            if trend_signals:
                buy_count = sum(1 for s in trend_signals if s == 'BUY')
                sell_count = sum(1 for s in trend_signals if s == 'SELL')
                if buy_count + sell_count > 0:
                    # Trend confirmation bonus: if 4+ agree, add extra weight
                    trend_score = (buy_count - sell_count) / len(trend_signals)
                    if buy_count >= 4 or sell_count >= 4:
                        trend_score *= 1.8  # Very strong trend consensus (Phase 3 upgrade: 1.5 -> 1.8)

                    # Market regime adjustment: reduce trend weight in cycling markets
                    if market_regime == 'CYCLE':
                        trend_score *= 0.5  # Half weight for trend indicators in cycling markets

                    tech_score += trend_score
                    indicator_count += 1

            # Advanced Momentum Indicators (MFI, Williams %R, ROC, CMO, StochRSI, ULTOSC, BOP, ADOSC)
            momentum_signals = []
            if 'mfi_signal' in indicators.columns:
                momentum_signals.append(indicators['mfi_signal'].iloc[-1])
            if 'willr_signal' in indicators.columns:
                momentum_signals.append(indicators['willr_signal'].iloc[-1])
            if 'roc_signal' in indicators.columns:
                momentum_signals.append(indicators['roc_signal'].iloc[-1])
            if 'cmo_signal' in indicators.columns:
                momentum_signals.append(indicators['cmo_signal'].iloc[-1])
            if 'stochrsi_signal' in indicators.columns:
                momentum_signals.append(indicators['stochrsi_signal'].iloc[-1])
            if 'ultosc_signal' in indicators.columns:
                momentum_signals.append(indicators['ultosc_signal'].iloc[-1])
            if 'bop_signal' in indicators.columns:
                momentum_signals.append(indicators['bop_signal'].iloc[-1])
            if 'adosc_signal' in indicators.columns:
                momentum_signals.append(indicators['adosc_signal'].iloc[-1])

            if momentum_signals:
                buy_count = sum(1 for s in momentum_signals if s == 'BUY')
                sell_count = sum(1 for s in momentum_signals if s == 'SELL')
                if buy_count + sell_count > 0:
                    # Momentum confirmation bonus
                    momentum_score = (buy_count - sell_count) / len(momentum_signals)
                    if buy_count >= 4 or sell_count >= 4:
                        momentum_score *= 1.5  # Strong momentum consensus (Phase 3 upgrade: 1.3 -> 1.5)

                    # Market regime adjustment: increase momentum weight in cycling markets
                    if market_regime == 'CYCLE':
                        momentum_score *= 1.5  # Higher weight for momentum in cycling markets

                    tech_score += momentum_score * 0.8  # Slightly lower weight than trend
                    indicator_count += 1

            # Linear Regression Slope (Trend strength)
            if 'linearreg_signal' in indicators.columns:
                lr_signal = indicators['linearreg_signal'].iloc[-1]
                if lr_signal == 'BUY':
                    tech_score += 0.7
                elif lr_signal == 'SELL':
                    tech_score -= 0.7
                indicator_count += 1

            if indicator_count > 0:
                scores['technical_indicators'] = tech_score / indicator_count
                scores['technical_indicators'] = max(-1.0, min(1.0, scores['technical_indicators']))

    except Exception as e:
        logger.warning(f"Technical indicator scoring failed: {e}")

    # ============================================
    # 4. SENTIMENT (weight 0.13)
    # ============================================
    try:
        if sentiment_score is not None:
            scores['sentiment'] = sentiment_score  # Already in -1.0 to 1.0 range
    except Exception as e:
        logger.warning(f"Sentiment scoring failed: {e}")

    # ============================================
    # 5. MARKET REGIME (weight 0.12)
    # ============================================
    try:
        scores['market_regime'] = REGIME_SCORES.get(regime, 0.0)
    except Exception as e:
        logger.warning(f"Market regime scoring failed: {e}")

    # ============================================
    # 6. DIVIDEND & SPLIT SIGNALS (weight 0.10)
    # ============================================
    try:
        if dividend_split_signal and dividend_split_signal.get('has_signal'):
            # Convert score_adjustment (-20 to +20) to normalized score (-1.0 to +1.0)
            scores['dividend_split_signals'] = dividend_split_signal['score_adjustment'] / 20.0
            scores['dividend_split_signals'] = max(-1.0, min(1.0, scores['dividend_split_signals']))
    except Exception as e:
        logger.warning(f"Dividend/split signal detection failed: {e}")

    return {"scores": scores, "regime": regime, "sentiment_score": sentiment_score,
            "direction": regime_direction}


def _decide_systematic(comp: Dict[str, Any], weights: Optional[Dict[str, float]] = None,
                       overlay_strength: float = 0.0) -> SignalResult:
    """Weight-dependent half of :func:`signal_systematic`: apply ``weights`` to the
    cached component scores -> BUY/SELL/HOLD. Pure; called once per GA candidate
    (and by :func:`signal_systematic` itself, so live + backtest stay identical)."""
    eff_weights: Dict[str, float] = weights if weights is not None else WEIGHTS
    scores: Dict[str, float] = comp["scores"]
    regime: str = comp["regime"]
    sentiment_score: Optional[float] = comp["sentiment_score"]
    direction: Optional[str] = comp.get("direction")
    # ============================================
    # CALCULATE FINAL RECOMMENDATION
    # ============================================
    weighted_score = sum(scores[key] * eff_weights[key] for key in scores.keys())

    # Regime de-risk overlay (Phase 2.5): scale the BUY-leaning (positive) score
    # down in a bearish per-stock regime — proportional, never a hard ban. OFF at
    # ``overlay_strength == 0`` (byte-identical). Sells (negative) / holds (~0)
    # are never touched, so bearish SELL signals keep full strength.
    overlay_factor = 1.0
    if overlay_strength > 0.0 and weighted_score > 0.0:
        overlay_factor = buy_score_factor(direction, overlay_strength)
        weighted_score *= overlay_factor

    if weighted_score > BUY_SELL_THRESHOLD:
        final_recommendation = 'BUY'
        overall_confidence = min(abs(weighted_score), 1.0)
    elif weighted_score < -BUY_SELL_THRESHOLD:
        final_recommendation = 'SELL'
        overall_confidence = min(abs(weighted_score), 1.0)
    else:
        final_recommendation = 'HOLD'
        overall_confidence = 0.5  # Moderate confidence in HOLD

    # config_version reflects the EFFECTIVE weights + overlay (None/0 => live
    # defaults); each GA candidate / overlay setting is thereby attributable.
    # Exact-default weights + overlay OFF hash identically to
    # _SYSTEMATIC_CONFIG_VERSION.
    cv = config_version_for(weights, overlay_strength)

    # ── human-readable reasoning (per-component breakdown, mirrors signal_swing) ──
    reasoning = [
        f"📊 Chart patterns (w {eff_weights['chart_patterns']:.2f}): {scores['chart_patterns']:+.2f}",
        f"🕯️ Candlestick (w {eff_weights['candlestick_patterns']:.2f}): {scores['candlestick_patterns']:+.2f}",
        f"📈 Technical indicators (w {eff_weights['technical_indicators']:.2f}): {scores['technical_indicators']:+.2f}",
        (f"💬 Sentiment (w {eff_weights['sentiment']:.2f}): {sentiment_score:+.2f}"
         if sentiment_score is not None
         else f"💬 Sentiment (w {eff_weights['sentiment']:.2f}): n/a"),
        f"🌐 Market regime (w {eff_weights['market_regime']:.2f}): {regime} → {scores['market_regime']:+.2f}",
        f"💰 Dividend/split (w {eff_weights['dividend_split_signals']:.2f}): {scores['dividend_split_signals']:+.2f}",
    ]
    if overlay_factor < 1.0:
        reasoning.append(
            f"🛡️ Regime overlay (strength {overlay_strength:.2f}): buy score × {overlay_factor:.2f} "
            f"(direction={direction}) — bearish-regime de-risk"
        )
    reasoning.append(
        f"➡️ Weighted {weighted_score:+.3f} (BUY/SELL when |·|>{BUY_SELL_THRESHOLD}) → "
        f"{final_recommendation} @ {overall_confidence:.0%} confidence"
    )

    return SignalResult(
        signal=final_recommendation,
        confidence=overall_confidence,
        weighted_score=weighted_score,
        component_scores=scores,
        config_version=cv,
        reasoning=reasoning,
        regime=regime,
    )
