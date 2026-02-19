"""
Model Training Orchestration

Handles training, evaluation, and logging for all models
"""
import sys
sys.path.insert(0, '/backend')

from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd
import polars as pl
import numpy as np
import mlflow
import logging

from ml_framework.config import Config
from ml_framework.models import (
    XGBoostModel, CatBoostModel, TabNetModel,
    AutoGluonModel
)
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
        """Load features and labels from parquet files using Polars"""
        logger.info("📂 Loading data...")

        base_path = self.config.data.base_path

        # Check if explicit paths are configured
        if self.config.data.dataset_dir and self.config.data.labels_file:
            # Use explicit paths from config
            dataset_dir = Path(base_path) / self.config.data.dataset_dir
            features_path = dataset_dir / "features.parquet"
            labels_path = dataset_dir / self.config.data.labels_file

            if not features_path.exists():
                raise FileNotFoundError(f"Features file not found: {features_path}")
            if not labels_path.exists():
                raise FileNotFoundError(f"Labels file not found: {labels_path}")

            logger.info(f"   Using explicit paths from config:")
            logger.info(f"   Dataset: {dataset_dir}")
            logger.info(f"   Labels: {self.config.data.labels_file}")

            # Load with Polars (faster)
            features = pl.read_parquet(features_path)
            labels = pl.read_parquet(labels_path)
        else:
            # Auto-detect latest files
            features_dir = Path(base_path) / self.config.data.features_path

            # Find latest files - support both old and new naming, recursive search
            feature_files = sorted(features_dir.glob('**/*.parquet')) if features_dir.exists() else []

            # Labels are co-located with features files in same subdirectories
            label_files = sorted(features_dir.glob('**/labels_*.parquet')) if features_dir.exists() else []

            if not feature_files:
                raise FileNotFoundError(f"No feature files found in {features_dir}. Run feature engineering first.")
            if not label_files:
                raise FileNotFoundError(f"No label files found. Run create_labels.py first.")

            logger.info(f"   Auto-detected latest files:")
            logger.info(f"   Features: {feature_files[-1]}")
            logger.info(f"   Labels: {label_files[-1]}")

            # Load with Polars (faster)
            features = pl.read_parquet(feature_files[-1])
            labels = pl.read_parquet(label_files[-1])

        logger.info(f"✅ Loaded {features.height} features, {labels.height} labels")

        return features, labels

    def prepare_data(self, features: pl.DataFrame, labels: pl.DataFrame):
        """
        Prepare data for training using Polars

        Args:
            features: Features Polars DataFrame
            labels: Labels Polars DataFrame

        Returns:
            X_train, X_val, X_test, y_train, y_val, y_test (as pandas for model compatibility)
        """
        logger.info("🔧 Preparing data...")

        # Determine which label column to use
        if 'label' in labels.columns:
            label_col = 'label'
        elif 'label_20d' in labels.columns:
            label_col = 'label_20d'
            labels = labels.with_columns(pl.col('label_20d').alias('label'))
            label_col = 'label'
        else:
            raise ValueError("No valid label column found in labels file")

        # Normalize timestamps (Polars way)
        features = features.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.truncate('1d')
        )
        labels = labels.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.truncate('1d')
        )

        # Merge features and labels (Polars join is faster)
        df = features.join(
            labels.select(['stock_id', 'timestamp', label_col]),
            on=['stock_id', 'timestamp'],
            how='inner'
        )

        logger.info(f"✅ Merged to {df.height} samples")

        # CRITICAL: Sort by timestamp for proper temporal split
        df = df.sort('timestamp')

        # Log date range
        min_ts = df['timestamp'].min()
        max_ts = df['timestamp'].max()
        logger.info(f"   Date range: {min_ts} to {max_ts}")

        # Drop non-feature columns
        exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
        feature_cols = [col for col in df.columns if col not in exclude_cols]

        # Handle missing values (Polars way)
        df = df.fill_null(0)

        # Temporal split (NOT random!)
        n = df.height
        train_end = int(n * self.config.data.train_ratio)
        val_end = int(n * (self.config.data.train_ratio + self.config.data.val_ratio))

        # Split data (Polars slicing)
        X_train_pl = df.slice(0, train_end).select(feature_cols)
        y_train_pl = df.slice(0, train_end).select('label')

        X_val_pl = df.slice(train_end, val_end - train_end).select(feature_cols)
        y_val_pl = df.slice(train_end, val_end - train_end).select('label')

        X_test_pl = df.slice(val_end, n - val_end).select(feature_cols)
        y_test_pl = df.slice(val_end, n - val_end).select('label')

        # Convert to pandas for model compatibility
        X_train = X_train_pl.to_pandas()
        y_train = y_train_pl.to_pandas()['label'].values

        X_val = X_val_pl.to_pandas()
        y_val = y_val_pl.to_pandas()['label'].values

        X_test = X_test_pl.to_pandas()
        y_test = y_test_pl.to_pandas()['label'].values

        # Log split info
        train_end_ts = df.slice(train_end - 1, 1).select('timestamp').item()
        val_end_ts = df.slice(val_end - 1, 1).select('timestamp').item()
        test_start_ts = df.slice(val_end, 1).select('timestamp').item()

        logger.info(f"✅ Temporal data split:")
        logger.info(f"  Train: {len(X_train)} samples (up to {train_end_ts})")
        logger.info(f"  Val:   {len(X_val)} samples ({df.slice(train_end, 1).select('timestamp').item()} to {val_end_ts})")
        logger.info(f"  Test:  {len(X_test)} samples (from {test_start_ts})")
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
                'tabnet': TabNetModel,
                'autogluon': AutoGluonModel,
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
