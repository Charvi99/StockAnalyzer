"""
Performance metrics calculation.

Calculates returns, risk metrics, and trading statistics.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

# Import from local modules (lazy load to avoid circular imports)
def _get_portfolio_classes():
    from core.portfolio import Portfolio, Trade
    return Portfolio, Trade

Portfolio, Trade = _get_portfolio_classes()


@dataclass
class PerformanceMetrics:
    """Container for all performance metrics"""

    # Returns
    total_return: float = 0.0
    cagr: float = 0.0
    annualized_return: float = 0.0

    # Risk
    volatility: float = 0.0
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    downside_deviation: float = 0.0

    # Risk-adjusted returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Trading statistics
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_win_loss_ratio: float = 0.0
    avg_hold_days: float = 0.0

    # Advanced
    var_95: float = 0.0  # Value at Risk at 95%
    cvar_95: float = 0.0  # Conditional VaR at 95%
    best_day: float = 0.0
    worst_day: float = 0.0

    # Monthly/Annual returns
    monthly_returns: Dict[str, float] = None
    annual_returns: Dict[str, float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'Returns': {
                'Total Return': f"{self.total_return:.2%}",
                'CAGR': f"{self.cagr:.2%}",
                'Annualized': f"{self.annualized_return:.2%}",
            },
            'Risk': {
                'Volatility': f"{self.volatility:.2%}",
                'Max Drawdown': f"{self.max_drawdown:.2%}",
                'Avg Drawdown': f"{self.avg_drawdown:.2%}",
                'Downside Deviation': f"{self.downside_deviation:.2%}",
            },
            'Risk-Adjusted': {
                'Sharpe Ratio': f"{self.sharpe_ratio:.2f}",
                'Sortino Ratio': f"{self.sortino_ratio:.2f}",
                'Calmar Ratio': f"{self.calmar_ratio:.2f}",
            },
            'Trading': {
                'Total Trades': self.total_trades,
                'Win Rate': f"{self.win_rate:.1%}",
                'Profit Factor': f"{self.profit_factor:.2f}",
                'Avg Win': f"${self.avg_win:.2f}",
                'Avg Loss': f"${self.avg_loss:.2f}",
                'Avg Win/Loss Ratio': f"{self.avg_win_loss_ratio:.2f}",
                'Avg Hold Days': f"{self.avg_hold_days:.1f}",
            },
            'Advanced': {
                'VaR 95%': f"{self.var_95:.2%}",
                'CVaR 95%': f"{self.cvar_95:.2%}",
                'Best Day': f"{self.best_day:.2%}",
                'Worst Day': f"{self.worst_day:.2%}",
            }
        }


class MetricsCalculator:
    """Calculate performance metrics from portfolio"""

    def __init__(self, risk_free_rate: float = 0.02):
        """
        Args:
            risk_free_rate: Annual risk-free rate (default 2%)
        """
        self.risk_free_rate = risk_free_rate
        self.daily_rf = (1 + risk_free_rate) ** (1/252) - 1  # Daily RF rate

    def calculate(self, portfolio: Portfolio) -> PerformanceMetrics:
        """
        Calculate all metrics from portfolio

        Args:
            portfolio: Portfolio with history and trades

        Returns:
            PerformanceMetrics object with all calculated metrics
        """
        metrics = PerformanceMetrics()

        # Get returns series
        returns_series = portfolio.get_returns_series()

        if returns_series.empty:
            return metrics

        # Calculate return metrics
        metrics.total_return = portfolio.total_return
        metrics.cagr = self._calculate_cagr(portfolio)
        metrics.annualized_return = self._calculate_annualized_return(returns_series)

        # Calculate risk metrics
        metrics.volatility = self._calculate_volatility(returns_series)
        metrics.max_drawdown = self._calculate_max_drawdown(returns_series)
        metrics.avg_drawdown = self._calculate_avg_drawdown(returns_series)
        metrics.downside_deviation = self._calculate_downside_deviation(returns_series)

        # Risk-adjusted returns
        metrics.sharpe_ratio = self._calculate_sharpe(returns_series)
        metrics.sortino_ratio = self._calculate_sortino(returns_series)
        metrics.calmar_ratio = self._calculate_calmar(metrics.cagr, metrics.max_drawdown)

        # Trading statistics
        metrics.total_trades = len(portfolio.trades)
        metrics.win_rate = self._calculate_win_rate(portfolio.trades)
        metrics.profit_factor = self._calculate_profit_factor(portfolio.trades)
        metrics.avg_win, metrics.avg_loss = self._calculate_avg_win_loss(portfolio.trades)
        if metrics.avg_loss != 0:
            metrics.avg_win_loss_ratio = abs(metrics.avg_win / metrics.avg_loss)
        metrics.avg_hold_days = self._calculate_avg_hold_days(portfolio.trades)

        # Advanced metrics
        metrics.var_95 = self._calculate_var(returns_series, 0.95)
        metrics.cvar_95 = self._calculate_cvar(returns_series, 0.95)
        metrics.best_day = returns_series.max()
        metrics.worst_day = returns_series.min()

        # Monthly/Annual returns
        metrics.monthly_returns = self._calculate_monthly_returns(returns_series)
        metrics.annual_returns = self._calculate_annual_returns(returns_series)

        return metrics

    def _calculate_cagr(self, portfolio: Portfolio) -> float:
        """Calculate Compound Annual Growth Rate"""
        history = portfolio.history
        if len(history) < 2:
            return 0.0

        start_value = history[0]['total_value']
        end_value = history[-1]['total_value']

        if start_value <= 0:
            return 0.0

        # Calculate years
        start_date = history[0]['date']
        end_date = history[-1]['date']
        years = (end_date - start_date).days / 365.25

        if years <= 0:
            return 0.0

        return (end_value / start_value) ** (1 / years) - 1

    def _calculate_annualized_return(self, returns: pd.Series) -> float:
        """Calculate annualized return from daily returns"""
        if len(returns) < 2:
            return 0.0

        # Geometric mean
        geometric_mean = (1 + returns).prod() ** (1 / len(returns))

        # Annualize (252 trading days)
        return geometric_mean ** 252 - 1

    def _calculate_volatility(self, returns: pd.Series) -> float:
        """Calculate annualized volatility"""
        if len(returns) < 2:
            return 0.0

        return returns.std() * np.sqrt(252)

    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown"""
        if len(returns) < 2:
            return 0.0

        # Calculate cumulative returns
        cumulative = (1 + returns).cumprod()

        # Calculate running maximum
        running_max = cumulative.expanding().max()

        # Calculate drawdown
        drawdown = (cumulative - running_max) / running_max

        return drawdown.min()

    def _calculate_avg_drawdown(self, returns: pd.Series) -> float:
        """Calculate average drawdown"""
        if len(returns) < 2:
            return 0.0

        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max

        # Only consider periods in drawdown
        drawdown_periods = drawdown[drawdown < 0]

        if len(drawdown_periods) == 0:
            return 0.0

        return drawdown_periods.mean()

    def _calculate_downside_deviation(self, returns: pd.Series) -> float:
        """Calculate downside deviation (only negative returns)"""
        negative_returns = returns[returns < 0]

        if len(negative_returns) == 0:
            return 0.0

        return negative_returns.std() * np.sqrt(252)

    def _calculate_sharpe(self, returns: pd.Series) -> float:
        """Calculate Sharpe Ratio"""
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - self.daily_rf

        if excess_returns.std() == 0:
            return 0.0

        return excess_returns.mean() / excess_returns.std() * np.sqrt(252)

    def _calculate_sortino(self, returns: pd.Series) -> float:
        """Calculate Sortino Ratio (downside deviation)"""
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - self.daily_rf
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0

        return excess_returns.mean() / downside_returns.std() * np.sqrt(252)

    def _calculate_calmar(self, cagr: float, max_drawdown: float) -> float:
        """Calculate Calmar Ratio (CAGR / Max Drawdown)"""
        if max_drawdown == 0:
            return 0.0

        return cagr / abs(max_drawdown)

    def _calculate_win_rate(self, trades: List[Trade]) -> float:
        """Calculate win rate"""
        if not trades:
            return 0.0

        winners = sum(1 for t in trades if t.is_profitable())
        return winners / len(trades)

    def _calculate_profit_factor(self, trades: List[Trade]) -> float:
        """Calculate profit factor (gross profit / gross loss)"""
        if not trades:
            return 0.0

        gross_profit = sum(t.pnl_dollars for t in trades if t.is_profitable())
        gross_loss = abs(sum(t.pnl_dollars for t in trades if not t.is_profitable()))

        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0

        return gross_profit / gross_loss

    def _calculate_avg_win_loss(self, trades: List[Trade]) -> tuple[float, float]:
        """Calculate average win and average loss"""
        if not trades:
            return 0.0, 0.0

        wins = [t.pnl_dollars for t in trades if t.is_profitable()]
        losses = [t.pnl_dollars for t in trades if not t.is_profitable()]

        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0

        return avg_win, avg_loss

    def _calculate_avg_hold_days(self, trades: List[Trade]) -> float:
        """Calculate average holding period"""
        if not trades:
            return 0.0

        return np.mean([t.days_held for t in trades])

    def _calculate_var(self, returns: pd.Series, level: float = 0.95) -> float:
        """Calculate Value at Risk"""
        if len(returns) < 2:
            return 0.0

        return np.percentile(returns, (1 - level) * 100)

    def _calculate_cvar(self, returns: pd.Series, level: float = 0.95) -> float:
        """Calculate Conditional VaR (Expected Shortfall)"""
        if len(returns) < 2:
            return 0.0

        var = self._calculate_var(returns, level)
        return returns[returns <= var].mean()

    def _calculate_monthly_returns(self, returns: pd.Series) -> Dict[str, float]:
        """Calculate monthly returns"""
        if len(returns) < 2:
            return {}

        if not isinstance(returns.index, pd.DatetimeIndex):
            returns.index = pd.to_datetime(returns.index)

        monthly = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)

        return {f"{idx.year}-{idx.month:02d}": val for idx, val in monthly.items()}

    def _calculate_annual_returns(self, returns: pd.Series) -> Dict[str, float]:
        """Calculate annual returns"""
        if len(returns) < 2:
            return {}

        if not isinstance(returns.index, pd.DatetimeIndex):
            returns.index = pd.to_datetime(returns.index)

        annual = returns.resample('Y').apply(lambda x: (1 + x).prod() - 1)

        return {str(idx.year): val for idx, val in annual.items()}
