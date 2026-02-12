"""
Stage 2: Feature Engineering

Creates technical indicators and engineered features from price data.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
import pandas as pd
import numpy as np

# Add paths
sys.path.insert(0, '/app/ml_framework')
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipelines.utils.validators import validate_dataframe, ValidationResult
from pipelines.utils.helpers import print_stage_header, print_stage_success, print_stage_error

logger = logging.getLogger(__name__)


class FeatureEngineeringStage:
    """Feature engineering for stock price data"""

    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self.feature_columns: list = []

    def run(self, df: pd.DataFrame, add_lags: bool = True) -> ValidationResult:
        """
        Run feature engineering

        Args:
            df: Input DataFrame with price data
            add_lags: Whether to add lag features

        Returns:
            ValidationResult with status
        """
        print_stage_header("Feature Engineering", "Creating technical indicators")

        try:
            self.df = df.copy()

            # Import feature engineering functions
            sys.path.insert(0, '/app/scripts')
            from feature_engineering import add_technical_indicators
            from add_lag_features import add_lag_features as add_lags_func

            # Add technical indicators
            logger.info("Adding technical indicators...")
            self.df = add_technical_indicators(self.df)

            # Add lag features
            if add_lags:
                logger.info("Adding lag features...")
                self.df = add_lags_func(self.df)

            # Get feature columns
            exclude_cols = {'stock_id', 'timestamp', 'ticker', 'label', 'max_upside', 'max_drawdown'}
            self.feature_columns = [col for col in self.df.columns if col not in exclude_cols]

            # Validate
            result = validate_dataframe(self.df, "Engineered Features")

            if not result.is_valid:
                print_stage_error("Feature Engineering", ValueError(result.message))
                return result

            print_stage_success(
                "Feature Engineering",
                f"{len(self.feature_columns)} features created"
            )

            return result

        except Exception as e:
            result = ValidationResult(
                is_valid=False,
                message=f"Feature engineering failed: {str(e)}",
                details={"error": str(e)}
            )
            print_stage_error("Feature Engineering", e)
            return result

    def save(self, output_path: Path) -> None:
        """Save engineered features to parquet"""
        if self.df is None:
            raise ValueError("No data to save - run feature engineering first")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_parquet(output_path, index=False)
        logger.info(f"Saved features to {output_path}")
