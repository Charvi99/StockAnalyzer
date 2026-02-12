"""
Stage 3: Create Labels

Creates prediction labels (binary, 3-class, 5-class) for ML training.
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Literal
import pandas as pd
import numpy as np

# Add paths
sys.path.insert(0, '/app/ml_framework')
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipelines.utils.validators import ValidationResult
from pipelines.utils.helpers import print_stage_header, print_stage_success, print_stage_error

logger = logging.getLogger(__name__)


class CreateLabelsStage:
    """Create prediction labels for ML training"""

    def __init__(self):
        self.df: Optional[pd.DataFrame] = None

    def run(
        self,
        df: pd.DataFrame,
        label_type: Literal["binary", "3class", "5class"] = "binary",
        forward_days: int = 5,
        upside_threshold: float = 0.03,
        downside_threshold: float = -0.03
    ) -> ValidationResult:
        """
        Create labels for prediction

        Args:
            df: DataFrame with price data
            label_type: Type of label (binary, 3class, 5class)
            forward_days: Days to look forward for label calculation
            upside_threshold: Threshold for positive class (3% = 0.03)
            downside_threshold: Threshold for negative class (-3% = -0.03)

        Returns:
            ValidationResult with status
        """
        print_stage_header("Create Labels", f"Creating {label_type} labels")

        try:
            self.df = df.copy()

            # Import label creation functions
            sys.path.insert(0, '/app/scripts')
            from create_labels import create_binary_labels, create_3class_labels, create_5class_labels

            # Create appropriate label type
            if label_type == "binary":
                logger.info(f"Creating binary labels (threshold: {upside_threshold:.1%})...")
                self.df = create_binary_labels(
                    self.df,
                    forward_days=forward_days,
                    upside_threshold=upside_threshold
                )
            elif label_type == "3class":
                logger.info(f"Creating 3-class labels...")
                self.df = create_3class_labels(
                    self.df,
                    forward_days=forward_days,
                    upside_threshold=upside_threshold,
                    downside_threshold=downside_threshold
                )
            elif label_type == "5class":
                logger.info(f"Creating 5-class labels...")
                self.df = create_5class_labels(
                    self.df,
                    forward_days=forward_days
                )
            else:
                raise ValueError(f"Unknown label_type: {label_type}")

            # Verify label column exists
            if 'label' not in self.df.columns:
                raise ValueError("Label column not created")

            # Report label distribution
            label_dist = self.df['label'].value_counts().sort_index()
            logger.info("Label distribution:")
            for label, count in label_dist.items():
                pct = count / len(self.df) * 100
                logger.info(f"  Class {int(label)}: {count:,} ({pct:.1f}%)")

            # Validate
            nan_count = self.df['label'].isna().sum()
            if nan_count > 0:
                logger.warning(f"NaN labels: {nan_count:,} ({nan_count/len(self.df)*100:.1f}%)")
                self.df['label'].fillna(0, inplace=True)

            print_stage_success(
                "Create Labels",
                f"{label_type} labels - distribution: {dict(label_dist)}"
            )

            return ValidationResult(
                is_valid=True,
                message=f"Created {label_type} labels",
                details={
                    "label_type": label_type,
                    "distribution": label_dist.to_dict(),
                    "nan_count": int(nan_count)
                }
            )

        except Exception as e:
            result = ValidationResult(
                is_valid=False,
                message=f"Label creation failed: {str(e)}",
                details={"error": str(e)}
            )
            print_stage_error("Create Labels", e)
            return result

    def save(self, output_path: Path) -> None:
        """Save DataFrame with labels to parquet"""
        if self.df is None:
            raise ValueError("No data to save - run label creation first")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_parquet(output_path, index=False)
        logger.info(f"Saved labels to {output_path}")
