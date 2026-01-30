"""
CatBoost Model Implementation
"""
import sys
sys.path.insert(0, '/backend')

from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
from catboost import CatBoostClassifier, Pool
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
import logging

from ml_framework.base import BaseModel
from ml_framework.config import CatBoostConfig

logger = logging.getLogger(__name__)


class CatBoostModel(BaseModel):
    """CatBoost model wrapper"""

    def __init__(self, config: CatBoostConfig, trial_params: Optional[Dict] = None):
        """
        Initialize CatBoost model

        Args:
            config: CatBoost configuration
            trial_params: Hyperparameters from Optuna trial (overrides config)
        """
        super().__init__(config, "catboost")
        self.trial_params = trial_params or {}

    def build_model(self, **kwargs):
        """Build CatBoost model"""
        # Merge config with trial params
        params = {
            'loss_function': self.config.loss_function,
            'eval_metric': self.config.eval_metric,
            'task_type': self.config.task_type,
            'verbose': self.config.verbose,
            'random_seed': 42,
        }

        # Add tunable parameters from trial or defaults
        if 'depth' in self.trial_params:
            params['depth'] = int(self.trial_params['depth'])
        else:
            params['depth'] = 6

        if 'learning_rate' in self.trial_params:
            params['learning_rate'] = self.trial_params['learning_rate']
        else:
            params['learning_rate'] = 0.01

        if 'l2_leaf_reg' in self.trial_params:
            params['l2_leaf_reg'] = self.trial_params['l2_leaf_reg']
        else:
            params['l2_leaf_reg'] = 3.0

        if 'bagging_temperature' in self.trial_params:
            params['bagging_temperature'] = self.trial_params['bagging_temperature']
        else:
            params['bagging_temperature'] = 1.0

        if 'border_count' in self.trial_params:
            params['border_count'] = int(self.trial_params['border_count'])
        else:
            params['border_count'] = 128

        if 'random_strength' in self.trial_params:
            params['random_strength'] = self.trial_params['random_strength']
        else:
            params['random_strength'] = 1.0

        self.model = CatBoostClassifier(**params)
        logger.info(f"✅ CatBoost model built with params: {params}")

        return self.model

    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """
        Train CatBoost model

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
        """
        if self.model is None:
            self.build_model()

        # Store feature columns
        self.feature_cols = X_train.columns.tolist()

        # Create CatBoost Pools
        train_pool = Pool(data=X_train, label=y_train)
        val_pool = Pool(data=X_val, label=y_val)

        # Fit model
        self.model.fit(
            train_pool,
            eval_set=val_pool,
            early_stopping_rounds=self.config.early_stopping_rounds,
            verbose=False
        )

        self.is_fitted = True
        logger.info(f"✅ CatBoost trained. Best iteration: {self.model.best_iteration_}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary predictions"""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call train() first.")

        return self.model.predict(X)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities"""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call train() first.")

        return self.model.predict_proba(X)

    def evaluate(self, X_test, y_test) -> Dict[str, float]:
        """
        Evaluate model on test set

        Returns:
            Dict with metrics
        """
        y_pred = self.predict(X_test)
        y_prob = self.predict_proba(X_test)[:, 1]

        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'auc': roc_auc_score(y_test, y_prob)
        }

        return metrics

    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance"""
        if not self.is_fitted:
            raise ValueError("Model not fitted.")

        importance = self.model.feature_importances_

        df = pd.DataFrame({
            'feature': self.feature_cols,
            'importance': importance
        }).sort_values('importance', ascending=False)

        return df

    def get_shap_values(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get SHAP values for interpretability

        Args:
            X: Features

        Returns:
            SHAP values array
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted.")

        return self.model.get_feature_importance(Pool(data=X, label=None))

    def _save_model(self, path: Path):
        """Save CatBoost model"""
        self.model.save_model(str(path / 'model.cbm'))

    def _load_model(self, path: Path):
        """Load CatBoost model"""
        self.model = CatBoostClassifier()
        self.model.load_model(str(path / 'model.cbm'))
        self.is_fitted = True
