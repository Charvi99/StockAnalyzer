"""
Strategy Manager

This module manages the registration and execution of trading strategies.
"""

from typing import Dict, List, Optional, Any, Type
import pandas as pd
from sqlalchemy.orm import Session

from .base_strategy import BaseStrategy
from .example_strategies import (
    RSIOversoldOverboughtStrategy,
    MACDCrossoverStrategy,
    MovingAverageCrossoverStrategy,
    BollingerBandsMeanReversionStrategy,
    TrendFollowingStrategy
)
from .technical_indicators import TechnicalIndicators


class StrategyManager:
    """
    Manages trading strategies and their execution.

    The StrategyManager handles:
    - Strategy registration
    - Strategy execution
    - Parameter management
    - Backtesting coordination
    """

    def __init__(self):
        """Initialize the strategy manager with built-in strategies."""
        self._strategies: Dict[str, BaseStrategy] = {}
        self._register_builtin_strategies()

    def _register_builtin_strategies(self):
        """Register all built-in example strategies."""
        builtin_strategies = [
            RSIOversoldOverboughtStrategy(),
            MACDCrossoverStrategy(),
            MovingAverageCrossoverStrategy(),
            BollingerBandsMeanReversionStrategy(),
            TrendFollowingStrategy()
        ]

        for strategy in builtin_strategies:
            self.register_strategy(strategy)

    def register_strategy(self, strategy: BaseStrategy) -> None:
        """
        Register a new strategy.

        Args:
            strategy: Instance of a strategy class that inherits from BaseStrategy
        """
        self._strategies[strategy.name] = strategy
        print(f"[StrategyManager] Registered strategy: {strategy.name}")

    def unregister_strategy(self, strategy_name: str) -> bool:
        """
        Unregister a strategy.

        Args:
            strategy_name: Name of the strategy to unregister

        Returns:
            True if strategy was unregistered, False if not found
        """
        if strategy_name in self._strategies:
            del self._strategies[strategy_name]
            print(f"[StrategyManager] Unregistered strategy: {strategy_name}")
            return True
        return False

    def get_strategy(self, strategy_name: str) -> Optional[BaseStrategy]:
        """
        Get a registered strategy by name.

        Args:
            strategy_name: Name of the strategy

        Returns:
            Strategy instance or None if not found
        """
        return self._strategies.get(strategy_name)

    def list_strategies(self) -> List[Dict[str, Any]]:
        """
        Get a list of all registered strategies with their metadata.

        Returns:
            List of dictionaries containing strategy information
        """
        strategies_list = []
        for name, strategy in self._strategies.items():
            strategies_list.append({
                'name': strategy.name,
                'description': strategy.description,
                'parameters': strategy.get_default_parameters() or strategy.parameters,
                'min_data_points': strategy.get_min_data_points()
            })
        return strategies_list

    async def execute_strategy(
        self,
        strategy_name: str,
        stock_id: int,
        db: Session,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a strategy on a stock.

        Args:
            strategy_name: Name of the strategy to execute
            stock_id: ID of the stock to analyze
            db: Database session
            parameters: Optional strategy parameters to override defaults

        Returns:
            Dictionary containing:
                - signal: 'BUY', 'SELL', or 'HOLD'
                - confidence: Float 0.0-1.0
                - details: Additional information from the strategy
                - strategy_name: Name of the executed strategy
        """
        # Get strategy
        strategy = self.get_strategy(strategy_name)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_name}' not found")

        # Update parameters if provided
        if parameters:
            strategy.set_parameters(parameters)

        # Get price data
        from ..models.stock import Stock, StockPrice
        stock = db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            raise ValueError(f"Stock with id {stock_id} not found")

        # Get last N days of price data
        min_days = strategy.get_min_data_points() + 50  # Add buffer
        prices_query = db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id
        ).order_by(StockPrice.timestamp.desc()).limit(min_days)

        prices_data = []
        for price in prices_query:
            prices_data.append({
                'timestamp': price.timestamp,
                'open': float(price.open),
                'high': float(price.high),
                'low': float(price.low),
                'close': float(price.close),
                'volume': float(price.volume)
            })

        # Reverse to chronological order
        prices_data.reverse()

        if not prices_data:
            raise ValueError(f"No price data available for stock {stock.symbol}")

        # Convert to DataFrame
        prices_df = pd.DataFrame(prices_data)

        # Calculate technical indicators
        prices_df = TechnicalIndicators.calculate_all_indicators(
            prices_df,
            rsi_period=parameters.get('rsi_period', 14) if parameters else 14,
            macd_fast=parameters.get('macd_fast', 12) if parameters else 12,
            macd_slow=parameters.get('macd_slow', 26) if parameters else 26,
            macd_signal=parameters.get('macd_signal', 9) if parameters else 9,
            bb_window=parameters.get('bb_window', 20) if parameters else 20,
            bb_std=parameters.get('bb_std', 2.0) if parameters else 2.0
        )

        # Get the recommendation with indicators
        indicators = TechnicalIndicators.generate_recommendation(prices_df)['indicators']

        # Execute strategy
        signal, confidence, details = strategy.analyze(prices_df, indicators)

        return {
            'signal': signal,
            'confidence': round(confidence, 3),
            'details': details,
            'strategy_name': strategy_name,
            'stock_symbol': stock.symbol,
            'stock_id': stock_id,
            'current_price': float(prices_df.iloc[-1]['close']),
            'timestamp': prices_df.iloc[-1]['timestamp'].isoformat() if hasattr(prices_df.iloc[-1]['timestamp'], 'isoformat') else str(prices_df.iloc[-1]['timestamp'])
        }

    async def backtest_strategy(
        self,
        strategy_name: str,
        stock_id: int,
        db: Session,
        initial_balance: float = 10000.0,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run a backtest for a strategy on a stock.

        Args:
            strategy_name: Name of the strategy to backtest
            stock_id: ID of the stock
            db: Database session
            initial_balance: Starting balance for backtest
            parameters: Optional strategy parameters

        Returns:
            Dictionary with backtest results
        """
        # Get strategy
        strategy = self.get_strategy(strategy_name)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_name}' not found")

        # Update parameters if provided
        if parameters:
            strategy.set_parameters(parameters)

        # Get price data
        from ..models.stock import Stock, StockPrice
        stock = db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            raise ValueError(f"Stock with id {stock_id} not found")

        # Get historical price data (more for backtest)
        prices_query = db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id
        ).order_by(StockPrice.timestamp.desc()).limit(500)  # Last ~2 years

        prices_data = []
        for price in prices_query:
            prices_data.append({
                'timestamp': price.timestamp,
                'open': float(price.open),
                'high': float(price.high),
                'low': float(price.low),
                'close': float(price.close),
                'volume': float(price.volume)
            })

        prices_data.reverse()

        if not prices_data:
            raise ValueError(f"No price data available for stock {stock.symbol}")

        prices_df = pd.DataFrame(prices_data)

        # Calculate indicators
        prices_df = TechnicalIndicators.calculate_all_indicators(
            prices_df,
            rsi_period=parameters.get('rsi_period', 14) if parameters else 14,
            macd_fast=parameters.get('macd_fast', 12) if parameters else 12,
            macd_slow=parameters.get('macd_slow', 26) if parameters else 26,
            macd_signal=parameters.get('macd_signal', 9) if parameters else 9,
            bb_window=parameters.get('bb_window', 20) if parameters else 20,
            bb_std=parameters.get('bb_std', 2.0) if parameters else 2.0
        )

        # Get the recommendation with indicators
        indicators = TechnicalIndicators.generate_recommendation(prices_df)['indicators']

        # Run backtest
        backtest_results = strategy.backtest(prices_df, indicators, initial_balance)

        # Add metadata
        backtest_results['strategy_name'] = strategy_name
        backtest_results['stock_symbol'] = stock.symbol
        backtest_results['stock_id'] = stock_id
        backtest_results['initial_balance'] = initial_balance
        backtest_results['parameters'] = strategy.get_parameters()

        return backtest_results


# Global strategy manager instance
strategy_manager = StrategyManager()
