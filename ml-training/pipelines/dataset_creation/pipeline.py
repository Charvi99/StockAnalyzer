"""
Dataset Creation Pipeline - Main Orchestration

This script orchestrates the entire dataset creation process:
1. Load data from database
2. Feature engineering (technical indicators + lag features)
3. Create labels (binary/3class/5class)
4. Create sequences (stock-wise)
5. Normalize sequences (RobustScaler, train-only fit)

Usage:
    # Run full pipeline
    python -m pipelines.dataset_creation.pipeline --full --label-type binary

    # Run specific stages
    python -m pipelines.dataset_creation.pipeline --stages 1 2 3 --label-type binary
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Literal
import traceback
import pandas as pd
import numpy as np

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from pipelines.utils.validators import print_validation_summary, ValidationResult
from pipelines.utils.helpers import (
    setup_logging, get_or_create_dataset_folder,
    print_stage_header, print_stage_success, format_number
)

# Import stages
from pipelines.dataset_creation.stages import (
    LoadDataStage,
    FeatureEngineeringStage,
    CreateLabelsStage,
    CreateSequencesStage,
    NormalizeSequencesStage
)

logger = logging.getLogger(__name__)


class DatasetCreationPipeline:
    """Main pipeline orchestration"""

    def __init__(
        self,
        dataset_name: Optional[str] = None,
        label_type: Literal["binary", "3class", "5class"] = "binary",
        sequence_length: int = 20,
        output_dir: Path = Path("/app/outputs/features")
    ):
        self.dataset_name = dataset_name
        self.label_type = label_type
        self.sequence_length = sequence_length
        self.output_dir = output_dir
        self.dataset_folder = get_or_create_dataset_folder(dataset_name)

        # Validation results
        self.validation_results: List[ValidationResult] = []

        # Stage outputs
        self.df = None
        self.df_features = None
        self.df_labels = None
        self.sequences = None
        self.sequences_normalized = None

    def run_stage_1_load_data(self, start_date: str = "2018-01-01") -> bool:
        """Stage 1: Load data from database"""
        try:
            stage = LoadDataStage()

            # Try loading from existing features file first
            existing_features = self.dataset_folder / "features.parquet"

            if existing_features.exists():
                logger.info(f"Found existing features file: {existing_features}")
                stage.df = pd.read_parquet(existing_features)
                result = ValidationResult(
                    is_valid=True,
                    message=f"Loaded existing features: {len(stage.df):,} rows"
                )
            else:
                # Load from database
                result = stage.run(start_date=start_date)

            self.validation_results.append(result)
            self.df = stage.df

            return result.is_valid

        except Exception as e:
            logger.error(f"Stage 1 failed: {e}")
            traceback.print_exc()
            return False

    def run_stage_2_feature_engineering(self, add_lags: bool = True) -> bool:
        """Stage 2: Feature engineering"""
        try:
            # Load existing features if available
            if self.df is None:
                features_file = self.dataset_folder / "features.parquet"
                if features_file.exists():
                    logger.info(f"Loading existing features from {features_file}")
                    self.df = pd.read_parquet(features_file)
                    # Skip to validation
                    result = ValidationResult(
                        is_valid=True,
                        message=f"Loaded existing features: {len(self.df):,} rows"
                    )
                    self.validation_results.append(result)
                    self.df_features = self.df
                    return result.is_valid

            stage = FeatureEngineeringStage()
            result = stage.run(self.df, add_lags=add_lags)

            self.validation_results.append(result)
            self.df_features = stage.df

            # Save features
            features_file = self.dataset_folder / "features.parquet"
            stage.save(features_file)

            return result.is_valid

        except Exception as e:
            logger.error(f"Stage 2 failed: {e}")
            traceback.print_exc()
            return False

    def run_stage_3_create_labels(
        self,
        label_type: str,
        forward_days: int = 5,
        upside_threshold: float = 0.03,
        downside_threshold: float = -0.03
    ) -> bool:
        """Stage 3: Create labels"""
        try:
            stage = CreateLabelsStage()
            result = stage.run(
                self.df_features,
                label_type=label_type,
                forward_days=forward_days,
                upside_threshold=upside_threshold,
                downside_threshold=downside_threshold
            )

            self.validation_results.append(result)
            self.df_labels = stage.df

            return result.is_valid

        except Exception as e:
            logger.error(f"Stage 3 failed: {e}")
            traceback.print_exc()
            return False

    def run_stage_4_create_sequences(self, include_labels: bool = True) -> bool:
        """Stage 4: Create sequences"""
        try:
            stage = CreateSequencesStage()
            result = stage.run(
                self.df_labels,
                sequence_length=self.sequence_length,
                include_labels=include_labels
            )

            self.validation_results.append(result)
            self.sequences = stage.sequences

            # Save sequences
            sequences_file = self.dataset_folder / f"sequences_{self.label_type}_{self.sequence_length}d.npz"
            stage.save(sequences_file, label_type=self.label_type, sequence_length=self.sequence_length)

            return result.is_valid

        except Exception as e:
            logger.error(f"Stage 4 failed: {e}")
            traceback.print_exc()
            return False

    def run_stage_5_normalize_sequences(self, train_ratio: float = 0.70) -> bool:
        """Stage 5: Normalize sequences"""
        try:
            # Load existing features if not already loaded
            if self.df_labels is None:
                features_file = self.dataset_folder / "features.parquet"
                if features_file.exists():
                    logger.info(f"Loading existing features from {features_file}")
                    self.df_labels = pd.read_parquet(features_file)
                else:
                    logger.error("No features found. Run stages 1-3 first.")
                    return False

            stage = NormalizeSequencesStage()

            # Pass output path - stage will save directly
            norm_file = self.dataset_folder / f"sequences_normalized_{self.sequence_length}d.npz"

            result = stage.run(
                self.df_labels,
                sequence_length=self.sequence_length,
                train_ratio=train_ratio,
                output_path=norm_file
            )

            self.validation_results.append(result)

            # Stage now saves directly, just store metadata
            logger.info(f"Normalized sequences saved to: {stage.output_file}")

            return result.is_valid

        except Exception as e:
            logger.error(f"Stage 5 failed: {e}")
            traceback.print_exc()
            return False

    def run_full(
        self,
        start_date: str = "2018-01-01",
        add_lags: bool = True,
        forward_days: int = 5,
        upside_threshold: float = 0.03,
        downside_threshold: float = -0.03,
        train_ratio: float = 0.70
    ) -> bool:
        """Run full pipeline"""
        print("\n" + "=" * 70)
        print("DATASET CREATION PIPELINE")
        print("=" * 70)
        print(f"Dataset folder: {self.dataset_folder.name}")
        print(f"Label type: {self.label_type}")
        print(f"Sequence length: {self.sequence_length}")
        print("=" * 70)

        # Stage 1: Load data
        if not self.run_stage_1_load_data(start_date=start_date):
            return False

        # Stage 2: Feature engineering
        if not self.run_stage_2_feature_engineering(add_lags=add_lags):
            return False

        # Stage 3: Create labels
        if not self.run_stage_3_create_labels(
            label_type=self.label_type,
            forward_days=forward_days,
            upside_threshold=upside_threshold,
            downside_threshold=downside_threshold
        ):
            return False

        # Stage 4: Create sequences (optional - can skip if just want normalized)
        # We'll skip this and go straight to normalized sequences

        # Stage 5: Normalize sequences (this creates sequences too)
        if not self.run_stage_5_normalize_sequences(train_ratio=train_ratio):
            return False

        # Print validation summary
        all_passed = print_validation_summary(self.validation_results)

        # Print final output
        print("\n" + "=" * 70)
        print("OUTPUT FILES")
        print("=" * 70)
        print(f"  📁 Dataset folder: {self.dataset_folder}")
        print(f"  📄 features.parquet - Engineered features ({format_number(self.df_features['stock_id'].nunique())} stocks)")
        print(f"  📄 sequences_normalized_{self.sequence_length}d.npz - Normalized sequences")
        print("=" * 70)

        return all_passed


def main():
    parser = argparse.ArgumentParser(
        description="Dataset Creation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--full',
        action='store_true',
        help='Run full pipeline (all stages)'
    )

    parser.add_argument(
        '--stages',
        type=int,
        nargs='+',
        choices=[1, 2, 3, 4, 5],
        help='Run specific stages (e.g., --stages 1 2 3)'
    )

    parser.add_argument(
        '--dataset-name',
        type=str,
        default=None,
        help='Dataset folder name (default: auto-generate with timestamp)'
    )

    parser.add_argument(
        '--label-type',
        type=str,
        default='binary',
        choices=['binary', '3class', '5class'],
        help='Label type (default: binary)'
    )

    parser.add_argument(
        '--sequence-length',
        type=int,
        default=20,
        help='Sequence length in days (default: 20)'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        default='2018-01-01',
        help='Start date for data loading (default: 2018-01-01)'
    )

    parser.add_argument(
        '--no-lags',
        action='store_true',
        help='Skip lag features'
    )

    parser.add_argument(
        '--forward-days',
        type=int,
        default=5,
        help='Forward days for label calculation (default: 5)'
    )

    parser.add_argument(
        '--upside-threshold',
        type=float,
        default=0.03,
        help='Upside threshold for labels (default: 0.03 = 3%%)'
    )

    parser.add_argument(
        '--downside-threshold',
        type=float,
        default=-0.03,
        help='Downside threshold for labels (default: -0.03 = -3%%)'
    )

    parser.add_argument(
        '--train-ratio',
        type=float,
        default=0.70,
        help='Train ratio for temporal split (default: 0.70)'
    )

    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level)

    # Create pipeline
    pipeline = DatasetCreationPipeline(
        dataset_name=args.dataset_name,
        label_type=args.label_type,
        sequence_length=args.sequence_length
    )

    # Run pipeline
    if args.full:
        success = pipeline.run_full(
            start_date=args.start_date,
            add_lags=not args.no_lags,
            forward_days=args.forward_days,
            upside_threshold=args.upside_threshold,
            downside_threshold=args.downside_threshold,
            train_ratio=args.train_ratio
        )
    elif args.stages:
        # Run specific stages
        success = True
        for stage_num in args.stages:
            if stage_num == 1:
                success &= pipeline.run_stage_1_load_data(start_date=args.start_date)
            elif stage_num == 2:
                success &= pipeline.run_stage_2_feature_engineering(add_lags=not args.no_lags)
            elif stage_num == 3:
                success &= pipeline.run_stage_3_create_labels(
                    label_type=args.label_type,
                    forward_days=args.forward_days,
                    upside_threshold=args.upside_threshold,
                    downside_threshold=args.downside_threshold
                )
            elif stage_num == 4:
                success &= pipeline.run_stage_4_create_sequences()
            elif stage_num == 5:
                success &= pipeline.run_stage_5_normalize_sequences(train_ratio=args.train_ratio)

        # Print summary
        print_validation_summary(pipeline.validation_results)
    else:
        parser.print_help()
        success = False

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
