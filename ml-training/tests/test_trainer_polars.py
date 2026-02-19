"""
Test that Polars migration produces identical results to pandas baseline.
Run: pytest tests/test_trainer_polars.py -v
"""
import pytest
import pandas as pd
import polars as pl
import numpy as np
from pathlib import Path


# Baseline values from pandas implementation (MUST match exactly)
BASELINE = {
    'total_rows': 472492,
    'feature_cols_count': 156,
    'train_size': 330744,
    'val_size': 70874,
    'test_size': 70874,
    'first_col': 'open',
    'last_col': 'news_data_available',
    'train_end_date': '2023-08-10 00:00:00',
    'val_end_date': '2024-10-02 00:00:00'
}


@pytest.fixture
def dataset_path():
    """Path to test dataset"""
    return Path("/app/outputs/features/dataset_20260211_193232")


class TestPolarsDataLoading:
    """Test that Polars loads data identically to pandas"""

    def test_load_features_polars(self, dataset_path):
        """Polars should load same rows as pandas"""
        # Load with pandas
        df_pd = pd.read_parquet(dataset_path / "features.parquet")

        # Load with polars
        df_pl = pl.read_parquet(dataset_path / "features.parquet")

        # Verify same shape
        assert df_pl.height == len(df_pd), f"Row count mismatch: {df_pl.height} vs {len(df_pd)}"
        assert df_pl.width == len(df_pd.columns), f"Column count mismatch: {df_pl.width} vs {len(df_pd.columns)}"

    def test_load_labels_polars(self, dataset_path):
        """Polars should load labels identically"""
        df_pd = pd.read_parquet(dataset_path / "labels_3class.parquet")
        df_pl = pl.read_parquet(dataset_path / "labels_3class.parquet")

        assert df_pl.height == len(df_pd)


class TestPolarsMerge:
    """Test that Polars merge produces same results as pandas"""

    def test_merge_row_count(self, dataset_path):
        """Merge should produce exact same row count"""
        # Load with polars
        features = pl.read_parquet(dataset_path / "features.parquet")
        labels = pl.read_parquet(dataset_path / "labels_3class.parquet")

        # Prepare labels (same logic as trainer)
        labels = labels.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.truncate('1d')
        )
        labels = labels.with_columns(pl.col('label_20d').alias('label'))

        # Prepare features
        features = features.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.truncate('1d')
        )

        # Merge
        df = features.join(
            labels.select(['stock_id', 'timestamp', 'label']),
            on=['stock_id', 'timestamp'],
            how='inner'
        )

        assert df.height == BASELINE['total_rows'], f"Merge row count mismatch: {df.height} vs {BASELINE['total_rows']}"


class TestPolarsSort:
    """Test that Polars sort produces same order"""

    def test_sort_by_timestamp(self, dataset_path):
        """Sort should produce same date boundaries"""
        features = pl.read_parquet(dataset_path / "features.parquet")
        labels = pl.read_parquet(dataset_path / "labels_3class.parquet")

        # Prepare and merge
        features = features.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.truncate('1d')
        )
        labels = labels.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.truncate('1d')
        )
        labels = labels.with_columns(pl.col('label_20d').alias('label'))

        df = features.join(
            labels.select(['stock_id', 'timestamp', 'label']),
            on=['stock_id', 'timestamp'],
            how='inner'
        )

        # Sort
        df = df.sort('timestamp')

        # Verify date range
        min_date = str(df['timestamp'].min())
        max_date = str(df['timestamp'].max())

        assert '2018-02-14' in min_date, f"Min date mismatch: {min_date}"
        assert '2025-12-01' in max_date, f"Max date mismatch: {max_date}"


class TestPolarsSplit:
    """Test that Polars split produces same sizes"""

    def test_temporal_split_sizes(self, dataset_path):
        """Split should produce exact same train/val/test sizes"""
        features = pl.read_parquet(dataset_path / "features.parquet")
        labels = pl.read_parquet(dataset_path / "labels_3class.parquet")

        # Prepare
        features = features.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.truncate('1d')
        )
        labels = labels.with_columns(
            pl.col('timestamp').cast(pl.Datetime).dt.truncate('1d')
        )
        labels = labels.with_columns(pl.col('label_20d').alias('label'))

        # Merge and sort
        df = features.join(
            labels.select(['stock_id', 'timestamp', 'label']),
            on=['stock_id', 'timestamp'],
            how='inner'
        )
        df = df.sort('timestamp')

        # Get feature columns (exclude non-features)
        exclude_cols = {'stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown'}
        feature_cols = [c for c in df.columns if c not in exclude_cols]

        # Fill nulls
        df = df.fill_null(0)

        # Split indices
        n = df.height
        train_end = int(n * 0.7)
        val_end = int(n * 0.85)

        # Verify sizes
        train_size = train_end
        val_size = val_end - train_end
        test_size = n - val_end

        assert train_size == BASELINE['train_size'], f"Train size mismatch: {train_size} vs {BASELINE['train_size']}"
        assert val_size == BASELINE['val_size'], f"Val size mismatch: {val_size} vs {BASELINE['val_size']}"
        assert test_size == BASELINE['test_size'], f"Test size mismatch: {test_size} vs {BASELINE['test_size']}"

        # Verify feature column count
        assert len(feature_cols) == BASELINE['feature_cols_count'], f"Feature count mismatch: {len(feature_cols)} vs {BASELINE['feature_cols_count']}"

        # Verify column order
        assert feature_cols[0] == BASELINE['first_col'], f"First col mismatch: {feature_cols[0]} vs {BASELINE['first_col']}"
        assert feature_cols[-1] == BASELINE['last_col'], f"Last col mismatch: {feature_cols[-1]} vs {BASELINE['last_col']}"


class TestPolarsToPandas:
    """Test that Polars to_pandas conversion works for models"""

    def test_to_pandas_preserves_columns(self, dataset_path):
        """Conversion to pandas should preserve column names and order"""
        features = pl.read_parquet(dataset_path / "features.parquet")

        # Select subset for speed
        df_pl = features.slice(0, 1000)
        df_pd = df_pl.to_pandas()

        # Verify columns match
        assert list(df_pl.columns) == list(df_pd.columns)
        assert len(df_pd) == 1000

    def test_to_pandas_dtypes(self, dataset_path):
        """Conversion should produce valid dtypes for models"""
        features = pl.read_parquet(dataset_path / "features.parquet")

        # Select numeric columns only
        exclude = {'stock_id', 'timestamp'}
        numeric_cols = [c for c in features.columns if c not in exclude]
        df_pl = features.select(numeric_cols).slice(0, 100).fill_null(0)
        df_pd = df_pl.to_pandas()

        # Verify no object dtypes (models hate these)
        object_cols = df_pd.select_dtypes(include='object').columns.tolist()
        assert len(object_cols) == 0, f"Found object columns: {object_cols}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
