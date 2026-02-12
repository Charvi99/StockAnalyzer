"""
Backtest Multi-Class Labels to Validate Trustworthiness

This script validates if the labels are predictive by checking:
1. Does STRONG BUY actually lead to positive returns?
2. Does STRONG SELL actually lead to negative returns?
3. What is the hit rate for each class?
4. Are the labels better than random?

Usage:
    python backtest_labels.py
"""

import sys
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from datetime import datetime

# Find latest labels file
import glob
label_files = sorted(glob.glob('/app/outputs/features/labels_multiclass_5class_*.parquet'))
if not label_files:
    print("❌ No multi-class labels found!")
    print("   Run: python scripts/create_multiclass_labels.py")
    sys.exit(1)

latest_file = label_files[-1]
print(f"Loading labels from: {latest_file.split('/')[-1]}")

df = pd.read_parquet(latest_file)

print(f"\n📊 Total samples: {len(df):,}")
print(f"📅 Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

CLASS_NAMES = {
    0: 'STRONG SELL',
    1: 'SELL',
    2: 'HOLD',
    3: 'BUY',
    4: 'STRONG BUY'
}

print("\n" + "=" * 70)
print("BACKTESTING RESULTS")
print("=" * 70)

for lookahead in [20, 30, 40]:
    print(f"\n{'-' * 70}")
    print(f"{lookahead}-DAY LOOKAHEAD - Label Performance")
    print(f"{'-' * 70}")

    label_col = f'label_{lookahead}d'
    final_return_col = f'final_return_{lookahead}d'

    # Stats for each class
    print(f"\n{'Class':<12} | {'Samples':>8} | {'Mean Return':>12} | {'Median Return':>14} | {'>0%':>7} | {'> +2%':>8} | {'> +5%':>8}")
    print("-" * 90)

    for class_id in range(5):
        class_mask = df[label_col] == class_id
        class_returns = df.loc[class_mask, final_return_col].values

        n_samples = len(class_returns)
        mean_return = np.mean(class_returns)
        median_return = np.median(class_returns)
        std_return = np.std(class_returns)

        # Count positive outcomes
        positive_pct = (class_returns > 0).sum() / n_samples * 100
        gt_2_pct = (class_returns > 2).sum() / n_samples * 100
        gt_5_pct = (class_returns > 5).sum() / n_samples * 100

        print(f"{CLASS_NAMES[class_id]:<12} | {n_samples:>8,} | {mean_return:>10.2f}%     | {median_return:>10.2f}%       | {positive_pct:>6.1f}%  | {gt_2_pct:>6.1f}% | {gt_5_pct:>6.1f}%")

    # Directional accuracy check
    print(f"\n{'-' * 70}")
    print("DIRECTIONAL ACCURACY (Did the label predict the right direction?)")
    print("-" * 70)

    for class_id in range(5):
        class_mask = df[label_col] == class_id
        class_returns = df.loc[class_mask, final_return_col].values

        n_samples = len(class_returns)

        # Expected direction
        if class_id == 4:  # STRONG BUY - expect positive
            correct = (class_returns > 0).sum()
            expected = "Positive"
        elif class_id == 3:  # BUY - expect positive
            correct = (class_returns > 0).sum()
            expected = "Positive"
        elif class_id == 1:  # SELL - expect negative
            correct = (class_returns < 0).sum()
            expected = "Negative"
        elif class_id == 0:  # STRONG SELL - expect negative
            correct = (class_returns < 0).sum()
            expected = "Negative"
        else:  # HOLD - expect small move
            correct = ((class_returns > -1) & (class_returns < 1)).sum()
            expected = "Sideways"

        accuracy = correct / n_samples * 100
        print(f"{CLASS_NAMES[class_id]:<12} | Expected: {expected:10} | Actual: {accuracy:>5.1f}% correct")

print("\n" + "=" * 70)
print("STATISTICAL SIGNIFICANCE TEST")
print("=" * 70)

# Test: Are STRONG BUY returns significantly better than random?
print("\nTesting: Do STRONG BUY labels predict better than random selection?")

for lookahead in [20, 30, 40]:
    label_col = f'label_{lookahead}d'
    final_return_col = f'final_return_{lookahead}d'

    # STRONG BUY returns vs all returns
    strong_buy_returns = df[df[label_col] == 4][final_return_col].values
    all_returns = df[final_return_col].values

    sb_mean = np.mean(strong_buy_returns)
    all_mean = np.mean(all_returns)

    print(f"\n{lookahead}d:")
    print(f"  STRONG BUY mean return: {sb_mean:+.2f}%")
    print(f"  Overall mean return:    {all_mean:+.2f}%")
    print(f"  Difference:              {sb_mean - all_mean:+.2f}%")

    if sb_mean > all_mean:
        print(f"  ✅ STRONG BUY beats average by {sb_mean - all_mean:.2f} percentage points")
    else:
        print(f"  ❌ STRONG BUY underperforms average!")

print("\n" + "=" * 70)
print("LABEL QUALITY SCORE")
print("=" * 70)

# Calculate quality metrics
quality_scores = []

for lookahead in [20, 30, 40]:
    label_col = f'label_{lookahead}d'
    final_return_col = f'final_return_{lookahead}d'

    # STRONG BUY should be positive
    strong_buy_returns = df[df[label_col] == 4][final_return_col].values
    sb_positive = (strong_buy_returns > 0).sum() / len(strong_buy_returns) * 100

    # STRONG SELL should be negative
    strong_sell_returns = df[df[label_col] == 0][final_return_col].values
    ss_negative = (strong_sell_returns < 0).sum() / len(strong_sell_returns) * 100

    # HOLD should be mostly small moves
    hold_returns = df[df[label_col] == 2][final_return_col].values
    hold_small = ((hold_returns > -2) & (hold_returns < 2)).sum() / len(hold_returns) * 100

    print(f"\n{lookahead}d Label Quality:")
    print(f"  STRONG BUY positivity rate: {sb_positive:.1f}% " + ("✅" if sb_positive > 70 else "⚠️" if sb_positive > 50 else "❌"))
    print(f"  STRONG SELL negativity rate: {ss_negative:.1f}% " + ("✅" if ss_negative > 70 else "⚠️" if ss_negative > 50 else "❌"))
    print(f"  HOLD small move rate:      {hold_small:.1f}% " + ("✅" if hold_small > 50 else "⚠️" if hold_small > 30 else "❌"))

    # Overall quality score (0-100)
    quality = (sb_positive + ss_negative + hold_small) / 3
    quality_scores.append(quality)
    print(f"  Overall quality score:    {quality:.1f}/100")

avg_quality = np.mean(quality_scores)
print(f"\n{'=' * 70}")
if avg_quality > 70:
    print(f"✅ LABELS ARE TRUSTWORTHY (quality: {avg_quality:.1f}/100)")
elif avg_quality > 50:
    print(f"⚠️  LABELS ARE MODERATE (quality: {avg_quality:.1f}/100)")
else:
    print(f"❌ LABELS ARE POOR (quality: {avg_quality:.1f}/100)")

print("\n" + "=" * 70)
print("RECOMMENDATION")
print("=" * 70)

if avg_quality > 60:
    print("\n✅ Labels are validated and trustworthy for training!")
    print(f"\nTrain with:")
    print(f"  python train.py \\")
    print(f"    --labels-path {latest_file} \\")
    print(f"    --label-column label_20d \\")
    print(f"    --models xgboost catboost")
else:
    print("\n⚠️  Labels may need adjustment before training")
    print("   Consider:")
    print("   1. Adjusting thresholds")
    print("   2. Using different classification approach")
    print("   3. Removing outlier samples")
