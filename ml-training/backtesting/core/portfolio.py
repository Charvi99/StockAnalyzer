"""
Portfolio tracking for backtesting.

Tracks positions, cash, and calculates P&L.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional
from enum import Enum
import pandas as pd


class PositionSide(Enum):
    """Position side (long or short)"""
    LONG = "long"
    SHORT = "short"


@dataclass
class Position:
    """Single position in a stock"""
    symbol: str
    side: PositionSide
    shares: int
    entry_price: float
    entry_date: date
    exit_price: Optional[float] = None
    exit_date: Optional[date] = None
    exit_reason: Optional[str] = None  # 'profit_target', 'stop_loss', 'time_exit', 'signal_change'

    @property
    def is_open(self) -> bool:
        """Check if position is still open"""
        return self.exit_date is None

    @property
    def days_held(self) -> int:
        """Calculate days held"""
        if self.exit_date:
            return (self.exit_date - self.entry_date).days
        return (datetime.now().date() - self.entry_date).days

    @property
    def current_pnl_pct(self) -> float:
        """Calculate P&L as percentage"""
        if self.exit_price:
            price = self.exit_price
        else:
            # Need current price from elsewhere
            return 0.0

        if self.side == PositionSide.LONG:
            return (price - self.entry_price) / self.entry_price
        else:  # SHORT
            return (self.entry_price - price) / self.entry_price

    @property
    def current_pnl(self) -> float:
        """Calculate P&L in dollars"""
        if self.exit_price:
            price = self.exit_price
        else:
            return 0.0

        if self.side == PositionSide.LONG:
            return (price - self.entry_price) * self.shares
        else:  # SHORT
            return (self.entry_price - price) * self.shares

    def close(self, exit_price: float, exit_date: date, reason: str = ""):
        """Close the position"""
        self.exit_price = exit_price
        self.exit_date = exit_date
        self.exit_reason = reason


@dataclass
class Trade:
    """A completed trade"""
    symbol: str
    side: PositionSide
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    shares: int
    exit_reason: str

    @property
    def pnl_pct(self) -> float:
        """P&L as percentage"""
        if self.side == PositionSide.LONG:
            return (self.exit_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.exit_price) / self.entry_price

    @property
    def pnl_dollars(self) -> float:
        """P&L in dollars"""
        if self.side == PositionSide.LONG:
            return (self.exit_price - self.entry_price) * self.shares
        else:
            return (self.entry_price - self.exit_price) * self.shares

    @property
    def days_held(self) -> int:
        """Days position was held"""
        return (self.exit_date - self.entry_date).days

    def is_profitable(self) -> bool:
        """Check if trade was profitable"""
        return self.pnl_dollars > 0


@dataclass
class Portfolio:
    """Portfolio tracking for backtesting"""

    cash: float = 100_000.0
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)

    # Track history
    history: List[dict] = field(default_factory=list)

    def get_value(self, prices: Dict[str, float]) -> float:
        """
        Calculate total portfolio value

        Args:
            prices: Dictionary of symbol -> current price

        Returns:
            Total portfolio value (cash + positions)
        """
        total = self.cash

        for symbol, position in self.positions.items():
            if position.is_open:
                price = prices.get(symbol, position.entry_price)
                total += price * position.shares

        return total

    def get_open_positions_count(self) -> int:
        """Get number of open positions"""
        return sum(1 for p in self.positions.values() if p.is_open)

    def can_buy(self, cost: float, max_positions: int) -> bool:
        """Check if we can buy"""
        return self.cash >= cost and self.get_open_positions_count() < max_positions

    def buy(self, symbol: str, shares: int, price: float, date: date,
            side: PositionSide = PositionSide.LONG) -> bool:
        """
        Enter a position

        Args:
            symbol: Stock symbol
            shares: Number of shares
            price: Entry price
            date: Entry date
            side: LONG or SHORT

        Returns:
            True if position opened successfully
        """
        cost = shares * price

        if side == PositionSide.SHORT:
            # For short, we receive cash but need margin
            # Simplified: assume 150% margin requirement
            margin_requirement = cost * 1.5
            if self.cash < margin_requirement:
                return False
            self.cash -= margin_requirement
        else:
            if self.cash < cost:
                return False
            self.cash -= cost

        self.positions[symbol] = Position(
            symbol=symbol,
            side=side,
            shares=shares,
            entry_price=price,
            entry_date=date
        )

        return True

    def sell(self, symbol: str, price: float, date: date, reason: str = "") -> Optional[Trade]:
        """
        Close a position

        Args:
            symbol: Stock symbol
            price: Exit price
            date: Exit date
            reason: Exit reason

        Returns:
            Trade record if position existed, None otherwise
        """
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        if not position.is_open:
            return None

        # Close the position
        position.close(price, date, reason)

        # Update cash
        proceeds = price * position.shares

        if position.side == PositionSide.SHORT:
            # For short, we get back margin + P&L
            pnl = position.current_pnl
            margin_return = position.entry_price * position.shares * 1.5
            self.cash += margin_return + pnl
        else:
            self.cash += proceeds

        # Create trade record
        trade = Trade(
            symbol=symbol,
            side=position.side,
            entry_date=position.entry_date,
            exit_date=position.exit_date,
            entry_price=position.entry_price,
            exit_price=price,
            shares=position.shares,
            exit_reason=reason
        )

        self.trades.append(trade)

        # Remove from open positions
        del self.positions[symbol]

        return trade

    def update_prices(self, prices: Dict[str, float], date: date):
        """
        Update position prices and record history

        Args:
            prices: Symbol -> price mapping
            date: Current date
        """
        portfolio_value = self.get_value(prices)

        # Record history
        self.history.append({
            'date': date,
            'cash': self.cash,
            'positions_value': portfolio_value - self.cash,
            'total_value': portfolio_value,
            'open_positions': self.get_open_positions_count()
        })

    def get_history_df(self) -> pd.DataFrame:
        """Get portfolio history as DataFrame"""
        return pd.DataFrame(self.history)

    def get_trades_df(self) -> pd.DataFrame:
        """Get trades as DataFrame"""
        if not self.trades:
            return pd.DataFrame()

        data = [{
            'symbol': t.symbol,
            'side': t.side.value,
            'entry_date': t.entry_date,
            'exit_date': t.exit_date,
            'entry_price': t.entry_price,
            'exit_price': t.exit_price,
            'shares': t.shares,
            'pnl_pct': t.pnl_pct,
            'pnl_dollars': t.pnl_dollars,
            'days_held': t.days_held,
            'exit_reason': t.exit_reason,
            'profitable': t.is_profitable()
        } for t in self.trades]

        return pd.DataFrame(data)

    @property
    def total_return(self) -> float:
        """Calculate total return"""
        if not self.history:
            return 0.0

        start_value = self.history[0]['total_value']
        current_value = self.history[-1]['total_value']

        if start_value == 0:
            return 0.0

        return (current_value - start_value) / start_value

    def get_returns_series(self) -> pd.Series:
        """Get daily returns series"""
        history_df = self.get_history_df()

        if len(history_df) < 2:
            return pd.Series([], dtype=float)

        # Ensure date is a DatetimeIndex
        if not isinstance(history_df.index, pd.DatetimeIndex):
            history_df['date'] = pd.to_datetime(history_df['date'])

        history_df['daily_return'] = history_df['total_value'].pct_change()

        # Drop the first row (NaN return from pct_change)
        history_df = history_df.dropna(subset=['daily_return'])

        # Set date as index and ensure it's a DatetimeIndex
        returns = history_df.set_index('date')['daily_return']
        if not isinstance(returns.index, pd.DatetimeIndex):
            returns.index = pd.to_datetime(returns.index)

        return returns
