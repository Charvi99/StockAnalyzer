"""
Train XGBoost Model

This script trains an XGBoost classifier on the engineered features.

Usage:
    python 03_train_xgboost.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
import mlflow
import mlflow.xgboost

# Paths
OUTPUTS_DIR = Path('/app/outputs')
FEATURES_DIR = OUTPUTS_DIR / 'features'
MODELS_DIR = OUTPUTS_DIR / 'models'


def load_data():
    """Load features and labels"""
    print("📂 Loading data...")

    # Find latest features and labels
    feature_files = sorted(FEATURES_DIR.glob('features_*.parquet'))
    label_files = sorted(FEATURES_DIR.glob('labels_*.parquet'))

    if not feature_files:
        raise FileNotFoundError("No feature files found. Run 01_feature_engineering.py first")

    if not label_files:
        raise FileNotFoundError("No label files found. Run 02_create_labels.py first")

    features = pd.read_parquet(feature_files[-1])
    labels = pd.read_parquet(label_files[-1])

    print(f"✅ Loaded {len(features)} features, {len(labels)} labels")

    return features, labels


def merge_features_labels(features, labels):
    """Merge features and labels on stock_id and timestamp"""
    print("🔗 Merging features and labels...")

    # Merge
    df = pd.merge(
        features,
        labels[['stock_id', 'timestamp', 'label']],
        on=['stock_id', 'timestamp'],
        how='inner'
    )

    print(f"✅ Merged to {len(df)} samples")

    return df


def prepare_features(df):
    """Prepare feature matrix X and target y"""
    print("🔧 Preparing features...")

    # Columns to exclude
    exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}

    # Get feature columns
    feature_cols = [col for col in df.columns if col not in exclude_cols]

    # Handle missing values
    X = df[feature_cols].fillna(0)
    y = df['label']

    print(f"✅ Features: {X.shape}")
    print(f"  Samples: {X.shape[0]}")
    print(f"  Feature columns: {X.shape[1]}")
    print(f"  Positive class: {y.sum()} ({y.sum()/len(y)*100:.1f}%)")

    return X, y, feature_cols


def temporal_train_test_split(X, y, train_ratio=0.7, val_ratio=0.15):
    """
    Split data temporally (NOT random!)

    This prevents data leakage from future.
    """
    print("✂️  Splitting data temporally...")

    n = len(X)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    X_train = X.iloc[:train_end]
    y_train = y.iloc[:train_end]

    X_val = X.iloc[train_end:val_end]
    y_val = y.iloc[train_end:val_end]

    X_test = X.iloc[val_end:]
    y_test = y.iloc[val_end:]

    print(f"✅ Data split:")
    print(f"  Train: {len(X_train)} ({X_train.index[0]} to {X_train.index[-1]})")
    print(f"  Val:   {len(X_val)} ({X_val.index[0]} to {X_val.index[-1]})")
    print(f"  Test:  {len(X_test)} ({X_test.index[0]} to {X_test.index[-1]})")

    return X_train, X_val, X_test, y_train, y_val, y_test


def train_xgboost(X_train, y_train, X_val, y_val):
    """Train XGBoost model"""
    print("🚂 Training XGBoost model...")

    # Calculate scale_pos_weight for class imbalance
    scale_pos_weight = (len(y_train) - y_train.sum()) / y_train.sum()

    model = XGBClassifier(
        max_depth=6,
        learning_rate=0.01,
        n_estimators=2000,
        subsample=0.7,
        colsample_bytree=0.7,
        reg_lambda=1.0,
        reg_alpha=0.1,
        scale_pos_weight=scale_pos_weight,
        eval_metric='auc',
        early_stopping_rounds=100,
        n_jobs=-1,
        random_state=42
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False
    )

    print(f"✅ Training complete. Best iteration: {model.best_iteration}")

    return model


def evaluate_model(model, X_test, y_test):
    """Evaluate model on test set"""
    print("📊 Evaluating model...")

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_prob)

    print(f"\n✅ Test Set Performance:")
    print(f"  Accuracy:  {accuracy*100:.1f}%")
    print(f"  Precision: {precision*100:.1f}%")
    print(f"  Recall:    {recall*100:.1f}%")
    print(f"  AUC:       {auc*100:.1f}%")

    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'auc': auc
    }


def save_model(model, feature_cols):
    """Save trained model"""
    print("💾 Saving model...")

    # Create versioned directory
    version = f"v1.0.0_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    model_dir = MODELS_DIR / 'xgboost' / version
    model_dir.mkdir(parents=True, exist_ok=True)

    # Save model
    model.save_model(str(model_dir / 'model.json'))

    # Save feature columns
    with open(model_dir / 'feature_cols.txt', 'w') as f:
        f.write('\n'.join(feature_cols))

    # Also save to latest (for easy loading)
    latest_dir = MODELS_DIR / 'xgboost' / 'latest'
    latest_dir.mkdir(parents=True, exist_ok=True)
    model.save_model(str(latest_dir / 'model.json'))
    with open(latest_dir / 'feature_cols.txt', 'w') as f:
        f.write('\n'.join(feature_cols))

    print(f"✅ Model saved to {model_dir}")
    print(f"✅ Also saved to {latest_dir}")


def main():
    """Main training pipeline"""
    print("=" * 60)
    print("StockAnalyzer ML - XGBoost Training")
    print("=" * 60)

    # Create directories
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Start MLflow run
    mlflow.set_experiment("stockanalyzer_xgboost")
    with mlflow.start_run():
        # Load data
        features, labels = load_data()
        df = merge_features_labels(features, labels)
        X, y, feature_cols = prepare_features(df)

        # Split data
        X_train, X_val, X_test, y_train, y_val, y_test = temporal_train_test_split(X, y)

        # Train model
        model = train_xgboost(X_train, y_train, X_val, y_val)

        # Evaluate
        metrics = evaluate_model(model, X_test, y_test)

        # Log to MLflow
        mlflow.log_metrics(metrics)
        mlflow.log_params({
            'max_depth': 6,
            'learning_rate': 0.01,
            'n_estimators': model.best_iteration
        })

        # Save model
        save_model(model, feature_cols)

    print("\n✅ Training complete!")


if __name__ == "__main__":
    main()
