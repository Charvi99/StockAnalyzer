"""
Risk Management Service - Phase 1.2
Provides ATR-based stop-loss, take-profit, and position sizing calculations
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from decimal import Decimal


class RiskManager:
    """Handles risk management calculations for trading strategies"""

    def __init__(self, df: pd.DataFrame):
        """
        Initialize with OHLC dataframe

        Args:
            df: DataFrame with columns: open, high, low, close, volume, timestamp
        """
        self.df = df.copy()
        self._calculate_atr()

    def _calculate_atr(self, period: int = 14):
        """
        Calculate Average True Range (ATR)

        Args:
            period: Lookback period for ATR (default: 14)
        """
        df = self.df

        # True Range calculation
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))

        df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)

        # ATR is the rolling average of True Range
        df['atr'] = df['true_range'].rolling(window=period, min_periods=1).mean()

    def get_current_atr(self) -> float:
        """Get the most recent ATR value"""
        return float(self.df['atr'].iloc[-1])

    def calculate_stop_loss_take_profit(
        self,
        entry_price: float,
        direction: str = 'long',
        atr_stop_multiplier: float = 2.0,
        atr_target_multiplier: float = 3.0,
        risk_reward_ratio: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate dynamic stop-loss and take-profit levels based on ATR

        Args:
            entry_price: Entry price for the trade
            direction: 'long' or 'short'
            atr_stop_multiplier: ATR multiplier for stop-loss (default: 2.0)
            atr_target_multiplier: ATR multiplier for take-profit (default: 3.0)
            risk_reward_ratio: If provided, calculates target based on R:R instead of ATR multiplier

        Returns:
            Dictionary with stop_loss, take_profit, risk_amount, reward_amount, risk_reward_ratio
        """
        current_atr = self.get_current_atr()

        if direction.lower() == 'long':
            # Long position
            stop_loss = entry_price - (current_atr * atr_stop_multiplier)

            if risk_reward_ratio:
                # Calculate target based on risk:reward ratio
                risk = entry_price - stop_loss
                target = entry_price + (risk * risk_reward_ratio)
            else:
                target = entry_price + (current_atr * atr_target_multiplier)

        else:  # short
            # Short position
            stop_loss = entry_price + (current_atr * atr_stop_multiplier)

            if risk_reward_ratio:
                risk = stop_loss - entry_price
                target = entry_price - (risk * risk_reward_ratio)
            else:
                target = entry_price - (current_atr * atr_target_multiplier)

        # Calculate risk and reward amounts
        risk_amount = abs(entry_price - stop_loss)
        reward_amount = abs(target - entry_price)
        actual_rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0

        return {
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(target, 2),
            'risk_amount': round(risk_amount, 2),
            'reward_amount': round(reward_amount, 2),
            'risk_reward_ratio': round(actual_rr_ratio, 2),
            'atr': round(current_atr, 2),
            'atr_stop_multiplier': atr_stop_multiplier,
            'atr_target_multiplier': atr_target_multiplier
        }

    def calculate_position_size(
        self,
        account_capital: float,
        risk_per_trade_percent: float,
        entry_price: float,
        stop_loss: float,
        max_position_value_percent: float = 20.0
    ) -> Dict[str, any]:
        """
        Calculate optimal position size based on risk management rules

        Args:
            account_capital: Total account capital
            risk_per_trade_percent: Percentage of capital to risk per trade (e.g., 1.0 for 1%)
            entry_price: Entry price for the trade
            stop_loss: Stop-loss price
            max_position_value_percent: Maximum percentage of capital to allocate (default: 20%)

        Returns:
            Dictionary with position_size (shares), position_value, risk_amount, and warnings
        """
        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss)

        if risk_per_share == 0:
            return {
                'position_size': 0,
                'position_value': 0,
                'risk_amount': 0,
                'capital_at_risk_percent': 0,
                'position_as_percent_of_capital': 0,
                'warnings': ['Invalid stop-loss: same as entry price']
            }

        # Calculate maximum risk amount
        max_risk_amount = account_capital * (risk_per_trade_percent / 100)

        # Calculate position size based on risk
        position_size_by_risk = int(max_risk_amount / risk_per_share)

        # Calculate maximum position value
        max_position_value = account_capital * (max_position_value_percent / 100)
        max_position_size_by_value = int(max_position_value / entry_price)

        # Use the smaller of the two position sizes
        position_size = min(position_size_by_risk, max_position_size_by_value)

        # Calculate actual position value and risk
        position_value = position_size * entry_price
        actual_risk_amount = position_size * risk_per_share
        actual_risk_percent = (actual_risk_amount / account_capital) * 100
        position_percent = (position_value / account_capital) * 100

        # Generate warnings
        warnings = []
        if position_size == 0:
            warnings.append('Position size is 0 - risk parameters too conservative')
        elif position_size < 10:
            warnings.append('Position size very small - consider larger capital or wider stops')
        if position_value > max_position_value:
            warnings.append(f'Position capped at {max_position_value_percent}% of capital')
        if actual_risk_percent > risk_per_trade_percent * 1.1:  # 10% tolerance
            warnings.append(f'Actual risk ({actual_risk_percent:.2f}%) exceeds target ({risk_per_trade_percent}%)')

        return {
            'position_size': position_size,
            'position_value': round(position_value, 2),
            'risk_amount': round(actual_risk_amount, 2),
            'capital_at_risk_percent': round(actual_risk_percent, 2),
            'position_as_percent_of_capital': round(position_percent, 2),
            'risk_per_share': round(risk_per_share, 2),
            'warnings': warnings if warnings else None
        }

    def calculate_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        direction: str = 'long',
        trailing_atr_multiplier: float = 1.0
    ) -> Dict[str, float]:
        """
        Calculate trailing stop-loss that moves with price

        Args:
            entry_price: Original entry price
            current_price: Current market price
            direction: 'long' or 'short'
            trailing_atr_multiplier: ATR multiplier for trailing stop (default: 1.0)

        Returns:
            Dictionary with trailing_stop, profit, and recommendation
        """
        current_atr = self.get_current_atr()
        profit = current_price - entry_price if direction.lower() == 'long' else entry_price - current_price
        profit_atr_multiple = profit / current_atr if current_atr > 0 else 0

        if direction.lower() == 'long':
            # For long positions, trail below current price
            trailing_stop = current_price - (current_atr * trailing_atr_multiplier)

            # Don't let trailing stop go below entry (protect capital)
            trailing_stop = max(trailing_stop, entry_price)

            recommendation = None
            if profit_atr_multiple >= 1.5:
                recommendation = 'move_stop_to_breakeven'
            if profit_atr_multiple >= 3.0:
                recommendation = 'consider_partial_profit'

        else:  # short
            # For short positions, trail above current price
            trailing_stop = current_price + (current_atr * trailing_atr_multiplier)

            # Don't let trailing stop go above entry
            trailing_stop = min(trailing_stop, entry_price)

            recommendation = None
            if profit_atr_multiple >= 1.5:
                recommendation = 'move_stop_to_breakeven'
            if profit_atr_multiple >= 3.0:
                recommendation = 'consider_partial_profit'

        return {
            'trailing_stop': round(trailing_stop, 2),
            'profit': round(profit, 2),
            'profit_atr_multiple': round(profit_atr_multiple, 2),
            'recommendation': recommendation
        }

    def calculate_portfolio_heat(
        self,
        open_positions: list[Dict],
        account_capital: float,
        max_portfolio_heat_percent: float = 6.0
    ) -> Dict[str, any]:
        """
        Calculate total portfolio risk (heat) across all open positions

        Args:
            open_positions: List of dicts with 'entry_price', 'stop_loss', 'position_size'
            account_capital: Total account capital
            max_portfolio_heat_percent: Maximum allowed portfolio heat (default: 6%)

        Returns:
            Dictionary with total_heat, heat_percent, positions_at_risk, and can_add_position
        """
        total_risk = 0

        for position in open_positions:
            risk_per_share = abs(position['entry_price'] - position['stop_loss'])
            position_risk = risk_per_share * position['position_size']
            total_risk += position_risk

        heat_percent = (total_risk / account_capital) * 100
        can_add_position = heat_percent < max_portfolio_heat_percent

        return {
            'total_risk_amount': round(total_risk, 2),
            'portfolio_heat_percent': round(heat_percent, 2),
            'max_allowed_heat_percent': max_portfolio_heat_percent,
            'positions_at_risk': len(open_positions),
            'can_add_position': can_add_position,
            'remaining_risk_capacity': round(account_capital * (max_portfolio_heat_percent / 100) - total_risk, 2) if can_add_position else 0
        }


