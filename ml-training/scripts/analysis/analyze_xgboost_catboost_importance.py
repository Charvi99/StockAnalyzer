#!/usr/bin/env python3
"""
Feature Importance Analysis for XGBoost and CatBoost

Analyzes trained XGBoost and CatBoost models to show which features
(including news sentiment) are most important for predictions.
"""

import sys
sys.path.insert(0, '/app/ml_framework')

import pandas as pd
import numpy as np
from pathlib import Path
import json

def analyze_xgboost():
    """Analyze XGBoost feature importance"""
    print("\n" + "=" * 80)
    print("XGBOOST FEATURE IMPORTANCE")
    print("=" * 80)

    try:
        import xgboost as xgb

        model_path = Path('/app/outputs/models/xgboost/v1.0.0-latest/model.json')
        if not model_path.exists():
            print(f"Model not found: {model_path}")
            return None

        # Load model
        model = xgb.XGBClassifier()
        model.load_model(str(model_path))

        # Get feature importance (gain) - use scores() method for newer XGBoost
        importance = model.get_booster().get_score(importance_type='gain')

        # Create DataFrame with proper index handling
        importance_df = pd.DataFrame({
            'feature': list(importance.keys()),
            'importance': list(importance.values())
        }).sort_values('importance', ascending=False)

        # Create DataFrame
        importance_df = pd.DataFrame({
            'feature': importance.index,
            'importance': importance.values
        }).sort_values('importance', ascending=False)

        importance_df['importance_pct'] = importance_df['importance'] / importance_df['importance'].sum() * 100

        print(f"\nTotal features: {len(importance_df)}")

        # Check news features
        news_features = [f for f in importance_df['feature'] if f.startswith('news_')]
        news_importance = importance_df[importance_df['feature'].isin(news_features)]

        print(f"\nNews features: {len(news_features)}")
        print(f"News importance total: {news_importance['importance'].sum():.4f}")
        print(f"News importance percentage: {news_importance['importance_pct'].sum():.2f}%")

        print("\n" + "-" * 80)
        print("TOP 30 FEATURES BY IMPORTANCE (GAIN)")
        print("-" * 80)

        print(importance_df.head(30).to_string(index=False))

        print("\n" + "-" * 80)
        print("NEWS FEATURES IMPORTANCE")
        print("-" * 80)

        print(news_importance.sort_values('importance', ascending=False).to_string(index=False))

        return importance_df

    except Exception as e:
        print(f"Error analyzing XGBoost: {e}")
        return None


def analyze_catboost():
    """Analyze CatBoost feature importance"""
    print("\n" + "=" * 80)
    print("CATBOOST FEATURE IMPORTANCE")
    print("=" * 80)

    try:
        import catboost
        from catboost import CatBoostClassifier, Pool

        model_path = Path('/app/outputs/models/catboost/v1.0.0-latest/model.cbm')
        if not model_path.exists():
            print(f"Model not found: {model_path}")
            return None

        # Load model
        model = CatBoostClassifier()
        model.load_model(str(model_path))

        # Get feature importance (prediction values change)
        # CatBoost doesn't store feature names, so we need to provide feature count

        # Get feature names from a sample dataset
        features_path = Path('/app/outputs/features/dataset_20260211_103304/features.parquet')
        features_df = pd.read_parquet(features_path)

        exclude_cols = {'timestamp', 'stock_id', 'timestamp.1'}
        feature_cols = [col for col in features_df.columns if col not in exclude_cols]

        # Get importance
        importance = model.get_feature_importance()

        # Create DataFrame
        importance_df = pd.DataFrame({
            'feature': feature_cols,
            'importance': importance
        }).sort_values('importance', ascending=False)

        importance_df['importance_pct'] = importance_df['importance'] / importance_df['importance'].sum() * 100

        print(f"\nTotal features: {len(importance_df)}")

        # Check news features
        news_features = [f for f in feature_cols if f.startswith('news_')]
        news_importance = importance_df[importance_df['feature'].isin(news_features)]

        print(f"\nNews features: {len(news_features)}")
        print(f"News importance total: {news_importance['importance'].sum():.4f}")
        print(f"News importance percentage: {news_importance['importance_pct'].sum():.2f}%")

        print("\n" + "-" * 80)
        print("TOP 30 FEATURES BY IMPORTANCE")
        print("-" * 80)

        print(importance_df.head(30).to_string(index=False))

        print("\n" + "-" * 80)
        print("NEWS FEATURES IMPORTANCE")
        print("-" * 80)

        print(news_importance.sort_values('importance', ascending=False).to_string(index=False))

        return importance_df

    except Exception as e:
        print(f"Error analyzing CatBoost: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("=" * 80)
    print("FEATURE IMPORTANCE ANALYSIS")
    print("=" * 80)
    print("Dataset: dataset_20260211_103304 (with correct news features)")
    print()

    # Analyze both models
    xgb_importance = analyze_xgboost()
    cat_importance = analyze_catboost()

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if xgb_importance is not None:
        news_imp_xgb = xgb_importance[xgb_importance['feature'].str.startswith('news_')]
        print(f"\nXGBoost: News features rank from {len(xgb_importance)} features")
        print(f"  Total news features: 20")
        print(f"  Non-zero news features: {(news_imp_xgb['importance'] > 0).sum()}")
        print(f"  Top news feature: {news_imp_xgb.nlargest(1, 'importance')['feature'].iloc[0]}")

    if cat_importance is not None:
        news_imp_cat = cat_importance[cat_importance['feature'].str.startswith('news_')]
        print(f"\nCatBoost: News features rank from {len(cat_importance)} features")
        print(f"  Total news features: 20")
        print(f"  Non-zero news features: {(news_imp_cat['importance'] > 0).sum()}")
        print(f"  Top news feature: {news_imp_cat.nlargest(1, 'importance')['feature'].iloc[0]}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
