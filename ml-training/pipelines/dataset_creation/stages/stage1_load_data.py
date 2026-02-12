"""
Stage 1: Load Data from Database

Loads stock price data and alternative data from the database.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Tuple
import pandas as pd
import numpy as np

# Add paths
sys.path.insert(0, '/app/ml_framework')
sys.path.insert(0, '/app')
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipelines.utils.validators import validate_dataframe, ValidationResult
from pipelines.utils.helpers import print_stage_header, print_stage_success, print_stage_error

logger = logging.getLogger(__name__)


class LoadDataStage:
    """Load data from database"""

    def __init__(self, db_url: Optional[str] = None):
        # Try environment variable first, then parameter, then default
        self.db_url = (
            db_url or
            os.environ.get('DATABASE_URL') or
            os.environ.get('DB_URL') or
            "postgresql://stockuser:stockpass123@database:5432/stock_analyzer"
        )
        self.df: Optional[pd.DataFrame] = None

    def run(self, stocks_subset: Optional[list] = None, start_date: str = "2018-01-01") -> ValidationResult:
        """
        Load data from database

        Args:
            stocks_subset: List of stock IDs to load (None = all stocks)
            start_date: Start date for data loading

        Returns:
            ValidationResult with status
        """
        print_stage_header("Load Data", "Loading stock data from database")

        try:
            # Import database connection (lazy import)
            from sqlalchemy import create_engine, text

            # Create engine
            engine = create_engine(self.db_url)

            # Build query
            query = """
                SELECT
                    s.id as stock_id,
                    s.symbol as ticker,
                    sp.timestamp,
                    sp.open,
                    sp.high,
                    sp.low,
                    sp.close,
                    sp.volume,
                    sp.adjusted_close as adj_close
                FROM stocks s
                JOIN stock_prices sp ON s.id = sp.stock_id
                WHERE sp.timestamp >= :start_date
            """

            params = {"start_date": start_date}

            if stocks_subset:
                query += " AND s.id = ANY(:stocks)"
                params["stocks"] = stocks_subset

            query += " ORDER BY s.id, sp.timestamp"

            # Load data
            logger.info(f"Executing query...")
            self.df = pd.read_sql(text(query), engine, params=params)

            # Basic validation
            result = validate_dataframe(self.df, "Loaded Data")

            if not result.is_valid:
                print_stage_error("Load Data", ValueError(result.message))
                return result

            print_stage_success("Load Data", f"{len(self.df):,} rows from {self.df['stock_id'].nunique()} stocks")

            return result

        except Exception as e:
            result = ValidationResult(
                is_valid=False,
                message=f"Failed to load data: {str(e)}",
                details={"error": str(e)}
            )
            print_stage_error("Load Data", e)
            return result

    def save(self, output_path: Path) -> None:
        """Save loaded data to parquet"""
        if self.df is None:
            raise ValueError("No data to save - run load first")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_parquet(output_path, index=False)
        logger.info(f"Saved data to {output_path}")

    @classmethod
    def from_parquet(cls, input_path: Path) -> 'LoadDataStage':
        """Load from previously saved parquet file"""
        stage = cls()
        stage.df = pd.read_parquet(input_path)
        logger.info(f"Loaded data from {input_path}")
        return stage
