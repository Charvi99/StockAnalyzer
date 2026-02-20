#!/usr/bin/env python3
"""
Create Professional Normalized Sequences for Transformer Models

This script creates properly normalized sequential data for TCN, LSTM, and Transformer models.
Key features:
- Professional feature normalization (per-stock + global)
- Time-series aware fitting (train-only to prevent leakage)
- Stores normalized features WITHOUT labels (reuse for all label types)
- Saves normalization parameters for reproducibility
- Metadata for tracking stock_ids and timestamps

Output:
- X: Normalized features (n_sequences, sequence_length, n_features)
- stock_ids: Stock identifier for each sequence
- timestamps: Timestamp for each sequence
- normalization_params: Parameters for reproducibility

Usage:
    python scripts/create_normalized_sequences.py --dataset-folder dataset_lags_20260206_111644 --sequence-length 20
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime
import tempfile
import json

import pandas as pd
import numpy as np
from tqdm import tqdm

# Add ml_framework to path
sys.path.insert(0, '/app/ml_framework')
from feature_normalization_simple import SimpleFeatureNormalizer, create_temporal_mask, create_sequences_memmap

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def count_sequences(df: pd.DataFrame, sequence_length: int) -> int:
    """Count total number of sequences that will be created"""
    total = 0
    for stock_id, stock_data in df.groupby('stock_id'):
        n = len(stock_data)
        if n >= sequence_length:
            total += n - sequence_length
    return total


def create_sequences_memmap(
    df: pd.DataFrame,
    X_normalized: np.ndarray,
    sequence_length: int,
    output_dir: Path,
    feature_columns: list
) -> tuple:
    """
    Create sequences from normalized features using memory-mapped files

    Args:
        df: DataFrame with stock_id, timestamp
        X_normalized: Normalized features array (n_samples, n_features)
        sequence_length: Number of timesteps per sequence
        output_dir: Directory for temporary memmap files
        feature_columns: List of feature column names

    Returns:
        X_seq: Sequences (n_total_sequences, sequence_length, n_features)
        stock_ids: Stock ID for each sequence
        timestamps: Timestamp for each sequence
    """
    print(f"\n📊 Creating sequences (length={sequence_length})...")

    # Add normalized features to dataframe temporarily
    df_temp = df.copy()
    for i, col in enumerate(feature_columns):
        df_temp[col] = X_normalized[:, i]

    # Count total sequences
    print(f"  Counting sequences...")
    n_total_sequences = count_sequences(df_temp, sequence_length)
    n_features = len(feature_columns)

    print(f"  Total sequences: {n_total_sequences:,}")
    print(f"  Shape: ({n_total_sequences}, {sequence_length}, {n_features})")

    # Estimate memory
    memory_gb = n_total_sequences * sequence_length * n_features * 4 / (1024**3)
    print(f"  MemMap file size: {memory_gb:.2f} GB (on disk, not RAM)")

    # Create memory-mapped files
    X_memmap_path = output_dir / 'X_sequences.tmp'
    stock_ids_memmap_path = output_dir / 'stock_ids.tmp'
    timestamps_memmap_path = output_dir / 'timestamps.tmp'

    X_seq = np.memmap(
        X_memmap_path,
        dtype='float32',
        mode='w+',
        shape=(n_total_sequences, sequence_length, n_features)
    )

    stock_ids_seq = np.memmap(
        stock_ids_memmap_path,
        dtype='int32',
        mode='w+',
        shape=(n_total_sequences,)
    )

    timestamps_seq = np.memmap(
        timestamps_memmap_path,
        dtype='datetime64[s]',
        mode='w+',
        shape=(n_total_sequences,)
    )

    # Fill sequences (grouped by stock!)
    print(f"\n  Processing stocks...")
    current_idx = 0
    stock_count = 0

    # Sort by stock_id then timestamp
    df_sorted = df_temp.sort_values(['stock_id', 'timestamp'])

    for stock_id, stock_data in tqdm(list(df_sorted.groupby('stock_id')), desc="  Stocks"):
        # Ensure data is sorted by timestamp
        stock_data = stock_data.sort_values('timestamp')

        # Extract normalized features
        features = stock_data[feature_columns].values.astype(np.float32)
        timestamps_vals = stock_data['timestamp'].values
        n_samples = len(stock_data)

        # Skip if not enough data
        if n_samples < sequence_length:
            continue

        # Number of sequences for this stock
        n_sequences = n_samples - sequence_length

        # Create sequences
        for i in range(n_sequences):
            X_seq[current_idx] = features[i:i+sequence_length]
            stock_ids_seq[current_idx] = stock_id
            timestamps_seq[current_idx] = timestamps_vals[i+sequence_length]
            current_idx += 1

        stock_count += 1

        # Flush every 50 stocks
        if stock_count % 50 == 0:
            X_seq.flush()
            stock_ids_seq.flush()
            timestamps_seq.flush()

    # Final flush
    X_seq.flush()
    stock_ids_seq.flush()
    timestamps_seq.flush()

    print(f"\n  ✅ Created {current_idx:,} sequences from {stock_count} stocks")

    return X_seq, stock_ids_seq, timestamps_seq


def main():
    parser = argparse.ArgumentParser(
        description='Create professional normalized sequences for transformer models',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--dataset-folder',
        type=str,
        required=True,
        help='Dataset folder name (e.g., dataset_lags_20260206_111644)'
    )

    parser.add_argument(
        '--sequence-length',
        type=int,
        default=20,
        help='Number of timesteps per sequence (default: 20)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Professional Normalized Sequence Creator")
    print("=" * 70)

    # ============================================================
    # LOAD DATA
    # ============================================================

    outputs_dir = Path('/app/outputs/features')
    dataset_folder = outputs_dir / args.dataset_folder

    if not dataset_folder.exists():
        print(f"\n❌ Dataset folder not found: {dataset_folder}")
        return

    print(f"\n📂 Dataset: {dataset_folder.name}")

    # Load features
    features_file = dataset_folder / 'features.parquet'
    if not features_file.exists():
        print(f"\n❌ features.parquet not found")
        return

    print(f"📂 Loading features...")
    df = pd.read_parquet(features_file)
    print(f"   Loaded: {len(df):,} rows × {len(df.columns)} columns")

    # Get feature columns
    exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
    feature_columns = [col for col in df.columns if col not in exclude_cols]

    print(f"   Features: {len(feature_columns)}")

    # ============================================================
    # TEMPORAL SPLIT
    # ============================================================

    print(f"\n🔪 Creating temporal split (train-only fitting)...")

    train_mask, val_mask, test_mask = create_temporal_mask(
        df,
        train_ratio=0.70,
        val_ratio=0.15,
        time_col='timestamp'
    )

    print(f"  Train: {train_mask.sum():,} rows")
    print(f"  Val:   {val_mask.sum():,} rows")
    print(f"  Test:  {test_mask.sum():,} rows")

    # ============================================================
    # FIT NORMALIZER (TRAINING DATA ONLY!)
    # ============================================================

    print(f"\n📏 Fitting feature normalizer (training data only)...")

    normalizer = ProfessionalFeatureNormalizer()
    normalizer.fit(df, feature_columns, train_mask)

    # ============================================================
    # TRANSFORM ALL DATA
    # ============================================================

    print(f"\n🔄 Transforming features...")

    X_normalized = normalizer.transform(df, feature_columns)

    print(f"  Shape: {X_normalized.shape}")
    print(f"  Mean: {X_normalized.mean():.4f}")
    print(f"  Std: {X_normalized.std():.4f}")
    print(f"  Min: {X_normalized.min():.4f}")
    print(f"  Max: {X_normalized.max():.4f}")
    print(f"  NaN count: {np.isnan(X_normalized).sum()}")
    print(f"  Inf count: {np.isinf(X_normalized).sum()}")

    # ============================================================
    # CREATE SEQUENCES
    # ============================================================

    # Use temporary directory for memmap files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        X_seq, stock_ids_seq, timestamps_seq = create_sequences_memmap(
            df=df,
            X_normalized=X_normalized,
            sequence_length=args.sequence_length,
            output_dir=tmp_path,
            feature_columns=feature_columns
        )

        # Copy to regular numpy arrays (these will be compressed by np.savez)
        print(f"\n💾 Saving sequences...")
        X_final = np.array(X_seq)
        stock_ids_final = np.array(stock_ids_seq)
        timestamps_final = np.array(timestamps_seq)

        # ============================================================
        # SAVE TO DISK
        # ============================================================

        output_file = dataset_folder / f'sequences_normalized_{args.sequence_length}d.npz'

        # Save with metadata
        np.savez_compressed(
            output_file,
            X=X_final,
            stock_ids=stock_ids_final,
            timestamps=timestamps_final,
            feature_columns=np.array(feature_columns),
            sequence_length=args.sequence_length,
            num_sequences=len(X_final),
            normalization_method='professional_per_stock_and_global'
        )

        file_size_mb = output_file.stat().st_size / (1024*1024)
        print(f"   ✅ Saved: {output_file.name}")
        print(f"   Size: {file_size_mb:.1f} MB")

    # ============================================================
    # SAVE NORMALIZATION PARAMETERS
    # ============================================================

    norm_params_file = dataset_folder / 'normalization_params.pkl'
    normalizer.save(norm_params_file)

    # Also save feature metadata as JSON for easy inspection
    metadata_file = dataset_folder / 'normalization_metadata.json'
    metadata = {
        'feature_types': normalizer.feature_types,
        'num_features': len(feature_columns),
        'sequence_length': args.sequence_length,
        'num_sequences': len(X_final),
        'num_stocks': df['stock_id'].nunique(),
        'date_created': datetime.now().isoformat(),
    }

    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"   ✅ Metadata: {metadata_file.name}")

    # ============================================================
    # SUMMARY
    # ============================================================

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Input:")
    print(f"  - {df['stock_id'].nunique()} stocks")
    print(f"  - {len(df):,} rows (tabular)")
    print(f"  - {len(feature_columns)} features")

    print(f"\nOutput:")
    print(f"  - {len(X_final):,} sequences")
    print(f"  - Sequence length: {args.sequence_length} days")
    print(f"  - Shape: X=({X_final.shape[0]}, {X_final.shape[1]}, {X_final.shape[2]})")

    print(f"\nFiles:")
    print(f"  - sequences_normalized_{args.sequence_length}d.npz (normalized features)")
    print(f"  - normalization_params.pkl (scaler parameters)")
    print(f"  - normalization_metadata.json (feature types)")

    print(f"\n💡 Usage:")
    print(f"  Load with: data = np.load('{output_file}')")
    print(f"  Access: X = data['X'], stock_ids = data['stock_ids']")
    print(f"  Merge with labels dynamically for any label type (binary/3class/5class)")

    print("\n✅ Done!")


if __name__ == '__main__':
    main()
