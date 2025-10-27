
"""
API routes for technical analysis and predictions
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from datetime import datetime, timedelta
import pandas as pd
import logging

from app.db.database import get_db
from app.models.stock import Stock, StockPrice, Prediction, SentimentScore, CandlestickPattern, ChartPattern
from app.schemas.analysis import (
    TechnicalAnalysisResponse,
    AnalysisRequest,
    MLPredictionRequest,
    MLPredictionResponse,
    RecommendationResponse,
    PredictionResponse
)
from app.services.technical_indicators import TechnicalIndicators
from app.services.order_calculator import OrderCalculatorService

router = APIRouter()
logger = logging.getLogger(__name__)


def _check_weekly_trend(df_daily: pd.DataFrame) -> dict:
    """
    Check weekly trend for swing trading validation
    Uses daily data and resamples to weekly

    Returns:
        dict: {
            'trend': 'bullish' | 'bearish' | 'neutral',
            'weekly_sma_50': float,
            'weekly_close': float
        }
    """
    if df_daily.empty or len(df_daily) < 60:  # Need ~12 weeks minimum
        return {'trend': 'neutral', 'weekly_sma_50': None, 'weekly_close': None}

    try:
        # Resample daily to weekly (Friday close)
        df_weekly = df_daily.resample('W-FRI').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

        if len(df_weekly) < 50:
            return {'trend': 'neutral', 'weekly_sma_50': None, 'weekly_close': None}

        # Calculate 50-week SMA on weekly chart
        df_weekly['sma_50'] = df_weekly['close'].rolling(window=50).mean()

        weekly_sma_50 = df_weekly['sma_50'].iloc[-1]
        weekly_close = df_weekly['close'].iloc[-1]

        # Determine trend
        if pd.notna(weekly_sma_50):
            if weekly_close > weekly_sma_50:
                trend = 'bullish'
            elif weekly_close < weekly_sma_50:
                trend = 'bearish'
            else:
                trend = 'neutral'
        else:
            trend = 'neutral'

        return {
            'trend': trend,
            'weekly_sma_50': round(float(weekly_sma_50), 2) if pd.notna(weekly_sma_50) else None,
            'weekly_close': round(float(weekly_close), 2)
        }
    except Exception as e:
        logger.warning(f"Error calculating weekly trend: {e}")
        return {'trend': 'neutral', 'weekly_sma_50': None, 'weekly_close': None}


def _detect_swing_points(df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    Detect swing highs and lows for candlestick pattern validation

    A swing high is a price peak where the high is greater than N bars before and after
    A swing low is a price valley where the low is less than N bars before and after

    Args:
        df: DataFrame with OHLC data
        lookback: Number of bars to look back/forward (default 5)

    Returns:
        dict: {
            'swing_highs': set of timestamps,
            'swing_lows': set of timestamps
        }
    """
    swing_highs = set()
    swing_lows = set()

    if len(df) < lookback * 2 + 1:
        return {'swing_highs': swing_highs, 'swing_lows': swing_lows}

    try:
        # Detect swing highs (local maxima)
        for i in range(lookback, len(df) - lookback):
            current_high = df['high'].iloc[i]
            is_swing_high = True

            # Check if current high is greater than surrounding bars
            for j in range(1, lookback + 1):
                if df['high'].iloc[i - j] >= current_high or df['high'].iloc[i + j] >= current_high:
                    is_swing_high = False
                    break

            if is_swing_high:
                swing_highs.add(df.index[i])

        # Detect swing lows (local minima)
        for i in range(lookback, len(df) - lookback):
            current_low = df['low'].iloc[i]
            is_swing_low = True

            # Check if current low is less than surrounding bars
            for j in range(1, lookback + 1):
                if df['low'].iloc[i - j] <= current_low or df['low'].iloc[i + j] <= current_low:
                    is_swing_low = False
                    break

            if is_swing_low:
                swing_lows.add(df.index[i])

    except Exception as e:
        logger.warning(f"Error detecting swing points: {e}")

    return {'swing_highs': swing_highs, 'swing_lows': swing_lows}


def _categorize_candlestick_pattern(pattern_name: str) -> str:
    """
    Categorize candlestick pattern as 'reversal' or 'continuation'

    Reversal patterns should only be valid at swing points
    Continuation patterns should align with weekly trend
    """
    # Bullish/Bearish reversal patterns (valid at swing lows/highs)
    reversal_patterns = {
        # Bullish reversal (at swing lows)
        'Hammer', 'Inverted Hammer', 'Bullish Engulfing', 'Piercing Line',
        'Tweezer Bottom', 'Bullish Kicker', 'Bullish Harami', 'Bullish Counterattack',
        'Morning Star', 'Morning Doji Star', 'Three White Soldiers',
        'Three Inside Up', 'Three Outside Up', 'Bullish Abandoned Baby',
        'Dragonfly Doji',
        # Bearish reversal (at swing highs)
        'Hanging Man', 'Shooting Star', 'Bearish Engulfing', 'Dark Cloud Cover',
        'Tweezer Top', 'Bearish Kicker', 'Bearish Harami', 'Bearish Counterattack',
        'Evening Star', 'Evening Doji Star', 'Three Black Crows',
        'Three Inside Down', 'Three Outside Down', 'Bearish Abandoned Baby',
        'Gravestone Doji'
    }

    # Continuation patterns (valid if aligned with weekly trend)
    continuation_patterns = {
        'Rising Three Methods', 'Upside Tasuki Gap', 'Mat Hold', 'Rising Window',
        'Falling Three Methods', 'Downside Tasuki Gap', 'On Neck Line', 'Falling Window',
        'Bullish Marubozu', 'Bearish Marubozu'  # Strong trend continuation
    }

    if pattern_name in reversal_patterns:
        return 'reversal'
    elif pattern_name in continuation_patterns:
        return 'continuation'
    else:
        return 'reversal'  # Default to reversal (more conservative)


