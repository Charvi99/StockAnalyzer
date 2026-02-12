#!/usr/bin/env python3
"""
Create Sequential Data for TCN/LSTM/Transformer Models (Memory-Efficient Version)

This script converts tabular stock data into sequential format for deep learning models.
Uses memory-mapped files to avoid RAM issues with large datasets.

Each sample is a sequence of consecutive days from the SAME stock.

Input format (tabular):
    stock_id | timestamp  | feature1 | feature2 | ... | label
    AAPL     | 2024-01-01 | 0.5      | 1.2      | ... | 1
    AAPL     | 2024-01-02 | 0.6      | 1.3      | ... | 0
    MSFT     | 2024-01-01 | 0.4      | 1.1      | ... | 1

Output format (sequential):
    X shape: (n_samples, sequence_length, n_features)
    y shape: (n_samples,)

    Sample 1 (AAPL): [days 0-39] → label for day 39
    Sample 2 (AAPL): [days 1-40] → label for day 40
    Sample 3 (MSFT): [days 0-39] → label for day 39
    ...

Usage:
    python scripts/create_tcn_sequences.py --dataset-folder dataset_lags_20260206_111644

    # With custom sequence length
    python scripts/create_tcn_sequences.py --dataset-folder dataset_lags_20260206_111644 --sequence-length 30

    # For specific label type
    python scripts/create_tcn_sequences.py --dataset-folder dataset_lags_20260206_111644 --label-type binary
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
import tempfile

import pandas as pd
import numpy as np
from tqdm import tqdm

sys.path.insert(0, '/backend')


def count_sequences(df: pd.DataFrame, sequence_length: int) -> int:
    """
    Count total number of sequences that will be created

    Args:
        df: DataFrame with stock_id column
        sequence_length: Number of timesteps per sequence

    Returns:
        Total number of sequences
    """
    total = 0
    for stock_id, stock_data in df.groupby('stock_id'):
        n = len(stock_data)
        if n >= sequence_length:
            total += n - sequence_length
    return total


def create_sequences_memmap(
    df: pd.DataFrame,
    feature_columns: list,
    label_column: str,
    sequence_length: int,
    output_dir: Path
) -> tuple:
    """
    Create sequences using memory-mapped files (avoids RAM overload)

    Args:
        df: Full DataFrame with all stocks
        feature_columns: List of feature column names
        label_column: Name of label column
        sequence_length: Number of timesteps per sequence
        output_dir: Directory for temporary memmap files

    Returns:
        X_all: Memory-mapped array (n_total_sequences, sequence_length, n_features)
        y_all: Memory-mapped array (n_total_sequences,)
    """
    print(f"\n📊 Creating sequences (length={sequence_length})...")

    # First pass: count total sequences
    print(f"  Counting sequences...")
    n_total_sequences = count_sequences(df, sequence_length)
    n_features = len(feature_columns)

    print(f"  Total sequences: {n_total_sequences:,}")
    print(f"  Shape: ({n_total_sequences}, {sequence_length}, {n_features})")

    # Estimate memory
    memory_gb = n_total_sequences * sequence_length * n_features * 4 / (1024**3)
    print(f"  MemMap file size: {memory_gb:.2f} GB (on disk, not RAM)")

    # Create memory-mapped files
    X_memmap_path = output_dir / 'X_sequences.tmp'
    y_memmap_path = output_dir / 'y_sequences.tmp'

    X_all = np.memmap(
        X_memmap_path,
        dtype='float32',
        mode='w+',
        shape=(n_total_sequences, sequence_length, n_features)
    )

    y_all = np.memmap(
        y_memmap_path,
        dtype='float32',
        mode='w+',
        shape=(n_total_sequences,)
    )

    # Second pass: fill memmap with sequences
    print(f"\n  Processing stocks...")
    current_idx = 0
    stock_count = 0

    for stock_id, stock_data in tqdm(list(df.groupby('stock_id')), desc="  Stocks"):
        # Sort by timestamp
        stock_data = stock_data.sort_values('timestamp')

        # Extract features and labels
        features = stock_data[feature_columns].fillna(0).values
        labels = stock_data[label_column].fillna(0).values

        # Clean data: convert to float, replace NaN/inf with 0
        features = np.asarray(features, dtype=np.float32)
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)

        # Clip extreme values to reasonable range (-100 to +100)
        # This prevents gradient explosion while preserving useful signal
        features = np.clip(features, -100, 100)

        n_samples = len(stock_data)

        # Skip if not enough data
        if n_samples < sequence_length:
            continue

        # Number of sequences for this stock
        n_sequences = n_samples - sequence_length

        # Create sequences and write to memmap
        for i in range(n_sequences):
            X_all[current_idx] = features[i:i+sequence_length]
            y_all[current_idx] = labels[i+sequence_length]
            current_idx += 1

        stock_count += 1

        # Flush every 50 stocks to be safe
        if stock_count % 50 == 0:
            X_all.flush()
            y_all.flush()

    # Final flush
    X_all.flush()
    y_all.flush()

    print(f"\n  ✅ Created {current_idx:,} sequences from {stock_count} stocks")

    return X_all, y_all


def main():
    parser = argparse.ArgumentParser(
        description='Create sequential data for TCN/LSTM models (memory-efficient)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create sequences with default length (40)
  python scripts/create_tcn_sequences.py --dataset-folder dataset_lags_20260206_111644

  # Shorter sequences (less memory, faster training)
  python scripts/create_tcn_sequences.py --dataset-folder dataset_lags_20260206_111644 --sequence-length 30

  # For specific label type
  python scripts/create_tcn_sequences.py --dataset-folder dataset_lags_20260206_111644 --label-type 3class
        """
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
        default=40,
        help='Number of timesteps per sequence (default: 40)'
    )

    parser.add_argument(
        '--label-type',
        type=str,
        default='binary',
        choices=['binary', '3class', '5class'],
        help='Label type to use (default: binary)'
    )

    parser.add_argument(
        '--label-column',
        type=str,
        default=None,
        help='Specific label column (e.g., label_20d). Auto-detects if not specified.'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("StockAnalyzer ML - TCN Sequence Creator (Memory-Efficient)")
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

    # Load labels
    labels_file = dataset_folder / f'labels_{args.label_type}.parquet'
    if not labels_file.exists():
        print(f"\n❌ {labels_file.name} not found")
        print(f"   Available: {list(dataset_folder.glob('labels_*.parquet'))}")
        return

    print(f"📂 Loading labels: {labels_file.name}")
    labels_df = pd.read_parquet(labels_file)
    print(f"   Loaded: {len(labels_df):,} rows")

    # ============================================================
    # MERGE FEATURES AND LABELS
    # ============================================================

    print(f"\n🔗 Merging features and labels...")
    df = df.merge(labels_df, on=['stock_id', 'timestamp'], how='inner')
    print(f"   After merge: {len(df):,} rows")

    # Determine label column
    if args.label_column:
        label_column = args.label_column
    else:
        # Auto-detect: prefer label_20d, then label_30d, then label
        label_candidates = ['label_20d', 'label_30d', 'label']
        label_column = None
        for col in label_candidates:
            if col in df.columns:
                label_column = col
                break

        if label_column is None:
            # Find any column starting with 'label'
            label_cols = [col for col in df.columns if col.startswith('label')]
            if label_cols:
                label_column = label_cols[0]
            else:
                raise ValueError("No label column found in dataset!")

    print(f"   Using label column: {label_column}")

    # Get label distribution
    label_dist = df[label_column].value_counts().sort_index()
    print(f"\n   Label distribution:")
    for label, count in label_dist.items():
        pct = count / len(df) * 100
        print(f"     {label}: {count:,} ({pct:.1f}%)")

    # ============================================================
    # PREPARE FEATURE COLUMNS
    # ============================================================

    # Columns to exclude from features
    exclude_cols = {'stock_id', 'timestamp', 'max_upside', 'max_drawdown',
                   'final_return_20d', 'final_return_30d', 'final_return_40d',
                   'score_20d', 'score_30d', 'score_40d'}

    # Exclude all label columns
    label_cols = [col for col in df.columns if col.startswith('label_') or col == 'label']
    exclude_cols.update(label_cols)

    # Get feature columns
    feature_columns = [col for col in df.columns if col not in exclude_cols]

    print(f"\n📊 Feature columns: {len(feature_columns)}")
    print(f"   Excluded: {len(exclude_cols)} columns (IDs, timestamps, labels)")

    # ============================================================
    # CREATE SEQUENCES (with memory mapping)
    # ============================================================

    # Create temp directory for memmap files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        X_sequences, y_labels = create_sequences_memmap(
            df,
            feature_columns,
            label_column,
            args.sequence_length,
            tmpdir
        )

        # ============================================================
        # SAVE SEQUENCES
        # ============================================================

        print(f"\n💾 Saving sequences...")

        output_file = dataset_folder / f'sequences_{args.label_type}_{args.sequence_length}d.npz'

        # Save as compressed numpy archive
        np.savez_compressed(
            output_file,
            X=X_sequences[:],  # Copy from memmap
            y=y_labels[:],     # Copy from memmap
            feature_columns=np.array(feature_columns),
            label_column=label_column,
            sequence_length=args.sequence_length,
            label_type=args.label_type,
            num_stocks=len(df['stock_id'].unique())
        )

        file_size_mb = output_file.stat().st_size / 1024 / 1024
        print(f"   ✅ Saved: {output_file.name}")
        print(f"   Size: {file_size_mb:.1f} MB")

        # Save counts before deleting memmaps
        n_sequences = len(y_labels)
        n_features = len(feature_columns)

        # Close memmaps
        del X_sequences
        del y_labels

    # ============================================================
    # SUMMARY
    # ============================================================

    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Input:")
    print(f"  - {len(df['stock_id'].unique()):,} stocks")
    print(f"  - {len(df):,} rows (tabular)")
    print(f"  - {n_features} features")
    print(f"\nOutput:")
    print(f"  - {n_sequences:,} sequences")
    print(f"  - Sequence length: {args.sequence_length} days")
    print(f"  - Shape: X=({n_sequences}, {args.sequence_length}, {n_features}), y=({n_sequences},)")
    print(f"\nFile:")
    print(f"  - {output_file.name}")
    print(f"  - Location: {dataset_folder}/")
    print(f"\n💡 Train TCN with:")
    print(f"   python train.py --dataset-folder {args.dataset_folder} --models tcn")


if __name__ == '__main__':
    main()
