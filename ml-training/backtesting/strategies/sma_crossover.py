"""
SMA Crossover Strategy - Classic technical analysis baseline.

Buy when fast SMA crosses above slow SMA.
Sell when fast SMA crosses below slow SMA.
"""
from datetime import date
from typing import Dict, List
import pandas as pd

# Import from local modules
from strategies.base import BaseStrategy, Signal
from config import BacktestConfig


class SMACrossoverStrategy(BaseStrategy):
    """
    SMA Crossover Strategy

    - Buy when fast SMA crosses above slow SMA
    - Sell when fast SMA crosses below slow SMA
    - Equal weight positioning
    """

    def __init__(self, config: BacktestConfig,
                 fast_period: int = 20,
                 slow_period: int = 50):
        """
        Args:
            config: BacktestConfig
            fast_period: Fast SMA period (default: 20)
            slow_period: Slow SMA period (default: 50)
        """
        super().__init__(config)

        self.fast_period = fast_period
        self.slow_period = slow_period

        # Track previous positions to detect crossovers
        self.previous_signals: Dict[str, str] = {}

        print(f"SMA Crossover Strategy initialized:")
        print(f"  Fast SMA: {fast_period} days")
        print(f"  Slow SMA: {slow_period} days")

    def generate_signals(self, current_date: date,
                        data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """
        Generate signals based on SMA crossover

        Args:
            current_date: Current simulation date
            data: Dictionary of symbol -> DataFrame

        Returns:
            List of signals
        """
        signals = []

        for symbol, df in data.items():
            # Need at least slow_period days of history
            if len(df) < self.slow_period:
                continue

            # Get current data point
            current_ts = pd.Timestamp(current_date)

            # Try exact match first
            if current_ts in df.index:
                current_data = df.loc[[current_ts]]
            else:
                # Find nearest date on or before current_date
                mask = df.index <= current_ts
                if not mask.any():
                    continue
                nearest_idx = df.index[mask].max()
                current_data = df.loc[[nearest_idx]]

            if len(current_data) == 0:
                continue

            price = current_data['close'].iloc[0]
            volume = current_data['volume'].iloc[0]

            # Validate stock
            if not self.validate_stock(symbol, price, volume):
                continue

            # Calculate SMAs
            close_series = df.loc[df.index <= current_ts, 'close']

            if len(close_series) < self.slow_period:
                continue

            fast_sma = close_series.tail(self.fast_period).mean()
            slow_sma = close_series.tail(self.slow_period).mean()

            # Calculate previous SMAs (for crossover detection)
            if len(close_series) < self.slow_period + 1:
                prev_close_series = close_series.iloc[:-1]
            else:
                prev_close_series = close_series.iloc[:-1]

            if len(prev_close_series) >= self.slow_period:
                prev_fast_sma = prev_close_series.tail(self.fast_period).mean()
                prev_slow_sma = prev_close_series.tail(self.slow_period).mean()
            else:
                # Not enough history for crossover detection
                continue

            # Detect crossover
            # Bullish crossover: fast crosses above slow
            if (prev_fast_sma <= prev_slow_sma and fast_sma > slow_sma):
                signals.append(Signal(
                    symbol=symbol,
                    action='buy',
                    confidence=1.0,
                    reason=f'sma_cross_bullish_{fast_sma:.2f}_above_{slow_sma:.2f}'
                ))
                self.previous_signals[symbol] = 'buy'

            # Bearish crossover: fast crosses below slow
            elif (prev_fast_sma >= prev_slow_sma and fast_sma < slow_sma):
                signals.append(Signal(
                    symbol=symbol,
                    action='sell',
                    confidence=1.0,
                    reason=f'sma_cross_bearish_{fast_sma:.2f}_below_{slow_sma:.2f}'
                ))
                self.previous_signals[symbol] = 'sell'

        return signals