def _evaluate_swing_trading_context(
    df: pd.DataFrame,
    weekly_trend: dict,
    tech_recommendation: dict,
    recommendation: str
) -> dict:
    """
    Phase 2C: Smart technical indicator alignment for swing trading.

    Uses weighted scoring instead of hard filters to preserve pullback opportunities
    while reducing confidence for low-probability setups.

    Args:
        df: DataFrame with calculated technical indicators
        weekly_trend: Weekly trend information
        tech_recommendation: Technical analysis results
        recommendation: Current recommendation (BUY/SELL/HOLD)

    Returns:
        dict: {
            'confidence_adjustment': float,  # Multiplier (0.7 to 1.2)
            'reasoning': list,               # Explanation strings
            'ma_alignment': str,             # 'strong', 'moderate', 'weak', 'counter'
            'rsi_context': str,              # 'opportunity', 'neutral', 'caution'
            'macd_alignment': str            # 'aligned', 'divergent', 'counter'
        }
    """
    latest = df.iloc[-1]
    current_price = float(latest['close'])
    confidence_multiplier = 1.0
    reasoning = []

    # Get indicator values
    ma_20 = float(latest['ma_short']) if pd.notna(latest['ma_short']) else None
    ma_50 = float(latest['ma_long']) if pd.notna(latest['ma_long']) else None
    sma_200 = float(latest['sma_200']) if 'sma_200' in latest and pd.notna(latest['sma_200']) else None
    rsi = float(latest['rsi']) if pd.notna(latest['rsi']) else None
    macd = float(latest['macd']) if pd.notna(latest['macd']) else None
    macd_signal = float(latest['macd_signal']) if pd.notna(latest['macd_signal']) else None

    weekly_is_bullish = weekly_trend['trend'] == 'bullish'
    weekly_is_bearish = weekly_trend['trend'] == 'bearish'

    # ============ 1. MOVING AVERAGE ALIGNMENT (Most Important) ============
    ma_alignment = 'neutral'

    if ma_50 and sma_200:
        # Check MA alignment with weekly trend
        if weekly_is_bullish:
            if current_price > ma_50 > sma_200:
                # Perfect alignment: price above both MAs, MAs stacked bullish
                ma_alignment = 'strong'
                confidence_multiplier *= 1.15
                reasoning.append(f"✅ Strong MA alignment: Price ${current_price:.2f} > 50SMA ${ma_50:.2f} > 200SMA ${sma_200:.2f} (bullish structure)")
            elif current_price > ma_50:
                # Good: price above 50 SMA
                ma_alignment = 'moderate'
                confidence_multiplier *= 1.08
                reasoning.append(f"✅ Price above 50-day SMA (${current_price:.2f} > ${ma_50:.2f}) - trend support holding")
            elif ma_20 and current_price > ma_20 and current_price < ma_50:
                # Pullback opportunity: price between 20-50 SMA
                ma_alignment = 'pullback'
                confidence_multiplier *= 1.0  # Neutral - valid pullback
                reasoning.append(f"📊 Pullback to structure: Price ${current_price:.2f} between 20SMA ${ma_20:.2f} and 50SMA ${ma_50:.2f} (potential entry)")
            elif current_price < ma_50:
                # Weak: price below 50 SMA but weekly still bullish
                ma_alignment = 'weak'
                confidence_multiplier *= 0.85
                reasoning.append(f"⚠️ Price below 50-day SMA (${current_price:.2f} < ${ma_50:.2f}) - deeper pullback, higher risk")

        elif weekly_is_bearish:
            if current_price < ma_50 < sma_200:
                # Perfect bearish alignment
                ma_alignment = 'strong'
                if recommendation == 'SELL':
                    confidence_multiplier *= 1.15
                reasoning.append(f"✅ Strong bearish MA alignment: Price ${current_price:.2f} < 50SMA ${ma_50:.2f} < 200SMA ${sma_200:.2f}")
            elif current_price < ma_50:
                # Good bearish positioning
                ma_alignment = 'moderate'
                if recommendation == 'SELL':
                    confidence_multiplier *= 1.08
                reasoning.append(f"✅ Price below 50-day SMA (${current_price:.2f} < ${ma_50:.2f}) - bearish structure intact")
            elif current_price > ma_50:
                # Counter-trend positioning (bad for longs)
                ma_alignment = 'counter'
                if recommendation == 'BUY':
                    confidence_multiplier *= 0.75
                    reasoning.append(f"⚠️ Counter-trend setup: Price ${current_price:.2f} > 50SMA ${ma_50:.2f} but weekly trend BEARISH - low probability")
    elif ma_50:
        # Only have 50 SMA, use simplified logic
        if weekly_is_bullish and current_price > ma_50:
            confidence_multiplier *= 1.1
            reasoning.append(f"✅ Price above 50-day SMA (${current_price:.2f} > ${ma_50:.2f})")
        elif weekly_is_bearish and current_price < ma_50:
            confidence_multiplier *= 1.1
            reasoning.append(f"✅ Price below 50-day SMA (${current_price:.2f} < ${ma_50:.2f})")

    # ============ 2. RSI CONTEXT (Opportunity Detection) ============
    rsi_context = 'neutral'

    if rsi:
        if weekly_is_bullish:
            if rsi < 30:
                # Oversold in uptrend = OPPORTUNITY (pullback buy)
                rsi_context = 'opportunity'
                if recommendation == 'BUY':
                    confidence_multiplier *= 1.12
                    reasoning.append(f"🎯 RSI oversold pullback: {rsi:.1f} < 30 in bullish weekly trend (strong entry opportunity)")
            elif 30 <= rsi <= 55:
                # Healthy pullback zone
                rsi_context = 'neutral'
                reasoning.append(f"📊 RSI neutral zone: {rsi:.1f} (healthy for continuation)")
            elif rsi > 70:
                # Overbought - reduce confidence (chasing)
                rsi_context = 'caution'
                if recommendation == 'BUY':
                    confidence_multiplier *= 0.90
                    reasoning.append(f"⚠️ RSI overbought: {rsi:.1f} > 70 (late entry, higher risk)")

        elif weekly_is_bearish:
            if rsi > 70:
                # Overbought in downtrend = OPPORTUNITY (pullback short)
                rsi_context = 'opportunity'
                if recommendation == 'SELL':
                    confidence_multiplier *= 1.12
                    reasoning.append(f"🎯 RSI overbought in bearish trend: {rsi:.1f} > 70 (short opportunity)")
            elif rsi < 30:
                # Oversold in downtrend - ignore long signals
                rsi_context = 'caution'
                if recommendation == 'BUY':
                    confidence_multiplier *= 0.70
                    reasoning.append(f"⚠️ RSI oversold in bearish weekly trend: {rsi:.1f} < 30 (catching falling knife)")
            else:
                rsi_context = 'neutral'

    # ============ 3. MACD ALIGNMENT ============
    macd_alignment = 'neutral'

    if macd is not None and macd_signal is not None:
        macd_bullish = macd > macd_signal
        macd_bearish = macd < macd_signal

        if weekly_is_bullish:
            if macd_bullish:
                # MACD aligned with weekly trend
                macd_alignment = 'aligned'
                confidence_multiplier *= 1.05
                reasoning.append(f"✅ MACD bullish cross aligned with weekly trend")
            else:
                # MACD bearish but weekly bullish = just a pullback
                macd_alignment = 'divergent'
                # Don't penalize - this could be a pullback entry
                reasoning.append(f"📊 MACD pullback in bullish weekly trend (watch for re-cross)")

        elif weekly_is_bearish:
            if macd_bearish:
                # MACD aligned with weekly trend
                macd_alignment = 'aligned'
                if recommendation == 'SELL':
                    confidence_multiplier *= 1.05
                reasoning.append(f"✅ MACD bearish cross aligned with weekly trend")
            elif macd_bullish and recommendation == 'BUY':
                # Counter-trend MACD signal
                macd_alignment = 'counter'
                confidence_multiplier *= 0.80
                reasoning.append(f"⚠️ MACD bullish but weekly trend bearish (counter-trend risk)")

    # Cap confidence adjustments
    confidence_multiplier = max(0.65, min(1.25, confidence_multiplier))

    return {
        'confidence_adjustment': confidence_multiplier,
        'reasoning': reasoning,
        'ma_alignment': ma_alignment,
        'rsi_context': rsi_context,
        'macd_alignment': macd_alignment
    }


