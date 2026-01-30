"""
Base Model Class

All models inherit from this for consistent interface
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np
from pathlib import Path
import mlflow
import mlflow.sklearn
import mlflow.pytorch
import logging

logger = logging.getLogger(__name__)


class BaseModel(ABC):
    """Base class for all models"""

    def __init__(self, config: Any, name: str):
        """
        Initialize model

        Args:
            config: Model configuration
            name: Model name (for logging/saving)
        """
        self.config = config
        self.name = name
        self.model = None
        self.feature_cols = None
        self.is_fitted = False

    @abstractmethod
    def build_model(self, **kwargs):
        """Build model architecture"""
        pass

    @abstractmethod
    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """
        Train model

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
        """
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make predictions

        Args:
            X: Features

        Returns:
            Predictions (binary)
        """
        pass

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict probabilities

        Args:
            X: Features

        Returns:
            Probabilities (shape: [n_samples, 2])
        """
        pass

    def get_params(self) -> Dict[str, Any]:
        """Get model hyperparameters"""
        if self.model is None:
            return {}
        return self.model.get_params() if hasattr(self.model, 'get_params') else {}

    def set_params(self, **params):
        """Set model hyperparameters"""
        if self.model is not None and hasattr(self.model, 'set_params'):
            self.model.set_params(**params)
        return self

    def save(self, path: Path):
        """Save model to disk"""
        path.mkdir(parents=True, exist_ok=True)

        # Save model
        self._save_model(path)

        # Save metadata
        metadata = {
            'name': self.name,
            'is_fitted': self.is_fitted,
            'feature_cols': self.feature_cols,
            'params': self.get_params()
        }

        import json
        with open(path / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"✅ {self.name} saved to {path}")

    def load(self, path: Path):
        """Load model from disk"""
        self._load_model(path)

        # Load metadata
        import json
        with open(path / 'metadata.json', 'r') as f:
            metadata = json.load(f)

        self.feature_cols = metadata['feature_cols']
        self.is_fitted = metadata['is_fitted']

        logger.info(f"✅ {self.name} loaded from {path}")

    @abstractmethod
    def _save_model(self, path: Path):
        """Save model (implementation-specific)"""
        pass

    @abstractmethod
    def _load_model(self, path: Path):
        """Load model (implementation-specific)"""
        pass

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """Log metrics to MLflow"""
        for key, value in metrics.items():
            mlflow.log_metric(key, value, step=step)

    def log_params(self, params: Dict[str, Any]):
        """Log parameters to MLflow"""
        mlflow.log_params(params)

    def log_model(self, artifact_path: str):
        """Log model to MLflow"""
        if self.name in ['xgboost', 'catboost']:
            mlflow.sklearn.log_model(self.model, artifact_path)
        elif self.name == 'tcn':
            mlflow.pytorch.log_model(self.model, artifact_path)
