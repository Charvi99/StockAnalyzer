"""
Main backtesting engine.

Orchestrates the backtesting process: data loading, signal generation,
order execution, and performance tracking.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

# Import from local modules
from .portfolio import Portfolio
from .executor import OrderExecutor

# Import from other modules (will be resolved at runtime)
from config import BacktestConfig
from strategies.base import BaseStrategy
from analysis.metrics import MetricsCalculator


@dataclass
class BacktestResult:
    """Results from a backtest run"""
    strategy_name: str
    portfolio: Portfolio
    metrics: dict
    trades_df: pd.DataFrame
    history_df: pd.DataFrame

    def get_summary(self) -> str:
        """Get text summary of results"""
        summary = f"""
{'=' * 70}
{self.strategy_name} - Backtest Results
{'=' * 70}

PERFORMANCE:
  Total Return: {self.metrics.get('total_return', 'N/A')}
  CAGR: {self.metrics.get('cagr', 'N/A')}
  Volatility: {self.metrics.get('volatility', 'N/A')}
  Max Drawdown: {self.metrics.get('max_drawdown', 'N/A')}

RISK-ADJUSTED:
  Sharpe Ratio: {self.metrics.get('sharpe_ratio', 'N/A')}
  Sortino Ratio: {self.metrics.get('sortino_ratio', 'N/A')}
  Calmar Ratio: {self.metrics.get('calmar_ratio', 'N/A')}

TRADING:
  Total Trades: {self.metrics.get('total_trades', 'N/A')}
  Win Rate: {self.metrics.get('win_rate', 'N/A')}
  Profit Factor: {self.metrics.get('profit_factor', 'N/A')}
  Avg Win / Loss: {self.metrics.get('avg_win_loss_ratio', 'N/A')}

