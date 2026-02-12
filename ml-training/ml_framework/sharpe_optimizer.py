"""
Sharpe Ratio Optimization for ML Models

Optimizes model predictions directly for Sharpe ratio instead of AUC/accuracy.
"""
import numpy as np
import pandas as pd
import optuna
from typing import Dict, Any, Optional, Tuple, Callable, TYPE_CHECKING
import logging
from pathlib import Path

# For type hints
if TYPE_CHECKING:
    import torch
else:
    import torch

logger = logging.getLogger(__name__)


class SharpeRatioOptimizer:
    """
    Optimize model predictions/trading parameters for maximum Sharpe ratio.

    Supports:
    1. Threshold optimization (find best confidence thresholds)
    2. Position sizing optimization
    3. Full hyperparameter optimization with Sharpe objective
    """

    def __init__(self, calculate_returns_func: Callable):
        """
        Initialize optimizer.

        Args:
            calculate_returns_func: Function that takes predictions and returns
                                  a DataFrame with 'returns' column
        """
        self.calculate_returns = calculate_returns_func
        self.best_params = {}

    @staticmethod
    def calculate_sharpe_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate annualized Sharpe ratio.

        Args:
            returns: Series of daily returns
            risk_free_rate: Annual risk-free rate (default 0)
            periods_per_year: Trading periods per year (default 252)

        Returns:
            Annualized Sharpe ratio
        """
        if len(returns) == 0 or returns.std() == 0:
            return 0.0

        excess_returns = returns - risk_free_rate / periods_per_year
        sharpe = excess_returns.mean() / returns.std() * np.sqrt(periods_per_year)

        return sharpe

    @staticmethod
    def calculate_sortino_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Sortino ratio (downside risk only).

        Args:
            returns: Series of daily returns
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year

        Returns:
            Annualized Sortino ratio
        """
        if len(returns) == 0:
            return 0.0

        excess_returns = returns - risk_free_rate / periods_per_year

        # Only consider downside deviation
        downside_returns = excess_returns[excess_returns < 0]
        if len(downside_returns) == 0:
            return np.inf if excess_returns.mean() > 0 else 0.0

        downside_deviation = downside_returns.std()
        if downside_deviation == 0:
            return 0.0

        sortino = excess_returns.mean() / downside_deviation * np.sqrt(periods_per_year)
        return sortino

    def optimize_thresholds(
        self,
        predictions: np.ndarray,
        prediction_probs: np.ndarray,
        prices: pd.DataFrame,
        n_trials: int = 100,
        search_space: Optional[Dict[str, Tuple[float, float]]] = None
    ) -> Dict[str, Any]:
        """
        Optimize confidence thresholds for maximum Sharpe ratio.

        Args:
            predictions: Model predictions (class labels)
            prediction_probs: Prediction probabilities [n_samples, n_classes]
            prices: DataFrame with price data (OHLCV)
            n_trials: Number of optimization trials
            search_space: Custom search space for thresholds

        Returns:
            Dictionary with best thresholds and metrics
        """
        logger.info("Optimizing thresholds for Sharpe ratio...")

        # Default search space
        if search_space is None:
            search_space = {
                'buy_confidence': (0.4, 0.7),
                'sell_confidence': (0.4, 0.7),
                'hold_confidence': (0.3, 0.6),
            }

        def objective(trial: optuna.Trial) -> float:
            # Suggest thresholds
            buy_conf = trial.suggest_float('buy_confidence', *search_space['buy_confidence'])
            sell_conf = trial.suggest_float('sell_confidence', *search_space['sell_confidence'])
            hold_conf = trial.suggest_float('hold_confidence', *search_space['hold_confidence'])

            # Generate signals based on thresholds
            signals = self._generate_signals_from_probs(
                prediction_probs,
                buy_conf,
                sell_conf,
                hold_conf
            )

            # Calculate returns
            returns_df = self.calculate_returns(signals, prices)

            if len(returns_df) == 0 or returns_df['returns'].std() == 0:
                return -1.0  # Penalize invalid configurations

            # Calculate Sharpe
            sharpe = self.calculate_sharpe_ratio(returns_df['returns'])

            return sharpe

        # Run optimization
        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        # Extract best parameters
        best_params = study.best_params
        best_sharpe = study.best_value

        logger.info(f"✅ Best Sharpe: {best_sharpe:.4f}")
        logger.info(f"   Best thresholds: {best_params}")

        # Calculate full metrics with best params
        signals = self._generate_signals_from_probs(
            prediction_probs,
            best_params['buy_confidence'],
            best_params['sell_confidence'],
            best_params['hold_confidence']
        )
        returns_df = self.calculate_returns(signals, prices)

        result = {
            'best_params': best_params,
            'best_sharpe': best_sharpe,
            'best_sortino': self.calculate_sortino_ratio(returns_df['returns']),
            'total_return': returns_df['returns'].sum(),
            'win_rate': (returns_df['returns'] > 0).mean(),
            'n_trades': (signals != 0).sum(),
            'study': study
        }

        return result

    def _generate_signals_from_probs(
        self,
        probs: np.ndarray,
        buy_conf: float,
        sell_conf: float,
        hold_conf: float
    ) -> np.ndarray:
        """
        Generate trading signals from prediction probabilities.

        Args:
            probs: Prediction probabilities [n_samples, n_classes]
            buy_conf: Minimum confidence for BUY signal
            sell_conf: Minimum confidence for SELL signal
            hold_conf: Minimum confidence for HOLD signal

        Returns:
            Array of signals: -1 (SELL), 0 (HOLD), 1 (BUY)
        """
        n_samples = probs.shape[0]
        signals = np.zeros(n_samples, dtype=int)

        # For 3-class: probs[:, 0] = SELL, probs[:, 1] = HOLD, probs[:, 2] = BUY
        if probs.shape[1] == 3:
            for i in range(n_samples):
                sell_prob, hold_prob, buy_prob = probs[i]

                if buy_prob >= buy_conf and buy_prob > sell_prob and buy_prob > hold_prob:
                    signals[i] = 1  # BUY
                elif sell_prob >= sell_conf and sell_prob > buy_prob and sell_prob > hold_prob:
                    signals[i] = -1  # SELL
                elif hold_prob >= hold_conf:
                    signals[i] = 0  # HOLD
                else:
                    # No strong signal - hold
                    signals[i] = 0

        # For binary: probs[:, 0] = SELL, probs[:, 1] = BUY
        elif probs.shape[1] == 2:
            for i in range(n_samples):
                sell_prob, buy_prob = probs[i]

                if buy_prob >= buy_conf:
                    signals[i] = 1  # BUY
                elif sell_prob >= sell_conf:
                    signals[i] = -1  # SELL
                else:
                    signals[i] = 0  # HOLD

        return signals

    def optimize_with_optuna(
        self,
        model_train_func: Callable,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        prices_val: pd.DataFrame,
        n_trials: int = 50,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Full hyperparameter optimization with Sharpe ratio as objective.

        This replaces AUC/accuracy optimization with direct Sharpe optimization.

        Args:
            model_train_func: Function that trains model with given params
            X_train, y_train: Training data
            X_val, y_val: Validation data
            prices_val: Price data for backtesting
            n_trials: Number of Optuna trials
            timeout: Optional timeout in seconds

        Returns:
            Dictionary with best parameters and metrics
        """
        logger.info(f"Starting Sharpe-based hyperparameter optimization ({n_trials} trials)...")

        def objective(trial: optuna.Trial) -> float:
            # Suggest hyperparameters (model-specific, defined in train function)
            params = model_train_func.suggest_hyperparameters(trial)

            # Train model
            model = model_train_func.train_with_params(X_train, y_train, params)

            # Get predictions
            pred_probs = model.predict_proba(X_val)

            # Generate signals (use default thresholds)
            signals = self._generate_signals_from_probs(
                pred_probs,
                buy_conf=0.5,
                sell_conf=0.5,
                hold_conf=0.4
            )

            # Calculate returns and Sharpe
            returns_df = self.calculate_returns(signals, prices_val)

            if len(returns_df) == 0 or returns_df['returns'].std() == 0:
                return -1.0

            sharpe = self.calculate_sharpe_ratio(returns_df['returns'])
            return sharpe

        # Run optimization
        study = optuna.create_study(direction='maximize')
        study.optimize(
            objective,
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=False
        )

        best_params = study.best_params
        best_sharpe = study.best_value

        logger.info(f"✅ Optimization complete")
        logger.info(f"   Best Sharpe: {best_sharpe:.4f}")
        logger.info(f"   Best params: {best_params}")

        return {
            'best_params': best_params,
            'best_sharpe': best_sharpe,
            'study': study
        }


def differentiable_sharpe_loss(
    y_pred_probs: torch.Tensor,
    y_true: torch.Tensor,
    prices: torch.Tensor,
    transaction_cost: float = 0.001
) -> torch.Tensor:
    """
    Differentiable approximation of Sharpe ratio for direct optimization.

    Uses continuous position sizing instead of discrete signals.

    Args:
        y_pred_probs: Prediction probabilities [batch_size, n_classes]
        y_true: True labels [batch_size]
        prices: Price data [batch_size]
        transaction_cost: Transaction cost rate

    Returns:
        Loss tensor (negative Sharpe - we minimize)
    """
    import torch

    # Convert probabilities to continuous positions
    # For 3-class: position ∈ [-1, 1] where -1=short, 0=cash, 1=long
    if y_pred_probs.shape[1] == 3:
        # Weight sum: [-1 * SELL + 0 * HOLD + 1 * BUY]
        positions = y_pred_probs[:, 2] - y_pred_probs[:, 0]  # BUY - SELL
    else:  # Binary
        positions = 2 * y_pred_probs[:, 1] - 1  # Scale from [0,1] to [-1,1]

    # Calculate gross returns (price change)
    price_changes = torch.diff(prices, prepend=prices[0:1])
    gross_returns = positions * price_changes

    # Subtract transaction costs (proportional to position changes)
    position_changes = torch.diff(positions, prepend=positions[0:1])
    costs = transaction_cost * torch.abs(position_changes)
    net_returns = gross_returns - costs

    # Calculate Sharpe-like ratio
    mean_return = net_returns.mean()
    std_return = net_returns.std() + 1e-6  # Numerical stability

    sharpe = mean_return / std_return

    # Return negative Sharpe (we want to maximize Sharpe, minimize loss)
    return -sharpe
