#!/usr/bin/env python3
"""
Create Professional Normalized Sequences - FIXED VERSION

This version:
1. Uses sklearn RobustScaler (proven to work)
2. Global normalization per feature (simpler, no per-stock complexity)
3. Actually applies normalization before creating sequences
4. NO labels in sequences (dynamic loading for all label types)
"""

import sys
import os
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime
import tempfile

import pandas as pd
import numpy as np
from tqdm import tqdm
from sklearn.preprocessing import RobustScaler

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def count_sequences(df: pd.DataFrame, sequence_length: int) -> int:
    """Count total sequences"""
    total = 0
    for stock_id, stock_data in df.groupby('stock_id'):
        n = len(stock_data)
        if n >= sequence_length:
            total += n - sequence_length
    return total


def main():
    parser = argparse.ArgumentParser(description='Create normalized sequences (FIXED)')
    parser.add_argument('--dataset-folder', type=str, required=True)
    parser.add_argument('--sequence-length', type=int, default=20)

    args = parser.parse_args()

    print("=" * 70)
    print("Professional Normalized Sequence Creator (FIXED)")
    print("=" * 70)

    # Load data
    outputs_dir = Path('/app/outputs/features')
    dataset_folder = outputs_dir / args.dataset_folder

    df = pd.read_parquet(dataset_folder / 'features.parquet')
    print(f"\n📂 Loaded: {len(df):,} rows × {len(df.columns)} columns")

    # Get feature columns
    exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
    feature_columns = [col for col in df.columns if col not in exclude_cols]
    print(f"   Features: {len(feature_columns)}")

    # Temporal split (70% train / 15% val / 15% test)
    print(f"\n🔪 Temporal split (train-only fitting)...")
    n = len(df)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)
    train_mask = np.zeros(n, dtype=bool)
    train_mask[:train_end] = True
    print(f"  Train: {train_mask.sum():,} rows")

    # Fit scalers on training data ONLY
    print(f"\n📏 Fitting RobustScaler (train data only)...")
    scalers = {}
    for feature in feature_columns:
        if feature not in df.columns:
            continue

        train_data = df.loc[train_mask, [feature]].fillna(0).values

        # Skip if all zeros
        if train_data.max() == 0 and train_data.min() == 0:
            scalers[feature] = None
            continue

        # Fit RobustScaler
        scaler = RobustScaler()
        scaler.fit(train_data)
        scalers[feature] = scaler

    print(f"  ✅ Fitted {len(scalers)} feature scalers")

    # Transform ALL data (train/val/test)
    print(f"\n🔄 Transforming features...")
    df_normalized = df.copy()

    for feature in feature_columns:
        if feature not in df.columns:
            continue

        scaler = scalers.get(feature)
        if scaler is None:
            df_normalized[feature] = df[feature].fillna(0)
        else:
            df_normalized[feature] = scaler.transform(df[[feature]].fillna(0).values).flatten()

    # Verify normalization worked
    feature_data = np.array([df_normalized[col].values for col in feature_columns]).T.flatten()
    feature_data = feature_data[~np.isnan(feature_data)]  # Remove NaN for stats

    print(f"  ✅ Transformed statistics:")
    print(f"     Mean: {np.mean(feature_data):.4f}")
    print(f"     Std:  {np.std(feature_data):.4f}")
    print(f"     Min:  {np.min(feature_data):.4f}")
    print(f"     Max:  {np.max(feature_data):.4f}")
    print(f"     NaN: {np.isnan(np.array([df_normalized[col].values for col in feature_columns])).sum()}")

    # Create sequences from NORMALIZED data
    print(f"\n📊 Creating sequences (length={args.sequence_length})...")

    n_total_sequences = count_sequences(df_normalized, args.sequence_length)
    n_features = len(feature_columns)

    print(f"  Total sequences: {n_total_sequences:,}")
    print(f"  Shape: ({n_total_sequences}, {args.sequence_length}, {n_features})")

    # Use temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create memmapped arrays
        X_memmap_path = tmp_path / 'X.tmp'
        stock_ids_memmap_path = tmp_path / 'stock_ids.tmp'
        timestamps_memmap_path = tmp_path / 'timestamps.tmp'

        X_seq = np.memmap(
            X_memmap_path,
            dtype='float32',
            mode='w+',
            shape=(n_total_sequences, args.sequence_length, n_features)
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

        # Fill sequences from NORMALIZED data
        print(f"\n  Processing stocks...")
        current_idx = 0
        stock_count = 0

        df_sorted = df_normalized.sort_values(['stock_id', 'timestamp'])

        for stock_id, stock_data in tqdm(list(df_sorted.groupby('stock_id')), desc="  Stocks"):
            stock_data = stock_data.sort_values('timestamp')

            features = stock_data[feature_columns].values.astype(np.float32)
            timestamps_vals = stock_data['timestamp'].values
            n_samples = len(stock_data)

            if n_samples < args.sequence_length:
                continue

            n_sequences = n_samples - args.sequence_length

            for i in range(n_sequences):
                X_seq[current_idx] = features[i:i+args.sequence_length]
                stock_ids_seq[current_idx] = stock_id
                timestamps_seq[current_idx] = timestamps_vals[i+args.sequence_length]
                current_idx += 1

            stock_count += 1

            if stock_count % 50 == 0:
                X_seq.flush()
                stock_ids_seq.flush()
                timestamps_seq.flush()

        # Copy to regular arrays for saving
        X_final = np.array(X_seq)
        stock_ids_final = np.array(stock_ids_seq)
        timestamps_final = np.array(timestamps_seq)

    # Save
    print(f"\n💾 Saving sequences...")
    output_file = dataset_folder / f'sequences_normalized_{args.sequence_length}d.npz'

    np.savez_compressed(
        output_file,
        X=X_final,
        stock_ids=stock_ids_final,
        timestamps=timestamps_final,
        feature_columns=np.array(feature_columns),
        sequence_length=args.sequence_length,
        num_sequences=len(X_final),
        normalization_method='global_robust_scaler'
    )

    file_size_mb = output_file.stat().st_size / (1024*1024)
    print(f"   ✅ Saved: {output_file.name}")
    print(f"   Size: {file_size_mb:.1f} MB")

    # Save metadata
    metadata = {
        'num_features': len(feature_columns),
        'num_sequences': len(X_final),
        'num_stocks': df['stock_id'].nunique(),
        'sequence_length': args.sequence_length,
        'normalization_method': 'global_robust_scaler',
        'date_created': datetime.now().isoformat(),
    }

    metadata_file = dataset_folder / 'normalization_metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"   ✅ Metadata: {metadata_file.name}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  - {len(X_final):,} sequences")
    print(f"  - Shape: ({X_final.shape[0]}, {X_final.shape[1]}, {X_final.shape[2]})")
    print(f"  - Properly normalized (RobustScaler)")
    print(f"  - No labels baked in (reuse for binary/3class/5class)")
    print("\n✅ Done!")


if __name__ == '__main__':
    main()
