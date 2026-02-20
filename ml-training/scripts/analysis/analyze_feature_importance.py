"""
Feature Importance Analysis for TabNet and AutoGluon Models
"""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, '/app')

from ml_framework.models.tabnet_model import TabNetModel
from ml_framework.config import TabNetConfig
from pathlib import Path
import torch

def analyze_autogluon_feature_importance():
    """Analyze AutoGluon feature importance"""
    print("="*80)
    print("AUTOGLUON FEATURE IMPORTANCE")
    print("="*80)

    from autogluon.tabular import TabularPredictor

    predictor = TabularPredictor.load('/tmp/autogluon_adgsni6w')

    features_df = pd.read_parquet('/app/outputs/features/dataset_for_autogluon/features.parquet')
    labels_df = pd.read_parquet('/app/outputs/features/dataset_for_autogluon/labels_3class.parquet')

    sample_size = min(10000, len(features_df))
    indices = np.random.choice(len(features_df), sample_size, replace=False)
    test_data = features_df.iloc[indices].copy()
    test_data['label'] = labels_df.iloc[indices]['label'].values
    test_data = test_data.reset_index(drop=True)

    print("Computing feature importance...")
    importance = predictor.feature_importance(test_data)

    print("\nTop 30:")
    print(importance.head(30))
    print(f"\nTotal: {len(importance)}")
    print(f"> 0.01: {(importance['importance'] > 0.01).sum()}")

    importance.to_csv('/app/autogluon_feature_importance.csv')
    print("✅ Saved to autogluon_feature_importance.csv")
    return importance

def analyze_tabnet_feature_importance():
    """Analyze TabNet feature importance"""
    print("\n" + "="*80)
    print("TABNET FEATURE IMPORTANCE")
    print("="*80)

    features_df = pd.read_parquet('/app/outputs/features/dataset_backtest_tabnet_20260210_072155/features.parquet')
    labels_df = pd.read_parquet('/app/outputs/features/dataset_backtest_tabnet_20260210_072155/labels_3class.parquet')

    non_feature_cols = ['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'stock_id']
    feature_cols = [c for c in features_df.columns if c not in non_feature_cols]

    X = features_df[feature_cols].values
    y = labels_df['label'].values

    print(f"Features: {X.shape}")

    model = TabNetModel(TabNetConfig())
    model.load_model(Path('/app/outputs/models/tabnet/latest/tabnet_model.zip.zip'))

    sample_idx = np.random.choice(len(X), min(10000, len(X)), replace=False)
    X_sample = X[sample_idx]

    explain_matrix, masks = model.model.explain(X_sample)
    feature_importance = np.abs(explain_matrix).sum(axis=(0, 1))
    feature_importance = feature_importance / feature_importance.sum() * 100

    importance_df = pd.DataFrame({
        'feature': feature_cols,
        'importance': feature_importance
    }).sort_values('importance', ascending=False)

    print("\nTop 30:")
    print(importance_df.head(30))
    print(f"\nTotal: {len(importance_df)}")

    importance_df.to_csv('/app/tabnet_feature_importance.csv', index=False)
    print("✅ Saved to tabnet_feature_importance.csv")
    return importance_df

if __name__ == '__main__':
    autogluon_imp = analyze_autogluon_feature_importance()
    tabnet_imp = analyze_tabnet_feature_importance()

    # Compare
    print("\n" + "="*80)
    print("COMPARISON")
    print("="*80)

    top_autogluon = set(autogluon_imp.head(20).index)
    top_tabnet = set(tabnet_imp.head(20)['feature'])

    print(f"\nAutoGluon-only top 20:")
    for f in (top_autogluon - top_tabnet):
        print(f"  - {f}")

    print(f"\nTabNet-only top 20:")
    for f in (top_tabnet - top_autogluon):
        print(f"  - {f}")
