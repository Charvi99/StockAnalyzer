"""
Random Strategy - Baseline for comparison.

Randomly buys stocks with given probability each day.
Holds for fixed period then exits.
Useful as a baseline to compare against ML strategies.
"""
from datetime import date, timedelta
from typing import Dict, List
import pandas as pd
import random

# Import from local modules
from strategies.base import BaseStrategy, Signal
from core.portfolio import Portfolio
from config import BacktestConfig


class RandomStrategy(BaseStrategy):
    """
    Random Strategy

    - Randomly buys stocks with given probability each day
    - Holds for fixed period then exits
    - Useful as a baseline to compare against ML strategies
    """

    def __init__(self, config: BacktestConfig,
                 buy_probability: float = 0.02,
                 hold_days: int = 20,
                 seed: int = 42):
        """
        Args:
            config: BacktestConfig
            buy_probability: Probability of buying each stock each day (default: 2%)
            hold_days: How long to hold positions (default: 20 days)
            seed: Random seed for reproducibility
        """
        super().__init__(config)

        self.buy_probability = buy_probability
        self.hold_days = hold_days

        # Set random seed for reproducibility
        random.seed(seed)

        # Track entry dates for exit logic
        self.position_entries: Dict[str, date] = {}

        print(f"Random Strategy initialized:")
        print(f"  Buy probability: {buy_probability:.1%} per stock per day")
        print(f"  Hold period: {hold_days} days")
        print(f"  Random seed: {seed}")

    def generate_signals(self, current_date: date,
                        data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """
        Generate random buy signals

        Args:
            current_date: Current simulation date
            data: Dictionary of symbol -> DataFrame

        Returns:
            List of buy signals
        """
        signals = []

        for symbol, df in data.items():
            # Skip if we already have a position
            if symbol in self.position_entries:
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

            # Random decision to buy
            if random.random() < self.buy_probability:
                signals.append(Signal(
                    symbol=symbol,
                    action='buy',
                    confidence=random.random(),  # Random confidence
                    reason='random_buy'
                ))

        return signals

    def execute_signals(self, signals: List[Signal],
                       portfolio: Portfolio,
                       prices: Dict[str, float],
                       current_date: date) -> List:
        """
        Execute signals and track entries for exit logic

        Args:
            signals: List of signals
            portfolio: Current portfolio
            prices: Current prices
            current_date: Current date

        Returns:
            List of executed fills
        """
        executed = super().execute_signals(signals, portfolio, prices, current_date)

        # Track entry dates for positions we just opened
        for fill in executed:
            if fill.side.value == 'buy':
                self.position_entries[fill.symbol] = current_date

        return executed

    def check_exits(self, portfolio: Portfolio,
                   prices: Dict[str, float],
                   current_date: date) -> List:
        """
        Check if positions should be closed based on hold time

        Args:
            portfolio: Current portfolio
            prices: Current prices
            current_date: Current date

        Returns:
            List of symbols that were exited
        """
        exits = []

        for symbol in list(portfolio.positions.keys()):
            if symbol not in self.position_entries:
                continue

            position = portfolio.positions[symbol]
            if not position.is_open:
                # Clean up closed positions
                del self.position_entries[symbol]
                continue

            entry_date = self.position_entries[symbol]
            days_held = (current_date - entry_date).days

            # Exit if hold period exceeded
            if days_held >= self.hold_days:
                current_price = prices.get(symbol, position.entry_price)
                portfolio.sell(symbol, current_price, current_date, 'time_exit')
                exits.append(symbol)

                # Clean up
                del self.position_entries[symbol]

                pnl_pct = (current_price - position.entry_price) / position.entry_price
                print(f"    EXIT {symbol}: time_exit (P&L: {pnl_pct:+.2%}, held: {days_held}d)")

        return exits
