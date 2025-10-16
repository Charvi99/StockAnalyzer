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

        # Calculate all indicators
        df = TechnicalIndicators.calculate_rsi(df, rsi_period)
        df = TechnicalIndicators.calculate_macd(df, macd_fast, macd_slow, macd_signal)
        df = TechnicalIndicators.calculate_bollinger_bands(df, bb_window, bb_std)
        df = TechnicalIndicators.calculate_moving_averages(df, ma_short, ma_long)

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
