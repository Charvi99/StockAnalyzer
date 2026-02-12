"""
Create backtest dataset by merging enhanced features with OHLCV data.

This script creates a dataset suitable for backtesting by combining:
- Enhanced features (128 features with sector ETF, advanced volatility)
- OHLCV data required for backtesting execution
"""
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime


def create_backtest_dataset():
    """Create dataset with both enhanced features and OHLCV for backtesting"""

    print("=" * 70)
    print("Creating Backtest Dataset for TabNet")
    print("=" * 70)

    # Paths
    features_dir = Path("/app/outputs/features")
    lags_file = features_dir / "dataset_lags_20260206_111644" / "features.parquet"
    enhanced_file = features_dir / "dataset_enhanced_20260209_132053" / "features.parquet"

    # Load lags dataset (has OHLCV and timestamp)
    print("\nLoading lags dataset (for OHLCV and timestamp)...")
    df_lags = pd.read_parquet(lags_file)
    print(f"  Lags shape: {df_lags.shape}")
    print(f"  Lags columns: {len(df_lags.columns)}")

    # Load enhanced dataset (has the features TabNet expects)
    print("\nLoading enhanced dataset (for TabNet features)...")
    df_enhanced = pd.read_parquet(enhanced_file)
    print(f"  Enhanced shape: {df_enhanced.shape}")
    print(f"  Enhanced columns: {len(df_enhanced.columns)}")

    # Check what columns each has
    ohlcv_cols = ['open', 'high', 'low', 'close', 'volume']
    print(f"\nOHLCV in lags: {all(c in df_lags.columns for c in ohlcv_cols)}")
    print(f"OHLCV in enhanced: {all(c in df_enhanced.columns for c in ohlcv_cols)}")

    # Load TabNet metadata to see what features it expects
    tabnet_metadata_path = Path("/app/outputs/models/tabnet/latest/metadata.json")
    with open(tabnet_metadata_path) as f:
        content = f.read()
        # Fix incomplete JSON
        if '"optimizer_fn":' in content and not content.strip().endswith('}'):
            content = content.split('"optimizer_fn":')[0] + '"optimizer_fn": "<torch.optim.Adam>",'
            content += '\n    "output_dim": 3,\n    "seed": 42\n  },\n  "num_classes": 3\n}'
        metadata = json.loads(content)
        tabnet_features = metadata['feature_cols']

    print(f"\nTabNet expects {len(tabnet_features)} features")
    print(f"  Features in enhanced: {sum(1 for f in tabnet_features if f in df_enhanced.columns)}")
    print(f"  Features in lags: {sum(1 for f in tabnet_features if f in df_lags.columns)}")

    # Strategy: Use enhanced features and add OHLCV + timestamp + symbol from lags
    # First, get the common identifier (should be able to match on index or symbol+date)

    # Check if both have timestamp/symbol
    print(f"\nDataset structure:")
    print(f"  Lags has timestamp: {'timestamp' in df_lags.columns}")
    print(f"  Lags has stock_id/symbol: {'stock_id' in df_lags.columns or 'symbol' in df_lags.columns}")
    print(f"  Enhanced has timestamp: {'timestamp' in df_enhanced.columns}")
    print(f"  Enhanced has stock_id/symbol: {'stock_id' in df_enhanced.columns or 'symbol' in df_enhanced.columns}")

    # Create backtest dataset by:
    # 1. Starting with enhanced features (what TabNet expects)
    # 2. Adding OHLCV columns from lags (but only those not already present)
    # 3. Ensuring single symbol/timestamp columns

    # For simplicity, let's assume both datasets are aligned by index
    # We'll create a new dataset with enhanced features + OHLCV from lags

    print("\nMerging datasets...")

    # Start with enhanced features
    df_backtest = df_enhanced.copy()

    # Remove symbol and timestamp from enhanced if they exist (will add from lags)
    cols_to_drop = []
    if 'symbol' in df_backtest.columns:
        cols_to_drop.append('symbol')
    if 'stock_id' in df_backtest.columns:
        cols_to_drop.append('stock_id')
    if 'timestamp' in df_backtest.columns:
        cols_to_drop.append('timestamp')
    if cols_to_drop:
        print(f"  Dropping from enhanced: {cols_to_drop}")
        df_backtest = df_backtest.drop(columns=cols_to_drop)

    # Add OHLCV from lags if not present
    for col in ohlcv_cols:
        if col not in df_backtest.columns and col in df_lags.columns:
            df_backtest[col] = df_lags[col]

    # Add OHLCV from lags if not present (avoiding duplicates)
    for col in ohlcv_cols:
        if col not in df_backtest.columns and col in df_lags.columns:
            df_backtest[col] = df_lags[col]
        elif col in df_backtest.columns and col in df_lags.columns:
            # Already exists, skip
            pass

    # Add timestamp from lags (we dropped it from enhanced earlier)
    if 'timestamp' in df_lags.columns:
        df_backtest['timestamp'] = df_lags['timestamp']

    # Add stock_id from lags (we dropped it from enhanced earlier)
    if 'stock_id' in df_lags.columns:
        df_backtest['stock_id'] = df_lags['stock_id']

    # Ensure we have a symbol column for backtesting
    if 'symbol' not in df_backtest.columns and 'stock_id' in df_backtest.columns:
        df_backtest['symbol'] = df_backtest['stock_id']

    # Remove any remaining duplicate columns
    if df_backtest.columns.duplicated().any():
        dup_cols = df_backtest.columns[df_backtest.columns.duplicated()].tolist()
        print(f"  WARNING: Removing duplicate columns: {dup_cols}")
        df_backtest = df_backtest.loc[:, ~df_backtest.columns.duplicated()]

    # Set timestamp as index if it's a datetime or can be converted
    if 'timestamp' in df_backtest.columns:
        if pd.api.types.is_numeric_dtype(df_backtest['timestamp']):
            # Convert numeric timestamp to datetime
            if df_backtest['timestamp'].max() > 1e10:  # Milliseconds
                df_backtest['date'] = pd.to_datetime(df_backtest['timestamp'], unit='ms')
            else:  # Seconds
                df_backtest['date'] = pd.to_datetime(df_backtest['timestamp'], unit='s')
        else:
            df_backtest['date'] = pd.to_datetime(df_backtest['timestamp'])

        df_backtest.set_index('date', inplace=True)

    print(f"Backtest dataset shape: {df_backtest.shape}")
    print(f"Backtest dataset has OHLCV: {all(c in df_backtest.columns for c in ohlcv_cols)}")
    print(f"Backtest dataset has TabNet features: {sum(1 for f in tabnet_features if f in df_backtest.columns)}/{len(tabnet_features)}")

    # Save the backtest dataset
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = features_dir / f"dataset_backtest_tabnet_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "features.parquet"
    df_backtest.to_parquet(output_file, index=True)

    # Save metadata
    metadata = {
        "created_at": datetime.now().isoformat(),
        "num_samples": len(df_backtest),
        "num_features": len(df_backtest.columns),
        "has_ohlcv": all(c in df_backtest.columns for c in ohlcv_cols),
        "source_datasets": ["dataset_enhanced_20260209_132053", "dataset_lags_20260206_111644"],
        "tabnet_features_count": sum(1 for f in tabnet_features if f in df_backtest.columns),
        "description": "Enhanced features + OHLCV for TabNet backtesting"
    }

    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n✅ Backtest dataset saved to: {output_dir}")
    print(f"   Shape: {df_backtest.shape}")
    print(f"   OHLCV: {metadata['has_ohlcv']}")
    print(f"   TabNet features: {metadata['tabnet_features_count']}/{len(tabnet_features)}")

    return output_dir


if __name__ == "__main__":
    create_backtest_dataset()
