"""
Base Strategy Class for Custom Trading Strategies

This module provides a base class for creating custom trading strategies.
Extend this class and implement the required methods to create your own strategy.

Example:
    class MyStrategy(BaseStrategy):
        def analyze(self, data, indicators):
            # Your strategy logic here
            return signal, confidence, details
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import pandas as pd


class BaseStrategy(ABC):
    """
    Base class for all trading strategies.

    All custom strategies should inherit from this class and implement
    the required abstract methods.

    Attributes:
        name: Strategy name
        description: Strategy description
        parameters: Strategy parameters that can be configured
    """

    def __init__(self, name: str, description: str = "", parameters: Optional[Dict[str, Any]] = None):
        """
        Initialize the strategy.

        Args:
            name: Name of the strategy
            description: Description of what the strategy does
            parameters: Dictionary of strategy parameters (optional)
        """
        self.name = name
        self.description = description
        self.parameters = parameters or {}

    @abstractmethod
    def analyze(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any]
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        Analyze the stock data and generate a trading signal.

        This is the main method that implements your strategy logic.

        Args:
            prices: DataFrame with columns: timestamp, open, high, low, close, volume
            indicators: Dictionary containing pre-calculated technical indicators
                Example: {
                    'rsi': {'value': 45.2, 'signal': 'BUY'},
                    'macd': {'macd': 0.5, 'signal_line': 0.3, 'histogram': 0.2},
                    'moving_averages': {'ma_short': 150.2, 'ma_long': 145.8}
                }

        Returns:
            Tuple of (signal, confidence, details):
                - signal: 'BUY', 'SELL', or 'HOLD'
                - confidence: Float between 0.0 and 1.0
                - details: Dictionary with additional information about the signal
                  Example: {
                      'entry_price': 150.5,
                      'stop_loss': 145.0,
                      'take_profit': 160.0,
                      'reason': 'RSI oversold + MACD bullish crossover'
                  }
        """
        pass

    def validate_data(self, prices: pd.DataFrame) -> bool:
        """
        Validate that the price data has the required columns and sufficient data.

        Args:
            prices: DataFrame with price data

        Returns:
            True if data is valid, False otherwise
        """
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

        if prices is None or prices.empty:
            return False

        if not all(col in prices.columns for col in required_columns):
            return False

        if len(prices) < self.get_min_data_points():
            return False

        return True

    def get_min_data_points(self) -> int:
        """
        Get the minimum number of data points required for this strategy.

        Override this method if your strategy needs a specific amount of historical data.

        Returns:
            Minimum number of price bars required
        """
        return 20  # Default: 20 bars

    def get_parameters(self) -> Dict[str, Any]:
        """
        Get the current strategy parameters.

        Returns:
            Dictionary of parameter names and values
        """
        return self.parameters

    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """
        Update strategy parameters.

        Args:
            parameters: Dictionary of parameter names and new values
        """
        self.parameters.update(parameters)

    def get_default_parameters(self) -> Dict[str, Any]:
        """
        Get the default parameters for this strategy.

        Override this method to define default parameters for your strategy.

        Returns:
            Dictionary of default parameter names and values
        """
        return {}

    def calculate_position_size(
        self,
        account_balance: float,
        risk_per_trade: float,
        entry_price: float,
        stop_loss: float
    ) -> int:
        """
        Calculate position size based on risk management rules.

        Args:
            account_balance: Total account balance
            risk_per_trade: Percentage of account to risk (e.g., 0.02 for 2%)
            entry_price: Planned entry price
            stop_loss: Stop loss price

        Returns:
            Number of shares to buy/sell
        """
        if stop_loss == 0 or entry_price == stop_loss:
            return 0

        risk_amount = account_balance * risk_per_trade
        risk_per_share = abs(entry_price - stop_loss)
        position_size = int(risk_amount / risk_per_share)

        return max(0, position_size)

    def backtest(
        self,
        prices: pd.DataFrame,
        indicators: Dict[str, Any],
        initial_balance: float = 10000.0
    ) -> Dict[str, Any]:
        """
        Run a simple backtest of the strategy.

        Args:
            prices: DataFrame with historical price data
            indicators: Pre-calculated technical indicators
            initial_balance: Starting account balance

        Returns:
            Dictionary with backtest results:
                - total_return: Percentage return
                - total_trades: Number of trades
                - winning_trades: Number of winning trades
                - losing_trades: Number of losing trades
                - win_rate: Percentage of winning trades
                - max_drawdown: Maximum drawdown percentage
        """
        balance = initial_balance
        position = 0
        trades = []
        equity_curve = [initial_balance]

        for i in range(len(prices)):
            current_prices = prices.iloc[:i+1]
            current_price = prices.iloc[i]['close']

            if len(current_prices) < self.get_min_data_points():
                equity_curve.append(balance)
                continue

            signal, confidence, details = self.analyze(current_prices, indicators)

            # Simple backtest logic
            if signal == 'BUY' and position == 0:
                shares = int(balance / current_price)
                if shares > 0:
                    position = shares
                    entry_price = current_price
                    balance -= shares * current_price
                    trades.append({
                        'type': 'BUY',
                        'price': current_price,
                        'shares': shares,
                        'timestamp': prices.iloc[i]['timestamp']
                    })

            elif signal == 'SELL' and position > 0:
                balance += position * current_price
                profit = (current_price - entry_price) * position
                trades.append({
                    'type': 'SELL',
                    'price': current_price,
                    'shares': position,
                    'profit': profit,
                    'timestamp': prices.iloc[i]['timestamp']
                })
                position = 0

            equity = balance + (position * current_price)
            equity_curve.append(equity)

        # Calculate statistics
        total_return = ((equity_curve[-1] - initial_balance) / initial_balance) * 100
        winning_trades = sum(1 for t in trades if t.get('profit', 0) > 0)
        losing_trades = sum(1 for t in trades if t.get('profit', 0) < 0)
        total_trades = len([t for t in trades if t['type'] == 'SELL'])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Calculate max drawdown
        peak = equity_curve[0]
        max_drawdown = 0
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = ((peak - value) / peak) * 100
            max_drawdown = max(max_drawdown, drawdown)

        return {
            'total_return': round(total_return, 2),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'max_drawdown': round(max_drawdown, 2),
            'final_balance': round(equity_curve[-1], 2),
            'trades': trades,
            'equity_curve': equity_curve
        }

    def __str__(self) -> str:
        """String representation of the strategy."""
        return f"{self.name}: {self.description}"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"<Strategy: {self.name}>"
