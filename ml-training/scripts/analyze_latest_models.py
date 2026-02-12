#!/usr/bin/env python3
"""
Feature Importance Analysis for Latest Trained Models

Analyzes feature importance from:
- CatBoost model (outputs/models/catboost/auc/)
- XGBoost model (outputs/models/xgboost/auc/)
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml_framework.models.catboost_model import CatBoostModel
from ml_framework.models.xgboost_model import XGBoostModel
from ml_framework.config import CatBoostConfig, XGBoostConfig


def load_model_metadata(model_path: Path) -> dict:
    """Load model metadata from JSON file"""
    metadata_file = model_path / "metadata.json"
    with open(metadata_file, 'r') as f:
        return json.load(f)


def load_features(features_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load features and labels from the dataset directory"""
    features_df = pd.read_parquet(features_dir / "features.parquet")
    labels_df = pd.read_parquet(features_dir / "labels_3class.parquet")
    return features_df, labels_df


def analyze_catboost_importance(model_path: Path, metadata: dict) -> pd.DataFrame:
    """Analyze CatBoost feature importance"""
    print("\n" + "=" * 80)
    print("CATBOOST FEATURE IMPORTANCE")
    print("=" * 80)

    # Load model
    config = CatBoostConfig()
    config.classes_count = metadata.get('params', {}).get('classes_count', 3)

    model = CatBoostModel(config)
    model.load_model(model_path / "model.cbm")

    # Get feature importance
    importance = model.model.get_feature_importance()

    importance_df = pd.DataFrame({
        'feature': metadata['feature_cols'],
        'importance': importance,
        'importance_pct': importance / importance.sum() * 100
    }).sort_values('importance', ascending=False)

    print(f"\nTotal features: {len(importance_df)}")
    print(f"Features with importance > 1%: {(importance_df['importance_pct'] > 1).sum()}")
    print(f"Features with importance > 0.5%: {(importance_df['importance_pct'] > 0.5).sum()}")
    print(f"\nTop 30 features:")
    print(importance_df.head(30).to_string(index=False))

    return importance_df


def analyze_xgboost_importance(model_path: Path, metadata: dict) -> pd.DataFrame:
    """Analyze XGBoost feature importance"""
    print("\n" + "=" * 80)
    print("XGBOOST FEATURE IMPORTANCE")
    print("=" * 80)

    # Load model
    config = XGBoostConfig()
    config.num_class = metadata.get('params', {}).get('num_class', 3)

    model = XGBoostModel(config)
    model.load_model(model_path / "model.json")

    # Get feature importance (weight-based)
    importance = model.model.feature_importances_

    importance_df = pd.DataFrame({
        'feature': metadata['feature_cols'],
        'importance': importance,
        'importance_pct': importance / importance.sum() * 100
    }).sort_values('importance', ascending=False)

    print(f"\nTotal features: {len(importance_df)}")
    print(f"Features with importance > 1%: {(importance_df['importance_pct'] > 1).sum()}")
    print(f"Features with importance > 0.5%: {(importance_df['importance_pct'] > 0.5).sum()}")
    print(f"\nTop 30 features:")
    print(importance_df.head(30).to_string(index=False))

    return importance_df


def categorize_features(feature_names: List[str]) -> Dict[str, List[str]]:
    """Categorize features by type"""
    categories = {
        'price_volume': [],
        'moving_averages': [],
        'momentum': [],
        'volatility': [],
        'insider_trading': [],
        'news_sentiment': [],
        'market_context': [],
        'pattern': [],
        'other': []
    }

    price_volume_keywords = ['open', 'high', 'low', 'close', 'volume', 'tp_volume']
    ma_keywords = ['ma_', 'ema', 'sma', 'kama', 'price_above_ma', 'above']
    momentum_keywords = ['rsi', 'macd', 'momentum', 'roc', 'cmo', 'stoch', 'willr', 'ppo', 'apo']
    volatility_keywords = ['atr', 'volatility', 'stddev', 'bb_', 'kc_', 'natr', 'chop']
    insider_keywords = ['insider', 'ceo_', 'cto_', 'cfo_', 'cluster']
    news_keywords = ['news_', 'sentiment']
    market_keywords = ['spy_', 'market_regime', 'stock_vs_spy']
    pattern_keywords = ['gap_', 'consecutive', 'bop', 'adosc', 'psar', 'aroon']

    for feature in feature_names:
        feature_lower = feature.lower()
        categorized = False

        for keyword in price_volume_keywords:
            if keyword in feature_lower:
                categories['price_volume'].append(feature)
                categorized = True
                break

        if not categorized:
            for keyword in ma_keywords:
                if keyword in feature_lower:
                    categories['moving_averages'].append(feature)
                    categorized = True
                    break

        if not categorized:
            for keyword in momentum_keywords:
                if keyword in feature_lower:
                    categories['momentum'].append(feature)
                    categorized = True
                    break

        if not categorized:
            for keyword in volatility_keywords:
                if keyword in feature_lower:
                    categories['volatility'].append(feature)
                    categorized = True
                    break

        if not categorized:
            for keyword in insider_keywords:
                if keyword in feature_lower:
                    categories['insider_trading'].append(feature)
                    categorized = True
                    break

        if not categorized:
            for keyword in news_keywords:
                if keyword in feature_lower:
                    categories['news_sentiment'].append(feature)
                    categorized = True
                    break

        if not categorized:
            for keyword in market_keywords:
                if keyword in feature_lower:
                    categories['market_context'].append(feature)
                    categorized = True
                    break

        if not categorized:
            for keyword in pattern_keywords:
                if keyword in feature_lower:
                    categories['pattern'].append(feature)
                    categorized = True
                    break

        if not categorized:
            categories['other'].append(feature)

    return categories


