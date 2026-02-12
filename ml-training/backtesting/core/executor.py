"""
Order execution simulation.

Simulates realistic order execution with slippage and transaction costs.
"""
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional
from enum import Enum

# Import PositionSide from portfolio module
from .portfolio import PositionSide

# Import config when used
def _get_config():
    """Lazy import of config to avoid circular imports"""
    from config import BacktestConfig, TransactionCosts, SlippageConfig
    return BacktestConfig, TransactionCosts, SlippageConfig

BacktestConfig, TransactionCosts, SlippageConfig = _get_config()


class OrderSide(Enum):
    """Order side"""
    BUY = "buy"
    SELL = "sell"
    SELL_SHORT = "sell_short"


@dataclass
class Order:
    """Order to execute"""
    symbol: str
    side: OrderSide
    shares: int
    expected_price: float  # Price we expect to get
    date: date

    @property
    def expected_value(self) -> float:
        """Expected order value"""
        return self.shares * self.expected_price


@dataclass
class Fill:
    """Executed order with actual execution details"""
    symbol: str
    side: OrderSide
    shares: int
    expected_price: float
    fill_price: float  # Actual price after slippage
    slippage_pct: float  # Slippage as percentage
    commission: float  # Commission paid
    total_cost: float  # Total cost including commission
    date: date

    @property
    def slippage_dollars(self) -> float:
        """Slippage in dollars"""
        if self.side in [OrderSide.BUY, OrderSide.SELL_SHORT]:
            return (self.fill_price - self.expected_price) * self.shares
        else:  # SELL
            return (self.expected_price - self.fill_price) * self.shares

    @property
    def effective_price(self) -> float:
        """Effective price including slippage and commission"""
        if self.side == OrderSide.BUY:
            return self.fill_price + self.commission / self.shares
        elif self.side == OrderSide.SELL:
            return self.fill_price - self.commission / self.shares
        else:  # SELL_SHORT
            return self.fill_price - self.commission / self.shares


class OrderExecutor:
    """
    Simulates order execution with realistic costs and slippage
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.costs = config.costs
        self.slippage_config = config.slippage

    def execute(self, order: Order, daily_volume: Optional[int] = None,
                daily_volatility: Optional[float] = None) -> Fill:
        """
        Execute an order with slippage and transaction costs

        Args:
            order: Order to execute
            daily_volume: Average daily volume (for slippage calculation)
            daily_volatility: Daily volatility (for slippage calculation)

        Returns:
            Fill with actual execution details
        """
        # Calculate slippage
        slippage_pct = self._calculate_slippage(
            order, daily_volume, daily_volatility
        )

        # Apply slippage to get fill price
        if order.side == OrderSide.BUY:
            fill_price = order.expected_price * (1 + slippage_pct)
        elif order.side == OrderSide.SELL:
            fill_price = order.expected_price * (1 - slippage_pct)
        else:  # SELL_SHORT
            fill_price = order.expected_price * (1 - slippage_pct)

        # Calculate commission
        commission = self._calculate_commission(order)

        # Calculate total cost
        if order.side == OrderSide.BUY:
            total_cost = fill_price * order.shares + commission
        elif order.side == OrderSide.SELL:
            total_cost = fill_price * order.shares - commission
        else:  # SELL_SHORT
            total_cost = fill_price * order.shares - commission

        return Fill(
            symbol=order.symbol,
            side=order.side,
            shares=order.shares,
            expected_price=order.expected_price,
            fill_price=fill_price,
            slippage_pct=slippage_pct,
            commission=commission,
            total_cost=total_cost,
            date=order.date
        )

    def _calculate_slippage(self, order: Order,
                           daily_volume: Optional[int] = None,
                           daily_volatility: Optional[float] = None) -> float:
        """
        Calculate slippage percentage

        Args:
            order: Order to execute
            daily_volume: Average daily volume
            daily_volatility: Daily volatility (as decimal, e.g., 0.02 for 2%)

        Returns:
            Slippage as percentage (e.g., 0.001 for 0.1%)
        """
        slippage = self.slippage_config.base_slippage

        # Check if stock is illiquid
        is_illiquid = False

        if daily_volume is not None:
            if daily_volume < self.slippage_config.min_daily_volume:
                is_illiquid = True

        # Add illiquid penalty
        if is_illiquid:
            slippage += (self.slippage_config.illiquid_slippage -
                        self.slippage_config.base_slippage)

        # Volume impact (order size vs daily volume)
        if daily_volume is not None and self.slippage_config.volume_impact_factor > 0:
            volume_ratio = order.shares / daily_volume
            volume_impact = volume_ratio * self.slippage_config.volume_impact_factor
            slippage += volume_impact

        # Volatility impact
        if daily_volatility is not None and self.slippage_config.volatility_impact_factor > 0:
            vol_impact = daily_volatility * self.slippage_config.volatility_impact_factor
            slippage += vol_impact

        return slippage

    def _calculate_commission(self, order: Order) -> float:
        """
        Calculate commission for order

        Args:
            order: Order to execute

        Returns:
            Commission in dollars
        """
        # Per-share commission
        commission = order.shares * self.costs.commission_per_share

        # ECN fees (apply when removing liquidity)
        if order.side in [OrderSide.BUY, OrderSide.SELL_SHORT]:
            # Buying/shorting typically removes liquidity
            ecn_fee = order.shares * self.costs.eec_fee_remove
        else:
            # Selling may add liquidity (get rebate) or remove (pay fee)
            ecn_fee = order.shares * self.costs.eec_fee_remove

        commission += max(0, ecn_fee)  # ECN rebates reduce cost

        # SEC and FINRA fees (selling only)
        if order.side == OrderSide.SELL:
            sec_fee = order.shares * order.expected_price * self.costs.sec_fee
            finra_fee = order.shares * self.costs.finra_taf
            commission += sec_fee + finra_fee

        return commission

    def calculate_position_cost(self, fill: Fill) -> float:
        """
        Calculate total cost of opening a position

        Args:
            fill: Executed order

        Returns:
            Total cost in dollars (for buy) or margin requirement (for short)
        """
        if fill.side == OrderSide.BUY:
            return fill.total_cost
        elif fill.side == OrderSide.SELL_SHORT:
            # For short, we need 150% margin
            return fill.expected_price * fill.shares * 1.5
        else:
            return 0.0  # SELL doesn't cost money to close

    def calculate_position_proceeds(self, fill: Fill) -> float:
        """
        Calculate proceeds from closing a position

        Args:
            fill: Executed order

        Returns:
            Total proceeds in dollars
        """
        if fill.side == OrderSide.SELL:
            return fill.total_cost
        elif fill.side == OrderSide.SELL_SHORT:
            # For closing short, return margin + P&L
            entry_value = fill.expected_price * fill.shares
            pnl = (fill.expected_price - fill.fill_price) * fill.shares
            margin_return = entry_value * 1.5
            return margin_return + pnl
        else:
            return 0.0  # BUY doesn't generate proceeds
