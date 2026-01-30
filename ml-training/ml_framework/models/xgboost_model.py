"""
XGBoost Model Implementation
"""
import sys
sys.path.insert(0, '/backend')

from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
import logging

from ml_framework.base import BaseModel
from ml_framework.config import XGBoostConfig

logger = logging.getLogger(__name__)


class XGBoostModel(BaseModel):
    """XGBoost model wrapper"""

    def __init__(self, config: XGBoostConfig, trial_params: Optional[Dict] = None):
        """
        Initialize XGBoost model

        Args:
            config: XGBoost configuration
            trial_params: Hyperparameters from Optuna trial (overrides config)
        """
        super().__init__(config, "xgboost")
        self.trial_params = trial_params or {}

    def build_model(self, **kwargs):
        """Build XGBoost model"""
        # Merge config with trial params
        params = {
            'objective': self.config.objective,
            'eval_metric': self.config.eval_metric,
            'tree_method': self.config.tree_method,
            'n_jobs': self.config.n_jobs,
            'random_state': 42,
        }

        # Add tunable parameters from trial or defaults
        if 'max_depth' in self.trial_params:
            params['max_depth'] = self.trial_params['max_depth']
        else:
            params['max_depth'] = 6  # Default

        if 'learning_rate' in self.trial_params:
            params['learning_rate'] = self.trial_params['learning_rate']
        else:
            params['learning_rate'] = 0.01

        if 'subsample' in self.trial_params:
            params['subsample'] = self.trial_params['subsample']
        else:
            params['subsample'] = 0.7

        if 'colsample_bytree' in self.trial_params:
            params['colsample_bytree'] = self.trial_params['colsample_bytree']
        else:
            params['colsample_bytree'] = 0.7

        if 'reg_lambda' in self.trial_params:
            params['reg_lambda'] = self.trial_params['reg_lambda']
        else:
            params['reg_lambda'] = 1.0

        if 'reg_alpha' in self.trial_params:
            params['reg_alpha'] = self.trial_params['reg_alpha']
        else:
            params['reg_alpha'] = 0.1

        if 'min_child_weight' in self.trial_params:
            params['min_child_weight'] = self.trial_params['min_child_weight']
        else:
            params['min_child_weight'] = 1

        if 'gamma' in self.trial_params:
            params['gamma'] = self.trial_params['gamma']
        else:
            params['gamma'] = 0.0

        self.model = XGBClassifier(**params)
        logger.info(f"✅ XGBoost model built with params: {params}")

        return self.model

    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """
        Train XGBoost model

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

        # Calculate scale_pos_weight if not provided
        if self.config.scale_pos_weight is None:
            neg_samples = (y_train == 0).sum()
            pos_samples = (y_train == 1).sum()
            scale_pos_weight = neg_samples / pos_samples
        else:
            scale_pos_weight = self.config.scale_pos_weight

        # Fit model
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            # eval_metric removed - already set in constructor
            early_stopping_rounds=self.config.early_stopping_rounds,
            verbose=False,
            sample_weight=None
        )

        self.is_fitted = True
        logger.info(f"✅ XGBoost trained. Best iteration: {self.model.best_iteration}")

        # Log training metrics
        results = self.model.evals_result()
        if results:
            val_metrics = results['validation_0']
            for metric_name, values in val_metrics.items():
                self.log_metrics({f'train_{metric_name}': values[-1]})

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

    def _save_model(self, path: Path):
        """Save XGBoost model"""
        self.model.save_model(str(path / 'model.json'))

    def _load_model(self, path: Path):
        """Load XGBoost model"""
        self.model = XGBClassifier()
        self.model.load_model(str(path / 'model.json'))
        self.is_fitted = True
