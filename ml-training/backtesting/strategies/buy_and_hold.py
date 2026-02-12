"""
Buy & Hold Strategy

Simple baseline strategy - buy all stocks at start and hold until end.
"""
from datetime import date
from typing import Dict, List
import pandas as pd

# Import from local modules
from strategies.base import BaseStrategy, Signal
from config import BacktestConfig


class BuyAndHoldStrategy(BaseStrategy):
    """
    Buy & Hold Strategy

    - Buy all eligible stocks at start date
    - Hold all positions until end date
    - Equal weight positioning
    """

    def __init__(self, config: BacktestConfig):
        super().__init__(config)
        self.initialized = False

    def generate_signals(self, current_date: date,
                        data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """
        Generate signals

        On first day: Buy all eligible stocks
        On other days: No signals (hold)
        """
        signals = []

        # Only generate signals on first day
        if self.initialized:
            return signals

        print(f"Generating buy signals for {len(data)} symbols...")

        for symbol, df in data.items():
            # Get current price
            if len(df) == 0:
                continue

            # Convert current_date to Timestamp for comparison
            # Handle both datetime index and date object
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

            # Generate buy signal
            signals.append(Signal(
                symbol=symbol,
                action='buy',
                confidence=1.0,
                reason='buy_and_hold_initial'
            ))

        self.initialized = True
        return signals

    def check_exits(self, portfolio, prices: Dict[str, float],
                   current_date: date) -> List:
        """
        Check for exits

        Buy & Hold never exits (except at end of backtest)
        """
        return []
