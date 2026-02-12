"""
Multi-Timeframe Label Correlation Analysis

Investigates whether 20d, 30d, 40d labels capture different signals
or if they're redundant (highly correlated).

Works with both 3-class (SELL/HOLD/BUY) and 5-class labels.

Usage:
    python scripts/analyze_multi_timeframe_correlation.py
"""

import sys
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from pathlib import Path

def convert_5class_to_3class(label_5class: int) -> int:
    """Convert 5-class label to 3-class label"""
    if label_5class in [0, 1]:  # STRONG SELL or SELL
        return 0  # SELL
    elif label_5class == 2:  # HOLD
        return 1  # HOLD
    else:  # BUY (3) or STRONG BUY (4)
        return 2  # BUY


def main():
    print("=" * 70)
    print("Multi-Timeframe Correlation Analysis")
    print("=" * 70)

    # Find latest labels (prefer 3-class, fallback to 5-class)
    features_dir = Path('/app/outputs/features')

    # Try 3-class first
    label_files = sorted(features_dir.glob('labels_3class_*.parquet'))
    class_mode = '3-class'

    # Fallback to 5-class
    if not label_files:
        label_files = sorted(features_dir.glob('labels_multiclass_5class_*.parquet'))
        class_mode = '5-class'

    if not label_files:
        print("❌ No label files found")
        return

    labels_path = label_files[-1]
    print(f"\n📂 Using: {labels_path.name}")
    print(f"   Mode: {class_mode}")

    df = pd.read_parquet(labels_path)
    print(f"   Rows: {len(df):,}")

    # Determine column names based on mode
    if class_mode == '3-class':
        label_columns_raw = {
            '20d': 'label_20d_3c',
            '30d': 'label_30d_3c',
            '40d': 'label_40d_3c'
        }
        class_names = ['SELL', 'HOLD', 'BUY']
        num_classes = 3
        needs_conversion = {}  # Track which columns need 5→3 class conversion
    else:
        label_columns_raw = {
            '20d': 'label_20d',
            '30d': 'label_30d',
            '40d': 'label_40d'
        }
        class_names = ['STRONG SELL', 'SELL', 'HOLD', 'BUY', 'STRONG BUY']
        num_classes = 5
        needs_conversion = None

    # Check if all timeframes exist and convert if needed
    label_columns = {}
    timeframes = ['20d', '30d', '40d']

    if class_mode == '3-class':
        for tf in timeframes:
            target_col = label_columns_raw[tf]
            if target_col in df.columns:
                # 3-class column exists, use directly
                label_columns[tf] = target_col
                needs_conversion[tf] = False
            else:
                # Try 5-class fallback
                fallback_col = f'label_{tf}'
                if fallback_col in df.columns:
                    # Convert 5-class to 3-class
                    df[f'{tf}_converted'] = df[fallback_col].apply(convert_5class_to_3class)
                    label_columns[tf] = f'{tf}_converted'
                    needs_conversion[tf] = True
                    print(f"   {tf}: Converting 5-class to 3-class")
                else:
                    print(f"❌ Column '{target_col}' not found and no fallback")
                    return
    else:
        for tf in timeframes:
            col = label_columns_raw[tf]
            if col not in df.columns:
                print(f"❌ Column '{col}' not found")
                return
            label_columns[tf] = col

    # Calculate correlations
    print("\n" + "=" * 70)
    print("LABEL CORRELATIONS")
    print("=" * 70)

    correlations = {}
    for tf1 in timeframes:
        for tf2 in timeframes:
            if tf1 >= tf2:
                continue

            col1, col2 = label_columns[tf1], label_columns[tf2]
            corr = df[col1].corr(df[col2])
            correlations[f'{tf1} vs {tf2}'] = corr

            print(f"\n{tf1.upper()} vs {tf2.upper()}:")
            print(f"  Correlation: {corr:.3f}")

            # Interpretation
            if corr > 0.85:
                print(f"  ❌ HIGHLY CORRELATED - Ensemble may not help much")
            elif corr > 0.70:
                print(f"  ⚠️  Moderately correlated - Some benefit from ensemble")
            else:
                print(f"  ✅ Low correlation - Significant ensemble potential")

    # Cross-tabulation
    print("\n" + "=" * 70)
    print(f"CROSS-TABULATION (20d vs 30d) - {class_mode}")
    print("=" * 70)

    crosstab = pd.crosstab(df[label_columns['20d']], df[label_columns['30d']], margins=True)
    print(crosstab)

    # Calculate agreement percentage
    agreement = (df[label_columns['20d']] == df[label_columns['30d']]).sum() / len(df) * 100
    print(f"\nAgreement: {agreement:.1f}%")

    if agreement > 80:
        print("  ⚠️  High agreement - Timeframes may be redundant")
    elif agreement > 60:
        print("  ✅ Moderate agreement - Some diversity")
    else:
        print("  ✅ Low agreement - Good diversity for ensemble")

    # Analyze per-class agreement
    print("\n" + "=" * 70)
    print(f"PER-CLASS AGREEMENT (20d vs 30d) - {class_mode}")
    print("=" * 70)

    for cls in range(num_classes):
        cls_mask = df[label_columns['20d']] == cls
        if cls_mask.sum() == 0:
            continue

        cls_agreement = (df.loc[cls_mask, label_columns['20d']] == df.loc[cls_mask, label_columns['30d']]).sum() / cls_mask.sum() * 100
        print(f"  {class_names[cls]}: {cls_agreement:.1f}% agreement")

    # Distribution comparison
    print("\n" + "=" * 70)
    print(f"LABEL DISTRIBUTIONS BY TIMEFRAME - {class_mode}")
    print("=" * 70)

    for tf in timeframes:
        col = label_columns[tf]
        dist = df[col].value_counts().sort_index()
        total = len(df)
        print(f"\n{tf.upper()}:")
        for cls, count in dist.items():
            pct = count / total * 100
            print(f"  {class_names[cls]}: {count:,} ({pct:.1f}%)")

    # Recommendation
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)

    avg_corr = np.mean(list(correlations.values()))

    if avg_corr > 0.85:
        print("\n❌ HIGH CORRELATION DETECTED")
        print("\nMulti-timeframe ensemble may NOT provide significant benefit.")
        print("\nAlternative approaches:")
        print("  1. Focus on single best timeframe (likely 20d for swing trading)")
        print("  2. Use ensemble for different models, not timeframes")
        print("  3. Investigate why timeframes are so similar")
    elif avg_corr > 0.70:
        print("\n⚠️  MODERATE CORRELATION")
        print("\nMulti-timeframe ensemble may provide modest benefit (+2-5% AUC).")
        print("\nRecommendation:")
        print("  1. Try simple weighted average first")
        print("  2. If gains < 3%, consider other improvements")
    else:
        print("\n✅ LOW CORRELATION")
        print("\nMulti-timeframe ensemble has HIGH potential (+5-10% AUC).")
        print("\nRecommendation:")
        print("  1. Implement stacking ensemble across timeframes")
        print("  2. Train separate models for each timeframe")
        print("  3. Combine with meta-learner")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
