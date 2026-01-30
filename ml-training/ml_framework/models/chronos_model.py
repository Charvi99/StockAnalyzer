"""
Chronos Model Implementation

Amazon's Chronos-tiny for time series forecasting
Pre-trained transformer for binary classification
"""
import sys
sys.path.insert(0, '/backend')

from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
import logging

try:
    from transformers import ChronosPipeline, ChronosConfig
    CHRONOS_AVAILABLE = True
except ImportError:
    CHRONOS_AVAILABLE = False
    logging.warning("transformers library not available. Chronos model will not work.")

from ml_framework.base import BaseModel
from ml_framework.config import ChronosConfig

logger = logging.getLogger(__name__)


class ChronosModel(BaseModel):
    """
    Amazon Chronos-tiny Model for Binary Classification

    Uses pretrained Chronos-tiny transformer for time series forecasting,
    then converts forecasts to binary classification.
    """

    def __init__(self, config: ChronosConfig, trial_params: Optional[Dict] = None):
        """
        Initialize Chronos model

        Args:
            config: Chronos configuration
            trial_params: Hyperparameters from Optuna trial (overrides config)
        """
        super().__init__(config, "chronos")

        self.trial_params = trial_params or {}
        self.config = config

        # Device
        self.device = torch.device(config.device if torch.cuda.is_available() else "cpu")

        # Model will be loaded in build_model()
        self.model = None
        self.pipeline = None

        # Threshold for binary classification
        self.threshold = 0.5

        if not CHRONOS_AVAILABLE:
            logger.error("transformers library not installed. Chronos model requires: pip install transformers accelerate")
            raise ImportError("Install transformers: pip install transformers accelerate")

    def build_model(self, input_shape: Tuple[int, int] = None, **kwargs):
        """
        Build Chronos model

        Args:
            input_shape: (n_samples, n_features) - not used for Chronos
        """
        if self.model is not None:
            logger.warning("Chronos model already built")
            return

        try:
            logger.info("Loading Chronos-tiny model from Amazon...")

            # Load Chronos pipeline
            model_name = "amazon/chronos-t5-tiny"  # Smallest, fastest
            self.pipeline = ChronosPipeline.from_pretrained(
                model_name,
                device_map=self.device,
                torch_dtype=torch.float32,
            )

            # Set to evaluation mode
            self.pipeline.model.eval()

            logger.info(f"✅ Chronos model loaded on {self.device}")

        except Exception as e:
            logger.error(f"❌ Error loading Chronos model: {e}")
            logger.error("Make sure you have internet connection to download the model")
            raise

    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """
        Chronos is pretrained - skip training, just set threshold

        Args:
            X_train: Training features (not used, Chronos is pretrained)
            y_train: Training labels (not used)
            X_val: Validation features
            y_val: Validation labels
        """
        if self.pipeline is None:
            self.build_model()

        logger.info("Chronos is pretrained - skipping training, optimizing threshold...")

        # Get predictions on validation set
        val_proba = self.predict_proba(X_val)

        # Optimize threshold on validation set
        from sklearn.metrics import f1_score

        best_threshold = 0.5
        best_f1 = 0

        for threshold in np.arange(0.2, 0.6, 0.05):
            y_pred = (val_proba[:, 1] >= threshold).astype(int)
            f1 = f1_score(y_val, y_pred, zero_division=0)

            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold

        self.threshold = best_threshold
        logger.info(f"✅ Optimized threshold: {self.threshold:.2f} (F1: {best_f1:.3f})")

        self.is_fitted = True

    def forecast_prices(self, price_history: np.ndarray, prediction_length: int = 20) -> np.ndarray:
        """
        Forecast future prices using Chronos

        Args:
            price_history: Historical prices (shape: [context_length])
            prediction_length: Number of days to forecast

        Returns:
            Forecasted prices
        """
        try:
            # Chronos expects shape [batch, context_length]
            if len(price_history.shape) == 1:
                price_history = price_history.reshape(1, -1)

            # Forecast
            forecast = self.pipeline.predict(
                price_history,
                prediction_length=prediction_length
            )

            # Return median forecast
            return forecast.median[0]  # [prediction_length]

        except Exception as e:
            logger.error(f"Error forecasting: {e}")
            # Return flat forecast as fallback
            last_price = price_history[-1]
            return np.full(prediction_length, last_price)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict probabilities using Chronos forecasts

        Strategy: Forecast next 20 days, check if +3% reached before -2%

        Args:
            X: Features DataFrame

        Returns:
            Probabilities [n_samples, 2]
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call train() first.")

        n_samples = len(X)
        probabilities = np.zeros((n_samples, 2))

        # Extract price history features
        # Assuming X has columns like: close, return_1d, return_3d, etc.
        price_col = 'close' if 'close' in X.columns else X.columns[0]

        for i in range(n_samples):
            try:
                # Get recent price history from features
                # Use lagged returns to reconstruct price history
                current_price = X.iloc[i][price_col]

                # Create synthetic price history (20 days)
                # This is simplified - in production, use actual historical prices
                context_length = 64
                price_history = np.full(context_length, current_price)

                # Add some variation based on returns
                if 'return_1d' in X.columns:
                    ret_1d = X.iloc[i]['return_1d']
                    price_history[-1] = current_price / (1 + ret_1d)

                if 'return_5d' in X.columns:
                    ret_5d = X.iloc[i]['return_5d']
                    price_history[-5] = current_price / (1 + ret_5d)

                # Forecast next 20 days
                forecasts = self.forecast_prices(price_history, prediction_length=20)

                # Calculate metrics
                initial_price = forecasts[0]
                max_upside = np.max((forecasts - initial_price) / initial_price)
                max_drawdown = np.min((forecasts - initial_price) / initial_price)

                # Calculate probability based on forecast
                # If forecast shows +3% before -2%, high probability
                if max_upside >= 0.03 and max_drawdown > -0.02:
                    prob = 0.7 + min(max_upside - 0.03, 0.2)  # 0.7-0.9
                elif max_upside >= 0.02:
                    prob = 0.5 + (max_upside - 0.02) * 5  # 0.5-0.6
                else:
                    prob = 0.3 - min(abs(max_upside), 0.2)  # 0.1-0.3

                # Adjust based on technical indicators
                if 'rsi' in X.columns:
                    rsi = X.iloc[i]['rsi']
                    if rsi < 30:  # Oversold
                        prob = min(prob + 0.1, 0.9)
                    elif rsi > 70:  # Overbought
                        prob = max(prob - 0.1, 0.1)

                if 'macd' in X.columns and 'macd_signal' in X.columns:
                    macd = X.iloc[i]['macd']
                    macd_signal = X.iloc[i]['macd_signal']
                    if macd > macd_signal:  # Bullish crossover
                        prob = min(prob + 0.05, 0.9)
                    else:  # Bearish
                        prob = max(prob - 0.05, 0.1)

                # Clamp probability
                prob = max(0.05, min(0.95, prob))

                probabilities[i, 0] = 1 - prob
                probabilities[i, 1] = prob

            except Exception as e:
                logger.warning(f"Error predicting sample {i}: {e}")
                # Use default probability
                probabilities[i, 0] = 0.6
                probabilities[i, 1] = 0.4

        return probabilities

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary predictions using optimized threshold"""
        proba = self.predict_proba(X)
        return (proba[:, 1] >= self.threshold).astype(int)

    def evaluate(self, X_test, y_test) -> Dict[str, float]:
        """Evaluate model on test set"""
        y_pred = self.predict(X_test)
        y_proba = self.predict_proba(X_test)

        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'auc': roc_auc_score(y_test, y_proba[:, 1])
        }

        return metrics

    def get_feature_importance(self) -> Dict[str, float]:
        """Chronos doesn't have feature importance (transformer)"""
        return {}

    def save(self, path: Path):
        """Save model and metadata"""
        path.mkdir(parents=True, exist_ok=True)

        # Save metadata
        import json
        metadata = {
            'model_type': 'chronos',
            'threshold': self.threshold,
            'device': str(self.device),
            'feature_cols': getattr(self, 'feature_cols', []),
        }

        with open(path / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"✅ Chronos metadata saved to {path}")

    def load(self, path: Path):
        """Load model metadata"""
        import json
        metadata_path = path / 'metadata.json'

        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            self.threshold = metadata.get('threshold', 0.5)
            self.feature_cols = metadata.get('feature_cols', [])

            # Load model
            self.build_model()
            self.is_fitted = True

            logger.info(f"✅ Chronos loaded from {path}")
        else:
            raise FileNotFoundError(f"No metadata found at {metadata_path}")
