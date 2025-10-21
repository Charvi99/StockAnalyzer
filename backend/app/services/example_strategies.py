"""
Example Trading Strategies

This module contains example strategies that demonstrate how to extend
the BaseStrategy class to create custom trading strategies.

Use these as templates for creating your own strategies!
"""

from typing import Dict, Tuple, Any
import pandas as pd
from .base_strategy import BaseStrategy


class RSIOversoldOverboughtStrategy(BaseStrategy):
    """
    Simple RSI-based strategy.

    BUY when RSI < oversold_threshold
    SELL when RSI > overbought_threshold
    """

    def __init__(self):
        super().__init__(
            name="RSI Oversold/Overbought",
            description="Buy when RSI is oversold, sell when overbought",
            parameters={
                'oversold_threshold': 30,
                'overbought_threshold': 70,
                'rsi_period': 14
            }
        )

    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any]
    ) -> Tuple[str, float, Dict[str, Any]]:
        """Analyze using RSI indicator."""

        if not self.validate_data(prices):
            return 'HOLD', 0.0, {'reason': 'Insufficient data'}

        # Get RSI value
        rsi = indicators.get('RSI', {})
        rsi_value = rsi.get('value', 50)

        current_price = prices.iloc[-1]['close']
        oversold = self.parameters['oversold_threshold']
        overbought = self.parameters['overbought_threshold']

        # Generate signal
        if rsi_value < oversold:
            # Oversold - potential buy signal
            confidence = (oversold - rsi_value) / oversold
            stop_loss = current_price * 0.95  # 5% stop loss
            take_profit = current_price * 1.10  # 10% take profit

            return 'BUY', min(confidence, 1.0), {
                'entry_price': current_price,
                'stop_loss': round(stop_loss, 2),
                'take_profit': round(take_profit, 2),
                'rsi_value': round(rsi_value, 2),
                'reason': f'RSI oversold at {rsi_value:.1f} (< {oversold})'
            }

        elif rsi_value > overbought:
            # Overbought - potential sell signal
            confidence = (rsi_value - overbought) / (100 - overbought)

            return 'SELL', min(confidence, 1.0), {
                'exit_price': current_price,
                'rsi_value': round(rsi_value, 2),
                'reason': f'RSI overbought at {rsi_value:.1f} (> {overbought})'
            }

        else:
            return 'HOLD', 0.5, {
                'reason': f'RSI neutral at {rsi_value:.1f}'
            }

    def get_min_data_points(self) -> int:
        return self.parameters['rsi_period'] + 5


class MACDCrossoverStrategy(BaseStrategy):
    """
    MACD Crossover Strategy.

    BUY when MACD crosses above signal line (bullish crossover)
    SELL when MACD crosses below signal line (bearish crossover)
    """

    def __init__(self):
        super().__init__(
            name="MACD Crossover",
            description="Trade MACD signal line crossovers",
            parameters={
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9
            }
        )

    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any]
    ) -> Tuple[str, float, Dict[str, Any]]:
        """Analyze using MACD crossovers."""

        if not self.validate_data(prices):
            return 'HOLD', 0.0, {'reason': 'Insufficient data'}

        macd_data = indicators.get('MACD', {})
        macd = macd_data.get('macd', 0)
        signal_line = macd_data.get('signal_line', 0)
        histogram = macd_data.get('histogram', 0)

        current_price = prices.iloc[-1]['close']

        # Check for crossover
        if histogram > 0 and macd > signal_line:
            # Bullish crossover
            confidence = min(abs(histogram) / 2, 1.0)
            stop_loss = current_price * 0.97
            take_profit = current_price * 1.08

            return 'BUY', confidence, {
                'entry_price': current_price,
                'stop_loss': round(stop_loss, 2),
                'take_profit': round(take_profit, 2),
                'macd': round(macd, 4),
                'signal_line': round(signal_line, 4),
                'histogram': round(histogram, 4),
                'reason': 'MACD bullish crossover detected'
            }

        elif histogram < 0 and macd < signal_line:
            # Bearish crossover
            confidence = min(abs(histogram) / 2, 1.0)

            return 'SELL', confidence, {
                'exit_price': current_price,
                'macd': round(macd, 4),
                'signal_line': round(signal_line, 4),
                'histogram': round(histogram, 4),
                'reason': 'MACD bearish crossover detected'
            }

        else:
            return 'HOLD', 0.3, {
                'reason': 'No MACD crossover signal'
            }

    def get_min_data_points(self) -> int:
        return self.parameters['slow_period'] + self.parameters['signal_period'] + 5


