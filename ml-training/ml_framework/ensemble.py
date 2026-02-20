"""
Ensemble Methods

Combines multiple models for better predictions
"""
import sys
sys.path.insert(0, '/backend')

from typing import Dict, List, Optional, Any
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
import joblib
import logging

from ml_framework.models import XGBoostModel, CatBoostModel

logger = logging.getLogger(__name__)


class Ensemble:
    """Ensemble of multiple models"""

    def __init__(self, models: Dict[str, Any], method: str = "weighted_average"):
        """
        Initialize ensemble

        Args:
            models: Dict of trained models
            method: 'weighted_average', 'stacking', or 'voting'
        """
        self.models = models
        self.method = method
        self.meta_learner = None
        self.weights = None

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get ensemble predictions

        Args:
            X: Features

        Returns:
            Probabilities (shape: [n_samples, 2])
        """
        if self.method == "weighted_average":
            return self._weighted_average(X)
        elif self.method == "stacking":
            return self._stacking(X)
        elif self.method == "voting":
            return self._voting(X)
        else:
            raise ValueError(f"Unknown ensemble method: {self.method}")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get binary predictions

        Args:
            X: Features

        Returns:
            Binary predictions (0 or 1)
        """
        proba = self.predict_proba(X)
        return (proba[:, 1] > 0.5).astype(int)

    def _weighted_average(self, X: pd.DataFrame) -> np.ndarray:
        """Weighted average of predictions"""
        # Default weights (equal)
        if self.weights is None:
            self.weights = {name: 1.0 / len(self.models) for name in self.models.keys()}

        # Get predictions from all models
        all_proba = {}
        for name, model in self.models.items():
            try:
                proba = model.predict_proba(X)[:, 1]
                all_proba[name] = proba
            except Exception as e:
                logger.warning(f"Error getting predictions from {name}: {e}")
                all_proba[name] = np.zeros(len(X))

        # Weighted average
        ensemble_proba = np.zeros(len(X))
        total_weight = 0.0

        for name, proba in all_proba.items():
            weight = self.weights.get(name, 0)
            ensemble_proba += proba * weight
            total_weight += weight

        if total_weight > 0:
            ensemble_proba /= total_weight

        # Convert to binary probabilities
        ensemble_proba_full = np.column_stack([1 - ensemble_proba, ensemble_proba])

        return ensemble_proba_full

    def _stacking(self, X: pd.DataFrame) -> np.ndarray:
        """Stacking with meta-learner"""
        # Get predictions from all models
        all_proba = []
        for name, model in self.models.items():
            try:
                proba = model.predict_proba(X)[:, 1]
                all_proba.append(proba)
            except Exception as e:
                logger.warning(f"Error getting predictions from {name}: {e}")
                all_proba.append(np.zeros(len(X)))

        if not all_proba:
            raise ValueError("No valid predictions from base models")

        # Stack predictions
        X_meta = np.column_stack(all_proba)

        # Use meta-learner
        if self.meta_learner is None:
            raise ValueError("Meta-learner not trained. Call train_meta_learner() first.")

        # Predict
        ensemble_proba = self.meta_learner.predict_proba(X_meta)

        return ensemble_proba

    def _voting(self, X: pd.DataFrame) -> np.ndarray:
        """Majority voting"""
        # Get predictions from all models
        all_pred = []
        for name, model in self.models.items():
            try:
                pred = model.predict(X)
                all_pred.append(pred)
            except Exception as e:
                logger.warning(f"Error getting predictions from {name}: {e}")
                all_pred.append(np.zeros(len(X)))

        # Majority vote
        ensemble_pred = np.round(np.mean(all_pred, axis=0)).astype(int)

        # For probabilities, use average of probabilities
        all_proba = []
        for name, model in self.models.items():
            try:
                proba = model.predict_proba(X)[:, 1]
                all_proba.append(proba)
            except Exception as e:
                logger.warning(f"Error getting predictions from {name}: {e}")
                all_proba.append(np.zeros(len(X)))

        ensemble_proba = np.mean(all_proba, axis=0)
        ensemble_proba_full = np.column_stack([1 - ensemble_proba, ensemble_proba])

        return ensemble_proba_full

    def train_meta_learner(self, X_val, y_val):
        """
        Train meta-learner for stacking

        Args:
            X_val: Validation features
            y_val: Validation labels
        """
        logger.info("🎯 Training meta-learner...")

        # Get predictions from all models
        all_proba = []
        for name, model in self.models.items():
            try:
                proba = model.predict_proba(X_val)[:, 1]
                all_proba.append(proba)
            except Exception as e:
                logger.warning(f"Error getting predictions from {name}: {e}")
                all_proba.append(np.zeros(len(X_val)))

        if not all_proba:
            raise ValueError("No valid predictions from base models")

        # Stack predictions
        X_meta = np.column_stack(all_proba)

        # Train meta-learner
        self.meta_learner = LogisticRegression(
            random_state=42,
            max_iter=1000
        )

        self.meta_learner.fit(X_meta, y_val)

        logger.info("✅ Meta-learner trained")

    def optimize_weights(self, X_val, y_val):
        """
        Optimize ensemble weights using validation set

        Args:
            X_val: Validation features
            y_val: Validation labels
        """
        logger.info("⚖️  Optimizing ensemble weights...")

        # Get predictions from all models
        all_proba = {}
        for name, model in self.models.items():
            try:
                proba = model.predict_proba(X_val)[:, 1]
                all_proba[name] = proba
            except Exception as e:
                logger.warning(f"Error getting predictions from {name}: {e}")

        # Simple grid search for best weights
        from itertools import product

        best_score = 0
        best_weights = None

        # Try weight combinations (step = 0.1)
        weight_range = np.arange(0.0, 1.1, 0.1)

        for weights_tuple in product(weight_range, repeat=len(self.models)):
            # Normalize weights
            total = sum(weights_tuple)
            if total == 0:
                continue
            norm_weights = {name: w/total for name, w in zip(self.models.keys(), weights_tuple)}

            # Calculate weighted prediction
            ensemble_proba = np.zeros(len(X_val))
            for name, proba in all_proba.items():
                ensemble_proba += proba * norm_weights[name]

            ensemble_proba /= total

            # Calculate AUC
            from sklearn.metrics import roc_auc_score
            score = roc_auc_score(y_val, ensemble_proba)

            if score > best_score:
                best_score = score
                best_weights = norm_weights

        self.weights = best_weights

        logger.info(f"✅ Optimized weights: {self.weights}")
        logger.info(f"   Validation AUC: {best_score:.4f}")

    def save(self, path):
        """Save ensemble"""
        import json

        # Save meta-learner
        if self.meta_learner is not None:
            joblib.dump(self.meta_learner, path / 'meta_learner.pkl')

        # Save weights
        if self.weights is not None:
            with open(path / 'weights.json', 'w') as f:
                json.dump(self.weights, f, indent=2)

        # Save method
        with open(path / 'metadata.json', 'w') as f:
            json.dump({'method': self.method, 'models': list(self.models.keys())}, f, indent=2)

        logger.info(f"✅ Ensemble saved to {path}")

    def load(self, path):
        """Load ensemble"""
        import json

        # Load method and models
        with open(path / 'metadata.json', 'r') as f:
            metadata = json.load(f)

        self.method = metadata['method']

        # Load meta-learner
        if (path / 'meta_learner.pkl').exists():
            self.meta_learner = joblib.load(path / 'meta_learner.pkl')

        # Load weights
        if (path / 'weights.json').exists():
            with open(path / 'weights.json', 'r') as f:
                self.weights = json.load(f)

        logger.info(f"✅ Ensemble loaded from {path}")
