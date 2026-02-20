"""
AutoGluon Model Implementation

AutoGluon is Amazon's AutoML library that automatically:
- Trains multiple models (XGBoost, CatBoost, LightGBM, etc.)
- Stacks and ensembles them
- Handles hyperparameter tuning
- Performs feature engineering

Key advantages:
- State-of-the-art performance on tabular data
- Minimal manual tuning required
- Automatic ensemble creation
"""
import sys
sys.path.insert(0, '/backend')

from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import pandas as pd
import numpy as np
import logging
import os

from ml_framework.base import BaseModel
from ml_framework.config import AutoGluonConfig

logger = logging.getLogger(__name__)

try:
    from autogluon.tabular import TabularDataset, TabularPredictor
    AUTOGLUON_AVAILABLE = True
except ImportError:
    AUTOGLUON_AVAILABLE = False
    TabularDataset = None
    TabularPredictor = None

# Class names for multi-class
CLASS_NAMES = {
    0: 'STRONG SELL',
    1: 'SELL',
    2: 'HOLD',
    3: 'BUY',
    4: 'STRONG BUY'
}


class AutoGluonModel(BaseModel):
    """AutoGluon AutoML model wrapper"""

    def __init__(self, config: AutoGluonConfig, trial_params: Optional[Dict] = None):
        """
        Initialize AutoGluon model

        Args:
            config: AutoGluon configuration
            trial_params: Hyperparameters from Optuna trial (overrides config)
        """
        if not AUTOGLUON_AVAILABLE:
            raise ImportError(
                "AutoGluon is not installed. "
                "Install it with: pip install autogluon"
            )

        super().__init__(config, "autogluon")
        self.trial_params = trial_params or {}
        self.predictor = None
        self.save_path = None

    def build_model(self, **kwargs):
        """
        Build AutoGluon predictor (lazy initialization)

        AutoGluon doesn't build models until fit() is called
        """
        num_classes = kwargs.get('num_classes', 2)
        is_multiclass = num_classes > 2

        # Determine problem type
        if is_multiclass:
            self.problem_type = 'multiclass'
        else:
            self.problem_type = 'binary'

        logger.info(f"✅ AutoGluon configured for {self.problem_type} classification")
        return self

    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """
        Train AutoGluon model

        AutoGluon will:
        1. Train multiple models
        2. Tune hyperparameters
        3. Create ensembles

        Args:
            X_train: Training features (DataFrame or numpy array)
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
        """
        # Detect number of classes
        num_classes = len(np.unique(y_train))
        is_multiclass = num_classes > 2

        # Determine problem type (needed for TabularPredictor)
        self.problem_type = 'multiclass' if is_multiclass else 'binary'

        # Store feature columns
        if hasattr(X_train, 'columns'):
            self.feature_cols = X_train.columns.tolist()
        else:
            self.feature_cols = [f'feature_{i}' for i in range(X_train.shape[1])]

        # Combine train and validation for AutoGluon
        # AutoGluon will handle the split internally
        X_combined = pd.concat([X_train, X_val], ignore_index=True)
        y_combined = pd.concat([y_train, y_val], ignore_index=True)

        # Create DataFrame for AutoGluon
        if not isinstance(X_combined, pd.DataFrame):
            X_combined = pd.DataFrame(X_combined, columns=self.feature_cols)

        # Add label column
        df = X_combined.copy()
        # Handle both Series and array-like y values
        if hasattr(y_combined, 'values'):
            label_values = y_combined.values
            # Flatten if 2D
            if hasattr(label_values, 'ndim') and label_values.ndim == 2:
                label_values = label_values.flatten()
            df['label'] = label_values
        else:
            df['label'] = y_combined

        # Convert to TabularDataset
        train_data = TabularDataset(df)

        # Determine eval_metric based on problem type
        if is_multiclass:
            eval_metric = self.trial_params.get('eval_metric', 'accuracy')
        else:
            eval_metric = self.trial_params.get('eval_metric', 'roc_auc')

        # Get time limit from config or trial params
        time_limit = self.trial_params.get(
            'time_limit',
            self.config.time_limit
        )

        # Get presets from config or trial params
        presets = self.trial_params.get(
            'presets',
            self.config.presets
        )

        # Get num_bag_sets from config or trial params
        num_bag_sets = self.trial_params.get(
            'num_bag_sets',
            self.config.num_bag_sets
        )

        # Get num_stack_levels from config or trial params
        num_stack_levels = self.trial_params.get(
            'num_stack_levels',
            self.config.num_stack_levels
        )

        # Create predictor
        # AutoGluon will save to this directory
        import tempfile
        self.save_path = tempfile.mkdtemp(prefix='autogluon_')

        self.predictor = TabularPredictor(
            label='label',
            problem_type=self.problem_type,
            eval_metric=eval_metric,
            path=self.save_path,
        )

        # Train AutoGluon
        logger.info(f"Training AutoGluon with presets={presets}, time_limit={time_limit}")

        hyperparameters = self.trial_params.get('hyperparameters', None)

        # Build fit kwargs - only pass bagging/stacking params if not using presets
        # that might override them
        fit_kwargs = {
            'train_data': train_data,
            'time_limit': time_limit,
            'presets': presets,
            'hyperparameters': hyperparameters,
            'ag_args_fit': {'num_gpus': 1 if self.config.use_gpu else 0} if self.config.use_gpu else {},
            'verbosity': self.config.verbosity,
        }

        # Only pass num_bag_sets and num_stack_levels if presets don't conflict
        # Some presets (like medium_quality_faster_train) set num_bag_folds=0
        # which conflicts with num_stack_levels > 0
        if presets not in ['medium_quality_faster_train', 'medium_quality']:
            fit_kwargs['num_bag_sets'] = num_bag_sets
            fit_kwargs['num_stack_levels'] = num_stack_levels

        self.predictor.fit(**fit_kwargs)

        self.is_fitted = True
        logger.info(f"✅ AutoGluon training complete")

        # Log training metrics
        try:
            # Get leaderboard
            leaderboard = self.predictor.leaderboard(silent=True)
            logger.info(f"AutoGluon leaderboard:\n{leaderboard}")

            # Log best model score
            best_model = leaderboard.iloc[0]['model']
            best_score = leaderboard.iloc[0]['score_val']
            self.log_metrics({'autogluon_best_score': best_score})
            self.log_metrics({'autogluon_num_models': len(leaderboard)})
        except Exception as e:
            logger.debug(f"Could not log AutoGluon leaderboard: {e}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make predictions

        Args:
            X: Features

        Returns:
            Predictions
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call train() first.")

        # Convert to DataFrame if needed
        if not isinstance(X, pd.DataFrame):
            if self.feature_cols:
                X = pd.DataFrame(X, columns=self.feature_cols)
            else:
                X = pd.DataFrame(X)

        # Use AutoGluon to predict
        predictions = self.predictor.predict(X)

        return predictions.values

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict probabilities

        Args:
            X: Features

        Returns:
            Probabilities
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call train() first.")

        # Convert to DataFrame if needed
        if not isinstance(X, pd.DataFrame):
            if self.feature_cols:
                X = pd.DataFrame(X, columns=self.feature_cols)
            else:
                X = pd.DataFrame(X)

        # Use AutoGluon to predict probabilities
        proba = self.predictor.predict_proba(X)

        # Return as numpy array
        return proba.values

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

        from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

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
            # Get probability of positive class
            if y_prob.shape[1] == 2:
                y_prob_binary = y_prob[:, 1]
            else:
                y_prob_binary = y_prob[:, 0]

            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred, zero_division=0),
                'recall': recall_score(y_test, y_pred, zero_division=0),
                'auc': roc_auc_score(y_test, y_prob_binary)
            }

        return metrics

    def get_feature_importance(self) -> pd.DataFrame:
        """
        Get feature importance from AutoGluon

        Note: AutoGluon doesn't always provide feature importance
        for all models (especially ensembles)
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted.")

        try:
            # Try to get feature importance from predictor
            importance = self.predictor.feature_importance(train_data=None)
            return importance
        except Exception as e:
            logger.warning(f"Could not get feature importance: {e}")
            # Return empty dataframe with feature names
            if self.feature_cols:
                return pd.DataFrame({
                    'feature': self.feature_cols,
                    'importance': 0.0
                })
            else:
                return pd.DataFrame({'feature': [], 'importance': []})

    def get_leaderboard(self) -> pd.DataFrame:
        """Get AutoGluon model leaderboard"""
        if not self.is_fitted:
            raise ValueError("Model not fitted.")

        return self.predictor.leaderboard(silent=True)

    def get_best_model(self) -> str:
        """Get the name of the best model"""
        if not self.is_fitted:
            raise ValueError("Model not fitted.")

        leaderboard = self.predictor.leaderboard(silent=True)
        return leaderboard.iloc[0]['model']

    def _save_model(self, path: Path):
        """
        Save AutoGluon model

        AutoGluon models are already saved during training.
        We just need to copy to the target path.
        """
        import shutil

        if self.predictor is None:
            raise ValueError("No model to save")

        # AutoGluon saves during training, just copy to target path
        if self.save_path and os.path.exists(self.save_path):
            shutil.copytree(self.save_path, path, dirs_exist_ok=True)
            logger.info(f"AutoGluon model copied from {self.save_path} to {path}")
        else:
            # Save using predictor's save method
            self.predictor.save(path)
            logger.info(f"AutoGluon model saved to {path}")

    def _load_model(self, path: Path):
        """Load AutoGluon model"""
        self.predictor = TabularPredictor.load(path)
        self.is_fitted = True
        self.save_path = str(path)
        logger.info(f"AutoGluon model loaded from {path}")


def check_autogluon_available() -> bool:
    """Check if AutoGluon is available"""
    return AUTOGLUON_AVAILABLE