class MovingAverageCrossoverStrategy(BaseStrategy):
    """
    Moving Average Crossover Strategy (Golden Cross / Death Cross).

    BUY when short MA crosses above long MA (Golden Cross)
    SELL when short MA crosses below long MA (Death Cross)
    """

    def __init__(self):
        super().__init__(
            name="MA Crossover (Golden/Death Cross)",
            description="Trade when fast MA crosses slow MA",
            parameters={
                'ma_short_period': 50,
                'ma_long_period': 200
            }
        )

    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any]
    ) -> Tuple[str, float, Dict[str, Any]]:
        """Analyze using MA crossovers."""

        if not self.validate_data(prices):
            return 'HOLD', 0.0, {'reason': 'Insufficient data'}

        ma_data = indicators.get('Moving_Averages', {})
        ma_short = ma_data.get('ma_short', 0)
        ma_long = ma_data.get('ma_long', 0)

        current_price = prices.iloc[-1]['close']

        # Calculate crossover strength
        if ma_short > ma_long:
            # Golden Cross (bullish)
            distance = ((ma_short - ma_long) / ma_long) * 100
            confidence = min(distance / 5, 1.0)  # Max confidence at 5% distance

            if distance > 0.5:  # Significant crossover
                stop_loss = ma_long * 0.98
                take_profit = current_price * 1.15

                return 'BUY', confidence, {
                    'entry_price': current_price,
                    'stop_loss': round(stop_loss, 2),
                    'take_profit': round(take_profit, 2),
                    'ma_short': round(ma_short, 2),
                    'ma_long': round(ma_long, 2),
                    'distance_pct': round(distance, 2),
                    'reason': f'Golden Cross: MA{self.parameters["ma_short_period"]} above MA{self.parameters["ma_long_period"]}'
                }

        elif ma_short < ma_long:
            # Death Cross (bearish)
            distance = ((ma_long - ma_short) / ma_long) * 100
            confidence = min(distance / 5, 1.0)

            if distance > 0.5:  # Significant crossover
                return 'SELL', confidence, {
                    'exit_price': current_price,
                    'ma_short': round(ma_short, 2),
                    'ma_long': round(ma_long, 2),
                    'distance_pct': round(distance, 2),
                    'reason': f'Death Cross: MA{self.parameters["ma_short_period"]} below MA{self.parameters["ma_long_period"]}'
                }

        return 'HOLD', 0.3, {
            'reason': 'No significant MA crossover'
        }

    def get_min_data_points(self) -> int:
        return self.parameters['ma_long_period'] + 10


class BollingerBandsMeanReversionStrategy(BaseStrategy):
    """
    Bollinger Bands Mean Reversion Strategy.

    BUY when price touches lower band (oversold)
    SELL when price touches upper band (overbought)
    """

    def __init__(self):
        super().__init__(
            name="Bollinger Bands Mean Reversion",
            description="Buy at lower band, sell at upper band",
            parameters={
                'bb_window': 20,
                'bb_std': 2.0,
                'touch_threshold': 0.005  # Price within 0.5% of band
            }
        )

    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any]
    ) -> Tuple[str, float, Dict[str, Any]]:
        """Analyze using Bollinger Bands."""

        if not self.validate_data(prices):
            return 'HOLD', 0.0, {'reason': 'Insufficient data'}

        bb_data = indicators.get('Bollinger_Bands', {})
        bb_upper = bb_data.get('upper', 0)
        bb_middle = bb_data.get('middle', 0)
        bb_lower = bb_data.get('lower', 0)

        current_price = prices.iloc[-1]['close']
        threshold = self.parameters['touch_threshold']

        # Check if price is at bands
        lower_distance = abs(current_price - bb_lower) / bb_lower
        upper_distance = abs(current_price - bb_upper) / bb_upper

        if lower_distance < threshold:
            # Price at lower band - oversold
            confidence = 1.0 - lower_distance / threshold
            stop_loss = bb_lower * 0.98
            take_profit = bb_middle

            return 'BUY', confidence, {
                'entry_price': current_price,
                'stop_loss': round(stop_loss, 2),
                'take_profit': round(take_profit, 2),
                'bb_upper': round(bb_upper, 2),
                'bb_middle': round(bb_middle, 2),
                'bb_lower': round(bb_lower, 2),
                'reason': 'Price touched lower Bollinger Band (oversold)'
            }

        elif upper_distance < threshold:
            # Price at upper band - overbought
            confidence = 1.0 - upper_distance / threshold

            return 'SELL', confidence, {
                'exit_price': current_price,
                'bb_upper': round(bb_upper, 2),
                'bb_middle': round(bb_middle, 2),
                'bb_lower': round(bb_lower, 2),
                'reason': 'Price touched upper Bollinger Band (overbought)'
            }

        else:
            return 'HOLD', 0.4, {
                'reason': 'Price within Bollinger Bands'
            }

    def get_min_data_points(self) -> int:
        return self.parameters['bb_window'] + 5


