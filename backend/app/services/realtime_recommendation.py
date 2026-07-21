"""
Realtime Recommendation Engine (Engine #2) — swing-trading-aware recommendation.

Behavior-preserving extraction (Stage 4A) from ``app/api/routes/analysis.py``, where this
~717 LOC previously lived inline in a route module and was imported *from the route* by
``services/order_calculator.py`` (a service->route layering inversion). Moving it to the
service layer fixes that inversion and shrinks the route file, with ZERO logic change.

Kept deliberately separate from ``recommendation_engine.generate_final_recommendation``
(Engine #1, the background systematic 6-factor score): the two are an **A/B pair**
(see ``docs/audit/BU1_analysis_brain.md``, decision D35) and will be unified only after
the paper-trading ledger can score each on real data — not by guessing.

NOTE: ``_get_recommendation_for_stock`` still raises ``HTTPException`` (an HTTP-layer
concern) for the not-found case; that is preserved verbatim on purpose. Replacing it with
a domain-level result is a separate refactor, out of scope for this move.
"""
from datetime import datetime, timedelta, timezone
import logging

import pandas as pd
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.stock import Stock
from app.schemas.analysis import RecommendationResponse
from app.services.technical_indicators import TechnicalIndicators

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

    PHASE 1 OPTIMIZATION: Works with filtered data (1d/200d only)
    - stock.prices contains only daily data from last 200 days (loaded by dashboard)
    - This is sufficient for all technical indicators (longest is 200-day MA)
    - Backward compatible: Falls back gracefully if insufficient data
    """
    # Get price data (use already-loaded relationship if available)
    # NOTE: After Phase 1 optimization, this contains only 1d/200d data (not all timeframes)
    # CRITICAL FOR SWING TRADING: Get absolute latest INTRADAY price (not aggregated weekly/monthly)
    # Filter to intraday timeframes (1m, 5m, 15m, 1h, 1d) - exclude aggregated (1w, 1mo) which extend into future
    intraday_prices = [p for p in stock.prices if p.timeframe in ['1m', '5m', '15m', '1h', '1d']] if stock.prices else []
    latest_price_any_timeframe = max(intraday_prices, key=lambda p: p.timestamp) if intraday_prices else None

    # For technical analysis, filter to daily (1d) prices OR fall back to all if insufficient daily data
    daily_prices = [p for p in stock.prices if p.timeframe == '1d'] if stock.prices else []
    if len(daily_prices) >= 50:
        # Sufficient daily data for technical analysis
        prices = sorted(daily_prices, key=lambda p: p.timestamp)
    else:
        # Fall back to all prices if not enough daily data (backward compatibility)
        prices = sorted(stock.prices, key=lambda p: p.timestamp) if stock.prices else []

    if not prices or len(prices) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient price data for analysis. Have {len(prices)}, need at least 50 daily bars for technical indicators."
        )

    # Try to get cached indicators first (FAST PATH - 45x speedup!)
    from app.services.indicator_cache_service import IndicatorCacheService
    cached_data = IndicatorCacheService.get_cached_indicators(db, stock.id, timeframe='1d')

    if cached_data:
        # Cache hit! Use pre-computed indicators and recommendation
        logger.debug(f"Cache HIT for stock_id={stock.id} ({stock.symbol}) - using cached indicators")
        tech_recommendation = {
            'indicators': cached_data['indicators'],
            'recommendation': cached_data['recommendation'],
            'confidence': cached_data['confidence'] if cached_data['confidence'] else 0.5,
            'reason': cached_data['reasoning'] if cached_data['reasoning'] else 'Technical analysis',
            'signals': cached_data['signals'] if cached_data['signals'] else {'buy': 0, 'sell': 0, 'hold': 0}
        }

        # Build DataFrame with OHLCV + cached indicators
        # This is needed for swing trading context evaluation and pattern filtering
        df = pd.DataFrame([{
            'timestamp': p.timestamp,
            'open': float(p.open),
            'high': float(p.high),
            'low': float(p.low),
            'close': float(p.close),
            'volume': int(p.volume)
        } for p in prices])
        df.set_index('timestamp', inplace=True)

        # Add cached indicator values to the last row of DataFrame
        # (assuming indicators were computed on most recent data)
        # Use dict to avoid DataFrame fragmentation warning
        indicator_cols = {indicator_name: [None] * (len(df) - 1) + [indicator_value]
                          for indicator_name, indicator_value in cached_data['indicators'].items()}
        indicator_df = pd.DataFrame(indicator_cols, index=df.index)
        df = pd.concat([df, indicator_df], axis=1)
    else:
        # Cache miss - calculate indicators on-the-fly (SLOW PATH - 2.5s per stock)
        logger.warning(f"Cache MISS for stock_id={stock.id} ({stock.symbol}) - calculating indicators on-the-fly")

        # Convert to DataFrame
        df = pd.DataFrame([{'timestamp': p.timestamp, 'open': float(p.open), 'high': float(p.high), 'low': float(p.low), 'close': float(p.close), 'volume': int(p.volume)} for p in prices])
        df.set_index('timestamp', inplace=True)

        # Calculate technical indicators (SLOW!)
        df = TechnicalIndicators.calculate_all_indicators(df)
        tech_recommendation = TechnicalIndicators.generate_recommendation(df)

    # Get latest prediction (use already-loaded relationship if available)
    latest_prediction = max(stock.predictions, key=lambda p: p.created_at, default=None) if stock.predictions else None

    # NOTE: sentiment is derived below from the `news` table (Polygon insights written
    # there by fetcher_tasks). The legacy `sentiment_scores` table is no longer
    # populated — reading it always returned None, so sentiment never propagated
    # (user-reported issue #4).

    # Prepare response
    latest = df.iloc[-1]
    current_price = float(latest['close'])

    # Extract technical signals
    # Handle both cached format (flat dict) and on-the-fly format (nested dict with signals)
    technical_signals = {}
    for indicator, details in tech_recommendation['indicators'].items():
        if isinstance(details, dict) and 'signal' in details:
            # On-the-fly format: {'indicator': {'signal': 'BUY', 'value': 45.5}}
            technical_signals[indicator] = details.get('signal', 'HOLD')
        else:
            # Cached format: {'indicator': 45.5} or {'indicator': 'HOLD'}
            # For cached data, we don't have signals, so skip or use a default
            technical_signals[indicator] = 'HOLD'

    # Determine final recommendation
    reasoning = [f"Technical analysis ({tech_recommendation['confidence']:.0%} confidence): {tech_recommendation['reason']}"]
    ml_rec, ml_conf, predicted_price = (latest_prediction.recommendation, float(latest_prediction.confidence_score), float(latest_prediction.predicted_price)) if latest_prediction and latest_prediction.confidence_score else (None, None, None)
    if ml_conf:
        reasoning.append(f"ML prediction ({ml_conf:.0%} confidence): {ml_rec}")

    # SENTIMENT — aggregated from recent news articles (Polygon per-ticker insights,
    # written to the `news` table with sentiment_score in [-1, 1] by fetcher_tasks).
    # Replaces the dead `sentiment_scores` read; produces the same -100..100 index
    # and BUY/SELL/HOLD + confidence the rest of this function expects.
    sentiment_rec, sentiment_conf, sentiment_index = (None, None, None)
    sentiment_positive, sentiment_negative = (None, None)
    recent_news = []
    if stock.news:
        news_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        recent_news = [
            n for n in stock.news
            if n.sentiment_score is not None
            and n.published_utc is not None
            and n.published_utc >= news_cutoff
        ]
    if recent_news:
        # Newest-first, cap at 20 (match Engine #1's window)
        recent_news = sorted(recent_news, key=lambda n: n.published_utc, reverse=True)[:20]
        scores = [float(n.sentiment_score) for n in recent_news]
        avg_sentiment = sum(scores) / len(scores)        # -1.0 .. 1.0
        sentiment_index = avg_sentiment * 100.0          # -100 .. 100 (radar scale)
        sentiment_positive = sum(1 for s in scores if s > 0)
        sentiment_negative = sum(1 for s in scores if s < 0)
        if sentiment_index > 30:
            sentiment_rec, sentiment_conf = "BUY", min(abs(sentiment_index) / 100, 0.9)
        elif sentiment_index < -30:
            sentiment_rec, sentiment_conf = "SELL", min(abs(sentiment_index) / 100, 0.9)
        else:
            sentiment_rec, sentiment_conf = "HOLD", 0.5
        reasoning.append(f"Market sentiment (index: {sentiment_index:.1f}, {sentiment_conf:.0%} confidence): {sentiment_rec} ({sentiment_positive} positive, {sentiment_negative} negative news)")

    # Check weekly trend for swing trading validation (Phase 2A)
    # IMPORTANT: Must check weekly trend BEFORE filtering patterns
    weekly_trend = _check_weekly_trend(df)

    # Detect swing points for candlestick pattern validation (Phase 2B)
    swing_points = _detect_swing_points(df, lookback=5)

    # Get recent candlestick patterns (last 30 days, use already-loaded data)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
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
    ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
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

    # Combine all AVAILABLE component signals into a weighted vote. Each component
    # contributes (signal, confidence, weight); weights are normalized over the
    # PRESENT components so a missing one (no ML, no sentiment, no chart pattern)
    # simply cedes its share to the rest — instead of being silently dropped.
    # (User-reported issues #2/#3: previously only technical+ML+sentiment were
    # combined, so chart & candlestick signals — though computed — never moved the
    # recommendation, and with no ML/sentiment the "Overall" collapsed to a copy of
    # "Technical". Chart/candlestick are now weighted in.)
    components = [
        (tech_recommendation['recommendation'], tech_recommendation['confidence'], 0.35),
    ]
    if chart_pattern_signal:
        components.append((chart_pattern_signal, chart_pattern_conf, 0.25))
    if candlestick_signal:
        components.append((candlestick_signal, candlestick_conf, 0.15))
    if sentiment_rec:
        components.append((sentiment_rec, sentiment_conf, 0.15))
    if ml_rec and ml_conf and ml_conf > 0.6:
        components.append((ml_rec, ml_conf, 0.10))

    total_weight = sum(w for _, _, w in components) or 1.0
    rec_scores = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
    for rec, conf, w in components:
        rec_scores[rec] += conf * (w / total_weight)

    final_rec = max(rec_scores, key=rec_scores.get)
    final_conf = rec_scores[final_rec]

    component_recs = [c[0] for c in components]
    if len(components) >= 2 and len(set(component_recs)) == 1:
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

    # DIVIDEND & SPLIT SIGNALS: Check for upcoming corporate events
    dividend_split_signal = None
    try:
        from app.services.dividend_split_detector import DividendSplitDetector
        detector = DividendSplitDetector()
        signal = detector.get_signals_for_recommendation(stock.id, db, days_ahead=30)

        if signal['has_signal']:
            dividend_split_signal = signal

            # Adjust recommendation based on signal
            if signal['signal_type'] == 'dividend_exit':
                # EXIT signal: Reduce BUY confidence or change to HOLD
                if final_rec == 'BUY':
                    original_rec = final_rec
                    original_conf = final_conf
                    final_rec = 'HOLD'
                    final_conf = final_conf * 0.7  # Reduce confidence
                    reasoning.append(f"💰 DIVIDEND EXIT: {signal['reasoning']}")
                else:
                    reasoning.append(f"💰 Dividend signal: {signal['reasoning']}")

            elif signal['signal_type'] == 'dividend_entry':
                # ENTRY signal: Boost BUY or change HOLD to BUY
                if final_rec == 'HOLD':
                    final_rec = 'BUY'
                    final_conf = 0.6
                elif final_rec == 'BUY':
                    final_conf = min(final_conf * 1.15, 0.95)
                reasoning.append(f"💰 DIVIDEND ENTRY: {signal['reasoning']}")

            elif signal['signal_type'] == 'split_entry':
                # Strong ENTRY signal: Boost BUY significantly
                if final_rec in ['HOLD', 'BUY']:
                    if final_rec == 'HOLD':
                        final_rec = 'BUY'
                    final_conf = min(final_conf * 1.25, 0.95)
                reasoning.append(f"✂️ SPLIT RALLY: {signal['reasoning']}")

            elif signal['signal_type'] == 'split_exit':
                # EXIT signal: Change BUY to HOLD or SELL
                if final_rec == 'BUY':
                    original_rec = final_rec
                    final_rec = 'HOLD'
                    final_conf = final_conf * 0.6
                reasoning.append(f"✂️ SPLIT EXIT: {signal['reasoning']}")

            elif signal['signal_type'] == 'split_reentry':
                # Re-entry signal: Moderate BUY boost
                if final_rec in ['HOLD', 'BUY']:
                    if final_rec == 'HOLD':
                        final_rec = 'BUY'
                        final_conf = 0.65
                    else:
                        final_conf = min(final_conf * 1.1, 0.90)
                reasoning.append(f"✂️ SPLIT RE-ENTRY: {signal['reasoning']}")

    except Exception as e:
        logger.warning(f"Dividend/split signal detection failed for stock {stock.id}: {e}")

    risk_level = "LOW" if final_conf >= 0.75 else "MEDIUM" if final_conf >= 0.50 else "HIGH"

    # CRITICAL FOR SWING TRADING: ALWAYS use absolute latest price across all timeframes
    # This ensures traders see the most recent price (e.g., today's 1h intraday price, not yesterday's 1d close)
    # NOTE: We don't compare timestamps because 1d data might extend into future (e.g., weekly aggregation)
    if latest_price_any_timeframe:
        actual_current_price = float(latest_price_any_timeframe.close)
        actual_timestamp = latest_price_any_timeframe.timestamp
        logger.info(f"{stock.symbol}: Using latest {latest_price_any_timeframe.timeframe} price ${actual_current_price:.2f} from {actual_timestamp}")
    else:
        # Fallback: use DataFrame's last price if no price data available (shouldn't happen)
        actual_current_price = current_price
        actual_timestamp = df.index[-1]
        logger.warning(f"{stock.symbol}: No latest price found, using DataFrame last price ${actual_current_price:.2f}")

    return RecommendationResponse(
        stock_id=stock.id,
        symbol=stock.symbol,
        name=stock.name,
        sector=stock.sector,
        industry=stock.industry,
        priority=stock.priority,
        priority_score=float(stock.priority_score) if stock.priority_score else None,
        last_fetch_at=stock.last_fetch_at,
        next_fetch_at=stock.next_fetch_at,
        current_price=actual_current_price,
        timestamp=actual_timestamp,
        technical_recommendation=tech_recommendation['recommendation'],
        technical_confidence=tech_recommendation['confidence'],
        technical_signals=technical_signals,
        ml_recommendation=ml_rec,
        ml_confidence=ml_conf,
        predicted_price=predicted_price,
        sentiment_index=sentiment_index,
        sentiment_positive=sentiment_positive,
        sentiment_negative=sentiment_negative,
        candlestick_signal=candlestick_signal,
        candlestick_confidence=candlestick_conf,
        candlestick_pattern_count=candlestick_count,
        chart_pattern_signal=chart_pattern_signal,
        chart_pattern_confidence=chart_pattern_conf,
        chart_pattern_count=chart_pattern_count,
        dividend_split_signal=dividend_split_signal,
        final_recommendation=final_rec,
        overall_confidence=final_conf,
        reasoning=reasoning,
        risk_level=risk_level,
        analysis_score=float(stock.analysis_score) if stock.analysis_score else 0.0,
        analysis_complete=stock.analysis_complete
    )
