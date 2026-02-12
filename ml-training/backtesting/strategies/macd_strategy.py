"""
MACD Strategy - Classic momentum indicator baseline.

Buy when MACD crosses above signal line.
Sell when MACD crosses below signal line.
"""
from datetime import date
from typing import Dict, List
import pandas as pd

# Import from local modules
from strategies.base import BaseStrategy, Signal
from config import BacktestConfig


class MACDStrategy(BaseStrategy):
    """
    MACD Strategy

    - Buy when MACD crosses above signal line
    - Sell when MACD crosses below signal line
    - Equal weight positioning
    """

    def __init__(self, config: BacktestConfig,
                 fast_period: int = 12,
                 slow_period: int = 26,
                 signal_period: int = 9):
        """
        Args:
            config: BacktestConfig
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal line EMA period (default: 9)
        """
        super().__init__(config)

        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

        # Track previous positions to detect crossovers
        self.previous_signals: Dict[str, str] = {}

        print(f"MACD Strategy initialized:")
        print(f"  Fast EMA: {fast_period}")
        print(f"  Slow EMA: {slow_period}")
        print(f"  Signal EMA: {signal_period}")

    def generate_signals(self, current_date: date,
                        data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """
        Generate signals based on MACD crossover

        Args:
            current_date: Current simulation date
            data: Dictionary of symbol -> DataFrame

        Returns:
            List of signals
        """
        signals = []

        for symbol, df in data.items():
            # Need at least slow_period + signal_period days of history
            min_history = self.slow_period + self.signal_period
            if len(df) < min_history:
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

            # Get historical close prices
            close_series = df.loc[df.index <= current_ts, 'close']

            if len(close_series) < min_history:
                continue

            # Calculate MACD if not already in data
            if 'macd' not in df.columns or 'macd_signal' not in df.columns:
                try:
                    # Calculate EMAs
                    ema_fast = close_series.ewm(span=self.fast_period, adjust=False).mean()
                    ema_slow = close_series.ewm(span=self.slow_period, adjust=False).mean()

                    # MACD line
                    macd_line = ema_fast - ema_slow

                    # Signal line
                    signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()

                    # Get current and previous values
                    macd = macd_line.iloc[-1]
                    signal = signal_line.iloc[-1]

                    if len(macd_line) > 1:
                        prev_macd = macd_line.iloc[-2]
                        prev_signal = signal_line.iloc[-2]
                    else:
                        continue

                except Exception:
                    continue
            else:
                # Use pre-calculated MACD from features
                current_row = current_data.iloc[0]
                macd = current_row.get('macd')
                signal = current_row.get('macd_signal')

                if pd.isna(macd) or pd.isna(signal):
                    continue

                # Get previous values
                prev_data = df.loc[df.index < current_ts]
                if len(prev_data) == 0:
                    continue

                prev_row = prev_data.iloc[-1]
                prev_macd = prev_row.get('macd', macd)
                prev_signal = prev_row.get('macd_signal', signal)

            # Detect crossover
            # Bullish crossover: MACD crosses above signal
            if (prev_macd <= prev_signal and macd > signal):
                signals.append(Signal(
                    symbol=symbol,
                    action='buy',
                    confidence=1.0,
                    reason=f'macd_cross_bullish_{macd:.4f}_above_{signal:.4f}'
                ))
                self.previous_signals[symbol] = 'buy'

            # Bearish crossover: MACD crosses below signal
            elif (prev_macd >= prev_signal and macd < signal):
                signals.append(Signal(
                    symbol=symbol,
                    action='sell',
                    confidence=1.0,
                    reason=f'macd_cross_bearish_{macd:.4f}_below_{signal:.4f}'
                ))
                self.previous_signals[symbol] = 'sell'

        return signals
