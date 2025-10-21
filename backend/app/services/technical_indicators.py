"""
Technical Indicators Service

Calculates various technical indicators for stock price analysis.
Inspired by existing tools but adapted for FastAPI backend.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """
    Service for calculating technical indicators on stock price data
    """

    @staticmethod
    def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        Calculate Relative Strength Index (RSI)

        RSI values:
        - Above 70: Overbought (potential sell signal)
        - Below 30: Oversold (potential buy signal)
        - Between 30-70: Neutral

        Args:
            data: DataFrame with 'close' column
            period: RSI period (default: 14)

        Returns:
            DataFrame with RSI column added
        """
        logger.info(f"Calculating RSI with period {period}")

        df = data.copy()
        delta = df['close'].diff()

        # Separate gains and losses
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period).mean()

        # Calculate RS and RSI
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Generate signal
        latest_rsi = df['rsi'].iloc[-1] if len(df) > 0 else None
        if latest_rsi:
            if latest_rsi < 30:
                df['rsi_signal'] = 'BUY'
                df['rsi_reason'] = f"RSI={latest_rsi:.2f} (Oversold)"
            elif latest_rsi > 70:
                df['rsi_signal'] = 'SELL'
                df['rsi_reason'] = f"RSI={latest_rsi:.2f} (Overbought)"
            else:
                df['rsi_signal'] = 'HOLD'
                df['rsi_reason'] = f"RSI={latest_rsi:.2f} (Neutral)"

        return df

    @staticmethod
    def calculate_macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """
        Calculate MACD (Moving Average Convergence Divergence)

        MACD signals:
        - MACD line crosses above signal line: Bullish (buy signal)
        - MACD line crosses below signal line: Bearish (sell signal)

        Args:
            data: DataFrame with 'close' column
            fast: Fast EMA period (default: 12)
            slow: Slow EMA period (default: 26)
            signal: Signal line period (default: 9)

        Returns:
            DataFrame with MACD columns added
        """
        logger.info(f"Calculating MACD (fast={fast}, slow={slow}, signal={signal})")

        df = data.copy()

        # Calculate EMAs
        df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()

        # Calculate MACD line
        df['macd'] = df['ema_fast'] - df['ema_slow']

        # Calculate signal line
        df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()

        # Calculate histogram
        df['macd_histogram'] = df['macd'] - df['macd_signal']

        # Generate signal
        if len(df) > 0:
            latest_macd = df['macd'].iloc[-1]
            latest_signal = df['macd_signal'].iloc[-1]

            if latest_macd > latest_signal:
                df['macd_trend'] = 'BUY'
                df['macd_reason'] = f"MACD above Signal"
            elif latest_macd < latest_signal:
                df['macd_trend'] = 'SELL'
                df['macd_reason'] = f"MACD below Signal"
            else:
                df['macd_trend'] = 'HOLD'
                df['macd_reason'] = "MACD equals Signal"

        return df

    @staticmethod
    def calculate_bollinger_bands(data: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
        """
        Calculate Bollinger Bands

        Bollinger Bands signals:
        - Price touches lower band: Oversold (potential buy)
        - Price touches upper band: Overbought (potential sell)
        - Price in middle: Neutral

        Args:
            data: DataFrame with 'close' column
            window: Moving average window (default: 20)
            num_std: Number of standard deviations (default: 2.0)

        Returns:
            DataFrame with Bollinger Bands columns added
        """
        logger.info(f"Calculating Bollinger Bands (window={window}, std={num_std})")

        df = data.copy()

        # Calculate middle band (SMA)
        df['bb_middle'] = df['close'].rolling(window=window).mean()

        # Calculate standard deviation
        df['bb_std'] = df['close'].rolling(window=window).std()

        # Calculate upper and lower bands
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * num_std)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * num_std)

        # Calculate bandwidth
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

        # Generate signal
        if len(df) > 0:
            latest_close = df['close'].iloc[-1]
            latest_upper = df['bb_upper'].iloc[-1]
            latest_lower = df['bb_lower'].iloc[-1]

            if latest_close > latest_upper:
                df['bb_signal'] = 'SELL'
                df['bb_reason'] = "Close above upper band (Overbought)"
            elif latest_close < latest_lower:
                df['bb_signal'] = 'BUY'
                df['bb_reason'] = "Close below lower band (Oversold)"
            else:
                df['bb_signal'] = 'HOLD'
                df['bb_reason'] = "Close inside bands (Neutral)"

        return df

    @staticmethod
    def calculate_moving_averages(data: pd.DataFrame, short_window: int = 20, long_window: int = 50) -> pd.DataFrame:
        """
        Calculate Simple Moving Averages (SMA)

        Moving Average signals:
        - Short MA crosses above long MA: Golden Cross (buy signal)
        - Short MA crosses below long MA: Death Cross (sell signal)

        Args:
            data: DataFrame with 'close' column
            short_window: Short MA period (default: 20)
            long_window: Long MA period (default: 50)

        Returns:
            DataFrame with MA columns added
        """
        logger.info(f"Calculating Moving Averages (short={short_window}, long={long_window})")

        df = data.copy()

        # Calculate moving averages
        df['ma_short'] = df['close'].rolling(window=short_window).mean()
        df['ma_long'] = df['close'].rolling(window=long_window).mean()

        # Calculate MA slopes (rate of change)
        df['ma_short_slope'] = df['ma_short'].diff()
        df['ma_long_slope'] = df['ma_long'].diff()

        # Generate signal
        if len(df) > 1:
            latest_close = df['close'].iloc[-1]
            latest_short = df['ma_short'].iloc[-1]
            latest_long = df['ma_long'].iloc[-1]
            prev_short = df['ma_short'].iloc[-2]
            prev_long = df['ma_long'].iloc[-2]

            # Check for crossovers
            golden_cross = (prev_short <= prev_long) and (latest_short > latest_long)
            death_cross = (prev_short >= prev_long) and (latest_short < latest_long)

            if golden_cross:
                df['ma_signal'] = 'BUY'
                df['ma_reason'] = f"Golden Cross detected"
            elif death_cross:
                df['ma_signal'] = 'SELL'
                df['ma_reason'] = f"Death Cross detected"
            elif latest_close > latest_short and latest_short > latest_long:
                df['ma_signal'] = 'BUY'
                df['ma_reason'] = f"Strong uptrend (Price > MA{short_window} > MA{long_window})"
            elif latest_close < latest_short and latest_short < latest_long:
                df['ma_signal'] = 'SELL'
                df['ma_reason'] = f"Strong downtrend (Price < MA{short_window} < MA{long_window})"
            else:
                df['ma_signal'] = 'HOLD'
                df['ma_reason'] = "Mixed signals"

        return df

    @staticmethod
    def calculate_adx(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        Calculate Average Directional Index (ADX)

        ADX measures trend strength (0-100):
        - Above 25: Strong trend
        - Below 20: Weak trend/ranging

        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            period: ADX period (default: 14)

        Returns:
            DataFrame with ADX, +DI, -DI columns added
        """
        logger.info(f"Calculating ADX with period {period}")

        df = data.copy()

        # Calculate True Range
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)

        # Calculate Directional Movement
        df['high_diff'] = df['high'] - df['high'].shift(1)
        df['low_diff'] = df['low'].shift(1) - df['low']

        df['plus_dm'] = np.where((df['high_diff'] > df['low_diff']) & (df['high_diff'] > 0), df['high_diff'], 0)
        df['minus_dm'] = np.where((df['low_diff'] > df['high_diff']) & (df['low_diff'] > 0), df['low_diff'], 0)

        # Smooth TR and DMs
        df['atr'] = df['tr'].rolling(window=period).mean()
        df['plus_dm_smooth'] = df['plus_dm'].rolling(window=period).mean()
        df['minus_dm_smooth'] = df['minus_dm'].rolling(window=period).mean()

        # Calculate Directional Indicators
        df['plus_di'] = 100 * (df['plus_dm_smooth'] / df['atr'])
        df['minus_di'] = 100 * (df['minus_dm_smooth'] / df['atr'])

        # Calculate DX and ADX
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
        df['adx'] = df['dx'].rolling(window=period).mean()

        # Generate signal
        if len(df) > 0:
            latest_adx = df['adx'].iloc[-1]
            latest_plus_di = df['plus_di'].iloc[-1]
            latest_minus_di = df['minus_di'].iloc[-1]

            if pd.notna(latest_adx) and pd.notna(latest_plus_di) and pd.notna(latest_minus_di):
                if latest_adx > 25:
                    if latest_plus_di > latest_minus_di:
                        df['adx_signal'] = 'BUY'
                        df['adx_reason'] = f"Strong uptrend (ADX={latest_adx:.1f}, +DI>-DI)"
                    else:
                        df['adx_signal'] = 'SELL'
                        df['adx_reason'] = f"Strong downtrend (ADX={latest_adx:.1f}, -DI>+DI)"
                else:
                    df['adx_signal'] = 'HOLD'
                    df['adx_reason'] = f"Weak trend (ADX={latest_adx:.1f})"

        return df

    @staticmethod
    def calculate_parabolic_sar(data: pd.DataFrame, acceleration: float = 0.02, maximum: float = 0.2) -> pd.DataFrame:
        """
        Calculate Parabolic SAR (Stop and Reverse)

        SAR signals:
        - Dots below price: Uptrend
        - Dots above price: Downtrend
        - Dots flip: Trend reversal

        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            acceleration: Acceleration factor (default: 0.02)
            maximum: Maximum acceleration (default: 0.2)

        Returns:
            DataFrame with SAR column added
        """
        logger.info(f"Calculating Parabolic SAR (af={acceleration}, max={maximum})")

        df = data.copy()

        # Initialize
        sar = []
        ep = []  # Extreme point
        af = []  # Acceleration factor
        trend = []  # 1 for uptrend, -1 for downtrend

        # Starting values
        sar.append(df['low'].iloc[0])
        ep.append(df['high'].iloc[0])
        af.append(acceleration)
        trend.append(1)

        for i in range(1, len(df)):
            # Calculate new SAR
            new_sar = sar[-1] + af[-1] * (ep[-1] - sar[-1])

            # Determine trend
            if trend[-1] == 1:  # Uptrend
                new_sar = min(new_sar, df['low'].iloc[i-1], df['low'].iloc[i-2] if i > 1 else df['low'].iloc[i-1])

                if df['low'].iloc[i] < new_sar:
                    # Trend reversal
                    new_trend = -1
                    new_sar = ep[-1]
                    new_ep = df['low'].iloc[i]
                    new_af = acceleration
                else:
                    new_trend = 1
                    if df['high'].iloc[i] > ep[-1]:
                        new_ep = df['high'].iloc[i]
                        new_af = min(af[-1] + acceleration, maximum)
                    else:
                        new_ep = ep[-1]
                        new_af = af[-1]
            else:  # Downtrend
                new_sar = max(new_sar, df['high'].iloc[i-1], df['high'].iloc[i-2] if i > 1 else df['high'].iloc[i-1])

                if df['high'].iloc[i] > new_sar:
                    # Trend reversal
                    new_trend = 1
                    new_sar = ep[-1]
                    new_ep = df['high'].iloc[i]
                    new_af = acceleration
                else:
                    new_trend = -1
                    if df['low'].iloc[i] < ep[-1]:
                        new_ep = df['low'].iloc[i]
                        new_af = min(af[-1] + acceleration, maximum)
                    else:
                        new_ep = ep[-1]
                        new_af = af[-1]

            sar.append(new_sar)
            ep.append(new_ep)
            af.append(new_af)
            trend.append(new_trend)

        df['psar'] = sar
        df['psar_trend'] = trend

        # Generate signal
        if len(df) > 1:
            latest_trend = df['psar_trend'].iloc[-1]
            prev_trend = df['psar_trend'].iloc[-2]

            if latest_trend == 1 and prev_trend == -1:
                df['psar_signal'] = 'BUY'
                df['psar_reason'] = "Parabolic SAR flipped to uptrend"
            elif latest_trend == -1 and prev_trend == 1:
                df['psar_signal'] = 'SELL'
                df['psar_reason'] = "Parabolic SAR flipped to downtrend"
            elif latest_trend == 1:
                df['psar_signal'] = 'HOLD'
                df['psar_reason'] = "Parabolic SAR in uptrend"
            else:
                df['psar_signal'] = 'HOLD'
                df['psar_reason'] = "Parabolic SAR in downtrend"

        return df

    @staticmethod
    def calculate_stochastic(data: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
        """
        Calculate Stochastic Oscillator

        Stochastic signals:
        - %K > 80: Overbought
        - %K < 20: Oversold
        - %K crosses above %D: Buy signal
        - %K crosses below %D: Sell signal

        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            k_period: %K period (default: 14)
            d_period: %D period (default: 3)

        Returns:
            DataFrame with Stochastic columns added
        """
        logger.info(f"Calculating Stochastic (k={k_period}, d={d_period})")

        df = data.copy()

        # Calculate %K
        lowest_low = df['low'].rolling(window=k_period).min()
        highest_high = df['high'].rolling(window=k_period).max()
        df['stoch_k'] = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)

        # Calculate %D (smoothed %K)
        df['stoch_d'] = df['stoch_k'].rolling(window=d_period).mean()

        # Generate signal
        if len(df) > 1:
            latest_k = df['stoch_k'].iloc[-1]
            latest_d = df['stoch_d'].iloc[-1]
            prev_k = df['stoch_k'].iloc[-2]
            prev_d = df['stoch_d'].iloc[-2]

            if pd.notna(latest_k) and pd.notna(latest_d):
                # Check for crossovers
                bullish_cross = (prev_k <= prev_d) and (latest_k > latest_d)
                bearish_cross = (prev_k >= prev_d) and (latest_k < latest_d)

                if bullish_cross and latest_k < 20:
                    df['stoch_signal'] = 'BUY'
                    df['stoch_reason'] = f"Bullish crossover in oversold zone (%K={latest_k:.1f})"
                elif bearish_cross and latest_k > 80:
                    df['stoch_signal'] = 'SELL'
                    df['stoch_reason'] = f"Bearish crossover in overbought zone (%K={latest_k:.1f})"
                elif latest_k < 20:
                    df['stoch_signal'] = 'BUY'
                    df['stoch_reason'] = f"Oversold (%K={latest_k:.1f})"
                elif latest_k > 80:
                    df['stoch_signal'] = 'SELL'
                    df['stoch_reason'] = f"Overbought (%K={latest_k:.1f})"
                else:
                    df['stoch_signal'] = 'HOLD'
                    df['stoch_reason'] = f"Neutral (%K={latest_k:.1f})"

        return df

    @staticmethod
    def calculate_cci(data: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """
        Calculate Commodity Channel Index (CCI)

        CCI signals:
        - CCI > +100: Overbought
        - CCI < -100: Oversold
        - CCI crosses above -100: Buy signal
        - CCI crosses below +100: Sell signal

        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            period: CCI period (default: 20)

        Returns:
            DataFrame with CCI column added
        """
        logger.info(f"Calculating CCI with period {period}")

        df = data.copy()

        # Calculate Typical Price
        df['tp'] = (df['high'] + df['low'] + df['close']) / 3

        # Calculate SMA of Typical Price
        df['tp_sma'] = df['tp'].rolling(window=period).mean()

        # Calculate Mean Deviation
        df['md'] = df['tp'].rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())

        # Calculate CCI
        df['cci'] = (df['tp'] - df['tp_sma']) / (0.015 * df['md'])

        # Generate signal
        if len(df) > 1:
            latest_cci = df['cci'].iloc[-1]
            prev_cci = df['cci'].iloc[-2]

            if pd.notna(latest_cci):
                if prev_cci < -100 and latest_cci >= -100:
                    df['cci_signal'] = 'BUY'
                    df['cci_reason'] = f"CCI crossed above -100 (CCI={latest_cci:.1f})"
                elif prev_cci > 100 and latest_cci <= 100:
                    df['cci_signal'] = 'SELL'
                    df['cci_reason'] = f"CCI crossed below +100 (CCI={latest_cci:.1f})"
                elif latest_cci < -100:
                    df['cci_signal'] = 'BUY'
                    df['cci_reason'] = f"Oversold (CCI={latest_cci:.1f})"
                elif latest_cci > 100:
                    df['cci_signal'] = 'SELL'
                    df['cci_reason'] = f"Overbought (CCI={latest_cci:.1f})"
                else:
                    df['cci_signal'] = 'HOLD'
                    df['cci_reason'] = f"Neutral (CCI={latest_cci:.1f})"

        return df

    @staticmethod
    def calculate_obv(data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate On-Balance Volume (OBV)

        OBV signals:
        - OBV rising with price: Healthy uptrend
        - OBV falling with price: Healthy downtrend
        - Divergence: Warning of potential reversal

        Args:
            data: DataFrame with 'close' and 'volume' columns

        Returns:
            DataFrame with OBV column added
        """
        logger.info("Calculating OBV")

        df = data.copy()

        # Calculate OBV
        df['obv'] = 0
        df['price_change'] = df['close'].diff()

        obv_values = [0]
        for i in range(1, len(df)):
            if df['price_change'].iloc[i] > 0:
                obv_values.append(obv_values[-1] + df['volume'].iloc[i])
            elif df['price_change'].iloc[i] < 0:
                obv_values.append(obv_values[-1] - df['volume'].iloc[i])
            else:
                obv_values.append(obv_values[-1])

        df['obv'] = obv_values

        # Calculate OBV trend
        df['obv_sma'] = df['obv'].rolling(window=20).mean()

        # Generate signal
        if len(df) > 20:
            latest_obv = df['obv'].iloc[-1]
            latest_sma = df['obv_sma'].iloc[-1]
            price_trend = df['close'].iloc[-1] > df['close'].iloc[-20]
            obv_trend = latest_obv > df['obv'].iloc[-20]

            if pd.notna(latest_sma):
                if price_trend and obv_trend:
                    df['obv_signal'] = 'BUY'
                    df['obv_reason'] = "OBV confirming uptrend"
                elif not price_trend and not obv_trend:
                    df['obv_signal'] = 'SELL'
                    df['obv_reason'] = "OBV confirming downtrend"
                elif price_trend and not obv_trend:
                    df['obv_signal'] = 'SELL'
                    df['obv_reason'] = "Bearish divergence (price up, OBV down)"
                elif not price_trend and obv_trend:
                    df['obv_signal'] = 'BUY'
                    df['obv_reason'] = "Bullish divergence (price down, OBV up)"
                else:
                    df['obv_signal'] = 'HOLD'
                    df['obv_reason'] = "Neutral OBV"

        return df

    @staticmethod
    def calculate_vwap(data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Volume Weighted Average Price (VWAP)

        VWAP signals:
        - Price above VWAP: Bullish
        - Price below VWAP: Bearish
        - VWAP acts as support/resistance

        Args:
            data: DataFrame with 'high', 'low', 'close', 'volume' columns

        Returns:
            DataFrame with VWAP column added
        """
        logger.info("Calculating VWAP")

        df = data.copy()

        # Calculate Typical Price
        df['tp'] = (df['high'] + df['low'] + df['close']) / 3

        # Calculate VWAP
        df['tp_volume'] = df['tp'] * df['volume']
        df['vwap'] = df['tp_volume'].cumsum() / df['volume'].cumsum()

        # Generate signal
        if len(df) > 0:
            latest_close = df['close'].iloc[-1]
            latest_vwap = df['vwap'].iloc[-1]

            if pd.notna(latest_vwap):
                diff_pct = ((latest_close - latest_vwap) / latest_vwap) * 100

                if latest_close > latest_vwap:
                    df['vwap_signal'] = 'BUY'
                    df['vwap_reason'] = f"Price above VWAP (+{diff_pct:.1f}%)"
                elif latest_close < latest_vwap:
                    df['vwap_signal'] = 'SELL'
                    df['vwap_reason'] = f"Price below VWAP ({diff_pct:.1f}%)"
                else:
                    df['vwap_signal'] = 'HOLD'
                    df['vwap_reason'] = "Price at VWAP"

        return df

    @staticmethod
    def calculate_ad_line(data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Accumulation/Distribution Line

        A/D Line signals:
        - A/D rising with price: Accumulation
        - A/D falling with price: Distribution
        - Divergence: Warning of potential reversal

        Args:
            data: DataFrame with 'high', 'low', 'close', 'volume' columns

        Returns:
            DataFrame with A/D Line column added
        """
        logger.info("Calculating A/D Line")

        df = data.copy()

        # Calculate Money Flow Multiplier
        df['mfm'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
        df['mfm'] = df['mfm'].fillna(0)

        # Calculate Money Flow Volume
        df['mfv'] = df['mfm'] * df['volume']

        # Calculate A/D Line (cumulative)
        df['ad_line'] = df['mfv'].cumsum()

        # Generate signal
        if len(df) > 20:
            latest_ad = df['ad_line'].iloc[-1]
            prev_ad = df['ad_line'].iloc[-20]
            latest_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-20]

            price_trend = latest_price > prev_price
            ad_trend = latest_ad > prev_ad

            if price_trend and ad_trend:
                df['ad_signal'] = 'BUY'
                df['ad_reason'] = "Accumulation phase"
            elif not price_trend and not ad_trend:
                df['ad_signal'] = 'SELL'
                df['ad_reason'] = "Distribution phase"
            elif price_trend and not ad_trend:
                df['ad_signal'] = 'SELL'
                df['ad_reason'] = "Bearish divergence"
            elif not price_trend and ad_trend:
                df['ad_signal'] = 'BUY'
                df['ad_reason'] = "Bullish divergence"
            else:
                df['ad_signal'] = 'HOLD'
                df['ad_reason'] = "Neutral"

        return df

    @staticmethod
    def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        Calculate Average True Range (ATR)

        ATR measures volatility:
        - High ATR: High volatility
        - Low ATR: Low volatility
        - Rising ATR: Increasing volatility

        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            period: ATR period (default: 14)

        Returns:
            DataFrame with ATR column added
        """
        logger.info(f"Calculating ATR with period {period}")

        df = data.copy()

        # Calculate True Range
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)

        # Calculate ATR
        df['atr'] = df['tr'].rolling(window=period).mean()

        # ATR doesn't generate buy/sell signals, but measures volatility
        if len(df) > period:
            latest_atr = df['atr'].iloc[-1]
            avg_atr = df['atr'].iloc[-period:].mean()

            if pd.notna(latest_atr):
                if latest_atr > avg_atr * 1.5:
                    df['atr_signal'] = 'HOLD'
                    df['atr_reason'] = f"High volatility (ATR={latest_atr:.2f})"
                elif latest_atr < avg_atr * 0.5:
                    df['atr_signal'] = 'HOLD'
                    df['atr_reason'] = f"Low volatility (ATR={latest_atr:.2f})"
                else:
                    df['atr_signal'] = 'HOLD'
                    df['atr_reason'] = f"Normal volatility (ATR={latest_atr:.2f})"

        return df

    @staticmethod
    def calculate_keltner_channels(data: pd.DataFrame, period: int = 20, multiplier: float = 2.0) -> pd.DataFrame:
        """
        Calculate Keltner Channels

        Keltner Channels signals:
        - Price above upper channel: Strong uptrend
        - Price below lower channel: Strong downtrend
        - Price returns to middle: Potential reversal

        Args:
            data: DataFrame with 'high', 'low', 'close' columns
            period: EMA period (default: 20)
            multiplier: ATR multiplier (default: 2.0)

        Returns:
            DataFrame with Keltner Channels columns added
        """
        logger.info(f"Calculating Keltner Channels (period={period}, multiplier={multiplier})")

        df = data.copy()

        # Calculate middle line (EMA)
        df['kc_middle'] = df['close'].ewm(span=period, adjust=False).mean()

        # Calculate ATR
        df = TechnicalIndicators.calculate_atr(df, period)

        # Calculate upper and lower channels
        df['kc_upper'] = df['kc_middle'] + (multiplier * df['atr'])
        df['kc_lower'] = df['kc_middle'] - (multiplier * df['atr'])

        # Generate signal
        if len(df) > 0:
            latest_close = df['close'].iloc[-1]
            latest_upper = df['kc_upper'].iloc[-1]
            latest_lower = df['kc_lower'].iloc[-1]
            latest_middle = df['kc_middle'].iloc[-1]

            if pd.notna(latest_upper):
                if latest_close > latest_upper:
                    df['kc_signal'] = 'BUY'
                    df['kc_reason'] = "Price above upper channel (strong uptrend)"
                elif latest_close < latest_lower:
                    df['kc_signal'] = 'SELL'
                    df['kc_reason'] = "Price below lower channel (strong downtrend)"
                elif abs(latest_close - latest_middle) / latest_middle < 0.01:
                    df['kc_signal'] = 'HOLD'
                    df['kc_reason'] = "Price at middle line"
                else:
                    df['kc_signal'] = 'HOLD'
                    df['kc_reason'] = "Price within channels"

        return df

    @staticmethod
    def calculate_all_indicators(data: pd.DataFrame,
                                  rsi_period: int = 14,
                                  macd_fast: int = 12,
                                  macd_slow: int = 26,
                                  macd_signal: int = 9,
                                  bb_window: int = 20,
                                  bb_std: float = 2.0,
                                  ma_short: int = 20,
                                  ma_long: int = 50) -> pd.DataFrame:
        """
        Calculate all technical indicators at once

        Args:
            data: DataFrame with OHLCV columns
            (other args): Parameters for individual indicators

        Returns:
            DataFrame with all indicators added
        """
        logger.info("Calculating all technical indicators")

        df = data.copy()

        # Trend Indicators
        df = TechnicalIndicators.calculate_moving_averages(df, ma_short, ma_long)
        df = TechnicalIndicators.calculate_macd(df, macd_fast, macd_slow, macd_signal)
        df = TechnicalIndicators.calculate_adx(df, 14)
        df = TechnicalIndicators.calculate_parabolic_sar(df, 0.02, 0.2)

        # Momentum Indicators
        df = TechnicalIndicators.calculate_rsi(df, rsi_period)
        df = TechnicalIndicators.calculate_stochastic(df, 14, 3)
        df = TechnicalIndicators.calculate_cci(df, 20)

        # Volume Indicators
        df = TechnicalIndicators.calculate_obv(df)
        df = TechnicalIndicators.calculate_vwap(df)
        df = TechnicalIndicators.calculate_ad_line(df)

        # Volatility Indicators
        df = TechnicalIndicators.calculate_bollinger_bands(df, bb_window, bb_std)
        df = TechnicalIndicators.calculate_atr(df, 14)
        df = TechnicalIndicators.calculate_keltner_channels(df, 20, 2.0)

        return df

    @staticmethod
    def generate_recommendation(df: pd.DataFrame) -> Dict:
        """
        Generate overall recommendation based on all indicators

        Args:
            df: DataFrame with all indicators calculated

        Returns:
            Dictionary with recommendation and reasoning
        """
        if len(df) == 0:
            return {
                'recommendation': 'HOLD',
                'confidence': 0.0,
                'reason': 'No data available',
                'indicators': {}
            }

        latest = df.iloc[-1]

        # Collect signals from each indicator
        signals = []
        indicator_details = {}

        # RSI
        if 'rsi_signal' in df.columns and pd.notna(latest.get('rsi_signal')):
            signals.append(latest['rsi_signal'])
            indicator_details['RSI'] = {
                'value': float(latest['rsi']) if pd.notna(latest.get('rsi')) else None,
                'signal': latest['rsi_signal'],
                'reason': latest.get('rsi_reason', '')
            }

        # MACD
        if 'macd_trend' in df.columns and pd.notna(latest.get('macd_trend')):
            signals.append(latest['macd_trend'])
            indicator_details['MACD'] = {
                'macd': float(latest['macd']) if pd.notna(latest.get('macd')) else None,
                'signal_line': float(latest['macd_signal']) if pd.notna(latest.get('macd_signal')) else None,
                'histogram': float(latest['macd_histogram']) if pd.notna(latest.get('macd_histogram')) else None,
                'signal': latest['macd_trend'],
                'reason': latest.get('macd_reason', '')
            }

        # Bollinger Bands
        if 'bb_signal' in df.columns and pd.notna(latest.get('bb_signal')):
            signals.append(latest['bb_signal'])
            indicator_details['Bollinger_Bands'] = {
                'upper': float(latest['bb_upper']) if pd.notna(latest.get('bb_upper')) else None,
                'middle': float(latest['bb_middle']) if pd.notna(latest.get('bb_middle')) else None,
                'lower': float(latest['bb_lower']) if pd.notna(latest.get('bb_lower')) else None,
                'signal': latest['bb_signal'],
                'reason': latest.get('bb_reason', '')
            }

        # Moving Averages
        if 'ma_signal' in df.columns and pd.notna(latest.get('ma_signal')):
            signals.append(latest['ma_signal'])
            indicator_details['Moving_Averages'] = {
                'ma_short': float(latest['ma_short']) if pd.notna(latest.get('ma_short')) else None,
                'ma_long': float(latest['ma_long']) if pd.notna(latest.get('ma_long')) else None,
                'signal': latest['ma_signal'],
                'reason': latest.get('ma_reason', '')
            }

        # ADX
        if 'adx_signal' in df.columns and pd.notna(latest.get('adx_signal')):
            signals.append(latest['adx_signal'])
            indicator_details['ADX'] = {
                'value': float(latest['adx']) if pd.notna(latest.get('adx')) else None,
                'plus_di': float(latest['plus_di']) if pd.notna(latest.get('plus_di')) else None,
                'minus_di': float(latest['minus_di']) if pd.notna(latest.get('minus_di')) else None,
                'signal': latest['adx_signal'],
                'reason': latest.get('adx_reason', '')
            }

        # Parabolic SAR
        if 'psar_signal' in df.columns and pd.notna(latest.get('psar_signal')):
            signals.append(latest['psar_signal'])
            indicator_details['Parabolic_SAR'] = {
                'value': float(latest['psar']) if pd.notna(latest.get('psar')) else None,
                'trend': int(latest['psar_trend']) if pd.notna(latest.get('psar_trend')) else None,
                'signal': latest['psar_signal'],
                'reason': latest.get('psar_reason', '')
            }

        # Stochastic
        if 'stoch_signal' in df.columns and pd.notna(latest.get('stoch_signal')):
            signals.append(latest['stoch_signal'])
            indicator_details['Stochastic'] = {
                'k': float(latest['stoch_k']) if pd.notna(latest.get('stoch_k')) else None,
                'd': float(latest['stoch_d']) if pd.notna(latest.get('stoch_d')) else None,
                'signal': latest['stoch_signal'],
                'reason': latest.get('stoch_reason', '')
            }

        # CCI
        if 'cci_signal' in df.columns and pd.notna(latest.get('cci_signal')):
            signals.append(latest['cci_signal'])
            indicator_details['CCI'] = {
                'value': float(latest['cci']) if pd.notna(latest.get('cci')) else None,
                'signal': latest['cci_signal'],
                'reason': latest.get('cci_reason', '')
            }

        # OBV
        if 'obv_signal' in df.columns and pd.notna(latest.get('obv_signal')):
            signals.append(latest['obv_signal'])
            indicator_details['OBV'] = {
                'value': float(latest['obv']) if pd.notna(latest.get('obv')) else None,
                'signal': latest['obv_signal'],
                'reason': latest.get('obv_reason', '')
            }

        # VWAP
        if 'vwap_signal' in df.columns and pd.notna(latest.get('vwap_signal')):
            signals.append(latest['vwap_signal'])
            indicator_details['VWAP'] = {
                'value': float(latest['vwap']) if pd.notna(latest.get('vwap')) else None,
                'signal': latest['vwap_signal'],
                'reason': latest.get('vwap_reason', '')
            }

        # A/D Line
        if 'ad_signal' in df.columns and pd.notna(latest.get('ad_signal')):
            signals.append(latest['ad_signal'])
            indicator_details['AD_Line'] = {
                'value': float(latest['ad_line']) if pd.notna(latest.get('ad_line')) else None,
                'signal': latest['ad_signal'],
                'reason': latest.get('ad_reason', '')
            }

        # ATR
        if 'atr_signal' in df.columns and pd.notna(latest.get('atr_signal')):
            # ATR doesn't contribute to signals (it's a volatility measure)
            indicator_details['ATR'] = {
                'value': float(latest['atr']) if pd.notna(latest.get('atr')) else None,
                'signal': latest['atr_signal'],
                'reason': latest.get('atr_reason', '')
            }

        # Keltner Channels
        if 'kc_signal' in df.columns and pd.notna(latest.get('kc_signal')):
            signals.append(latest['kc_signal'])
            indicator_details['Keltner_Channels'] = {
                'upper': float(latest['kc_upper']) if pd.notna(latest.get('kc_upper')) else None,
                'middle': float(latest['kc_middle']) if pd.notna(latest.get('kc_middle')) else None,
                'lower': float(latest['kc_lower']) if pd.notna(latest.get('kc_lower')) else None,
                'signal': latest['kc_signal'],
                'reason': latest.get('kc_reason', '')
            }

        # Calculate overall recommendation based on majority vote
        if not signals:
            return {
                'recommendation': 'HOLD',
                'confidence': 0.0,
                'reason': 'Insufficient indicator data',
                'indicators': indicator_details
            }

        buy_count = signals.count('BUY')
        sell_count = signals.count('SELL')
        hold_count = signals.count('HOLD')
        total = len(signals)

        # Determine recommendation
        if buy_count > sell_count and buy_count >= hold_count:
            recommendation = 'BUY'
            confidence = buy_count / total
            reason = f"{buy_count}/{total} indicators suggest buying"
        elif sell_count > buy_count and sell_count >= hold_count:
            recommendation = 'SELL'
            confidence = sell_count / total
            reason = f"{sell_count}/{total} indicators suggest selling"
        else:
            recommendation = 'HOLD'
            confidence = max(hold_count, buy_count, sell_count) / total
            reason = f"Mixed signals ({buy_count} buy, {sell_count} sell, {hold_count} hold)"

        return {
            'recommendation': recommendation,
            'confidence': round(confidence, 2),
            'reason': reason,
            'indicators': indicator_details,
            'signal_counts': {
                'buy': buy_count,
                'sell': sell_count,
                'hold': hold_count
            }
        }