def calculate_risk_metrics_for_pattern(
    df: pd.DataFrame,
    pattern_signal: str,
    current_price: float,
    account_capital: float = 10000,
    risk_per_trade_percent: float = 1.0
) -> Dict[str, any]:
    """
    Convenience function to calculate all risk metrics for a detected pattern

    Args:
        df: OHLC dataframe
        pattern_signal: 'bullish' or 'bearish'
        current_price: Current/entry price
        account_capital: Trading capital
        risk_per_trade_percent: Risk percentage per trade

    Returns:
        Complete risk management package with stops, targets, and position size
    """
    risk_manager = RiskManager(df)

    direction = 'long' if pattern_signal == 'bullish' else 'short'

    # Calculate stop-loss and take-profit
    stops_targets = risk_manager.calculate_stop_loss_take_profit(
        entry_price=current_price,
        direction=direction,
        atr_stop_multiplier=2.0,
        atr_target_multiplier=3.0
    )

    # Calculate position size
    position_sizing = risk_manager.calculate_position_size(
        account_capital=account_capital,
        risk_per_trade_percent=risk_per_trade_percent,
        entry_price=current_price,
        stop_loss=stops_targets['stop_loss']
    )

    return {
        **stops_targets,
        **position_sizing,
        'direction': direction,
        'entry_price': current_price
    }
