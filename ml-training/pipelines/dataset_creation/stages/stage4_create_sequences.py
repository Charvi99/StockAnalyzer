"""
Stage 4: Create Sequences

Creates stock-wise sequential data for TCN/LSTM/Transformer models.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
import pandas as pd
import numpy as np
from tqdm import tqdm

# Add paths
sys.path.insert(0, '/app/ml_framework')
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipelines.utils.validators import validate_sequences, ValidationResult
from pipelines.utils.helpers import print_stage_header, print_stage_success, print_stage_error, format_size

logger = logging.getLogger(__name__)


class CreateSequencesStage:
    """Create sequential data for deep learning models"""

    def __init__(self):
        self.sequences: Optional[np.ndarray] = None
        self.stock_ids: Optional[np.ndarray] = None
        self.timestamps: Optional[np.ndarray] = None
        self.labels: Optional[np.ndarray] = None
        self.feature_columns: list = []

    def run(
        self,
        df: pd.DataFrame,
        sequence_length: int = 20,
        include_labels: bool = True
    ) -> ValidationResult:
        """
        Create stock-wise sequences

        Args:
            df: DataFrame with features and labels
            sequence_length: Number of timesteps per sequence
            include_labels: Whether to include labels in sequences

        Returns:
            ValidationResult with status
        """
        print_stage_header("Create Sequences", f"Creating {sequence_length}-day stock-wise sequences")

        try:
            # Get feature columns
            exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
            self.feature_columns = [col for col in df.columns if col not in exclude_cols]

            logger.info(f"Features: {len(self.feature_columns)}")

            # Count sequences
            n_sequences = 0
            for stock_id, stock_data in df.groupby('stock_id'):
                n = len(stock_data)
                if n >= sequence_length:
                    n_sequences += n - sequence_length

            logger.info(f"Total sequences to create: {n_sequences:,}")

            # Create arrays
            n_features = len(self.feature_columns)
            self.sequences = np.zeros((n_sequences, sequence_length, n_features), dtype=np.float32)
            self.stock_ids = np.zeros(n_sequences, dtype=np.int32)
            self.timestamps = np.zeros(n_sequences, dtype='datetime64[s]')

            if include_labels:
                self.labels = np.zeros(n_sequences, dtype=np.int32)

            # Fill sequences
            logger.info("Processing stocks...")
            current_idx = 0

            df_sorted = df.sort_values(['stock_id', 'timestamp'])

            for stock_id, stock_data in tqdm(list(df_sorted.groupby('stock_id')), desc="  Creating"):
                stock_data = stock_data.sort_values('timestamp')

                features = stock_data[self.feature_columns].values.astype(np.float32)
                timestamps_vals = stock_data['timestamp'].values
                labels_vals = stock_data['label'].values if include_labels else None
                n_samples = len(stock_data)

                if n_samples < sequence_length:
                    continue

                n_stock_seqs = n_samples - sequence_length

                for i in range(n_stock_seqs):
                    self.sequences[current_idx] = features[i:i+sequence_length]
                    self.stock_ids[current_idx] = stock_id
                    self.timestamps[current_idx] = timestamps_vals[i+sequence_length]

                    if include_labels and labels_vals is not None:
                        self.labels[current_idx] = labels_vals[i+sequence_length]

                    current_idx += 1

            logger.info(f"Created {current_idx:,} sequences")

            # Validate
            result = validate_sequences(self.sequences, "Created Sequences")

            print_stage_success(
                "Create Sequences",
                f"{n_sequences:,} sequences × {sequence_length} × {n_features}"
            )

            return result

        except Exception as e:
            result = ValidationResult(
                is_valid=False,
                message=f"Sequence creation failed: {str(e)}",
                details={"error": str(e)}
            )
            print_stage_error("Create Sequences", e)
            return result

    def save(self, output_path: Path, label_type: str = "binary", sequence_length: int = 20) -> None:
        """Save sequences to compressed npz file"""
        if self.sequences is None:
            raise ValueError("No sequences to save - run sequence creation first")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        save_dict = {
            'X': self.sequences,
            'stock_ids': self.stock_ids,
            'timestamps': self.timestamps,
            'feature_columns': np.array(self.feature_columns),
            'sequence_length': sequence_length,
            'num_sequences': len(self.sequences)
        }

        if self.labels is not None:
            save_dict['y'] = self.labels

        np.savez_compressed(output_path, **save_dict)

        file_size = output_path.stat().st_size
        logger.info(f"Saved sequences to {output_path} ({format_size(file_size)})")