def _get_recommendation_for_stock(stock: Stock, db: Session) -> RecommendationResponse:
    """
    Reusable function to get a comprehensive recommendation for a single stock.

    NOTE: When called from dashboard endpoint, stock.prices/predictions/etc are already loaded!
    This avoids re-querying the database.
    """
    # Get price data (use already-loaded relationship if available)
    prices = sorted(stock.prices, key=lambda p: p.timestamp) if stock.prices else []

    if not prices or len(prices) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient price data for analysis. Have {len(prices)}, need at least 50."
        )

    # Convert to DataFrame
    df = pd.DataFrame([{'timestamp': p.timestamp, 'open': float(p.open), 'high': float(p.high), 'low': float(p.low), 'close': float(p.close), 'volume': int(p.volume)} for p in prices])
    df.set_index('timestamp', inplace=True)

    # Calculate technical indicators
    df = TechnicalIndicators.calculate_all_indicators(df)
    tech_recommendation = TechnicalIndicators.generate_recommendation(df)

    # Get latest prediction (use already-loaded relationship if available)
    latest_prediction = max(stock.predictions, key=lambda p: p.created_at, default=None) if stock.predictions else None

    # Get latest sentiment (use already-loaded relationship if available)
    latest_sentiment = max(stock.sentiment_scores, key=lambda s: s.timestamp, default=None) if stock.sentiment_scores else None

    # Prepare response
    latest = df.iloc[-1]
    current_price = float(latest['close'])

    # Extract technical signals
    technical_signals = {indicator: details.get('signal', 'HOLD') for indicator, details in tech_recommendation['indicators'].items()}

    # Determine final recommendation
    reasoning = [f"Technical analysis ({tech_recommendation['confidence']:.0%} confidence): {tech_recommendation['reason']}"]
    ml_rec, ml_conf, predicted_price = (latest_prediction.recommendation, float(latest_prediction.confidence_score), float(latest_prediction.predicted_price)) if latest_prediction and latest_prediction.confidence_score else (None, None, None)
    if ml_conf:
        reasoning.append(f"ML prediction ({ml_conf:.0%} confidence): {ml_rec}")

    sentiment_rec, sentiment_conf, sentiment_index = (None, None, None)
    if latest_sentiment:
        sentiment_index = float(latest_sentiment.sentiment_index)
        if sentiment_index > 30:
            sentiment_rec, sentiment_conf = "BUY", min(abs(sentiment_index) / 100, 0.9)
        elif sentiment_index < -30:
            sentiment_rec, sentiment_conf = "SELL", min(abs(sentiment_index) / 100, 0.9)
        else:
            sentiment_rec, sentiment_conf = "HOLD", 0.5
        reasoning.append(f"Market sentiment (index: {sentiment_index:.1f}, {sentiment_conf:.0%} confidence): {sentiment_rec} ({latest_sentiment.positive_count} positive, {latest_sentiment.negative_count} negative news)")

    # Check weekly trend for swing trading validation (Phase 2A)
    # IMPORTANT: Must check weekly trend BEFORE filtering patterns
    weekly_trend = _check_weekly_trend(df)

    # Detect swing points for candlestick pattern validation (Phase 2B)
    swing_points = _detect_swing_points(df, lookback=5)

    # Get recent candlestick patterns (last 30 days, use already-loaded data)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    candlestick_patterns_raw = [p for p in stock.candlestick_patterns if p.timestamp >= thirty_days_ago] if stock.candlestick_patterns else []

    # PHASE 2B: Filter candlestick patterns for swing trading
    candlestick_patterns = []
    for p in candlestick_patterns_raw:
        pattern_category = _categorize_candlestick_pattern(p.pattern_name)

        if pattern_category == 'reversal':
            # Reversal patterns: Must be at swing points
            if p.pattern_type == 'bullish':
                # Bullish reversal should be at swing low
                if p.timestamp not in swing_points['swing_lows']:
                    continue  # Not at swing low, ignore
            elif p.pattern_type == 'bearish':
                # Bearish reversal should be at swing high
                if p.timestamp not in swing_points['swing_highs']:
                    continue  # Not at swing high, ignore

        elif pattern_category == 'continuation':
            # Continuation patterns: Must align with weekly trend
            if p.pattern_type == 'bullish' and weekly_trend['trend'] == 'bearish':
                continue  # Bullish continuation in bearish weekly trend = low probability
            if p.pattern_type == 'bearish' and weekly_trend['trend'] == 'bullish':
                continue  # Bearish continuation in bullish weekly trend = low probability

        # Pattern passed filters, include it
        candlestick_patterns.append(p)

    candlestick_signal, candlestick_conf, candlestick_count = (None, None, len(candlestick_patterns))
    if candlestick_patterns:
        bullish_count = sum(1 for p in candlestick_patterns if p.pattern_type == 'bullish')
        bearish_count = sum(1 for p in candlestick_patterns if p.pattern_type == 'bearish')
        avg_confidence = sum(float(p.confidence_score) for p in candlestick_patterns) / len(candlestick_patterns)

        if bullish_count > bearish_count:
            candlestick_signal = "BUY"
            candlestick_conf = min((bullish_count / len(candlestick_patterns)) * avg_confidence, 0.85)
        elif bearish_count > bullish_count:
            candlestick_signal = "SELL"
            candlestick_conf = min((bearish_count / len(candlestick_patterns)) * avg_confidence, 0.85)
        else:
            candlestick_signal = "HOLD"
            candlestick_conf = 0.5

        reasoning.append(f"Candlestick patterns ({candlestick_conf:.0%} confidence): {candlestick_signal} ({bullish_count} bullish, {bearish_count} bearish patterns) - swing-validated")
    else:
        reasoning.append("No valid swing trading candlestick patterns detected (filtered by swing points and trend alignment)")

    # Get recent chart patterns (last 90 days, use already-loaded data)
    ninety_days_ago = datetime.now() - timedelta(days=90)
    chart_patterns_raw = [p for p in stock.chart_patterns if p.end_date >= ninety_days_ago] if stock.chart_patterns else []

    # PHASE 2B: Filter chart patterns for swing trading
    chart_patterns = []
    for p in chart_patterns_raw:
        # 1. Minimum duration: 10 days (swing patterns, not day-trading micro patterns)
        pattern_duration = (p.end_date - p.start_date).days
        if pattern_duration < 10:
            continue

        # 2. Trend alignment: Only count patterns aligned with weekly trend
        if p.signal == 'bullish' and weekly_trend['trend'] == 'bearish':
            # Bullish pattern in bearish weekly trend = low probability, ignore
            continue
        if p.signal == 'bearish' and weekly_trend['trend'] == 'bullish':
            # Bearish pattern in bullish weekly trend = low probability, ignore
            continue

        chart_patterns.append(p)

    chart_pattern_signal, chart_pattern_conf, chart_pattern_count = (None, None, len(chart_patterns))
    if chart_patterns:
        bullish_count = sum(1 for p in chart_patterns if p.signal == 'bullish')
        bearish_count = sum(1 for p in chart_patterns if p.signal == 'bearish')
        avg_confidence = sum(float(p.confidence_score) for p in chart_patterns) / len(chart_patterns)

        if bullish_count > bearish_count:
            chart_pattern_signal = "BUY"
            chart_pattern_conf = min((bullish_count / len(chart_patterns)) * avg_confidence, 0.85)
        elif bearish_count > bullish_count:
            chart_pattern_signal = "SELL"
            chart_pattern_conf = min((bearish_count / len(chart_patterns)) * avg_confidence, 0.85)
        else:
            chart_pattern_signal = "HOLD"
            chart_pattern_conf = 0.5

        reasoning.append(f"Chart patterns ({chart_pattern_conf:.0%} confidence): {chart_pattern_signal} ({bullish_count} bullish, {bearish_count} bearish patterns detected) - swing-validated")
    else:
        reasoning.append("No valid swing trading patterns detected (filtered by duration and trend alignment)")

    # Combine all recommendations
    recommendations = [(tech_recommendation['recommendation'], tech_recommendation['confidence'])]
    weights = [0.4]
    if ml_rec and ml_conf and ml_conf > 0.6:
        recommendations.append((ml_rec, ml_conf))
        weights.append(0.4)
    else:
        weights[0] += 0.4

    if sentiment_rec and sentiment_conf:
        recommendations.append((sentiment_rec, sentiment_conf))
        weights.append(0.2)
    else:
        extra_weight = 0.2 / len(weights)
        weights = [w + extra_weight for w in weights]

    rec_scores = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
    for (rec, conf), weight in zip(recommendations, weights):
        rec_scores[rec] += conf * weight

    final_rec = max(rec_scores, key=rec_scores.get)
    final_conf = rec_scores[final_rec]

    if len(recommendations) >= 2 and len(set([r[0] for r in recommendations])) == 1:
        reasoning.append("✓ All indicators agree")
        final_conf = min(final_conf * 1.1, 1.0)
    else:
        reasoning.append("⚠ Mixed signals - use caution")

    # PHASE 2A: Swing Trading Filter - Override BUY if weekly trend is bearish
    weekly_conflict = False
    if final_rec == 'BUY' and weekly_trend['trend'] == 'bearish':
        original_rec = final_rec
        original_conf = final_conf
        final_rec = 'HOLD'
        final_conf = final_conf * 0.5  # Cut confidence in half
        weekly_conflict = True
        reasoning.append(f"⚠️ SWING TRADING OVERRIDE: {original_rec} downgraded to HOLD - Weekly trend is BEARISH (price ${weekly_trend['weekly_close']:.2f} < 50-week SMA ${weekly_trend['weekly_sma_50']:.2f})")
        reasoning.append("⛔ Swing trades against weekly trend have low probability - Wait for weekly trend to turn bullish")
    elif final_rec == 'BUY' and weekly_trend['trend'] == 'bullish':
        reasoning.append(f"✅ SWING TRADING CONFIRMED: Weekly trend is BULLISH (price ${weekly_trend['weekly_close']:.2f} > 50-week SMA ${weekly_trend['weekly_sma_50']:.2f}) - Trend alignment favorable")
        # Boost confidence slightly for trend alignment
        final_conf = min(final_conf * 1.05, 1.0)
    elif weekly_trend['trend'] == 'neutral':
        reasoning.append(f"ℹ️ Weekly trend is NEUTRAL - Exercise caution with swing positions")

    # PHASE 2C: Smart Technical Indicator Alignment (Preserves pullback opportunities)
    swing_context = _evaluate_swing_trading_context(
        df=df,
        weekly_trend=weekly_trend,
        tech_recommendation=tech_recommendation,
        recommendation=final_rec
    )

    # Apply smart confidence adjustment (0.65x to 1.25x multiplier)
    original_conf_before_2c = final_conf
    final_conf = final_conf * swing_context['confidence_adjustment']
    final_conf = max(0.3, min(1.0, final_conf))  # Cap between 30% and 100%

    # Add swing trading context reasoning
    if swing_context['confidence_adjustment'] != 1.0:
        adj_pct = (swing_context['confidence_adjustment'] - 1.0) * 100
        if adj_pct > 0:
            reasoning.append(f"📈 Swing trading context: Confidence boosted {adj_pct:+.0f}% ({original_conf_before_2c:.0%} → {final_conf:.0%})")
        else:
            reasoning.append(f"📉 Swing trading context: Confidence reduced {adj_pct:+.0f}% ({original_conf_before_2c:.0%} → {final_conf:.0%})")

    # Add detailed context reasoning
    reasoning.extend(swing_context['reasoning'])

    risk_level = "LOW" if final_conf >= 0.75 else "MEDIUM" if final_conf >= 0.50 else "HIGH"

    return RecommendationResponse(
        stock_id=stock.id,
        symbol=stock.symbol,
        name=stock.name,
        sector=stock.sector,
        industry=stock.industry,
        current_price=current_price,
        timestamp=df.index[-1],
        technical_recommendation=tech_recommendation['recommendation'],
        technical_confidence=tech_recommendation['confidence'],
        technical_signals=technical_signals,
        ml_recommendation=ml_rec,
        ml_confidence=ml_conf,
        predicted_price=predicted_price,
        sentiment_index=sentiment_index,
        sentiment_positive=latest_sentiment.positive_count if latest_sentiment else None,
        sentiment_negative=latest_sentiment.negative_count if latest_sentiment else None,
        candlestick_signal=candlestick_signal,
        candlestick_confidence=candlestick_conf,
        candlestick_pattern_count=candlestick_count,
        chart_pattern_signal=chart_pattern_signal,
        chart_pattern_confidence=chart_pattern_conf,
        chart_pattern_count=chart_pattern_count,
        final_recommendation=final_rec,
        overall_confidence=final_conf,
        reasoning=reasoning,
        risk_level=risk_level
    )


