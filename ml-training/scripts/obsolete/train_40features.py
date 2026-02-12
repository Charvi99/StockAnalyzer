#!/usr/bin/env python3
"""
Training with 40-Feature Dataset

This script:
1. Loads the new 40-feature dataset
2. Fixes data types (encodes string columns)
3. Runs trials for selected models
4. Creates ensemble

Usage:
    python train_40features.py                          # Train all models with 5 trials
    python train_40features.py --models catboost xgboost # Train only specific models
    python train_40features.py --trials 50              # Use 50 trials instead of default
"""
import sys
import os
import logging
import argparse
from pathlib import Path

sys.path.insert(0, '/app/ml-framework')
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from ml_framework.config import Config, DEFAULT_CONFIG
from ml_framework.trainer import ModelTrainer
from ml_framework.ensemble import Ensemble
from ml_framework.resource_manager import get_resource_manager

# Available models
AVAILABLE_MODELS = ['catboost', 'xgboost', 'tcn', 'chronos']


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Train StockAnalyzer ML models with 40 features',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train_40features.py                          # Train all models (5 trials)
  python train_40features.py --models catboost xgboost # Train only specific models
  python train_40features.py --trials 50              # Use 50 trials instead of default
  python train_40features.py --models tcn --trials 10   # Quick train TCN with 10 trials
        """
    )

    parser.add_argument(
        '--models',
        nargs='+',
        choices=AVAILABLE_MODELS,
        default=None,
        help='Models to train (default: all models). Choose from: %(choices)s'
    )

    parser.add_argument(
        '--trials',
        type=int,
        default=None,
        help='Number of Optuna trials (overrides config default)'
    )

    return parser.parse_args()


def main():
    """Main training function"""
    args = parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    global logger
    logger = logging.getLogger(__name__)

    print("=" * 70)
    print(" " * 18)
    print("StockAnalyzer ML Training - 40 Features")
    print(" " * 18)
    print("=" * 70)

    # Initialize config
    config = DEFAULT_CONFIG

    # Override trials if specified
    if args.trials:
        config.training.n_trials = args.trials
        logger.info(f"Using {args.trials} trials for all models")

    # Set models to train
    models_to_train = args.models if args.models else AVAILABLE_MODELS

    config.ensemble.models = models_to_train
    config.data.features_dir = Path('/app/outputs/features')

    # Initialize trainer
    logger.info("Initializing trainer...")
    trainer = ModelTrainer(config)

    # Hardware Detection
    print("\n" + "=" * 70)
    print("HARDWARE DETECTION")
    print("=" * 70)

    resource_manager = get_resource_manager()
    print(f"\n{resource_manager}")

    # Load data
    logger.info("=" * 70)
    logger.info("LOADING 40-FEATURE DATASET")
    logger.info("=" * 70)

    features_path = "/app/outputs/features/features_20260203_103015.parquet"
    labels_path = "/app/outputs/features/labels_20260203_103015.parquet"

    if not os.path.exists(features_path):
        raise FileNotFoundError(f"40-feature dataset not found: {features_path}")

    logger.info(f"Loading features from: {features_path}")
    features = pd.read_parquet(features_path)
    labels = pd.read_parquet(labels_path)

    logger.info(f"Features shape: {features.shape}")
    logger.info(f"Labels shape: {labels.shape}")

    # Identify and fix string columns in features
    string_cols = features.select_dtypes(include=['object']).columns.tolist()
    logger.info(f"String columns to encode: {string_cols}")

    for col in string_cols:
        if col == 'macd_trend':
            logger.info(f"  Encoding {col}: SOLD=-1, HOLD=0, BUY=1")
            encoding = {'SOLD': -1, 'HOLD': 0, 'BUY': 1}
            features[col] = features[col].map(encoding).fillna(0)
        else:
            logger.info(f"  Converting {col} to numeric")
            features[col] = pd.to_numeric(features[col], errors='coerce').fillna(0)

    # Ensure all columns are numeric (except identifiers)
    for col in features.columns:
        if col in ['timestamp', 'stock_id']:
            continue
        if features[col].dtype == 'object':
            logger.warning(f"  Column {col} still has object type, converting to float")
            features[col] = pd.to_numeric(features[col], errors='coerce').fillna(0)

    # Convert to float32 for efficiency (skip identifiers)
    for col in features.columns:
        if col in ['timestamp', 'stock_id']:
            continue
        features[col] = features[col].astype('float32')

    # Remove any remaining NaN or Inf values
    features = features.replace([np.inf, -np.inf], np.nan).fillna(0)

    logger.info(f"Clean dataset shape: {features.shape}")
    logger.info(f"Positive class: {labels['label'].mean()*100:.1f}%")

    # Prepare data (train/val/test split) - this handles merge and split
    print("\n" + "=" * 70)
    print("PREPARING DATA")
    print("=" * 70)

    X_train, X_val, X_test, y_train, y_val, y_test = trainer.prepare_data(features, labels)

    print(f"\nModels to train: {', '.join(models_to_train)}")
    print(f"Trials per model: {config.training.n_trials}")
    print(f"Total trials: {len(models_to_train) * config.training.n_trials}")

    # Train all models using trainer's method
    print("\n" + "=" * 70)
    print("TRAINING PHASE")
    print("=" * 70)

    trainer.train_all_models(X_train, y_train, X_val, y_val, tune=True)

    # Evaluate all models
    print("\n" + "=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)

    all_metrics = trainer.evaluate_all_models(X_test, y_test)

    # Print summary
    print("\n" + "=" * 70)
    print("MODEL COMPARISON")
    print("=" * 70)

    for model_name, metrics in all_metrics.items():
        print(f"\n{model_name.upper()}:")
        print(f"  Accuracy:  {metrics.get('accuracy', 'N/A')*100:.1f}%")
        print(f"  Precision: {metrics.get('precision', 'N/A')*100:.1f}%")
        print(f"  Recall:    {metrics.get('recall', 'N/A')*100:.1f}%")
        print(f"  AUC:       {metrics.get('auc', 'N/A')*100:.1f}%")

    # Create ensemble if we have at least 2 models
    print("\n" + "=" * 70)
    if len(trainer.models) > 1:
        print("ENSEMBLE CREATION")
        print("=" * 70)

        try:
            ensemble = Ensemble(trainer.models, method=config.ensemble.method)

            # Train meta-learner if using stacking
            if config.ensemble.method == "stacking":
                ensemble.train_meta_learner(X_val, y_val)
            elif config.ensemble.method == "weighted_average":
                ensemble.optimize_weights(X_val, y_val)

            # Evaluate ensemble
            ensemble_pred = ensemble.predict(X_test)
            ensemble_proba = ensemble.predict_proba(X_test)[:, 1]

            from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

            ensemble_metrics = {
                'accuracy': accuracy_score(y_test, ensemble_pred),
                'precision': precision_score(y_test, ensemble_pred, zero_division=0),
                'recall': recall_score(y_test, ensemble_pred, zero_division=0),
                'auc': roc_auc_score(y_test, ensemble_proba)
            }

            print(f"\nENSEMBLE PERFORMANCE:")
            print(f"  Accuracy:  {ensemble_metrics['accuracy']*100:.1f}%")
            print(f"  Precision: {ensemble_metrics['precision']*100:.1f}%")
            print(f"  Recall:    {ensemble_metrics['recall']*100:.1f}%")
            print(f"  AUC:       {ensemble_metrics['auc']*100:.1f}%")

        except Exception as e:
            logger.error(f"Error creating ensemble: {e}", exc_info=True)
    else:
        print("ENSEMBLE CREATION SKIPPED")
        print("=" * 70)
        print("Not enough models trained successfully")

    print("\n" + "=" * 70)
    print("TRAINING COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
