"""
Convert 5-Class Labels to 3-Class Labels

This script converts 5-class labels to 3-class by merging:
- STRONG SELL (0) + SELL (1) → SELL (0)
- HOLD (2) → HOLD (1)
- BUY (3) + STRONG BUY (4) → BUY (2)

This reduces class imbalance and makes the classification problem simpler.

Usage:
    python scripts/convert_to_3class.py --input labels_multiclass_5class_20260204_111327.parquet
    python scripts/convert_to_3class.py --input labels_multiclass_5class_20260204_111327.parquet --timeframe 20d
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np


def convert_5class_to_3class(label_5class: int) -> int:
    """
    Convert 5-class label to 3-class label

    Args:
        label_5class: 5-class label (0=STRONG SELL, 1=SELL, 2=HOLD, 3=BUY, 4=STRONG BUY)

    Returns:
        3-class label (0=SELL, 1=HOLD, 2=BUY)
    """
    if label_5class in [0, 1]:  # STRONG SELL or SELL
        return 0  # SELL
    elif label_5class == 2:  # HOLD
        return 1  # HOLD
    else:  # BUY (3) or STRONG BUY (4)
        return 2  # BUY


def main():
    parser = argparse.ArgumentParser(
        description='Convert 5-class labels to 3-class labels',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/convert_to_3class.py
  python scripts/convert_to_3class.py --input labels_multiclass_5class_20260204_111327.parquet
  python scripts/convert_to_3class.py --timeframe 20d
  python scripts/convert_to_3class.py --input labels_5class.parquet --output labels_3class.parquet
        """
    )

    parser.add_argument(
        '--input',
        type=str,
        default=None,
        help='Input 5-class label file (auto-detects latest if not specified)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output 3-class label file (auto-generated if not specified)'
    )

    parser.add_argument(
        '--timeframe',
        type=str,
        default='20d',
        choices=['20d', '30d', '40d', 'all'],
        help='Which timeframe(s) to convert (default: 20d)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print(" " * 15)
    print("5-Class to 3-Class Label Converter")
    print(" " * 15)
    print("=" * 70)

    # ============================================================
    # FIND INPUT FILE
    # ============================================================

    features_dir = Path('/app/outputs/features')

    if args.input:
        input_path = features_dir / args.input
        if not input_path.exists():
            # Try as full path
            input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {args.input}")
    else:
        # Auto-detect latest 5-class label file
        label_files = sorted(features_dir.glob('labels_multiclass_5class_*.parquet'))
        if not label_files:
            raise FileNotFoundError(
                "No 5-class label files found. Run create_multiclass_labels.py first:\n"
                "  python scripts/create_multiclass_labels.py"
            )
        input_path = label_files[-1]

    print(f"\n📂 Input file: {input_path.name}")

    # ============================================================
    # LOAD DATA
    # ============================================================

    print("\n" + "=" * 70)
    print("LOADING DATA")
    print("=" * 70)

    df = pd.read_parquet(input_path)
    print(f"✅ Loaded {len(df):,} rows")

    # ============================================================
    # CONVERT LABELS
    # ============================================================

    print("\n" + "=" * 70)
    print("CONVERTING LABELS")
    print("=" * 70)

    print("\nMapping:")
    print("  5-Class                →  3-Class")
    print("  ──────────────────────────────────────")
    print("  0: STRONG SELL         →  0: SELL")
    print("  1: SELL                →  0: SELL")
    print("  2: HOLD                →  1: HOLD")
    print("  3: BUY                 →  2: BUY")
    print("  4: STRONG BUY          →  2: BUY")

    # Determine which columns to convert
    timeframes = ['20d', '30d', '40d'] if args.timeframe == 'all' else [args.timeframe]

    for tf in timeframes:
        col_5class = f'label_{tf}'
        col_3class = f'label_{tf}_3c'  # 3c = 3-class

        if col_5class not in df.columns:
            print(f"\n⚠️  Column '{col_5class}' not found, skipping...")
            continue

        # Convert labels
        df[col_3class] = df[col_5class].apply(convert_5class_to_3class)

        # Show distribution
        print(f"\n{tf.upper()} - 5-Class Distribution:")
        counts_5c = df[col_5class].value_counts().sort_index()
        total_5c = len(df)
        class_names_5c = ['STRONG SELL', 'SELL', 'HOLD', 'BUY', 'STRONG BUY']
        for cls, count in counts_5c.items():
            pct = count / total_5c * 100
            print(f"  Class {cls} ({class_names_5c[cls]}): {count:,} ({pct:.1f}%)")

        print(f"\n{tf.upper()} - 3-Class Distribution:")
        counts_3c = df[col_3class].value_counts().sort_index()
        total_3c = len(df)
        class_names_3c = ['SELL', 'HOLD', 'BUY']
        for cls, count in counts_3c.items():
            pct = count / total_3c * 100
            print(f"  Class {cls} ({class_names_3c[cls]}): {count:,} ({pct:.1f}%)")

        # Calculate class balance (Gini coefficient approximation)
        counts = counts_3c.values
        proportions = counts / counts.sum()
        gini = 1 - (proportions ** 2).sum()
        print(f"\n  Class Balance (lower is more balanced): {gini:.3f}")
        if gini < 0.2:
            print("  ✅ Well balanced!")
        elif gini < 0.4:
            print("  ⚠️  Moderately balanced")
        else:
            print("  ❌ Imbalanced (but better than 5-class)")

    # ============================================================
    # SAVE OUTPUT
    # ============================================================

    print("\n" + "=" * 70)
    print("SAVING OUTPUT")
    print("=" * 70)

    # Generate output filename
    if args.output:
        output_path = features_dir / args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = features_dir / f'labels_3class_{timestamp}.parquet'

    df.to_parquet(output_path, index=False)
    print(f"✅ Saved to: {output_path.name}")
    print(f"   Full path: {output_path}")

    # ============================================================
    # SUMMARY
    # ============================================================

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\nInput:  {input_path.name}")
    print(f"Output: {output_path.name}")
    print(f"Rows:   {len(df):,}")

    print("\n" + "=" * 70)
    print("✅ CONVERSION COMPLETE!")
    print("=" * 70)

    print("\nYou can now train with 3-class labels:")
    print(f"  python train.py --labels-path {output_path.name} --label-column label_20d_3c --num-classes 3")

    # Also show how to use other timeframes
    if args.timeframe == 'all' or '30d' in timeframes:
        print(f"  python train.py --labels-path {output_path.name} --label-column label_30d_3c --num-classes 3")
    if args.timeframe == 'all' or '40d' in timeframes:
        print(f"  python train.py --labels-path {output_path.name} --label-column label_40d_3c --num-classes 3")


if __name__ == "__main__":
    main()