@router.get("/analysis/dashboard", response_model=List[RecommendationResponse])
def get_dashboard_analysis(db: Session = Depends(get_db)):
    """
    Get comprehensive analysis for all tracked stocks for the dashboard.
    This is an efficient endpoint to avoid N+1 API calls from the frontend.

    Uses eager loading to avoid N+1 query problem (1651 queries -> 6 queries!)
    """
    logger.info("Getting dashboard analysis for all tracked stocks")

    # CRITICAL FIX: Use selectinload() to eagerly load all relationships
    # This changes 1651 queries (1 + 330*5) into just 6 queries total!
    stocks = db.query(Stock).filter(Stock.is_tracked == True).options(
        selectinload(Stock.prices),
        selectinload(Stock.predictions),
        selectinload(Stock.sentiment_scores),
        selectinload(Stock.candlestick_patterns),
        selectinload(Stock.chart_patterns)
    ).all()

    logger.info(f"Loaded {len(stocks)} stocks with all relationships eagerly loaded")

    dashboard_data = []
    for stock in stocks:
        try:
            recommendation = _get_recommendation_for_stock(stock, db)
            dashboard_data.append(recommendation)
        except HTTPException as e:
            logger.warning(f"Could not get recommendation for stock {stock.id} ('{stock.symbol}'): {e.detail}")
            dashboard_data.append(RecommendationResponse(stock_id=stock.id, symbol=stock.symbol, name=stock.name, sector=stock.sector, industry=stock.industry, error=e.detail))
        except Exception as e:
            logger.error(f"An unexpected error occurred for stock {stock.id} ('{stock.symbol}'): {e}")
            dashboard_data.append(RecommendationResponse(stock_id=stock.id, symbol=stock.symbol, name=stock.name, sector=stock.sector, industry=stock.industry, error="An unexpected error occurred during analysis."))
    return dashboard_data


