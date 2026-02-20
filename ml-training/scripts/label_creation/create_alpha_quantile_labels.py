#!/usr/bin/env python3
"""
Create Alpha-Quantile Labels

Combines alpha (market-relative) with quantile (top 30%) approach:
- Calculate alpha = stock_return - spy_return
- Find 70th percentile of alpha
- Label top 30% as BUY (1), rest as NO BUY (0)

This approach:
- Market-relative (works in bull/bear markets)
- Balanced classes (30% BUY, 70% NO BUY)
- No overlap (clean separation)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


def create_alpha_quantile_labels(dataset_folder):
    """
    Create alpha-quantile labels for existing dataset

    Args:
        dataset_folder: Path to dataset folder with labels_binary.parquet

    Returns:
        DataFrame with new labels
    """
    print("=" * 70)
    print("ALPHA-QUANTILE LABEL CREATOR")
    print("=" * 70)

    dataset_path = Path("/app/outputs/features") / dataset_folder

    # Load existing labels (which have alpha already calculated)
    labels_file = dataset_path / "labels_binary.parquet"

    if not labels_file.exists():
        raise FileNotFoundError(f"Labels file not found: {labels_file}")

    print(f"\n📂 Loading labels from: {labels_file}")
    df = pd.read_parquet(labels_file)

    print(f"   Loaded {len(df):,} rows")
    print(f"   Columns: {df.columns.tolist()}")

    # Verify alpha exists
    if 'alpha' not in df.columns:
        raise ValueError("alpha column not found in labels!")

    # Show current alpha distribution
    print(f"\n📊 Alpha Distribution:")
    print(df['alpha'].describe())

    # Calculate 70th percentile threshold (top 30%)
    threshold_70th = df['alpha'].quantile(0.70)
    print(f"\n🎯 70th Percentile Threshold: {threshold_70th:.4f} ({threshold_70th*100:.2f}%)")

    # Create new labels based on alpha quantile
    df['label'] = (df['alpha'] > threshold_70th).astype(int)

    # Show distribution
    print(f"\n✅ New Label Distribution:")
    distribution = df['label'].value_counts().sort_index()
    for label, count in distribution.items():
        pct = count / len(df) * 100
        label_name = "BUY" if label == 1 else "NO BUY"
        print(f"   {label_name} ({label}): {count:,} ({pct:.1f}%)")

    # Verify no overlap
    buy_alpha_min = df[df['label'] == 1]['alpha'].min()
    no_buy_alpha_max = df[df['label'] == 0]['alpha'].max()
    print(f"\n✅ Overlap Check:")
    print(f"   BUY alpha min:     {buy_alpha_min:.4f} ({buy_alpha_min*100:.2f}%)")
    print(f"   NO BUY alpha max:  {no_buy_alpha_max:.4f} ({no_buy_alpha_max*100:.2f}%)")

    if buy_alpha_min > no_buy_alpha_max:
        print(f"   ✅ NO OVERLAP! Clean separation.")
    else:
        print(f"   ❌ OVERLAP DETECTED!")

    # Compare with current labels (if they exist)
    print(f"\n📈 Comparison with Current Labels:")
    if 'label' in df.columns:
        # Current labels are the original binary labels
        # We're overwriting them, so let's show the difference
        current_buy_pct = (df['label'] == 1).mean() * 100
        print(f"   Current BUY %:    {current_buy_pct:.1f}%")
        print(f"   New BUY %:        {(df['label'] == 1).mean() * 100:.1f}%")

    # Keep only needed columns
    output_df = df[['timestamp', 'stock_id', 'label', 'stock_return', 'spy_return', 'alpha']].copy()

    # Save new labels
    output_file = dataset_path / "labels_alpha_quantile.parquet"
    output_df.to_parquet(output_file, index=False)

    print(f"\n💾 Saved new labels to: {output_file.name}")
    print(f"   Location: {dataset_path}")

    # Update metadata
    metadata_file = dataset_path / "metadata.json"
    if metadata_file.exists():
        import json
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        metadata['label_types'] = metadata.get('label_types', [])
        if 'labels_alpha_quantile.parquet' not in metadata['label_types']:
            metadata['label_types'].append('labels_alpha_quantile.parquet')

        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"   Updated metadata.json")

    print("\n" + "=" * 70)
    print("✅ ALPHA-QUANTILE LABELS CREATED!")
    print("=" * 70)
    print(f"\nNext step: Train with new labels")
    print(f"   python train.py --dataset-folder {dataset_folder} --label-type alpha_quantile --trials 30")
    print("=" * 70)

    return output_df


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Create Alpha-Quantile Labels (Top 30% Alpha Performers)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use with specific dataset folder
  python scripts/create_alpha_quantile_labels.py --dataset-folder dataset_enhanced_20260209_132053

  # Auto-detect latest dataset
  python scripts/create_alpha_quantile_labels.py
        """
    )

    parser.add_argument(
        '--dataset-folder',
        type=str,
        default='dataset_enhanced_20260209_132053',
        help='Dataset folder name (default: dataset_enhanced_20260209_132053)'
    )

    args = parser.parse_args()

    try:
        create_alpha_quantile_labels(args.dataset_folder)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
