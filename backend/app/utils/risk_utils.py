"""
Shared Risk Management Utilities

Common functions used across risk management and order calculation services
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional


def calculate_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """
    Calculate Average True Range (ATR)

    Args:
        df: DataFrame with columns: open, high, low, close
        period: Lookback period for ATR (default: 14)

    Returns:
        ATR value or None if insufficient data
    """
    if df.empty or len(df) < period:
        return None

    df = df.copy()

    # True Range calculation
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_close'] = abs(df['low'] - df['close'].shift(1))

    df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)

    # ATR is the rolling average of True Range
    df['atr'] = df['true_range'].rolling(window=period, min_periods=1).mean()

    return float(df['atr'].iloc[-1])


def calculate_position_size(
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
        Dictionary with position_size, position_value, risk_amount, and warnings
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
            'risk_per_share': 0,
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


def calculate_risk_reward_ratio(
    entry_price: float,
    stop_loss: float,
    take_profit: float
) -> float:
    """
    Calculate risk/reward ratio

    Args:
        entry_price: Entry price
        stop_loss: Stop-loss price
        take_profit: Take-profit price

    Returns:
        Risk/reward ratio
    """
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)

    if risk == 0:
        return 0

    return reward / risk


def calculate_trailing_stop(
    df: pd.DataFrame,
    entry_price: float,
    current_price: float,
    direction: str = 'long',
    trailing_atr_multiplier: float = 1.0
) -> Dict[str, float]:
    """
    Calculate trailing stop-loss that moves with price

    Args:
        df: DataFrame with price data
        entry_price: Original entry price
        current_price: Current market price
        direction: 'long' or 'short'
        trailing_atr_multiplier: ATR multiplier for trailing stop (default: 1.0)

    Returns:
        Dictionary with trailing_stop, profit, profit_atr_multiple, and recommendation
    """
    current_atr = calculate_atr(df)

    if not current_atr:
        return {
            'trailing_stop': entry_price,
            'profit': 0,
            'profit_atr_multiple': 0,
            'recommendation': None
        }

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
        'recommendation': recommendation,
        'atr': round(current_atr, 2)
    }


def calculate_portfolio_heat(
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
