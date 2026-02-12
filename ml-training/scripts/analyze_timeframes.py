#!/usr/bin/env python3
"""
Simplified Multi-Timeframe Label Creator

Uses existing alpha data from labels_binary.parquet and creates
timeframe-specific labels by applying the same alpha-quantile approach.

Note: This uses the existing 20-day alpha data as a proxy.
For true 10d/30d labels, you'd need to recalculate from raw prices.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime


def create_timeframe_labels_from_existing(
    dataset_folder: str,
    timeframes: list = [10, 20, 30]
):
    """
    Create labels for different timeframes using existing alpha data

    Note: This applies the alpha-quantile approach to existing 20d alpha.
    For proper 10d/30d labels, raw price data would be needed.
    """
    print("=" * 70)
    print("TIMEFRAME LABEL ANALYSIS")
    print("=" * 70)

    dataset_path = Path("/app/outputs/features") / dataset_folder

    # Load existing 20-day labels (has alpha)
    labels_20d = dataset_path / "labels_binary.parquet"

    if not labels_20d.exists():
        raise FileNotFoundError(f"20-day labels not found: {labels_20d}")

    print(f"\n📂 Loading 20-day labels: {labels_20d.name}")
    df = pd.read_parquet(labels_20d)
    print(f"   Loaded {len(df):,} rows")

    # Calculate alpha percentile thresholds for different "timeframes"
    # In reality, you'd recalculate alpha for each timeframe
    # Here we use the same 20d alpha but analyze different top percentiles

    print(f"\n📊 Analyzing different percentile thresholds:")

    # Current 70th percentile = top 30%
    threshold_70 = df['alpha'].quantile(0.70)
    print(f"   70th percentile (current): {threshold_70:.4f} ({threshold_70*100:.2f}%)")

    # Simulate shorter/longer timeframes by adjusting percentile
    # Shorter timeframe (10d) = more volatile = higher threshold needed
    # Longer timeframe (30d) = less volatile = lower threshold

    results = {}

    # For 20d (baseline)
    df_20d = df.copy()
    df_20d['label'] = (df_20d['alpha'] > threshold_70).astype(int)
    df_20d['label_type'] = '20d'
    results['20d'] = {
        'threshold': threshold_70,
        'buy_count': int((df_20d['label'] == 1).sum()),
        'total': len(df_20d),
        'buy_pct': (df_20d['label'] == 1).mean() * 100
    }

    # For 10d (simulate with higher percentile = more selective)
    percentile_10d = 0.80  # Top 20% only (more volatile, need higher alpha)
    threshold_10d = df['alpha'].quantile(percentile_10d)
    df_10d = df.copy()
    df_10d['label'] = (df_10d['alpha'] > threshold_10d).astype(int)
    df_10d['label_type'] = '10d'
    results['10d'] = {
        'threshold': threshold_10d,
        'buy_count': int((df_10d['label'] == 1).sum()),
        'total': len(df_10d),
        'buy_pct': (df_10d['label'] == 1).mean() * 100,
        'note': 'Simulated (uses 80th percentile of 20d alpha)'
    }

    # For 30d (simulate with lower percentile = less selective)
    percentile_30d = 0.60  # Top 40% (less volatile, can accept lower alpha)
    threshold_30d = df['alpha'].quantile(percentile_30d)
    df_30d = df.copy()
    df_30d['label'] = (df_30d['alpha'] > threshold_30d).astype(int)
    df_30d['label_type'] = '30d'
    results['30d'] = {
        'threshold': threshold_30d,
        'buy_count': int((df_30d['label'] == 1).sum()),
        'total': len(df_30d),
        'buy_pct': (df_30d['label'] == 1).mean() * 100,
        'note': 'Simulated (uses 60th percentile of 20d alpha)'
    }

    # Display results
    print(f"\n📊 Results:")
    print(f"{'Timeframe':<12} {'Threshold':<12} {'BUY Count':<12} {'BUY %':<8} {'Notes'}")
    print("-" * 70)
    for tf, info in results.items():
        print(f"{tf:<12} {info['threshold']*100:>6.2f}%     {info['buy_count']:>8,}      {info['buy_pct']:>5.1f}%   {info.get('note', '')}")

    # Save comparison
    comparison = []
    for tf, info in results.items():
        comparison.append({
            'timeframe': tf,
            'threshold': info['threshold'],
            'buy_count': info['buy_count'],
            'buy_pct': info['buy_pct'],
            'total': info['total']
        })

    comparison_df = pd.DataFrame(comparison)
    output_file = dataset_path / "timeframe_label_comparison.csv"
    comparison_df.to_csv(output_file, index=False)
    print(f"\n💾 Saved comparison to: {output_file.name}")

    print(f"\n⚠️  IMPORTANT NOTE:")
    print(f"   This uses 20-day alpha data to simulate different timeframes.")
    print(f"   For true 10d/30d labels, need to:")
    print(f"   1. Fetch raw price data from database")
    print(f"   2. Calculate returns for each timeframe (10d, 20d, 30d)")
    print(f"   3. Calculate alpha for each timeframe")
    print(f"   4. Apply 70th percentile threshold to each")

    print(f"\n💡 Current workaround:")
    print(f"   - 10d: Simulated as top 20% (80th percentile) - more selective")
    print(f"   - 20d: Top 30% (70th percentile) - baseline")
    print(f"   - 30d: Simulated as top 40% (60th percentile) - less selective")

    return results


def create_true_timeframe_labels(dataset_folder: str):
    """
    Create TRUE timeframe labels from raw price data

    Requires database connection to fetch historical prices
    and calculate returns for each timeframe.
    """
    print("=" * 70)
    print("TRUE TIMEFRAME LABEL CREATOR (from price data)")
    print("=" * 70)

    dataset_path = Path("/app/outputs/features") / dataset_folder

    # Get stock IDs and date range from features
    features_file = dataset_path / "features.parquet"
    features_df = pd.read_parquet(features_file)

    stock_ids = features_df['stock_id'].unique().tolist()
    min_date = features_df['timestamp'].min()
    max_date = features_df['timestamp'].max()

    print(f"\nStock IDs: {len(stock_ids)}")
    print(f"Date range: {min_date} to {max_date}")

    # This would require:
    # 1. Database connection to fetch prices
    # 2. Calculate 10d, 20d, 30d forward returns
    # 3. Calculate SPY returns for each period
    # 4. Calculate alpha (stock - spy)
    # 5. Apply 70th percentile threshold per timeframe

    print(f"\n❌ Database connection required")
    print(f"   The script needs access to raw price data to calculate")
    print(f"   true 10d/30d returns.")
    print(f"\n   Recommendation:")
    print(f"   1. Use backend API to fetch historical prices")
    print(f"   2. Or use Polygon.io API directly")
    print(f"   3. Calculate returns and alpha per timeframe")
    print(f"   4. Apply alpha-quantile labeling")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Multi-Timeframe Label Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--dataset-folder',
        type=str,
        default='dataset_enhanced_20260209_132053',
        help='Dataset folder name'
    )

    parser.add_argument(
        '--simulate',
        action='store_true',
        help='Simulate timeframes using 20d alpha (faster, no DB needed)'
    )

    parser.add_argument(
        '--true',
        action='store_true',
        help='Create true timeframe labels (requires DB connection)'
    )

    args = parser.parse_args()

    if args.true:
        create_true_timeframe_labels(args.dataset_folder)
    else:
        create_timeframe_labels_from_existing(args.dataset_folder)


if __name__ == "__main__":
    main()