@router.get("/analysis/dashboard/chunk", response_model=List[RecommendationResponse])
def get_dashboard_analysis_chunk(
    offset: int = Query(0, ge=0, description="Starting index for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Number of stocks to return"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive analysis for a chunk of tracked stocks.
    Used for progressive loading in the frontend with loading states.

    This endpoint loads stocks in batches to provide immediate visual feedback
    while maintaining efficient database queries using eager loading.

    Args:
        offset: Starting index (default 0)
        limit: Number of stocks to return (default 50, max 100)

    Returns:
        List of recommendations for the requested chunk
    """
    logger.info(f"Getting dashboard chunk: offset={offset}, limit={limit}")

    # Use eager loading to avoid N+1 queries (same optimization as full dashboard)
    stocks = db.query(Stock).filter(Stock.is_tracked == True).options(
        selectinload(Stock.prices),
        selectinload(Stock.predictions),
        selectinload(Stock.sentiment_scores),
        selectinload(Stock.candlestick_patterns),
        selectinload(Stock.chart_patterns)
    ).order_by(Stock.symbol).offset(offset).limit(limit).all()

    logger.info(f"Loaded {len(stocks)} stocks for chunk (offset={offset})")

    dashboard_data = []
    for stock in stocks:
        try:
            recommendation = _get_recommendation_for_stock(stock, db)
            dashboard_data.append(recommendation)
        except HTTPException as e:
            logger.warning(f"Could not get recommendation for stock {stock.id} ('{stock.symbol}'): {e.detail}")
            dashboard_data.append(RecommendationResponse(
                stock_id=stock.id,
                symbol=stock.symbol,
                name=stock.name,
                sector=stock.sector,
                industry=stock.industry,
                error=e.detail
            ))
        except Exception as e:
            logger.error(f"An unexpected error occurred for stock {stock.id} ('{stock.symbol}'): {e}")
            dashboard_data.append(RecommendationResponse(
                stock_id=stock.id,
                symbol=stock.symbol,
                name=stock.name,
                sector=stock.sector,
                industry=stock.industry,
                error="An unexpected error occurred during analysis."
            ))

    return dashboard_data


@router.post("/stocks/{stock_id}/analyze-complete")
async def analyze_complete(
    stock_id: int,
    db: Session = Depends(get_db)
):
    """
    Comprehensive analysis - fetches data and runs all analyses
    """
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    try:
        recommendation = _get_recommendation_for_stock(stock, db)
        return {
            "stock_id": stock_id,
            "symbol": stock.symbol,
            "status": "completed",
            "recommendation": recommendation
        }
    except HTTPException as e:
        return {"stock_id": stock_id, "symbol": stock.symbol, "status": "error", "error": e.detail}
    except Exception as e:
        logger.error(f"Error in comprehensive analysis for stock {stock_id}: {e}")
        return {"stock_id": stock_id, "symbol": stock.symbol, "status": "error", "error": str(e)}


@router.post("/stocks/{stock_id}/analyze", response_model=TechnicalAnalysisResponse)
def analyze_stock(
    stock_id: int,
    request: AnalysisRequest = AnalysisRequest(),
    db: Session = Depends(get_db)
):
    """
    Perform technical analysis on a stock
    """
    logger.info(f"Analyzing stock {stock_id}")
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    prices = db.query(StockPrice).filter(StockPrice.stock_id == stock_id).order_by(StockPrice.timestamp.asc()).all()
    if not prices or len(prices) < 50:
        raise HTTPException(status_code=400, detail=f"Insufficient price data. Need at least 50 data points, have {len(prices)}")

    df = pd.DataFrame([{'timestamp': p.timestamp, 'open': float(p.open), 'high': float(p.high), 'low': float(p.low), 'close': float(p.close), 'volume': int(p.volume)} for p in prices])
    df.set_index('timestamp', inplace=True)

    df = TechnicalIndicators.calculate_all_indicators(df, rsi_period=request.rsi_period, macd_fast=request.macd_fast, macd_slow=request.macd_slow, macd_signal=request.macd_signal, bb_window=request.bb_window, bb_std=request.bb_std, ma_short=request.ma_short, ma_long=request.ma_long)
    recommendation = TechnicalIndicators.generate_recommendation(df)
    latest = df.iloc[-1]

    return TechnicalAnalysisResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        timestamp=df.index[-1],
        current_price=float(latest['close']),
        indicators=recommendation['indicators'],
        recommendation=recommendation['recommendation'],
        confidence=recommendation['confidence'],
        reason=recommendation['reason'],
        signal_counts=recommendation['signal_counts']
    )


@router.get("/stocks/{stock_id}/recommendation", response_model=RecommendationResponse)
def get_recommendation(
    stock_id: int,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive recommendation for a stock
    """
    logger.info(f"Getting recommendation for stock {stock_id}")
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    return _get_recommendation_for_stock(stock, db)


@router.get("/stocks/{stock_id}/predictions", response_model=List[PredictionResponse])
def get_predictions(
    stock_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get prediction history for a stock
    """
    logger.info(f"Getting predictions for stock {stock_id}")
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    predictions = db.query(Prediction).filter(Prediction.stock_id == stock_id).order_by(Prediction.created_at.desc()).limit(limit).all()
    return predictions


@router.get("/stocks/{stock_id}/indicators")
def get_stock_indicators(
    stock_id: int,
    days: int = Query(default=365, description="Number of days of historical data to return"),
    rsi_period: int = Query(default=14, ge=2, le=50),
    macd_fast: int = Query(default=12, ge=1, le=50),
    macd_slow: int = Query(default=26, ge=1, le=100),
    macd_signal: int = Query(default=9, ge=1, le=50),
    bb_window: int = Query(default=20, ge=2, le=100),
    bb_std: float = Query(default=2.0, ge=0.1, le=5.0),
    ma_short: int = Query(default=20, ge=1, le=200),
    ma_long: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Get stock prices with calculated technical indicators for chart overlays
    """
    logger.info(f"Getting indicator data for stock {stock_id}")
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    prices = db.query(StockPrice).filter(StockPrice.stock_id == stock_id).order_by(StockPrice.timestamp.desc()).limit(days).all()
    if not prices or len(prices) < 50:
        raise HTTPException(status_code=400, detail=f"Insufficient price data. Need at least 50 data points, have {len(prices)}")

    prices.reverse()
    df = pd.DataFrame([{'timestamp': p.timestamp, 'open': float(p.open), 'high': float(p.high), 'low': float(p.low), 'close': float(p.close), 'volume': int(p.volume)} for p in prices])

    df = TechnicalIndicators.calculate_all_indicators(df, rsi_period=rsi_period, macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal, bb_window=bb_window, bb_std=bb_std, ma_short=ma_short, ma_long=ma_long)

    result_data = []
    for _, row in df.iterrows():
        record = {'timestamp': row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp']), 'open': float(row['open']) if pd.notna(row['open']) else None, 'high': float(row['high']) if pd.notna(row['high']) else None, 'low': float(row['low']) if pd.notna(row['low']) else None, 'close': float(row['close']) if pd.notna(row['close']) else None, 'volume': int(row['volume']) if pd.notna(row['volume']) else 0}
        if 'ma_short' in row and pd.notna(row['ma_short']): record['ma_short'] = float(row['ma_short'])
        if 'ma_long' in row and pd.notna(row['ma_long']): record['ma_long'] = float(row['ma_long'])
        if 'ema_fast' in row and pd.notna(row['ema_fast']): record['ema_fast'] = float(row['ema_fast'])
        if 'ema_slow' in row and pd.notna(row['ema_slow']): record['ema_slow'] = float(row['ema_slow'])
        if 'bb_upper' in row and pd.notna(row['bb_upper']): record['bb_upper'] = float(row['bb_upper'])
        if 'bb_middle' in row and pd.notna(row['bb_middle']): record['bb_middle'] = float(row['bb_middle'])
        if 'bb_lower' in row and pd.notna(row['bb_lower']): record['bb_lower'] = float(row['bb_lower'])
        if 'psar' in row and pd.notna(row['psar']): record['psar'] = float(row['psar'])
        result_data.append(record)

    return {'stock_id': stock_id, 'symbol': stock.symbol, 'prices': result_data}


@router.post("/stocks/{stock_id}/predict", response_model=MLPredictionResponse)
def create_ml_prediction(
    stock_id: int,
    request: MLPredictionRequest = MLPredictionRequest(),
    db: Session = Depends(get_db)
):
    """
    Create a new ML-based prediction
    """
    logger.info(f"Creating ML prediction for stock {stock_id}")
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    prices = db.query(StockPrice).filter(StockPrice.stock_id == stock_id).order_by(StockPrice.timestamp.asc()).all()
    if not prices or len(prices) < 50:
        raise HTTPException(status_code=400, detail="Insufficient price data for prediction")

    df = pd.DataFrame([{'timestamp': p.timestamp, 'close': float(p.close), 'open': float(p.open), 'high': float(p.high), 'low': float(p.low), 'volume': int(p.volume)} for p in prices])
    df.set_index('timestamp', inplace=True)

    df = TechnicalIndicators.calculate_all_indicators(df)
    recommendation = TechnicalIndicators.generate_recommendation(df)

    current_price = float(df['close'].iloc[-1])
    ma_slope = df['ma_short_slope'].iloc[-5:].mean()
    predicted_change = ma_slope * request.forecast_days
    predicted_price = current_price + predicted_change

    confidence = recommendation['confidence']

    new_prediction = Prediction(stock_id=stock_id, prediction_date=datetime.now(), target_date=datetime.now() + timedelta(days=request.forecast_days), predicted_price=predicted_price, predicted_change_percent=(predicted_change / current_price) * 100, confidence_score=confidence, model_version=f"technical_v1_{request.model_type}", recommendation=recommendation['recommendation'])
    db.add(new_prediction)
    db.commit()
    db.refresh(new_prediction)

    logger.info(f"Created prediction {new_prediction.id} for stock {stock_id}")

    return MLPredictionResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        current_price=current_price,
        predicted_price=predicted_price,
        predicted_change=predicted_change,
        confidence=confidence,
        recommendation=recommendation['recommendation'],
        model_used=request.model_type,
        forecast_horizon=request.forecast_days,
        technical_indicators=recommendation['indicators'],
        reason=recommendation['reason']
    )


@router.post("/stocks/{stock_id}/order-calculator")
async def calculate_order_parameters(
    stock_id: int,
    account_size: float = Query(default=10000.0, ge=100, le=10000000, description="Total account size"),
    risk_percentage: float = Query(default=2.0, ge=0.5, le=10.0, description="Risk percentage per trade"),
    db: Session = Depends(get_db)
):
    """
    Calculate recommended order parameters including entry, stop loss, and take profit

    Combines:
    - Chart pattern levels (stop loss, target prices)
    - Candlestick patterns for bias
    - Technical indicators (ATR for volatility)
    - Support/resistance levels

    Returns position sizing and risk/reward calculations
    """
    try:
        calculator = OrderCalculatorService(db)
        result = calculator.calculate_order_parameters(
            stock_id=stock_id,
            account_size=account_size,
            risk_percentage=risk_percentage
        )
        return result
    except ValueError as e:
        logger.error(f"Order calculator ValueError for stock {stock_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Order calculator error for stock {stock_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate order parameters: {str(e)}")

