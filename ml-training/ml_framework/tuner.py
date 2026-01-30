"""
Hyperparameter Tuning with Optuna

Optimizes hyperparameters for all models using Bayesian optimization
"""
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
import mlflow
import logging
from typing import Dict, Any, Optional

from ml_framework.config import Config, XGBoostConfig, CatBoostConfig, TCNConfig
from ml_framework.models import XGBoostModel, CatBoostModel, TCNModel

logger = logging.getLogger(__name__)


class HyperparameterTuner:
    """Hyperparameter tuning with Optuna"""

    def __init__(self, config: Config):
        """
        Initialize tuner

        Args:
            config: Training configuration
        """
        self.config = config
        self.study = None
        self.best_params = {}

    def _xgboost_objective(self, trial: optuna.Trial, X_train, y_train, X_val, y_val):
        """XGBoost objective function for Optuna"""

        # Suggest hyperparameters
        params = {
            'max_depth': trial.suggest_int('max_depth', *self.config.xgboost.max_depth),
            'learning_rate': trial.suggest_float('learning_rate', *self.config.xgboost.learning_rate, log=True),
            'subsample': trial.suggest_float('subsample', *self.config.xgboost.subsample),
            'colsample_bytree': trial.suggest_float('colsample_bytree', *self.config.xgboost.colsample_bytree),
            'reg_lambda': trial.suggest_float('reg_lambda', *self.config.xgboost.reg_lambda),
            'reg_alpha': trial.suggest_float('reg_alpha', *self.config.xgboost.reg_alpha),
            'min_child_weight': trial.suggest_int('min_child_weight', *self.config.xgboost.min_child_weight),
            'gamma': trial.suggest_float('gamma', *self.config.xgboost.gamma),
        }

        # Create and train model
        model = XGBoostModel(self.config.xgboost, trial_params=params)
        model.train(X_train, y_train, X_val, y_val)

        # Evaluate
        metrics = model.evaluate(X_val, y_val)

        # Log to MLflow
        trial.set_user_attr('auc', metrics['auc'])
        trial.set_user_attr('accuracy', metrics['accuracy'])

        return metrics['auc']  # Optimize AUC

    def _catboost_objective(self, trial: optuna.Trial, X_train, y_train, X_val, y_val):
        """CatBoost objective function for Optuna"""

        # Suggest hyperparameters
        params = {
            'depth': trial.suggest_int('depth', *self.config.catboost.depth),
            'learning_rate': trial.suggest_float('learning_rate', *self.config.catboost.learning_rate, log=True),
            'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', *self.config.catboost.l2_leaf_reg),
            'bagging_temperature': trial.suggest_float('bagging_temperature', *self.config.catboost.bagging_temperature),
            'border_count': trial.suggest_int('border_count', *self.config.catboost.border_count),
            'random_strength': trial.suggest_float('random_strength', *self.config.catboost.random_strength),
        }

        # Create and train model
        model = CatBoostModel(self.config.catboost, trial_params=params)
        model.train(X_train, y_train, X_val, y_val)

        # Evaluate
        metrics = model.evaluate(X_val, y_val)

        # Log to MLflow
        trial.set_user_attr('auc', metrics['auc'])
        trial.set_user_attr('accuracy', metrics['accuracy'])

        return metrics['auc']

    def _tcn_objective(self, trial: optuna.Trial, X_train, y_train, X_val, y_val):
        """TCN objective function for Optuna"""

        # Suggest hyperparameters
        params = {
            'num_layers': trial.suggest_int('num_layers', *self.config.tcn.num_layers),
            'kernel_size': trial.suggest_int('kernel_size', *self.config.tcn.kernel_size_range),
            'dropout': trial.suggest_float('dropout', *self.config.tcn.dropout_range),
            'learning_rate': trial.suggest_float('learning_rate', *self.config.tcn.learning_rate, log=True),
        }

        # Create and train model
        model = TCNModel(self.config.tcn, trial_params=params)
        model.train(X_train, y_train, X_val, y_val)

        # Evaluate
        metrics = model.evaluate(X_val, y_val)

        # Log to MLflow
        trial.set_user_attr('auc', metrics['auc'])
        trial.set_user_attr('accuracy', metrics['accuracy'])

        return metrics['auc']

    def _chronos_objective(self, trial: optuna.Trial, X_train, y_train, X_val, y_val):
        """Chronos objective - pretrained, no tuning needed"""

        # Import ChronosModel here to avoid circular import
        from ml_framework.models.chronos_model import ChronosModel

        # Create model with default config (no trial params needed)
        model = ChronosModel(self.config.chronos)

        # Train (just optimizes threshold)
        model.train(X_train, y_train, X_val, y_val)

        # Evaluate
        metrics = model.evaluate(X_val, y_val)

        # Log to MLflow
        trial.set_user_attr('auc', metrics['auc'])
        trial.set_user_attr('accuracy', metrics['accuracy'])

        return metrics['auc']

    def tune_model(self, model_name: str, X_train, y_train, X_val, y_val, n_trials: Optional[int] = None):
        """
        Tune hyperparameters for a specific model

        Args:
            model_name: 'xgboost', 'catboost', or 'tcn'
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            n_trials: Number of Optuna trials (default from config)

        Returns:
            best_params: Dictionary of best hyperparameters
        """
        n_trials = n_trials or self.config.training.n_trials

        logger.info(f"🎯 Tuning {model_name} with {n_trials} trials...")

        # Create study
        sampler = TPESampler(seed=self.config.training.random_seed)
        pruner = MedianPruner(n_warmup_steps=10)

        self.study = optuna.create_study(
            direction='maximize',
            sampler=sampler,
            pruner=pruner
        )

        # Select objective function
        objective_map = {
            'xgboost': self._xgboost_objective,
            'catboost': self._catboost_objective,
            'tcn': self._tcn_objective,
            'chronos': self._chronos_objective,
        }

        objective = objective_map[model_name]

        # Optimize
        self.study.optimize(
            lambda trial: objective(trial, X_train, y_train, X_val, y_val),
            n_trials=n_trials,
            timeout=self.config.training.timeout,
            show_progress_bar=True
        )

        # Get best parameters
        self.best_params[model_name] = self.study.best_params

        logger.info(f"✅ {model_name} tuning complete")
        logger.info(f"   Best AUC: {self.study.best_value:.4f}")
        logger.info(f"   Best params: {self.study.best_params}")

        return self.best_params[model_name]

    def tune_all_models(self, X_train, y_train, X_val, y_val):
        """
        Tune all models sequentially

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels

        Returns:
            Dict of best params for each model
        """
        logger.info("=" * 60)
        logger.info("Hyperparameter Tuning - All Models")
        logger.info("=" * 60)

        for model_name in self.config.ensemble.models:
            try:
                self.tune_model(model_name, X_train, y_train, X_val, y_val)
            except Exception as e:
                logger.error(f"❌ Error tuning {model_name}: {e}")
                continue

        return self.best_params

    def get_importance(self, model_name: str) -> Dict[str, float]:
        """
        Get hyperparameter importance

        Args:
            model_name: Model name

        Returns:
            Dict of parameter importance
        """
        if self.study is None:
            raise ValueError("No study available. Run tune_model() first.")

        return optuna.importance.get_param_importances(self.study)

    def get_trials_dataframe(self):
        """Get trials as pandas DataFrame"""
        if self.study is None:
            raise ValueError("No study available. Run tune_model() first.")

        return self.study.trials_dataframe()