"""
        return summary


class Backtester:
    """
    Main backtesting engine

    Runs backtests by:
    1. Loading data for specified period
    2. Initializing portfolio and strategy
    3. Iterating through each day
    4. Generating and executing signals
    5. Tracking performance
    6. Calculating metrics
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.calculator = MetricsCalculator()

    def run(self, strategy: BaseStrategy,
            data: Dict[str, pd.DataFrame]) -> BacktestResult:
        """
        Run backtest with given strategy

        Args:
            strategy: Strategy instance to test
            data: Dictionary of symbol -> DataFrame with OHLCV

        Returns:
            BacktestResult with all results
        """
        # Parse dates
        start_date = datetime.strptime(
            self.config.period.test_start, '%Y-%m-%d'
        ).date()
        end_date = datetime.strptime(
            self.config.period.test_end, '%Y-%m-%d'
        ).date()

        # Initialize portfolio
        portfolio = Portfolio(cash=self.config.initial_cash)

        # Get all trading days
        all_dates = self._get_trading_days(data, start_date, end_date)

        if not all_dates:
            raise ValueError(f"No trading days found between {start_date} and {end_date}")

        # Run backtest day by day
        print(f"Processing {len(all_dates)} trading days...")

        for i, current_date in enumerate(all_dates):
            if i == 0 or i == len(all_dates) - 1:
                print(f"  Day {i+1}/{len(all_dates)}: {current_date}")
            # Get current prices
            prices = self._get_current_prices(data, current_date)

            # Check for exits first
            strategy.check_exits(portfolio, prices, current_date)

            # Generate signals
            signals = strategy.generate_signals(current_date, data)
            if i == 0 and len(signals) > 0:
                print(f"    Day 1: Generated {len(signals)} signals")

            # Execute signals
            strategy.execute_signals(signals, portfolio, prices, current_date)

            # Update portfolio history
            portfolio.update_prices(prices, current_date)

        # Debug info
        print(f"Portfolio ended with ${portfolio.get_value(prices):,.2f}")
        print(f"Open positions: {portfolio.get_open_positions_count()}")
        print(f"Total trades: {len(portfolio.trades)}")

        # Calculate metrics
        metrics_obj = self.calculator.calculate(portfolio)
        metrics = metrics_obj.to_dict()

        # Create result
        result = BacktestResult(
            strategy_name=strategy.__class__.__name__,
            portfolio=portfolio,
            metrics=metrics,
            trades_df=portfolio.get_trades_df(),
            history_df=portfolio.get_history_df()
        )

        return result

    def compare_strategies(self,
                         strategies: List[BaseStrategy],
                         data: Dict[str, pd.DataFrame],
                         names: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Compare multiple strategies

        Args:
            strategies: List of strategy instances
            data: Price data
            names: Optional names for strategies

        Returns:
            DataFrame with comparison metrics
        """
        if names is None:
            names = [s.__class__.__name__ for s in strategies]

        results = []
        for strategy, name in zip(strategies, names):
            result = self.run(strategy, data)

            # Flatten metrics
            flat_metrics = {
                'Strategy': name,
                'Total Return': result.metrics.get('total_return', 'N/A'),
                'CAGR': result.metrics.get('cagr', 'N/A'),
                'Volatility': result.metrics.get('volatility', 'N/A'),
                'Max Drawdown': result.metrics.get('max_drawdown', 'N/A'),
                'Sharpe Ratio': result.metrics.get('sharpe_ratio', 'N/A'),
                'Sortino Ratio': result.metrics.get('sortino_ratio', 'N/A'),
                'Calmar Ratio': result.metrics.get('calmar_ratio', 'N/A'),
                'Total Trades': result.metrics.get('total_trades', 'N/A'),
                'Win Rate': result.metrics.get('win_rate', 'N/A'),
                'Profit Factor': result.metrics.get('profit_factor', 'N/A'),
            }

            results.append(flat_metrics)

        return pd.DataFrame(results)

    def _get_trading_days(self, data: Dict[str, pd.DataFrame],
                         start_date: date,
                         end_date: date) -> List[date]:
        """
        Get all unique trading days in date range

        Args:
            data: Symbol -> DataFrame mapping
            start_date: Start date
            end_date: End date

        Returns:
            Sorted list of unique dates
        """
        dates = set()

        for df in data.values():
            # Ensure index is datetime
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # Get dates in range
            mask = (df.index >= pd.Timestamp(start_date)) & \
                   (df.index <= pd.Timestamp(end_date))
            dates_in_range = df.index[mask]

            # Convert to date objects
            for d in dates_in_range:
                if hasattr(d, 'date'):
                    dates.add(d.date())
                else:
                    dates.add(d)

        return sorted(list(dates))

    def _get_current_prices(self, data: Dict[str, pd.DataFrame],
                           current_date: date) -> Dict[str, float]:
        """
        Get current prices for all stocks

        Args:
            data: Symbol -> DataFrame mapping
            current_date: Current date

        Returns:
            Dictionary of symbol -> close price
        """
        prices = {}

        for symbol, df in data.items():
            # Ensure index is datetime
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # Get price for current date
            # First try exact match
            current_ts = pd.Timestamp(current_date)
            if current_ts in df.index:
                prices[symbol] = df.loc[current_ts, 'close']
            else:
                # Try to find nearest previous date
                mask = df.index <= current_ts
                if mask.any():
                    nearest_date = df.index[mask].max()
                    prices[symbol] = df.loc[nearest_date, 'close']

        return prices

    def save_results(self, result: BacktestResult, output_dir: Path):
        """
        Save backtest results to files

        Args:
            result: Backtest result
            output_dir: Directory to save results
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save trades
        if not result.trades_df.empty:
            result.trades_df.to_csv(
                output_dir / 'trades.csv',
                index=False
            )

        # Save history
        if not result.history_df.empty:
            result.history_df.to_csv(
                output_dir / 'portfolio_history.csv',
                index=False
            )

        # Save summary
        with open(output_dir / 'summary.txt', 'w') as f:
            f.write(result.get_summary())

        # Save metrics as JSON
        import json
        with open(output_dir / 'metrics.json', 'w') as f:
            json.dump(result.metrics, f, indent=2)

        # Save config
        self.config.save(output_dir / 'config.json')

        print(f"Results saved to: {output_dir}")