class TrendFollowingStrategy(BaseStrategy):
    """
    Multi-Indicator Trend Following Strategy.

    Combines ADX (trend strength), moving averages (trend direction),
    and RSI (entry timing) for robust trend following.
    """

    def __init__(self):
        super().__init__(
            name="Multi-Indicator Trend Following",
            description="Follow strong trends using ADX, MA, and RSI",
            parameters={
                'adx_threshold': 25,  # Minimum ADX for strong trend
                'rsi_buy_max': 60,    # Don't buy if RSI too high
                'rsi_sell_min': 40,   # Don't sell if RSI too low
                'ma_short': 20,
                'ma_long': 50
            }
        )

    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any]
    ) -> Tuple[str, float, Dict[str, Any]]:
        """Analyze using multiple indicators."""

        if not self.validate_data(prices):
            return 'HOLD', 0.0, {'reason': 'Insufficient data'}

        # Get indicator values
        adx_data = indicators.get('ADX', {})
        adx = adx_data.get('value', 0)

        ma_data = indicators.get('Moving_Averages', {})
        ma_short = ma_data.get('ma_short', 0)
        ma_long = ma_data.get('ma_long', 0)

        rsi_data = indicators.get('RSI', {})
        rsi = rsi_data.get('value', 50)

        current_price = prices.iloc[-1]['close']

        # Check for strong trend
        if adx < self.parameters['adx_threshold']:
            return 'HOLD', 0.2, {
                'reason': f'No strong trend detected (ADX: {adx:.1f})'
            }

        # Uptrend conditions
        if ma_short > ma_long and rsi < self.parameters['rsi_buy_max']:
            trend_strength = min(adx / 50, 1.0)
            confidence = trend_strength * 0.8

            stop_loss = ma_short * 0.96
            take_profit = current_price * 1.12

            return 'BUY', confidence, {
                'entry_price': current_price,
                'stop_loss': round(stop_loss, 2),
                'take_profit': round(take_profit, 2),
                'adx': round(adx, 1),
                'rsi': round(rsi, 1),
                'ma_short': round(ma_short, 2),
                'ma_long': round(ma_long, 2),
                'reason': f'Strong uptrend (ADX: {adx:.1f}, MA bullish, RSI: {rsi:.1f})'
            }

        # Downtrend conditions
        elif ma_short < ma_long and rsi > self.parameters['rsi_sell_min']:
            trend_strength = min(adx / 50, 1.0)
            confidence = trend_strength * 0.8

            return 'SELL', confidence, {
                'exit_price': current_price,
                'adx': round(adx, 1),
                'rsi': round(rsi, 1),
                'ma_short': round(ma_short, 2),
                'ma_long': round(ma_long, 2),
                'reason': f'Strong downtrend (ADX: {adx:.1f}, MA bearish, RSI: {rsi:.1f})'
            }

        else:
            return 'HOLD', 0.3, {
                'reason': 'Trend detected but conditions not met for entry'
            }

    def get_min_data_points(self) -> int:
        return max(self.parameters['ma_long'], 50) + 10
