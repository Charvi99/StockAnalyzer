"""
Pure signal helpers (Phase 0.4 refactor).

Moved verbatim from ``app.services.realtime_recommendation`` (Engine #2), where
these were private ``_``-prefixed module functions. They are pure: they take
DataFrames / plain values and return plain dicts, with NO database or ORM access.
Lifting them here is the first step of making the whole signal layer replayable
(the live engine, the Phase-1 ledger, and the Phase-2 backtester all need the
same pure helpers).

Bodies are byte-identical to the originals — only the names lost their leading
underscore (they are now a shared public API) and the ``logger`` resolves to this
module. Behavior is unchanged.

Imported by:
- ``app.services.realtime_recommendation`` (Engine #2) — replaces its inline copies
- ``app.services.signal.swing`` (0.4c, the Engine #2 pure signal function)
- ``backend/tests/test_signal_core.py``
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def check_weekly_trend(df_daily: pd.DataFrame) -> dict:
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


def detect_swing_points(df: pd.DataFrame, lookback: int = 5) -> dict:
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


def categorize_candlestick_pattern(pattern_name: str) -> str:
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


def evaluate_swing_trading_context(
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
