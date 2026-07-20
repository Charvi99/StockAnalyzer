"""
Risk Management Service - Phase 1.2
Provides ATR-based stop-loss, take-profit, and position sizing calculations
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from decimal import Decimal

from app.utils.risk_utils import (
    calculate_position_size as _calc_position_size,
    calculate_trailing_stop as _calc_trailing_stop,
    calculate_portfolio_heat as _calc_portfolio_heat,
    atr_series,
)


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
        Fill self.df['atr'] using the shared risk_utils ATR formula (min_periods=1,
        so a partial ATR exists even with < period rows). Single source of truth:
        app.utils.risk_utils.atr_series. (Stage 2 collapse — BU5 R7.)
        """
        self.df['atr'] = atr_series(self.df, period)

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
        # Delegate to the single source of truth (BU5 R7 collapse). risk_utils owns
        # the math + the div-zero guards; this keeps RiskManager's stateful df surface.
        return _calc_position_size(
            account_capital=account_capital,
            risk_per_trade_percent=risk_per_trade_percent,
            entry_price=entry_price,
            stop_loss=stop_loss,
            max_position_value_percent=max_position_value_percent,
        )

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
        # Delegate to risk_utils, passing the precomputed ATR (no recompute).
        # (BU5 R7 collapse — return shape now matches risk_utils, incl. 'atr'.)
        return _calc_trailing_stop(
            entry_price=entry_price,
            current_price=current_price,
            direction=direction,
            trailing_atr_multiplier=trailing_atr_multiplier,
            current_atr=self.get_current_atr(),
        )

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
        # Delegate to the single source of truth (BU5 R7 collapse).
        return _calc_portfolio_heat(
            open_positions=open_positions,
            account_capital=account_capital,
            max_portfolio_heat_percent=max_portfolio_heat_percent,
        )


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
