"""
Base strategy class for backtesting.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional
import pandas as pd

# Import from local modules
from core.portfolio import Portfolio, PositionSide
from core.executor import Order, OrderSide, OrderExecutor
from config import BacktestConfig


@dataclass
class Signal:
    """Trading signal"""
    symbol: str
    action: str  # 'buy', 'sell', 'hold'
    confidence: float = 1.0  # 0 to 1
    reason: str = ""  # Why this signal was generated


class BaseStrategy(ABC):
    """
    Base class for all trading strategies

    All strategies must implement:
    - generate_signals(): Convert data to buy/sell signals
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.executor = OrderExecutor(config)
        self.signals_generated: List[Signal] = []

    @abstractmethod
    def generate_signals(self, current_date: date,
                        data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """
        Generate trading signals for given date

        Args:
            current_date: Current simulation date
            data: Dictionary of symbol -> DataFrame with OHLCV and features

        Returns:
            List of Signal objects
        """
        pass

    def execute_signals(self, signals: List[Signal],
                       portfolio: Portfolio,
                       prices: Dict[str, float],
                       current_date: date) -> List:
        """
        Execute trading signals

        Args:
            signals: List of signals to execute
            portfolio: Current portfolio
            prices: Current prices (symbol -> price)
            current_date: Current date

        Returns:
            List of executed trades (fills)
        """
        executed = []

        print(f"  Executing {len(signals)} buy signals...")

        for signal in signals:
            if signal.action == 'buy':
                # Check if we can buy
                price = prices[signal.symbol]
                shares = self._calculate_shares(
                    portfolio.cash, price, self.config.universe.max_position_pct
                )

                if shares > 0:
                    # Debug: check why not buying
                    can_buy_result = portfolio.can_buy(
                        shares * price,
                        self.config.universe.max_positions
                    )
                    if not can_buy_result:
                        print(f"    ❌ {signal.symbol}: Cannot buy (cash={portfolio.cash:.2f}, need={shares*price:.2f}, max_pos={self.config.universe.max_positions})")
                        continue

                    # Create order
                    order = Order(
                        symbol=signal.symbol,
                        side=OrderSide.BUY,
                        shares=shares,
                        expected_price=price,
                        date=current_date
                    )

                    # Execute order
                    fill = self.executor.execute(order)

                    # Update portfolio
                    cost = self.executor.calculate_position_cost(fill)
                    if portfolio.buy(
                        signal.symbol,
                        fill.shares,
                        fill.fill_price,
                        current_date,
                        PositionSide.LONG
                    ):
                        executed.append(fill)
                        print(f"    ✅ {signal.symbol}: Bought {shares} shares @ ${fill.fill_price:.2f}")
                    else:
                        print(f"    ❌ {signal.symbol}: Buy failed")

            elif signal.action == 'sell':
                # Check if we have position
                if signal.symbol in portfolio.positions:
                    position = portfolio.positions[signal.symbol]
                    price = prices[signal.symbol]

                    # Create order
                    order = Order(
                        symbol=signal.symbol,
                        side=OrderSide.SELL,
                        shares=position.shares,
                        expected_price=price,
                        date=current_date
                    )

                    # Execute order
                    fill = self.executor.execute(order)

                    # Close position
                    portfolio.sell(
                        signal.symbol,
                        fill.fill_price,
                        current_date,
                        signal.reason or "signal"
                    )

                    executed.append(fill)

        return executed

    def check_exits(self, portfolio: Portfolio,
                   prices: Dict[str, float],
                   current_date: date) -> List:
        """
        Check if any positions should be closed based on strategy rules

        Args:
            portfolio: Current portfolio
            prices: Current prices
            current_date: Current date

        Returns:
            List of executed exit trades
        """
        # Base implementation - override in subclasses
        return []

    def _calculate_shares(self, cash: float, price: float,
                         max_position_pct: float) -> int:
        """
        Calculate number of shares to buy

        Args:
            cash: Available cash
            price: Price per share
            max_position_pct: Max position as percentage of portfolio

        Returns:
            Number of shares to buy
        """
        max_cost = cash * max_position_pct
        shares = int(max_cost / price)

        # Round down to nearest share
        return shares if shares > 0 else 0

    def validate_stock(self, symbol: str, price: float,
                      volume: int) -> bool:
        """
        Check if stock meets trading criteria

        Args:
            symbol: Stock symbol
            price: Current price
            volume: Daily volume

        Returns:
            True if stock is tradeable
        """
        # Check price
        if price < self.config.universe.min_price:
            return False

        # Check volume
        if volume < self.config.universe.min_daily_volume:
            return False

        return True
