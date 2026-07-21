"""
Built-in example trading strategies (Phase 0.5).

Each strategy subclasses :class:`BaseStrategy` and is decorated with
``@register_strategy`` so the :class:`StrategyManager` picks it up via
auto-discovery — no manual registration list.

Parameter names that flow into ``TechnicalIndicators.calculate_all_indicators``
use the canonical indicator kwargs (``rsi_period``/``macd_fast``/…), which
removes the audit-finding **S3** mismatch at its source. The ``analyze()``
bodies are preserved verbatim from the pre-0.5 behavior.
"""
from typing import Any, Dict, Tuple

import pandas as pd

from .base import BaseStrategy, register_strategy


@register_strategy
class RSIOversoldOverboughtStrategy(BaseStrategy):
    """BUY when RSI < oversold; SELL when RSI > overbought."""

    name = "RSI Oversold/Overbought"
    description = "Buy when RSI is oversold, sell when overbought"

    def get_default_parameters(self) -> Dict[str, Any]:
        return {
            'oversold_threshold': 30,
            'overbought_threshold': 70,
            'rsi_period': 14,  # canonical: flows into calculate_all_indicators
        }

    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any],
    ) -> Tuple[str, float, Dict[str, Any]]:
        if not self.validate_data(prices):
            return 'HOLD', 0.0, {'reason': 'Insufficient data'}

        rsi = indicators.get('RSI', {})
        rsi_value = rsi.get('value', 50)

        current_price = prices.iloc[-1]['close']
        oversold = self.parameters['oversold_threshold']
        overbought = self.parameters['overbought_threshold']

        if rsi_value < oversold:
            confidence = (oversold - rsi_value) / oversold
            stop_loss = current_price * 0.95
            take_profit = current_price * 1.10
            return 'BUY', min(confidence, 1.0), {
                'entry_price': current_price,
                'stop_loss': round(stop_loss, 2),
                'take_profit': round(take_profit, 2),
                'rsi_value': round(rsi_value, 2),
                'reason': f'RSI oversold at {rsi_value:.1f} (< {oversold})'
            }
        elif rsi_value > overbought:
            confidence = (rsi_value - overbought) / (100 - overbought)
            return 'SELL', min(confidence, 1.0), {
                'exit_price': current_price,
                'rsi_value': round(rsi_value, 2),
                'reason': f'RSI overbought at {rsi_value:.1f} (> {overbought})'
            }
        else:
            return 'HOLD', 0.5, {'reason': f'RSI neutral at {rsi_value:.1f}'}

    def get_min_data_points(self) -> int:
        return self.parameters['rsi_period'] + 5


@register_strategy
class MACDCrossoverStrategy(BaseStrategy):
    """BUY on MACD bullish crossover; SELL on bearish crossover."""

    name = "MACD Crossover"
    description = "Trade MACD signal line crossovers"

    def get_default_parameters(self) -> Dict[str, Any]:
        # Canonical indicator names (S3): flow into calculate_all_indicators.
        return {
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
        }

    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any],
    ) -> Tuple[str, float, Dict[str, Any]]:
        if not self.validate_data(prices):
            return 'HOLD', 0.0, {'reason': 'Insufficient data'}

        macd_data = indicators.get('MACD', {})
        macd = macd_data.get('macd', 0)
        signal_line = macd_data.get('signal_line', 0)
        histogram = macd_data.get('histogram', 0)

        current_price = prices.iloc[-1]['close']

        if histogram > 0 and macd > signal_line:
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
            confidence = min(abs(histogram) / 2, 1.0)
            return 'SELL', confidence, {
                'exit_price': current_price,
                'macd': round(macd, 4),
                'signal_line': round(signal_line, 4),
                'histogram': round(histogram, 4),
                'reason': 'MACD bearish crossover detected'
            }
        else:
            return 'HOLD', 0.3, {'reason': 'No MACD crossover signal'}

    def get_min_data_points(self) -> int:
        return self.parameters['macd_slow'] + self.parameters['macd_signal'] + 5


