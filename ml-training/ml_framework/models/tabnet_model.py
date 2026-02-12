"""
TabNet Model Implementation

TabNet: Attentive Interpretable Tabular Learning
https://arxiv.org/abs/1908.07442

Key advantages for tabular data:
- Sequential attention mechanism for feature selection
- Interpretable feature selection
- State-of-the-art performance on many tabular datasets
- Handles both classification and regression
"""
import sys
sys.path.insert(0, '/backend')

from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
import logging
import torch

try:
    from pytorch_tabnet.tab_model import TabNetClassifier
    TABNET_AVAILABLE = True
except ImportError:
    TABNET_AVAILABLE = False
    TabNetClassifier = None

from ml_framework.base import BaseModel
from ml_framework.config import TabNetConfig

logger = logging.getLogger(__name__)

# Class names for multi-class
CLASS_NAMES = {
    0: 'STRONG SELL',
    1: 'SELL',
    2: 'HOLD',
    3: 'BUY',
    4: 'STRONG BUY'
}


class TabNetModel(BaseModel):
    """TabNet model wrapper for tabular deep learning"""

    def __init__(self, config: TabNetConfig, trial_params: Optional[Dict] = None):
        """
        Initialize TabNet model

        Args:
            config: TabNet configuration
            trial_params: Hyperparameters from Optuna trial (overrides config)
        """
        if not TABNET_AVAILABLE:
            raise ImportError(
                "pytorch-tabnet is not installed. "
                "Install it with: pip install pytorch-tabnet"
            )

        super().__init__(config, "tabnet")
        self.trial_params = trial_params or {}

        # Detect device
        if torch.cuda.is_available():
            self.device = torch.device('cuda')
            logger.info(f"✅ TabNet using GPU: {torch.cuda.get_device_name(0)}")
        else:
            self.device = torch.device('cpu')
            logger.info("✅ TabNet using CPU")

    def build_model(self, **kwargs):
        """Build TabNet model"""
        # Detect if multi-class
        num_classes = kwargs.get('num_classes', 2)
        is_multiclass = num_classes > 2

        # Merge config with trial params
        params = {
            'n_d': self._get_param('n_d', 32),
            'n_a': self._get_param('n_a', 32),
            'n_steps': self._get_param('n_steps', 5),
            'gamma': self._get_param('gamma', 1.5),
            'n_independent': self._get_param('n_independent', 2),
            'n_shared': self._get_param('n_shared', 2),
            'lambda_sparse': self._get_param('lambda_sparse', 1e-4),
            'optimizer_fn': torch.optim.Adam,
            'optimizer_params': dict(lr=self._get_param('learning_rate', 0.02)),
            'mask_type': self.config.mask_type,
            'scheduler_params': self.config.scheduler_params,
            'scheduler_fn': torch.optim.lr_scheduler.StepLR,
            'verbose': self.config.verbose,
            'device_name': self.config.device_name,
            'seed': self.config.seed,
        }

        # Add num_classes for multi-class
        if is_multiclass:
            # For multi-class, TabNet needs to know the number of classes
            # It will handle this automatically during fit
            pass

        self.model = TabNetClassifier(**params)
        mode_str = "multi-class" if is_multiclass else "binary"
        logger.info(f"✅ TabNet model built ({mode_str}) with params: {params}")

        return self.model

    def _get_param(self, param_name: str, default: Any) -> Any:
        """Get parameter from trial_params or use default"""
        if param_name in self.trial_params:
            return self.trial_params[param_name]

        # Check if it's a tuple (search space) - use midpoint
        if hasattr(self.config, param_name):
            val = getattr(self.config, param_name)
            if isinstance(val, tuple) and len(val) == 2:
                # Return midpoint of search space
                return (val[0] + val[1]) / 2
            return val

        return default

    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """
        Train TabNet model

        Args:
            X_train: Training features (DataFrame or numpy array)
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
        """
        # Detect number of classes from training data
        num_classes = len(np.unique(y_train))

        if self.model is None:
            self.build_model(num_classes=num_classes)

        # Store feature columns
        if hasattr(X_train, 'columns'):
            self.feature_cols = X_train.columns.tolist()
        else:
            self.feature_cols = [f'feature_{i}' for i in range(X_train.shape[1])]

        # Convert to numpy arrays (TabNet requires numpy, not pandas)
        if isinstance(X_train, pd.DataFrame):
            X_train_np = X_train.values.astype(np.float32)
        else:
            X_train_np = X_train.astype(np.float32)

        if isinstance(X_val, pd.DataFrame):
            X_val_np = X_val.values.astype(np.float32)
        else:
            X_val_np = X_val.astype(np.float32)

        y_train_np = y_train.values if isinstance(y_train, pd.Series) else y_train
        y_val_np = y_val.values if isinstance(y_val, pd.Series) else y_val

        # Fit model
        self.model.fit(
            X_train=X_train_np,
            y_train=y_train_np,
            eval_set=[(X_val_np, y_val_np)],
            max_epochs=self.config.max_epochs,
            patience=self.config.patience,
            batch_size=self.config.batch_size,
            virtual_batch_size=self.config.virtual_batch_size,
            num_workers=self.config.num_workers,
            drop_last=False,
        )

        self.is_fitted = True
        logger.info(f"✅ TabNet trained. Max epochs: {self.config.max_epochs}")

        # Log training metrics - TabNet history structure is different, handle safely
        if hasattr(self.model, 'history'):
            try:
                history = self.model.history
                # Try to access common metric keys that TabNet might use
                for metric_key in ['val_auc', 'val_0_auc', 'valid_auc', 'test_auc']:
                    try:
                        if history and metric_key in history:
                            metric_value = history[metric_key]
                            if hasattr(metric_value, '__iter__') and len(metric_value) > 0:
                                self.log_metrics({'train_val_auc': float(metric_value[-1])})
                                break
                    except (KeyError, TypeError, AttributeError):
                        continue
            except Exception as e:
                logger.debug(f"Could not log TabNet history metrics: {e}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions"""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call train() first.")

        # Convert to numpy
        if isinstance(X, pd.DataFrame):
            X_np = X.values.astype(np.float32)
        else:
            X_np = X.astype(np.float32)

        return self.model.predict(X_np)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities"""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call train() first.")

        # Convert to numpy
        if isinstance(X, pd.DataFrame):
            X_np = X.values.astype(np.float32)
        else:
            X_np = X.astype(np.float32)

        return self.model.predict_proba(X_np)

    def evaluate(self, X_test, y_test) -> Dict[str, float]:
        """
        Evaluate model on test set

        Returns:
            Dict with metrics
        """
        y_pred = self.predict(X_test)
        y_prob = self.predict_proba(X_test)

        # Detect if multi-class
        num_classes = len(np.unique(y_test))
        is_multiclass = num_classes > 2

        if is_multiclass:
            # Multi-class metrics
            accuracy = accuracy_score(y_test, y_pred)

            # Use macro averaging for precision/recall
            precision = precision_score(y_test, y_pred, average='macro', zero_division=0)
            recall = recall_score(y_test, y_pred, average='macro', zero_division=0)

            # For multi-class AUC, use one-vs-rest with macro averaging
            try:
                auc = roc_auc_score(y_test, y_prob, multi_class='ovr', average='macro')
            except:
                auc = 0.5  # Fallback

            metrics = {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'auc': auc
            }

            # Add per-class metrics if 5 classes
            if num_classes == 5:
                for i in range(5):
                    class_mask = y_test == i
                    if class_mask.sum() > 0:
                        class_acc = accuracy_score(y_test[class_mask], y_pred[class_mask])
                        metrics[f'class_{i}_{CLASS_NAMES[i]}_acc'] = class_acc
        else:
            # Binary metrics
            y_prob_binary = y_prob[:, 1]
            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred, zero_division=0),
                'recall': recall_score(y_test, y_pred, zero_division=0),
                'auc': roc_auc_score(y_test, y_prob_binary)
            }

        return metrics

    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance from TabNet"""
        if not self.is_fitted:
            raise ValueError("Model not fitted.")

        # TabNet provides feature importance
        importance = self.model.feature_importances_

        df = pd.DataFrame({
            'feature': self.feature_cols,
            'importance': importance
        }).sort_values('importance', ascending=False)

        return df

    def explain(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get global and local feature importance from TabNet's attention mechanism

        Args:
            X: Features to explain

        Returns:
            (global_importance, local_importance) arrays
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted.")

        # Convert to numpy
        if isinstance(X, pd.DataFrame):
            X_np = X.values.astype(np.float32)
        else:
            X_np = X.astype(np.float32)

        # Get explainability
        explain_matrix, masks = self.model.explain(X_np)

        return explain_matrix, masks

    def _save_model(self, path: Path):
        """Save TabNet model"""
        self.model.save_model(str(path / 'tabnet_model.zip'))

    def _load_model(self, path: Path):
        """Load TabNet model"""
        self.model = TabNetClassifier()
        self.model.load_model(str(path / 'tabnet_model.zip'))
        self.is_fitted = True


def check_tabnet_available() -> bool:
    """Check if TabNet is available"""
    return TABNET_AVAILABLE
