"""
Model Training Orchestration

Handles training, evaluation, and logging for all models
"""
import sys
sys.path.insert(0, '/backend')

from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd
import numpy as np
import mlflow
import logging

from ml_framework.config import Config
from ml_framework.models import XGBoostModel, CatBoostModel, TCNModel, ChronosModel
from ml_framework.tuner import HyperparameterTuner

logger = logging.getLogger(__name__)


class ModelTrainer:
    """Orchestrate model training and evaluation"""

    def __init__(self, config: Config):
        """
        Initialize trainer

        Args:
            config: Training configuration
        """
        self.config = config
        self.models = {}
        self.best_params = {}

    @property
    def models_dir(self) -> Path:
        """Build models directory path from base_path and models_path"""
        return Path(self.config.data.base_path) / self.config.data.models_path

    def load_data(self):
        """Load features and labels from parquet files"""
        logger.info("📂 Loading data...")

        base_path = self.config.data.base_path
        features_dir = Path(base_path) / self.config.data.features_path

        # Find latest files - support both old and new naming, recursive search
        feature_files = sorted(features_dir.glob('**/*.parquet')) if features_dir.exists() else []

        # Labels are co-located with features files in same subdirectories
        label_files = sorted(features_dir.glob('**/labels_*.parquet')) if features_dir.exists() else []

        if not feature_files:
            raise FileNotFoundError(f"No feature files found in {features_dir}. Run feature engineering first.")
        if not label_files:
            raise FileNotFoundError(f"No label files found. Run create_labels.py first.")

        if not feature_files:
            raise FileNotFoundError("No feature files found. Run feature engineering first.")

        if not label_files:
            raise FileNotFoundError("No label files found. Run label creation first.")

        features = pd.read_parquet(feature_files[-1])
        labels = pd.read_parquet(label_files[-1])

        logger.info(f"✅ Loaded {len(features)} features, {len(labels)} labels")

        return features, labels

    def prepare_data(self, features: pd.DataFrame, labels: pd.DataFrame):
        """
        Prepare data for training

        Args:
            features: Features DataFrame
            labels: Labels DataFrame

        Returns:
            X_train, X_val, X_test, y_train, y_val, y_test
        """
        logger.info("🔧 Preparing data...")

        # Merge features and labels
        df = pd.merge(
            features,
            labels[['stock_id', 'timestamp', 'label']],
            on=['stock_id', 'timestamp'],
            how='inner'
        )

        logger.info(f"✅ Merged to {len(df)} samples")

        # Drop non-feature columns
        exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
        feature_cols = [col for col in df.columns if col not in exclude_cols]

        # Handle missing values
        X = df[feature_cols].fillna(0)
        y = df['label']

        # Temporal split (NOT random!)
        n = len(X)
        train_end = int(n * self.config.data.train_ratio)
        val_end = int(n * (self.config.data.train_ratio + self.config.data.val_ratio))

        X_train = X.iloc[:train_end]
        y_train = y.iloc[:train_end]

        X_val = X.iloc[train_end:val_end]
        y_val = y.iloc[train_end:val_end]

        X_test = X.iloc[val_end:]
        y_test = y.iloc[val_end:]

        logger.info(f"✅ Data split:")
        logger.info(f"  Train: {len(X_train)} samples")
        logger.info(f"  Val:   {len(X_val)} samples")
        logger.info(f"  Test:  {len(X_test)} samples")
        logger.info(f"  Positive class: {y_train.sum() / len(y_train) * 100:.1f}%")

        return X_train, X_val, X_test, y_train, y_val, y_test

    def train_model(self, model_name: str, X_train, y_train, X_val, y_val,
                   tune: bool = True, params: Optional[Dict] = None):
        """
        Train a single model

        Args:
            model_name: 'xgboost', 'catboost', or 'tcn'
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            tune: Whether to tune hyperparameters first
            params: Pre-defined params (skip tuning)

        Returns:
            Trained model
        """
        logger.info(f"🚂 Training {model_name}...")

        # Chronos is pretrained - skip tuning
        if model_name == 'chronos':
            tune = False

        # Start MLflow run
        with mlflow.start_run(run_name=f"{model_name}_training"):
            # Hyperparameter tuning
            if tune and params is None:
                tuner = HyperparameterTuner(self.config)
                params = tuner.tune_model(model_name, X_train, y_train, X_val, y_val)
                self.best_params[model_name] = params

            # Create model
            model_map = {
                'xgboost': XGBoostModel,
                'catboost': CatBoostModel,
                'tcn': TCNModel,
                'chronos': ChronosModel,
            }

            ModelClass = model_map[model_name]
            model = ModelClass(
                getattr(self.config, model_name),
                trial_params=params
            )

            # Train
            model.train(X_train, y_train, X_val, y_val)

            # Evaluate on validation set
            val_metrics = model.evaluate(X_val, y_val)
            logger.info(f"   Validation AUC: {val_metrics['auc']:.4f}")

            # Log metrics and params
            mlflow.log_metrics(val_metrics)
            if hasattr(model, 'get_params'):
                mlflow.log_params(model.get_params())

            # Save model
            model_dir = self.models_dir / model_name / 'latest'
            model.save(model_dir)

            self.models[model_name] = model

        return model

    def train_all_models(self, X_train, y_train, X_val, y_val, tune: bool = True):
        """
        Train all models

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            tune: Whether to tune hyperparameters

        Returns:
            Dict of trained models
        """
        logger.info("=" * 60)
        logger.info("Training All Models")
        logger.info("=" * 60)

        for model_name in self.config.ensemble.models:
            try:
                self.train_model(model_name, X_train, y_train, X_val, y_val, tune=tune)
            except Exception as e:
                logger.error(f"❌ Error training {model_name}: {e}")

        return self.models

    def evaluate_all_models(self, X_test, y_test) -> Dict[str, Dict[str, float]]:
        """
        Evaluate all models on test set

        Args:
            X_test: Test features
            y_test: Test labels

        Returns:
            Dict of metrics for each model
        """
        logger.info("📊 Evaluating all models...")

        all_metrics = {}

        for model_name, model in self.models.items():
            try:
                metrics = model.evaluate(X_test, y_test)
                all_metrics[model_name] = metrics

                logger.info(f"   {model_name.upper()}:")
                logger.info(f"     Accuracy:  {metrics['accuracy']*100:.1f}%")
                logger.info(f"     Precision: {metrics['precision']*100:.1f}%")
                logger.info(f"     Recall:    {metrics['recall']*100:.1f}%")
                logger.info(f"     AUC:       {metrics['auc']*100:.1f}%")

            except Exception as e:
                logger.error(f"❌ Error evaluating {model_name}: {e}")

        return all_metrics

    def get_feature_importance(self, model_name: str) -> pd.DataFrame:
        """
        Get feature importance for a model

        Args:
            model_name: Model name

        Returns:
            DataFrame with feature importance
        """
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not trained yet.")

        model = self.models[model_name]

        if hasattr(model, 'get_feature_importance'):
            return model.get_feature_importance()
        else:
            raise ValueError(f"Model {model_name} doesn't support feature importance")

    def save_all_models(self, version: str):
        """
        Save all models with version

        Args:
            version: Version string (e.g., "v1.0.0")
        """
        logger.info(f"💾 Saving all models as version {version}...")

        for model_name, model in self.models.items():
            model_dir = self.models_dir / model_name / version
            model.save(model_dir)

        logger.info(f"✅ All models saved as version {version}")
