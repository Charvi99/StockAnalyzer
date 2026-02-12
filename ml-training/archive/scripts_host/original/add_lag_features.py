#!/usr/bin/env python3
"""
Add Lag Features to Existing Dataset

Lag features use values from previous time periods WITHOUT rolling/averaging.
This avoids beta/lookahead bias while still providing temporal context.

Example:
- rsi_lag1: Yesterday's RSI
- rsi_lag2: RSI 2 days ago
- daily_return_lag1: Yesterday's return

These are safer than rolling features because they don't mix multiple time periods.
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from datetime import datetime


def add_lag_features(df: pd.DataFrame, lags: list = [1, 2, 3, 5]) -> pd.DataFrame:
    """
    Add lag features for key indicators

    Args:
        df: DataFrame with stock data (must have stock_id and timestamp columns)
        lags: List of lag periods to create

    Returns:
        DataFrame with lag features added
    """
    print(f"\n📊 Adding lag features: {lags}")

    # Features to create lags for (chosen by importance and variability)
    lag_features = [
        # Technical indicators (most important for timing)
        'rsi',
        'macd',
        'macd_signal',
        'macd_histogram',
        'cci',
        'mfi',
        'willr',
        'roc',
        'stoch_k',
        'stoch_d',

        # Price-based features
        'daily_return',
        'close',  # Raw price for momentum calculation
        'volume',

        # Volatility features
        'atr',
        'atr_normalized',
        'natr',
        'stddev',

        # Moving averages
        'ma_short',
        'ma_long',
        'ema_fast',
        'ema_slow',
        'bb_upper',
        'bb_lower',
        'bb_middle',
        'bb_width',

        # Momentum features
        'momentum_5d',
        'momentum_10d',

        # SPY relative features
        'stock_vs_spy_5d',
        'spy_rsi',
        'rsi_vs_spy',
    ]

    # Filter to features that exist in the dataframe
    available_lag_features = [f for f in lag_features if f in df.columns]

    if not available_lag_features:
        print("  ⚠️  No lag features found in dataset!")
        return df

    print(f"  Creating lags for {len(available_lag_features)} features:")

    features_before = len(df.columns)

    # Group by stock to avoid mixing data between stocks
    for feature in available_lag_features:
        for lag in lags:
            # Create lag feature within each stock group
            df[f'{feature}_lag{lag}'] = df.groupby('stock_id')[feature].shift(lag)

        if feature in available_lag_features[:5]:  # Print first 5 for brevity
            print(f"    ✓ {feature} (lags: {lags})")

    # Calculate lag-derived features (changes from previous periods)
    print("\n  📈 Calculating lag changes (rate of change)...")

    # RSI change (momentum in indicator itself)
    if 'rsi_lag1' in df.columns and 'rsi_lag2' in df.columns:
        df['rsi_change_1d'] = df['rsi'] - df['rsi_lag1']
        df['rsi_acceleration'] = df['rsi_lag1'] - df['rsi_lag2']
        print("    ✓ rsi_change_1d, rsi_acceleration")

    # MACD change
    if 'macd_lag1' in df.columns:
        df['macd_change_1d'] = df['macd'] - df['macd_lag1']
        print("    ✓ macd_change_1d")

    # Price momentum confirmation
    if 'close_lag1' in df.columns:
        df['price_vs_lag1'] = (df['close'] - df['close_lag1']) / df['close_lag1']
        print("    ✓ price_vs_lag1")

    # Volume surge detection (use available lags)
    available_volume_lags = [f'volume_lag{i}' for i in lags if f'volume_lag{i}' in df.columns]
    if len(available_volume_lags) >= 3:
        # Sum all available volume lags
        volume_sum = df[available_volume_lags].sum(axis=1)
        df['volume_vs_avg_recent'] = df['volume'] / (volume_sum / len(available_volume_lags) + 1e-6)
        print(f"    ✓ volume_vs_avg_recent (using {len(available_volume_lags)} lags)")

    features_after = len(df.columns)
    added = features_after - features_before

    print(f"\n  ✅ Added {added} lag features")
    print(f"     Before: {features_before} features")
    print(f"     After:  {features_after} features")

    # Drop rows with NaN from lagging (first few rows of each stock)
    rows_before = len(df)
    df = df.dropna()
    rows_after = len(df)
    dropped = rows_before - rows_after

    if dropped > 0:
        print(f"\n  🗑️  Dropped {dropped:,} rows with NaN values (from lagging)")
        print(f"     Before: {rows_before:,} rows")
        print(f"     After:  {rows_after:,} rows")

    return df


def main():
    parser = argparse.ArgumentParser(
        description='Add lag features to existing dataset',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add default lags (1, 2, 3, 5 days) to latest dataset
  python scripts/add_lag_features.py

  # Add custom lags
  python scripts/add_lag_features.py --lags 1 2 5 10

  # Use specific dataset folder
  python scripts/add_lag_features.py --dataset-folder dataset_20260204_185139
        """
    )

    parser.add_argument(
        '--dataset-folder',
        type=str,
        default=None,
        help='Dataset folder name (e.g., dataset_20260204_185139). Auto-detects latest if not specified.'
    )

    parser.add_argument(
        '--lags',
        type=int,
        nargs='+',
        default=[1, 2, 3, 5],
        help='Lag periods to create (default: 1 2 3 5)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("StockAnalyzer ML - Lag Feature Generator")
    print("=" * 70)

    # Find dataset folder
    outputs_dir = Path('/app/outputs/features')

    if args.dataset_folder:
        dataset_folder = outputs_dir / args.dataset_folder
        if not dataset_folder.exists():
            print(f"\n❌ Dataset folder not found: {dataset_folder}")
            print(f"   Available folders:")
            for folder in sorted(outputs_dir.glob('dataset_*')) + sorted(outputs_dir.glob('alpha_dataset_*')):
                print(f"   - {folder.name}")
            return
    else:
        # Auto-detect latest dataset folder
        dataset_folders = sorted(
            list(outputs_dir.glob('dataset_*')) +
            list(outputs_dir.glob('alpha_dataset_*')),
            reverse=True
        )
        if not dataset_folders:
            print("\n❌ No dataset folders found!")
            return
        dataset_folder = dataset_folders[0]
        print(f"\n📂 Auto-detected dataset: {dataset_folder.name}")

    # Load features
    features_file = dataset_folder / 'features.parquet'
    if not features_file.exists():
        print(f"\n❌ features.parquet not found in {dataset_folder}")
        return

    print(f"📂 Loading features from: {features_file.name}")
    df = pd.read_parquet(features_file)

    print(f"   Loaded: {len(df):,} rows × {len(df.columns)} columns")

    # Check for required columns
    if 'stock_id' not in df.columns or 'timestamp' not in df.columns:
        print("\n❌ DataFrame must have 'stock_id' and 'timestamp' columns")
        return

    # Add lag features
    df = add_lag_features(df, lags=args.lags)

    # Save updated features
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_folder = outputs_dir / f'dataset_lags_{timestamp}'
    output_folder.mkdir(parents=True, exist_ok=True)

    output_file = output_folder / 'features.parquet'
    df.to_parquet(output_file, index=False)

    print(f"\n✅ Saved lag-enhanced features to: {output_folder.name}/")
    print(f"   File: {output_file.name}")
    print(f"   Size: {output_file.stat().st_size / 1024 / 1024:.1f} MB")

    # Copy label files if they exist
    label_files = list(dataset_folder.glob('labels_*.parquet'))
    if label_files:
        print(f"\n📋 Copying label files...")
        for label_file in label_files:
            dest = output_folder / label_file.name
            import shutil
            shutil.copy(label_file, dest)
            print(f"   ✓ {label_file.name}")

    # Create metadata
    metadata = {
        'created_at': datetime.now().isoformat(),
        'num_samples': len(df),
        'num_features': len(df.columns) - 2,  # Exclude stock_id, timestamp
        'features': [col for col in df.columns if col not in ['stock_id', 'timestamp']],
        'lag_periods': args.lags,
        'parent_dataset': dataset_folder.name,
        'description': f'Lag-enhanced dataset (lags: {args.lags})'
    }

    import json
    metadata_file = output_folder / 'metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"\n📝 Created metadata.json")

    print(f"\n💡 Train with lag-enhanced dataset:")
    print(f"   python train.py --dataset-folder {output_folder.name} --models xgboost catboost")


if __name__ == '__main__':
    main()