def compare_feature_importance(catboost_df: pd.DataFrame, xgboost_df: pd.DataFrame):
    """Compare feature importance between models"""
    print("\n" + "=" * 80)
    print("MODEL COMPARISON")
    print("=" * 80)

    # Merge dataframes
    merged = catboost_df[['feature', 'importance_pct']].rename(
        columns={'importance_pct': 'catboost_pct'}
    ).merge(
        xgboost_df[['feature', 'importance_pct']].rename(
            columns={'importance_pct': 'xgboost_pct'}
        ),
        on='feature',
        how='outer'
    ).fillna(0)

    merged['avg_pct'] = (merged['catboost_pct'] + merged['xgboost_pct']) / 2
    merged['diff_pct'] = abs(merged['catboost_pct'] - merged['xgboost_pct'])
    merged = merged.sort_values('avg_pct', ascending=False)

    print(f"\nTop 30 features (by average importance):")
    print(merged.head(30).to_string(index=False))

    print(f"\nTop 10 CatBoost-only features:")
    catboost_only = merged[merged['xgboost_pct'] == 0].head(10)
    print(catboost_only[['feature', 'catboost_pct']].to_string(index=False))

    print(f"\nTop 10 XGBoost-only features:")
    xgboost_only = merged[merged['catboost_pct'] == 0].head(10)
    print(xgboost_only[['feature', 'xgboost_pct']].to_string(index=False))

    print(f"\nTop 10 features with largest disagreement:")
    print(merged.nlargest(10, 'diff_pct')[['feature', 'catboost_pct', 'xgboost_pct', 'diff_pct']].to_string(index=False))

    return merged


def analyze_by_category(importance_df: pd.DataFrame, model_name: str):
    """Analyze feature importance by category"""
    print(f"\n{model_name} - Feature Importance by Category")
    print("-" * 80)

    categories = categorize_features(importance_df['feature'].tolist())

    for category, features in categories.items():
        if features:
            cat_importance = importance_df[importance_df['feature'].isin(features)]
            total_importance = cat_importance['importance_pct'].sum()
            print(f"\n{category.replace('_', ' ').title()}: {len(features)} features, {total_importance:.2f}% total importance")
            print(f"  Top 5: {', '.join(cat_importance.nlargest(5, 'importance_pct')['feature'].tolist())}")


def save_results(catboost_df: pd.DataFrame, xgboost_df: pd.DataFrame, merged_df: pd.DataFrame, output_dir: Path):
    """Save analysis results to CSV files"""
    output_dir.mkdir(parents=True, exist_ok=True)

    catboost_df.to_csv(output_dir / "catboost_feature_importance.csv", index=False)
    xgboost_df.to_csv(output_dir / "xgboost_feature_importance.csv", index=False)
    merged_df.to_csv(output_dir / "merged_feature_importance.csv", index=False)

    print(f"\n✅ Results saved to {output_dir}/")


def main():
    # Paths
    base_dir = Path("/app/ml-training")
    outputs_dir = base_dir / "outputs"
    models_dir = outputs_dir / "models"
    analysis_dir = outputs_dir / "analysis"

    # Model paths
    catboost_path = models_dir / "catboost" / "auc"
    xgboost_path = models_dir / "xgboost" / "auc"

    # Check models exist
    if not catboost_path.exists():
        print(f"❌ CatBoost model not found at {catboost_path}")
        return

    if not xgboost_path.exists():
        print(f"❌ XGBoost model not found at {xgboost_path}")
        return

    # Load metadata
    catboost_metadata = load_model_metadata(catboost_path)
    xgboost_metadata = load_model_metadata(xgboost_path)

    print(f"CatBoost model: MultiClass, {catboost_metadata['params'].get('classes_count', 3)} classes")
    print(f"XGBoost model: multi:softmax, {xgboost_metadata['params'].get('num_class', 3)} classes")

    # Analyze feature importance
    catboost_importance = analyze_catboost_importance(catboost_path, catboost_metadata)
    xgboost_importance = analyze_xgboost_importance(xgboost_path, xgboost_metadata)

    # Category analysis
    analyze_by_category(catboost_importance, "CATBOOST")
    analyze_by_category(xgboost_importance, "XGBOOST")

    # Compare models
    merged_importance = compare_feature_importance(catboost_importance, xgboost_importance)

    # Save results
    save_results(catboost_importance, xgboost_importance, merged_importance, analysis_dir)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
