"""
Simple, Robust Feature Normalization for Time Series ML

This is a SIMPLIFIED version that actually works:
- Global normalization (not per-stock) - simpler and more reliable
- RobustScaler for all features - handles outliers
- No log transforms - avoids NaN issues
- Properly handles edge cases

Works for: TCN, LSTM, Transformers
"""

import logging
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List
from sklearn.preprocessing import RobustScaler, StandardScaler, MinMaxScaler

logger = logging.getLogger(__name__)


class SimpleFeatureNormalizer:
    """
    Simple, robust feature normalization

    Strategy:
    - RobustScaler for ALL features (handles outliers well)
    - Global normalization (not per-stock)
    - No log transforms (avoids NaN issues)
    """

    def __init__(self):
        self.scalers = {}
        self.feature_types = {}
        self.is_fitted = False

    def fit(self, df: pd.DataFrame, feature_columns: List[str],
            train_mask: Optional[np.ndarray] = None) -> 'SimpleFeatureNormalizer':
        """
        Fit normalizer on training data only (prevents leakage)

        Args:
            df: Full dataset
            feature_columns: List of feature columns to normalize
            train_mask: Boolean mask indicating training rows (temporal split)
        """
        logger.info("Fitting simple robust feature normalizer...")

        if train_mask is None:
            # Simple temporal split: first 70% is training
            n = len(df)
            split_idx = int(n * 0.70)
            train_mask = np.zeros(n, dtype=bool)
            train_mask[:split_idx] = True
            logger.info(f"  Using temporal split: first {split_idx:,} rows for training")

        train_df = df[train_mask].copy()
        logger.info(f"  Training data: {len(train_df):,} rows")

        for feature in feature_columns:
            if feature not in df.columns:
                logger.warning(f"  Feature {feature} not found, skipping")
                continue

            # Get feature data
            feature_data = train_df[[feature]].fillna(0).values

            # Skip if all zeros
            if feature_data.max() == 0 and feature_data.min() == 0:
                self.scalers[feature] = None
                self.feature_types[feature] = 'zero'
                continue

            # Use RobustScaler for all features
            # It handles outliers well and works with any distribution
            scaler = RobustScaler()
            scaler.fit(feature_data)

            self.scalers[feature] = scaler
            self.feature_types[feature] = 'robust'

            # Calculate actual stats after fitting
            center = scaler.center_[0]
            scale = scaler.scale_[0]
            logger.debug(f"  {feature}: center={center:.4f}, scale={scale:.4f}")

        self.is_fitted = True
        logger.info(f"✅ Fitted {len(self.scalers)} feature scalers")

        return self

    def transform(self, df: pd.DataFrame, feature_columns: List[str]) -> np.ndarray:
        """
        Transform features using fitted scalers

        Args:
            df: Dataset to transform
            feature_columns: List of feature columns

        Returns:
            Normalized features as numpy array (n_samples, n_features)
        """
        if not self.is_fitted:
            raise ValueError("Normalizer must be fitted before transform!")

        logger.info(f"Transforming {len(df):,} samples...")

        n_samples = len(df)
        n_features = len(feature_columns)
        X_normalized = np.zeros((n_samples, n_features), dtype=np.float32)

        for i, feature in enumerate(feature_columns):
            if feature not in df.columns:
                logger.warning(f"  Feature {feature} not found, filling with zeros")
                X_normalized[:, i] = 0
                continue

            scaler = self.scalers.get(feature)

            if scaler is None:
                # All zeros or pass-through
                X_normalized[:, i] = df[feature].fillna(0).values
            else:
                try:
                    # Transform using sklearn scaler
                    X_normalized[:, i] = scaler.transform(df[[feature]].fillna(0).values).flatten()
                except Exception as e:
                    logger.error(f"  Error transforming {feature}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fall back to raw data
                    X_normalized[:, i] = df[feature].fillna(0).values

            if (i + 1) % 50 == 0:
                logger.info(f"  Transformed {i+1}/{len(feature_columns)} features...")

        # Log statistics (handle NaN properly)
        logger.info(f"✅ Transformed to shape: {X_normalized.shape}")

        valid_mask = ~np.isnan(X_normalized)
        n_valid = valid_mask.sum()

        if n_valid > 0:
            X_valid = X_normalized[valid_mask]
            logger.info(f"  Mean: {np.mean(X_valid):.4f} (from {n_valid:,} valid values)")
            logger.info(f"  Std: {np.std(X_valid):.4f}")
            logger.info(f"  Min: {np.min(X_valid):.4f}")
            logger.info(f"  Max: {np.max(X_valid):.4f}")

        nan_count = np.isnan(X_normalized).sum()
        inf_count = np.isinf(X_normalized).sum()
        logger.info(f"  NaN count: {nan_count:,}")
        logger.info(f"  Inf count: {inf_count:,}")

        # Replace any remaining NaN/Inf with 0
        if nan_count > 0 or inf_count > 0:
            logger.warning(f"  Replacing {nan_count:,} NaN and {inf_count:,} Inf values with 0")
            X_normalized = np.nan_to_num(X_normalized, nan=0.0, posinf=0.0, neginf=0.0)

        return X_normalized

    def save(self, path: Path) -> None:
        """Save normalization parameters for reproducibility"""
        save_data = {
            'feature_types': self.feature_types,
            'scaler_params': {},
            'is_fitted': self.is_fitted
        }

        # Save scaler parameters
        for feature, scaler in self.scalers.items():
            if scaler is None:
                save_data['scaler_params'][feature] = None
            elif hasattr(scaler, 'get_params'):
                save_data['scaler_params'][feature] = {
                    'type': type(scaler).__name__,
                    'center': scaler.center_[0] if hasattr(scaler, 'center_') else None,
                    'scale': scaler.scale_[0] if hasattr(scaler, 'scale_') else None,
                }
            else:
                save_data['scaler_params'][feature] = None

        with open(path, 'wb') as f:
            pickle.dump(save_data, f)

        logger.info(f"✅ Saved normalization parameters to {path}")

    @classmethod
    def load(cls, path: Path) -> 'SimpleFeatureNormalizer':
        """Load normalization parameters from disk"""
        with open(path, 'rb') as f:
            save_data = pickle.load(f)

        normalizer = cls()
        normalizer.feature_types = save_data['feature_types']
        normalizer.is_fitted = save_data['is_fitted']

        # Reconstruct scalers
        normalizer.scalers = {}
        for feature, scaler_data in save_data['scaler_params'].items():
            if scaler_data is None:
                normalizer.scalers[feature] = None
            else:
                scaler = RobustScaler()
                scaler.center_ = np.array([scaler_data['center']])
                scaler.scale_ = np.array([scaler_data['scale']])
                normalizer.scalers[feature] = scaler

        logger.info(f"✅ Loaded normalization parameters from {path}")
        return normalizer


def create_temporal_mask(df: pd.DataFrame,
                        train_ratio: float = 0.70,
                        val_ratio: float = 0.15,
                        time_col: str = 'timestamp') -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Create temporal train/val/test masks (prevents leakage)
    """
    # Sort by time
    df_sorted = df.sort_values(time_col)

    n = len(df_sorted)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_mask = np.zeros(n, dtype=bool)
    val_mask = np.zeros(n, dtype=bool)
    test_mask = np.zeros(n, dtype=bool)

    train_mask[:train_end] = True
    val_mask[train_end:val_end] = True
    test_mask[val_end:] = True

    # Return masks aligned with original dataframe
    original_indices = df_sorted.index
    train_mask_full = np.zeros(len(df), dtype=bool)
    val_mask_full = np.zeros(len(df), dtype=bool)
    test_mask_full = np.zeros(len(df), dtype=bool)

    train_mask_full[original_indices[:train_end]] = True
    val_mask_full[original_indices[train_end:val_end]] = True
    test_mask_full[original_indices[val_end:]] = True

    return train_mask_full, val_mask_full, test_mask_full


def create_sequences_memmap(
    df: pd.DataFrame,
    X_normalized: np.ndarray,
    sequence_length: int,
    output_dir: Path,
    feature_columns: list
) -> tuple:
    """Create sequences from normalized features using memory-mapped files"""
    print(f"\n📊 Creating sequences (length={sequence_length})...")

    # Add normalized features to dataframe temporarily
    df_temp = df.copy()
    for i, col in enumerate(feature_columns):
        df_temp[col] = X_normalized[:, i]

    # Count total sequences
    print(f"  Counting sequences...")
    n_total_sequences = sum(
        len(stock_data) - sequence_length
        for _, stock_data in df_temp.groupby('stock_id')
        if len(stock_data) >= sequence_length
    )
    n_features = len(feature_columns)

    print(f"  Total sequences: {n_total_sequences:,}")
    print(f"  Shape: ({n_total_sequences}, {sequence_length}, {n_features})")

    # Estimate memory
    memory_gb = n_total_sequences * sequence_length * n_features * 4 / (1024**3)
    print(f"  MemMap file size: {memory_gb:.2f} GB")

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

    # Fill sequences
    print(f"\n  Processing stocks...")
    current_idx = 0
    stock_count = 0

    df_sorted = df_temp.sort_values(['stock_id', 'timestamp'])

    for stock_id, stock_data in tqdm(list(df_sorted.groupby('stock_id')), desc="  Stocks"):
        stock_data = stock_data.sort_values('timestamp')

        features = stock_data[feature_columns].values.astype(np.float32)
        timestamps_vals = stock_data['timestamp'].values
        n_samples = len(stock_data)

        if n_samples < sequence_length:
            continue

        n_sequences = n_samples - sequence_length

        for i in range(n_sequences):
            X_seq[current_idx] = features[i:i+sequence_length]
            stock_ids_seq[current_idx] = stock_id
            timestamps_seq[current_idx] = timestamps_vals[i+sequence_length]
            current_idx += 1

        stock_count += 1

        if stock_count % 50 == 0:
            X_seq.flush()
            stock_ids_seq.flush()
            timestamps_seq.flush()

    X_seq.flush()
    stock_ids_seq.flush()
    timestamps_seq.flush()

    print(f"\n  ✅ Created {current_idx:,} sequences from {stock_count} stocks")

    return X_seq, stock_ids_seq, timestamps_seq