@register_strategy
class MovingAverageCrossoverStrategy(BaseStrategy):
    """Golden Cross / Death Cross (short MA vs long MA)."""

    name = "MA Crossover (Golden/Death Cross)"
    description = "Trade when fast MA crosses slow MA"

    def get_default_parameters(self) -> Dict[str, Any]:
        # Strategy-only (not indicator-calc kwargs); names kept for clarity.
        return {
            'ma_short_period': 50,
            'ma_long_period': 200,
        }

    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any],
    ) -> Tuple[str, float, Dict[str, Any]]:
        if not self.validate_data(prices):
            return 'HOLD', 0.0, {'reason': 'Insufficient data'}

        ma_data = indicators.get('Moving_Averages', {})
        ma_short = ma_data.get('ma_short', 0)
        ma_long = ma_data.get('ma_long', 0)

        current_price = prices.iloc[-1]['close']

        if ma_short > ma_long:
            distance = ((ma_short - ma_long) / ma_long) * 100
            confidence = min(distance / 5, 1.0)
            if distance > 0.5:
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
            distance = ((ma_long - ma_short) / ma_long) * 100
            confidence = min(distance / 5, 1.0)
            if distance > 0.5:
                return 'SELL', confidence, {
                    'exit_price': current_price,
                    'ma_short': round(ma_short, 2),
                    'ma_long': round(ma_long, 2),
                    'distance_pct': round(distance, 2),
                    'reason': f'Death Cross: MA{self.parameters["ma_short_period"]} below MA{self.parameters["ma_long_period"]}'
                }

        return 'HOLD', 0.3, {'reason': 'No significant MA crossover'}

    def get_min_data_points(self) -> int:
        return self.parameters['ma_long_period'] + 10


@register_strategy
class BollingerBandsMeanReversionStrategy(BaseStrategy):
    """BUY at lower band (oversold); SELL at upper band (overbought)."""

    name = "Bollinger Bands Mean Reversion"
    description = "Buy at lower band, sell at upper band"

    def get_default_parameters(self) -> Dict[str, Any]:
        return {
            'bb_window': 20,   # canonical: flows into calculate_all_indicators
            'bb_std': 2.0,     # canonical
            'touch_threshold': 0.005,
        }

    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any],
    ) -> Tuple[str, float, Dict[str, Any]]:
        if not self.validate_data(prices):
            return 'HOLD', 0.0, {'reason': 'Insufficient data'}

        bb_data = indicators.get('Bollinger_Bands', {})
        bb_upper = bb_data.get('upper', 0)
        bb_middle = bb_data.get('middle', 0)
        bb_lower = bb_data.get('lower', 0)

        current_price = prices.iloc[-1]['close']
        threshold = self.parameters['touch_threshold']

        lower_distance = abs(current_price - bb_lower) / bb_lower
        upper_distance = abs(current_price - bb_upper) / bb_upper

        if lower_distance < threshold:
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
            confidence = 1.0 - upper_distance / threshold
            return 'SELL', confidence, {
                'exit_price': current_price,
                'bb_upper': round(bb_upper, 2),
                'bb_middle': round(bb_middle, 2),
                'bb_lower': round(bb_lower, 2),
                'reason': 'Price touched upper Bollinger Band (overbought)'
            }
        else:
            return 'HOLD', 0.4, {'reason': 'Price within Bollinger Bands'}

    def get_min_data_points(self) -> int:
        return self.parameters['bb_window'] + 5


@register_strategy
class TrendFollowingStrategy(BaseStrategy):
    """Multi-indicator trend following (ADX + MA + RSI)."""

    name = "Multi-Indicator Trend Following"
    description = "Follow strong trends using ADX, MA, and RSI"

    def get_default_parameters(self) -> Dict[str, Any]:
        return {
            'adx_threshold': 25,
            'rsi_buy_max': 60,
            'rsi_sell_min': 40,
            'ma_short': 20,
            'ma_long': 50,
        }

    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any],
    ) -> Tuple[str, float, Dict[str, Any]]:
        if not self.validate_data(prices):
            return 'HOLD', 0.0, {'reason': 'Insufficient data'}

        adx_data = indicators.get('ADX', {})
        adx = adx_data.get('value', 0)

        ma_data = indicators.get('Moving_Averages', {})
        ma_short = ma_data.get('ma_short', 0)
        ma_long = ma_data.get('ma_long', 0)

        rsi_data = indicators.get('RSI', {})
        rsi = rsi_data.get('value', 50)

        current_price = prices.iloc[-1]['close']

        if adx < self.parameters['adx_threshold']:
            return 'HOLD', 0.2, {'reason': f'No strong trend detected (ADX: {adx:.1f})'}

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
            return 'HOLD', 0.3, {'reason': 'Trend detected but conditions not met for entry'}

    def get_min_data_points(self) -> int:
        return max(self.parameters['ma_long'], 50) + 10
