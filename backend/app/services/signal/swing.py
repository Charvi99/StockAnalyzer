"""
Engine #2 swing pure signal function (Phase 0.4c).

Extracted from ``realtime_recommendation._get_recommendation_for_stock`` — the
swing-trading-aware recommendation: a normalized weighted vote over the PRESENT
components (technical / chart pattern / candlestick / sentiment / ML), a weekly-
trend override, a Phase-2C confidence multiplier, and dividend/split adjustments.

This is the DB-free core: it takes the indicator DataFrame + pre-time-filtered
pattern/news/ml/dividend data and returns a :class:`SignalResult`. It has no
current-time reads and no database access — every ``now``-based time window
(30-day candlesticks, 90-day chart patterns, 30-day news) is applied by the
adapter, so the function is a pure function of its inputs and is replayable
bar-by-bar by the backtester (Phase 2) and stampable by the ledger (Phase 1).

Behavior is identical to ``_get_recommendation_for_stock`` as of this refactor,
verified head-to-head on live data (5 stocks) to floating-point exactness. The
Engine #2-specific fields the response needs are carried in ``SignalResult.extras``;
the common contract (signal/confidence/regime/config_version) is on the result.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.services.signal.types import SignalResult, config_version
from app.services.signal.core import (
    check_weekly_trend,
    detect_swing_points,
    categorize_candlestick_pattern,
    evaluate_swing_trading_context,
)

logger = logging.getLogger(__name__)

# ── Policy constants ─────────────────────────────────────────────────────────
# Weighted vote over PRESENT components (normalized). A missing component cedes
# its share to the rest instead of being silently dropped.
STRATEGY_WEIGHT = 0.10  # Phase 0.5: weight of the strategy-consensus component
COMPONENT_WEIGHTS = {
    "technical": 0.35,
    "chart_pattern": 0.25,
    "candlestick": 0.15,
    "sentiment": 0.15,
    "ml": 0.10,
    # The strategy consensus across the registered strategies (Phase 0.5).
    # The vote below is self-normalizing over the present components, so adding
    # this claims ~STRATEGY_WEIGHT/(1+STRATEGY_WEIGHT) ≈ 9% of the vote from the
    # existing components. Captured by _SWING_CONFIG_VERSION so the Phase 1
    # ledger attributes pre/post-strategy signals to different versions.
    "strategy": STRATEGY_WEIGHT,
}
ML_CONFIDENCE_GATE = 0.6       # ML only votes if confidence > this
ALL_AGREE_BOOST = 1.1          # confidence multiplier when every component agrees
WEEKLY_BULLISH_BOOST = 1.05    # BUY into a bullish weekly trend
BEARISH_OVERRIDE_CONF_CUT = 0.5  # BUY -> HOLD against bearish weekly: halve confidence
FINAL_CONF_FLOOR = 0.3         # overall_confidence is capped to [0.3, 1.0]
SCHEMA = "swing-v1"

_SWING_CONFIG_VERSION = config_version(
    COMPONENT_WEIGHTS,
    {"ml_gate": ML_CONFIDENCE_GATE, "agree_boost": ALL_AGREE_BOOST,
     "weekly_bullish_boost": WEEKLY_BULLISH_BOOST,
     "bearish_override_cut": BEARISH_OVERRIDE_CONF_CUT,
     "floor": FINAL_CONF_FLOOR},
    SCHEMA,
)


def config_version_for(weights: Optional[Dict[str, float]] = None) -> str:
    """Deterministic config_version for a weight set (``None`` => live defaults).

    Single source of truth shared by :func:`signal_swing` and the backtester
    (replay engine), so a run's recorded ``config_version`` always matches its
    EFFECTIVE weights. Passing the exact defaults reproduces
    ``_SWING_CONFIG_VERSION``.
    """
    eff = weights if weights is not None else COMPONENT_WEIGHTS
    return config_version(
        eff,
        {"ml_gate": ML_CONFIDENCE_GATE, "agree_boost": ALL_AGREE_BOOST,
         "weekly_bullish_boost": WEEKLY_BULLISH_BOOST,
         "bearish_override_cut": BEARISH_OVERRIDE_CONF_CUT,
         "floor": FINAL_CONF_FLOOR},
        SCHEMA,
    )


def _signed(rec: Optional[str], conf: Optional[float]) -> float:
    """Map a (BUY/SELL/HOLD, confidence) component vote to a signed [-1,1] score
    for ledger feature analysis (BUY -> +conf, SELL -> -conf, else 0)."""
    if not rec or conf is None:
        return 0.0
    if rec == "BUY":
        return conf
    if rec == "SELL":
        return -conf
    return 0.0


def signal_swing(
    df: pd.DataFrame,
    tech_recommendation: Dict[str, Any],
    chart_patterns_raw: List[Dict[str, Any]],
    candlestick_patterns_raw: List[Dict[str, Any]],
    sentiment_scores: Optional[List[float]],
    ml: Tuple[Optional[str], Optional[float], Optional[float]],
    dividend_split_signal: Optional[Dict[str, Any]],
    strategy_consensus: Optional[Tuple[Optional[str], Optional[float]]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> SignalResult:
    """
    Pure Engine #2 signal: swing-aware weighted vote -> BUY/SELL/HOLD.

    Args:
        df: OHLCV DataFrame (DatetimeIndex) WITH indicator columns on the last
            row (ma_short/ma_long/sma_200/rsi/macd/macd_signal, ...). Used for
            weekly trend, swing points, and Phase-2C context.
        tech_recommendation: ``{recommendation, confidence, reason, signals,
            indicators}`` (from the cache or ``TechnicalIndicators.generate_recommendation``).
        chart_patterns_raw: chart-pattern dicts (last 90d), each
            ``{signal, confidence_score, start_date, end_date}``.
        candlestick_patterns_raw: candlestick dicts (last 30d), each
            ``{pattern_name, pattern_type, timestamp, confidence_score}``.
        sentiment_scores: list of news sentiment scores in [-1,1] (last 30d,
            newest-first, capped at 20), or None/empty.
        ml: ``(recommendation, confidence, predicted_price)`` or all-None.
        dividend_split_signal: DividendSplitDetector signal dict, or None.
        strategy_consensus: ``(signal, confidence)`` aggregated across the
            registered trading strategies (Phase 0.5), or None. When present
            with confidence > 0 it joins the weighted vote as the "strategy"
            component (weight = COMPONENT_WEIGHTS["strategy"]).
        weights: optional override for the 6 COMPONENT_WEIGHTS (Phase 3 GA /
            backtest candidates). ``None`` (default) uses the module
            COMPONENT_WEIGHTS — behaviour-identical to every existing caller.
            Passing the exact defaults yields the same ``config_version`` + signal.

    Returns:
        SignalResult. ``extras`` carries the Engine #2-specific fields the adapter
        maps onto ``RecommendationResponse``.
    """
    # Phase 3 #3: behaviour-preserving factor. The component votes are
    # weight-independent (cached per (stock,T) by the GA — detect_swing_points +
    # check_weekly_trend, ~99% of signal cost, run ONCE there); only the normalized
    # weighted vote + the weekly/swing-context/dividend tail depend on weights.
    # signal_swing = compose(compute, assemble) so live + backtest share ONE impl.
    return _assemble_swing(
        _swing_components(df, tech_recommendation, chart_patterns_raw,
                          candlestick_patterns_raw, sentiment_scores, ml,
                          dividend_split_signal, strategy_consensus),
        weights,
    )


def _swing_components(
    df: pd.DataFrame,
    tech_recommendation: Dict[str, Any],
    chart_patterns_raw: List[Dict[str, Any]],
    candlestick_patterns_raw: List[Dict[str, Any]],
    sentiment_scores: Optional[List[float]],
    ml: Tuple[Optional[str], Optional[float], Optional[float]],
    dividend_split_signal: Optional[Dict[str, Any]],
    strategy_consensus: Optional[Tuple[Optional[str], Optional[float]]] = None,
) -> Dict[str, Any]:
    """Weight-independent Engine #2 component votes + trend context as-of T — the
    cacheable half of :func:`signal_swing`. Runs the expensive
    :func:`check_weekly_trend` + :func:`detect_swing_points` once. Returns a dict
    of every intermediate :func:`_assemble_swing` needs, incl. the partial
    ``reasoning`` list (items 1-6). No weights are read here."""
    # ── technical signals (from tech_recommendation) ─────────────────────
    technical_signals: Dict[str, str] = {}
    for indicator, details in tech_recommendation['indicators'].items():
        if isinstance(details, dict) and 'signal' in details:
            technical_signals[indicator] = details.get('signal', 'HOLD')
        else:
            technical_signals[indicator] = 'HOLD'

    reasoning: List[str] = [
        f"Technical analysis ({tech_recommendation['confidence']:.0%} confidence): {tech_recommendation['reason']}"
    ]

    ml_rec, ml_conf, predicted_price = ml
    if ml_conf:
        reasoning.append(f"ML prediction ({ml_conf:.0%} confidence): {ml_rec}")

    # ── sentiment (from pre-filtered news scores) ────────────────────────
    sentiment_rec, sentiment_conf, sentiment_index = (None, None, None)
    sentiment_positive, sentiment_negative = (None, None)
    if sentiment_scores:
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)   # -1.0 .. 1.0
        sentiment_index = avg_sentiment * 100.0                          # -100 .. 100
        sentiment_positive = sum(1 for s in sentiment_scores if s > 0)
        sentiment_negative = sum(1 for s in sentiment_scores if s < 0)
        if sentiment_index > 30:
            sentiment_rec, sentiment_conf = "BUY", min(abs(sentiment_index) / 100, 0.9)
        elif sentiment_index < -30:
            sentiment_rec, sentiment_conf = "SELL", min(abs(sentiment_index) / 100, 0.9)
        else:
            sentiment_rec, sentiment_conf = "HOLD", 0.5
        reasoning.append(
            f"Market sentiment (index: {sentiment_index:.1f}, {sentiment_conf:.0%} confidence): "
            f"{sentiment_rec} ({sentiment_positive} positive, {sentiment_negative} negative news)"
        )

    # ── weekly trend + swing points (from df) ────────────────────────────
    weekly_trend = check_weekly_trend(df)
    swing_points = detect_swing_points(df, lookback=5)

    # ── candlestick patterns: swing validation + scoring ─────────────────
    candlestick_patterns: List[Dict[str, Any]] = []
    for p in candlestick_patterns_raw:
        pattern_category = categorize_candlestick_pattern(p.get('pattern_name'))

        if pattern_category == 'reversal':
            if p.get('pattern_type') == 'bullish':
                if p.get('timestamp') not in swing_points['swing_lows']:
                    continue
            elif p.get('pattern_type') == 'bearish':
                if p.get('timestamp') not in swing_points['swing_highs']:
                    continue
        elif pattern_category == 'continuation':
            if p.get('pattern_type') == 'bullish' and weekly_trend['trend'] == 'bearish':
                continue
            if p.get('pattern_type') == 'bearish' and weekly_trend['trend'] == 'bullish':
                continue

        candlestick_patterns.append(p)

    candlestick_signal, candlestick_conf, candlestick_count = (None, None, len(candlestick_patterns))
    if candlestick_patterns:
        bullish_count = sum(1 for p in candlestick_patterns if p.get('pattern_type') == 'bullish')
        bearish_count = sum(1 for p in candlestick_patterns if p.get('pattern_type') == 'bearish')
        avg_confidence = sum(float(p.get('confidence_score')) for p in candlestick_patterns) / len(candlestick_patterns)

        if bullish_count > bearish_count:
            candlestick_signal = "BUY"
            candlestick_conf = min((bullish_count / len(candlestick_patterns)) * avg_confidence, 0.85)
        elif bearish_count > bullish_count:
            candlestick_signal = "SELL"
            candlestick_conf = min((bearish_count / len(candlestick_patterns)) * avg_confidence, 0.85)
        else:
            candlestick_signal = "HOLD"
            candlestick_conf = 0.5

        reasoning.append(
            f"Candlestick patterns ({candlestick_conf:.0%} confidence): {candlestick_signal} "
            f"({bullish_count} bullish, {bearish_count} bearish patterns) - swing-validated"
        )
    else:
        reasoning.append("No valid swing trading candlestick patterns detected (filtered by swing points and trend alignment)")

    # ── chart patterns: duration + trend validation + scoring ────────────
    chart_patterns: List[Dict[str, Any]] = []
    for p in chart_patterns_raw:
        pattern_duration = (p.get('end_date') - p.get('start_date')).days
        if pattern_duration < 10:
            continue
        if p.get('signal') == 'bullish' and weekly_trend['trend'] == 'bearish':
            continue
        if p.get('signal') == 'bearish' and weekly_trend['trend'] == 'bullish':
            continue
        chart_patterns.append(p)

    chart_pattern_signal, chart_pattern_conf, chart_pattern_count = (None, None, len(chart_patterns))
    if chart_patterns:
        bullish_count = sum(1 for p in chart_patterns if p.get('signal') == 'bullish')
        bearish_count = sum(1 for p in chart_patterns if p.get('signal') == 'bearish')
        avg_confidence = sum(float(p.get('confidence_score')) for p in chart_patterns) / len(chart_patterns)

        if bullish_count > bearish_count:
            chart_pattern_signal = "BUY"
            chart_pattern_conf = min((bullish_count / len(chart_patterns)) * avg_confidence, 0.85)
        elif bearish_count > bullish_count:
            chart_pattern_signal = "SELL"
            chart_pattern_conf = min((bearish_count / len(chart_patterns)) * avg_confidence, 0.85)
        else:
            chart_pattern_signal = "HOLD"
            chart_pattern_conf = 0.5

        reasoning.append(
            f"Chart patterns ({chart_pattern_conf:.0%} confidence): {chart_pattern_signal} "
            f"({bullish_count} bullish, {bearish_count} bearish patterns detected) - swing-validated"
        )
    else:
        reasoning.append("No valid swing trading patterns detected (filtered by duration and trend alignment)")

    # Phase 0.5: strategy consensus — unpack + reasoning are weight-independent.
    # The reasoning line must precede the weight-dependent all-agree line, so it
    # is appended here (compute half); the components.append happens in assemble.
    strat_rec, strat_conf = strategy_consensus or (None, None)
    if strat_rec and strat_conf is not None and strat_conf > 0:
        reasoning.append(
            f"📐 Strategy consensus ({strat_conf:.0%} confidence): {strat_rec} "
            f"(aggregated vote across registered trading strategies)"
        )

    return {
        "technical_signals": technical_signals,
        "technical_rec": tech_recommendation['recommendation'],
        "technical_conf": tech_recommendation['confidence'],
        "tech_recommendation": tech_recommendation,
        "chart_pattern_signal": chart_pattern_signal,
        "chart_pattern_conf": chart_pattern_conf,
        "chart_pattern_count": chart_pattern_count,
        "candlestick_signal": candlestick_signal,
        "candlestick_conf": candlestick_conf,
        "candlestick_count": candlestick_count,
        "sentiment_rec": sentiment_rec,
        "sentiment_conf": sentiment_conf,
        "sentiment_index": sentiment_index,
        "sentiment_positive": sentiment_positive,
        "sentiment_negative": sentiment_negative,
        "ml_rec": ml_rec,
        "ml_conf": ml_conf,
        "predicted_price": predicted_price,
        "strat_rec": strat_rec,
        "strat_conf": strat_conf,
        "weekly_trend": weekly_trend,
        "df": df,
        "dividend_split_signal": dividend_split_signal,
        "reasoning": reasoning,
    }


def _assemble_swing(comp: Dict[str, Any], weights: Optional[Dict[str, float]] = None) -> SignalResult:
    """Weight-dependent half of :func:`signal_swing`: the normalized weighted vote
    + the all-agree / weekly-override / swing-context / dividend tail ->
    SignalResult. Pure; called once per GA candidate (and by :func:`signal_swing`
    itself, so live + backtest stay identical)."""
    eff_weights: Dict[str, float] = weights if weights is not None else COMPONENT_WEIGHTS

    technical_rec = comp["technical_rec"]
    technical_conf = comp["technical_conf"]
    technical_signals = comp["technical_signals"]
    tech_recommendation = comp["tech_recommendation"]
    chart_pattern_signal = comp["chart_pattern_signal"]
    chart_pattern_conf = comp["chart_pattern_conf"]
    chart_pattern_count = comp["chart_pattern_count"]
    candlestick_signal = comp["candlestick_signal"]
    candlestick_conf = comp["candlestick_conf"]
    candlestick_count = comp["candlestick_count"]
    sentiment_rec = comp["sentiment_rec"]
    sentiment_conf = comp["sentiment_conf"]
    sentiment_index = comp["sentiment_index"]
    sentiment_positive = comp["sentiment_positive"]
    sentiment_negative = comp["sentiment_negative"]
    ml_rec = comp["ml_rec"]
    ml_conf = comp["ml_conf"]
    predicted_price = comp["predicted_price"]
    strat_rec = comp["strat_rec"]
    strat_conf = comp["strat_conf"]
    weekly_trend = comp["weekly_trend"]
    df = comp["df"]
    dividend_split_signal = comp["dividend_split_signal"]
    # Copy the partial reasoning list: comp may be a SHARED GA cache entry reused
    # across weight candidates, so we must not mutate it. (Live path builds a fresh
    # comp per call, so the copy is behaviour-identical there.)
    reasoning: List[str] = list(comp["reasoning"])

    # ── weighted vote over PRESENT components (normalized) ───────────────
    components: List[Tuple[str, float, float]] = [
        (technical_rec, technical_conf, eff_weights["technical"]),
    ]
    if chart_pattern_signal:
        components.append((chart_pattern_signal, chart_pattern_conf, eff_weights["chart_pattern"]))
    if candlestick_signal:
        components.append((candlestick_signal, candlestick_conf, eff_weights["candlestick"]))
    if sentiment_rec:
        components.append((sentiment_rec, sentiment_conf, eff_weights["sentiment"]))
    if ml_rec and ml_conf and ml_conf > ML_CONFIDENCE_GATE:
        components.append((ml_rec, ml_conf, eff_weights["ml"]))
    if strat_rec and strat_conf is not None and strat_conf > 0:
        components.append((strat_rec, strat_conf, eff_weights["strategy"]))

    total_weight = sum(w for _, _, w in components) or 1.0
    rec_scores = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
    for rec, conf, w in components:
        rec_scores[rec] += conf * (w / total_weight)

    final_rec = max(rec_scores, key=rec_scores.get)
    final_conf = rec_scores[final_rec]

    component_recs = [c[0] for c in components]
    if len(components) >= 2 and len(set(component_recs)) == 1:
        reasoning.append("✓ All indicators agree")
        final_conf = min(final_conf * ALL_AGREE_BOOST, 1.0)
    else:
        reasoning.append("⚠ Mixed signals - use caution")

    # ── Phase 2A: weekly-trend override ──────────────────────────────────
    weekly_conflict = False
    if final_rec == 'BUY' and weekly_trend['trend'] == 'bearish':
        original_rec = final_rec
        final_rec = 'HOLD'
        final_conf = final_conf * BEARISH_OVERRIDE_CONF_CUT
        weekly_conflict = True
        reasoning.append(
            f"⚠️ SWING TRADING OVERRIDE: {original_rec} downgraded to HOLD - Weekly trend is BEARISH "
            f"(price ${weekly_trend['weekly_close']:.2f} < 50-week SMA ${weekly_trend['weekly_sma_50']:.2f})"
        )
        reasoning.append("⛔ Swing trades against weekly trend have low probability - Wait for weekly trend to turn bullish")
    elif final_rec == 'BUY' and weekly_trend['trend'] == 'bullish':
        reasoning.append(
            f"✅ SWING TRADING CONFIRMED: Weekly trend is BULLISH (price ${weekly_trend['weekly_close']:.2f} "
            f"> 50-week SMA ${weekly_trend['weekly_sma_50']:.2f}) - Trend alignment favorable"
        )
        final_conf = min(final_conf * WEEKLY_BULLISH_BOOST, 1.0)
    elif weekly_trend['trend'] == 'neutral':
        reasoning.append("ℹ️ Weekly trend is NEUTRAL - Exercise caution with swing positions")

    # ── Phase 2C: smart technical alignment multiplier ───────────────────
    swing_context = evaluate_swing_trading_context(
        df=df,
        weekly_trend=weekly_trend,
        tech_recommendation=tech_recommendation,
        recommendation=final_rec,
    )

    original_conf_before_2c = final_conf
    final_conf = final_conf * swing_context['confidence_adjustment']
    final_conf = max(FINAL_CONF_FLOOR, min(1.0, final_conf))  # [0.3, 1.0]

    if swing_context['confidence_adjustment'] != 1.0:
        adj_pct = (swing_context['confidence_adjustment'] - 1.0) * 100
        arrow = "📈" if adj_pct > 0 else "📉"
        verb = "boosted" if adj_pct > 0 else "reduced"
        reasoning.append(
            f"{arrow} Swing trading context: Confidence {verb} {adj_pct:+.0f}% "
            f"({original_conf_before_2c:.0%} → {final_conf:.0%})"
        )

    reasoning.extend(swing_context['reasoning'])

    # ── dividend & split adjustments ─────────────────────────────────────
    if dividend_split_signal and dividend_split_signal.get('has_signal'):
        signal_type = dividend_split_signal['signal_type']
        sig_reasoning = dividend_split_signal['reasoning']

        if signal_type == 'dividend_exit':
            if final_rec == 'BUY':
                final_rec = 'HOLD'
                final_conf = final_conf * 0.7
                reasoning.append(f"💰 DIVIDEND EXIT: {sig_reasoning}")
            else:
                reasoning.append(f"💰 Dividend signal: {sig_reasoning}")

        elif signal_type == 'dividend_entry':
            if final_rec == 'HOLD':
                final_rec = 'BUY'
                final_conf = 0.6
            elif final_rec == 'BUY':
                final_conf = min(final_conf * 1.15, 0.95)
            reasoning.append(f"💰 DIVIDEND ENTRY: {sig_reasoning}")

        elif signal_type == 'split_entry':
            if final_rec in ['HOLD', 'BUY']:
                if final_rec == 'HOLD':
                    final_rec = 'BUY'
                final_conf = min(final_conf * 1.25, 0.95)
            reasoning.append(f"✂️ SPLIT RALLY: {sig_reasoning}")

        elif signal_type == 'split_exit':
            if final_rec == 'BUY':
                final_rec = 'HOLD'
                final_conf = final_conf * 0.6
            reasoning.append(f"✂️ SPLIT EXIT: {sig_reasoning}")

        elif signal_type == 'split_reentry':
            if final_rec in ['HOLD', 'BUY']:
                if final_rec == 'HOLD':
                    final_rec = 'BUY'
                    final_conf = 0.65
                else:
                    final_conf = min(final_conf * 1.1, 0.90)
            reasoning.append(f"✂️ SPLIT RE-ENTRY: {sig_reasoning}")

    risk_level = "LOW" if final_conf >= 0.75 else "MEDIUM" if final_conf >= 0.50 else "HIGH"

    # ── assemble SignalResult ────────────────────────────────────────────
    return SignalResult(
        signal=final_rec,
        confidence=final_conf,
        weighted_score=final_conf,
        component_scores={
            "technical": _signed(tech_recommendation['recommendation'], tech_recommendation['confidence']),
            "chart_pattern": _signed(chart_pattern_signal, chart_pattern_conf),
            "candlestick": _signed(candlestick_signal, candlestick_conf),
            "sentiment": _signed(sentiment_rec, sentiment_conf),
            "ml": _signed(ml_rec, ml_conf),
            "strategy": _signed(strat_rec, strat_conf),
        },
        config_version=config_version_for(weights),
        reasoning=reasoning,
        regime=weekly_trend['trend'],
        extras={
            "technical_recommendation": tech_recommendation['recommendation'],
            "technical_confidence": tech_recommendation['confidence'],
            "technical_signals": technical_signals,
            "chart_pattern_signal": chart_pattern_signal,
            "chart_pattern_confidence": chart_pattern_conf,
            "chart_pattern_count": chart_pattern_count,
            "candlestick_signal": candlestick_signal,
            "candlestick_confidence": candlestick_conf,
            "candlestick_pattern_count": candlestick_count,
            "sentiment_index": sentiment_index,
            "sentiment_positive": sentiment_positive,
            "sentiment_negative": sentiment_negative,
            "ml_recommendation": ml_rec,
            "ml_confidence": ml_conf,
            "predicted_price": predicted_price,
            "strategy_consensus_signal": strat_rec,
            "strategy_consensus_confidence": strat_conf,
            "risk_level": risk_level,
        },
    )
