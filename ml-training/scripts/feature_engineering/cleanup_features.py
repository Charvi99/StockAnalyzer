"""
Feature Cleanup Script

Keeps only top N features by importance to reduce noise and improve training.
"""
import pandas as pd
import json
from pathlib import Path


def load_feature_importance(importance_file):
    """Load feature importance from CSV"""
    df = pd.read_csv(importance_file)
    return df


def get_top_features(importance_df, top_n=100, preserve_insider=True):
    """
    Get top N features by importance, optionally preserving all insider features.

    Args:
        importance_df: DataFrame with feature importance
        top_n: Number of top features to keep
        preserve_insider: If True, keep all insider features even if not in top N

    Returns:
        List of features to keep
    """
    # Identify insider features
    if preserve_insider:
        insider_features = importance_df[
            importance_df['feature'].str.startswith('insider_')
        ]['feature'].tolist()
        print(f"📊 Found {len(insider_features)} insider features to preserve")
    else:
        insider_features = []

    # Sort by mean_importance descending
    sorted_df = importance_df.sort_values('mean_importance', ascending=False)

    # Get top N features
    top_features = sorted_df.head(top_n)['feature'].tolist()

    # Add insider features not already in top N
    for feature in insider_features:
        if feature not in top_features:
            top_features.append(feature)

    return top_features, sorted_df.head(top_n)


def save_feature_lists(features_to_keep, output_dir):
    """Save feature lists to files"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save features to keep
    keep_file = output_dir / f"features_to_keep_top{len(features_to_keep)}.txt"
    with open(keep_file, 'w') as f:
        for feature in features_to_keep:
            f.write(f"{feature}\n")

    print(f"✅ Saved {len(features_to_keep)} features to {keep_file}")

    return keep_file


def main():
    print("=" * 70)
    print("FEATURE CLEANUP - Keep Top 100 Features")
    print("=" * 70)

    # Find latest feature importance file
    analysis_dir = Path("/app/outputs/analysis")
    importance_files = sorted(analysis_dir.glob("feature_importance_*.csv"))

    if not importance_files:
        print("❌ No feature importance files found!")
        print("   Run: python scripts/analyze_feature_importance.py")
        return

    latest_file = importance_files[-1]
    print(f"📂 Using: {latest_file.name}")

    # Load feature importance
    df = load_feature_importance(latest_file)
    print(f"   Loaded {len(df)} features")

    # Get top 100 features + all insider features
    top_n = 100
    top_features, top_df = get_top_features(df, top_n, preserve_insider=True)

    # Count insider features
    insider_count = sum(1 for f in top_features if f.startswith('insider_'))
    non_insider_count = len(top_features) - insider_count

    print(f"\n✅ Selected {len(top_features)} features:")
    print(f"   Top {top_n} by importance: {non_insider_count}")
    print(f"   Insider features preserved: {insider_count}")
    print(f"   Total features: {len(top_features)}")
    print(f"   Cumulative importance (top {top_n}): {top_df['mean_importance'].sum():.1%}")

    print(f"\n   Top 20 features:")
    for i, row in top_df.head(20).iterrows():
        print(f"      {i+1:2d}. {row['feature']:30s} {row['mean_importance']:>6.2%}")

    print(f"\n   Insider features ({insider_count}):")
    insider_features = [f for f in top_features if f.startswith('insider_')]
    for feature in sorted(insider_features):
        # Find importance for this feature
        importance = df[df['feature'] == feature]['mean_importance'].values[0]
        print(f"      - {feature:40s} {importance:>6.2%}")

    # Save feature list
    keep_file = save_feature_lists(top_features, analysis_dir)

    # Create summary
    insider_count = sum(1 for f in top_features if f.startswith('insider_'))

    summary_file = analysis_dir / f"cleanup_summary_top{top_n}.txt"
    with open(summary_file, 'w') as f:
        f.write(f"Feature Cleanup Summary - Top {top_n} + All Insider Features\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Total features analyzed: {len(df)}\n")
        f.write(f"Features kept: {len(top_features)}\n")
        f.write(f"  - Top {top_n} by importance: {non_insider_count}\n")
        f.write(f"  - Insider features preserved: {insider_count}\n")
        f.write(f"Features removed: {len(df) - len(top_features)}\n")
        f.write(f"Cumulative importance (top {top_n}): {top_df['mean_importance'].sum():.1%}\n\n")
        f.write("Top 20 Features:\n")
        for i, row in top_df.head(20).iterrows():
            f.write(f"  {i+1:2d}. {row['feature']:30s} {row['mean_importance']:>6.2%}\n")
        f.write(f"\nInsider Features ({insider_count}):\n")
        for feature in sorted(insider_features):
            importance = df[df['feature'] == feature]['mean_importance'].values[0]
            f.write(f"  - {feature:40s} {importance:>6.2%}\n")

    print(f"\n✅ Summary saved to: {summary_file}")
    print("\n" + "=" * 70)
    print("NEXT STEPS:")
    print("=" * 70)
    print(f"1. Update feature engineering to use only these {len(top_features)} features")
    print(f"2. Run training: python train.py --trials 30 --dataset-folder dataset_lags_20260206_111644")
    print(f"3. Compare results with original 261 features")
    print("=" * 70)


if __name__ == "__main__":
    main()
