"""
Stage 5: Normalize Sequences

Applies professional feature normalization using RobustScaler.
Based on the working create_normalized_sequences_fixed.py script.
"""

import logging
import sys
import tempfile
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.preprocessing import RobustScaler
from tqdm import tqdm

# Add paths
sys.path.insert(0, '/app/ml_framework')
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipelines.utils.validators import validate_sequences, validate_normalization, ValidationResult
from pipelines.utils.helpers import print_stage_header, print_stage_success, print_stage_error, format_size

logger = logging.getLogger(__name__)


class NormalizeSequencesStage:
    """Normalize features using RobustScaler and create normalized sequences"""

    def __init__(self):
        # Only keep metadata, not full arrays (to save memory)
        self.scalers: dict = {}
        self.feature_columns: list = []
        self.n_sequences: int = 0
        self.output_file: Optional[Path] = None

    def run(
        self,
        df: pd.DataFrame,
        sequence_length: int = 20,
        train_ratio: float = 0.70,
        output_path: Optional[Path] = None
    ) -> ValidationResult:
        """
        Normalize features and create normalized sequences

        Args:
            df: DataFrame with features (already has labels created)
            sequence_length: Number of timesteps per sequence
            train_ratio: Ratio of training data for scaler fitting (temporal split)
            output_path: Where to save the output file

        Returns:
            ValidationResult with status
        """
        print_stage_header("Normalize Sequences", "Applying RobustScaler normalization")

        try:
            # Get feature columns
            exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
            self.feature_columns = [col for col in df.columns if col not in exclude_cols]

            logger.info(f"Features: {len(self.feature_columns)}")

            # ============================================================
            # TEMPORAL SPLIT (train-only fitting to prevent leakage)
            # ============================================================
            logger.info(f"Creating temporal split (train ratio: {train_ratio:.0%})...")

            n = len(df)
            train_end = int(n * train_ratio)
            train_mask = np.zeros(n, dtype=bool)
            train_mask[:train_end] = True

            logger.info(f"  Train: {train_mask.sum():,} rows")

            # ============================================================
            # FIT SCALERS ON TRAINING DATA ONLY
            # ============================================================
            logger.info("Fitting RobustScaler (train data only)...")

            for feature in self.feature_columns:
                if feature not in df.columns:
                    continue

                train_data = df.loc[train_mask, [feature]].fillna(0).values

                # Skip if all zeros
                if train_data.max() == 0 and train_data.min() == 0:
                    self.scalers[feature] = None
                    continue

                # Fit RobustScaler
                scaler = RobustScaler()
                scaler.fit(train_data)
                self.scalers[feature] = scaler

            logger.info(f"  Fitted {len(self.scalers)} feature scalers")

            # ============================================================
            # TRANSFORM ALL DATA
            # ============================================================
            logger.info("Transforming features...")

            df_normalized = df.copy()

            for feature in self.feature_columns:
                if feature not in df.columns:
                    continue

                scaler = self.scalers.get(feature)
                if scaler is None:
                    df_normalized[feature] = df[feature].fillna(0)
                else:
                    original_values = df[feature].fillna(0).values
                    df_normalized[feature] = scaler.transform(
                        df[[feature]].fillna(0).values
                    ).flatten()

                    # Debug: Check first 5 features
                    if list(self.feature_columns).index(feature) < 5:
                        logger.info(f"  {feature}: orig_mean={original_values.mean():.2f}, norm_mean={df_normalized[feature].mean():.4f}")

            # Verify normalization worked
            feature_data = np.array([
                df_normalized[col].values for col in self.feature_columns
            ]).T.flatten()
            feature_data = feature_data[~np.isnan(feature_data)]

            logger.info(f"  Transformed statistics:")
            logger.info(f"     Mean: {np.mean(feature_data):.4f}")
            logger.info(f"     Std:  {np.std(feature_data):.4f}")
            logger.info(f"     Min:  {np.min(feature_data):.4f}")
            logger.info(f"     Max:  {np.max(feature_data):.4f}")
            logger.info(f"     NaN: {np.isnan(feature_data).sum()}")

            # ============================================================
            # CREATE SEQUENCES FROM NORMALIZED DATA (using memmap for memory efficiency)
            # ============================================================
            logger.info(f"Creating normalized sequences (length={sequence_length})...")

            # Count sequences
            n_sequences = 0
            for stock_id, stock_data in df_normalized.groupby('stock_id'):
                n = len(stock_data)
                if n >= sequence_length:
                    n_sequences += n - sequence_length

            self.n_sequences = n_sequences
            n_features = len(self.feature_columns)

            logger.info(f"  Total sequences: {n_sequences:,}")
            logger.info(f"  Shape: ({n_sequences}, {sequence_length}, {n_features})")

            # Estimate memory
            memory_gb = n_sequences * sequence_length * n_features * 4 / (1024**3)
            logger.info(f"  Estimated memory: {memory_gb:.2f} GB")

            # Use temporary directory with memmapped arrays
            # Save INSIDE the context to avoid OOM from copying to RAM
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
                    shape=(n_sequences, sequence_length, n_features)
                )

                stock_ids_seq = np.memmap(
                    stock_ids_memmap_path,
                    dtype='int32',
                    mode='w+',
                    shape=(n_sequences,)
                )

                timestamps_seq = np.memmap(
                    timestamps_memmap_path,
                    dtype='datetime64[s]',
                    mode='w+',
                    shape=(n_sequences,)
                )

                # Fill sequences from NORMALIZED data
                logger.info("  Processing stocks...")
                current_idx = 0
                stock_count = 0

                df_sorted = df_normalized.sort_values(['stock_id', 'timestamp'])

                for stock_id, stock_data in tqdm(list(df_sorted.groupby('stock_id')), desc="  Creating"):
                    stock_data = stock_data.sort_values('timestamp')

                    features = stock_data[self.feature_columns].values.astype(np.float32)
                    timestamps_vals = stock_data['timestamp'].values
                    n_samples = len(stock_data)

                    if n_samples < sequence_length:
                        continue

                    n_stock_seqs = n_samples - sequence_length

                    for i in range(n_stock_seqs):
                        X_seq[current_idx] = features[i:i+sequence_length]
                        stock_ids_seq[current_idx] = stock_id
                        timestamps_seq[current_idx] = timestamps_vals[i+sequence_length]
                        current_idx += 1

                    stock_count += 1

                    if stock_count % 50 == 0:
                        X_seq.flush()
                        stock_ids_seq.flush()
                        timestamps_seq.flush()

                # ============================================================
                # VALIDATION (sample only, not full data)
                # ============================================================
                sample_size = min(10000, len(X_seq))
                sample_indices = np.random.choice(len(X_seq), sample_size, replace=False)
                X_sample = X_seq[sample_indices]

                result = validate_normalization(
                    X_sample.reshape(-1, n_features),
                    self.feature_columns,
                    "Normalized Sequences"
                )

                # ============================================================
                # SAVE INSIDE TEMPFILE CONTEXT (before it closes!)
                # ============================================================
                if output_path is None:
                    output_path = Path('/app/outputs/features') / f'sequences_normalized_{sequence_length}d.npz'

                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                logger.info(f"  Saving to {output_path}...")

                np.savez_compressed(
                    output_path,
                    X=X_seq,
                    stock_ids=stock_ids_seq,
                    timestamps=timestamps_seq,
                    feature_columns=np.array(self.feature_columns),
                    sequence_length=sequence_length,
                    num_sequences=len(X_seq),
                    normalization_method='global_robust_scaler'
                )

                file_size = output_path.stat().st_size
                logger.info(f"  Saved: {format_size(file_size)}")

                # Save metadata
                metadata_path = output_path.parent / 'normalization_metadata.json'
                metadata = {
                    'num_features': len(self.feature_columns),
                    'num_sequences': len(X_seq),
                    'num_stocks': len(np.unique(stock_ids_seq)),
                    'sequence_length': sequence_length,
                    'normalization_method': 'global_robust_scaler',
                    'date_created': datetime.now().isoformat(),
                }

                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

                logger.info(f"  Metadata: {metadata_path}")

                # Store output path for later access
                self.output_file = output_path

            print_stage_success(
                "Normalize Sequences",
                f"{n_sequences:,} normalized sequences → {output_path.name}"
            )

            return result

        except Exception as e:
            result = ValidationResult(
                is_valid=False,
                message=f"Normalization failed: {str(e)}",
                details={"error": str(e)}
            )
            print_stage_error("Normalize Sequences", e)
            return result
