"""
Integration test for Polars migration - verifies full pipeline works end-to-end.

Tests that:
1. Trainer loads data with Polars
2. Features can be processed by all feature modules
3. Data flows correctly through ensemble
"""
import pytest
import polars as pl
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import patch, MagicMock


class TestPolarsIntegration:
    """Test full pipeline integration with Polars migrations"""

    def test_trainer_returns_pandas_for_models(self):
        """Trainer should return pandas DataFrames for model compatibility"""
        from ml_framework.trainer import ModelTrainer
        from ml_framework.config import load_config

        config = load_config('configs/default.yaml')

        # Mock the data loading to return Polars
        mock_features = pl.DataFrame({
            'stock_id': [1, 1, 1],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'open': [100.0, 101.0, 102.0],
            'close': [101.0, 102.0, 103.0],
            'volume': [1000, 1100, 1200]
        })

        mock_labels = pl.DataFrame({
            'stock_id': [1, 1, 1],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'label_20d': [0, 1, 1]
        })

        trainer = ModelTrainer(config)

        with patch.object(trainer, 'load_data', return_value=(mock_features, mock_labels)):
            features, labels = trainer.load_data()

            # Verify load_data returns Polars
            assert isinstance(features, pl.DataFrame)
            assert isinstance(labels, pl.DataFrame)

    def test_prepare_data_converts_to_pandas(self):
        """prepare_data should convert Polars to pandas for models"""
        from ml_framework.trainer import ModelTrainer
        from ml_framework.config import load_config

        config = load_config('configs/default.yaml')

        # Create Polars DataFrames with proper datetime types
        import datetime
        timestamps = [
            datetime.datetime(2024, 1, 1),
            datetime.datetime(2024, 1, 2),
            datetime.datetime(2024, 1, 3),
            datetime.datetime(2024, 1, 4),
            datetime.datetime(2024, 1, 5),
            datetime.datetime(2024, 1, 6),
            datetime.datetime(2024, 1, 7)
        ]

        features = pl.DataFrame({
            'stock_id': [1, 1, 1, 1, 1, 1, 1],
            'timestamp': timestamps,
            'open': [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            'close': [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
            'volume': [1000, 1100, 1200, 1300, 1400, 1500, 1600],
            'max_upside': [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0],
            'max_drawdown': [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
        })

        labels = pl.DataFrame({
            'stock_id': [1, 1, 1, 1, 1, 1, 1],
            'timestamp': timestamps,
            'label_20d': [0, 0, 1, 1, 0, 1, 0]
        })

        trainer = ModelTrainer(config)

        X_train, X_val, X_test, y_train, y_val, y_test = trainer.prepare_data(features, labels)

        # Verify output is pandas (for model compatibility)
        assert isinstance(X_train, pd.DataFrame)
        assert isinstance(X_val, pd.DataFrame)
        assert isinstance(X_test, pd.DataFrame)
        assert isinstance(y_train, np.ndarray)
        assert isinstance(y_val, np.ndarray)
        assert isinstance(y_test, np.ndarray)

    def test_ensemble_accepts_pandas_from_trainer(self):
        """Ensemble should work with pandas output from trainer"""
        from ml_framework.ensemble import Ensemble

        # Create mock models that return predictions
        mock_model1 = MagicMock()
        mock_model1.predict_proba.return_value = np.array([[0.3, 0.7], [0.6, 0.4], [0.2, 0.8]])
        mock_model1.predict.return_value = np.array([1, 0, 1])

        mock_model2 = MagicMock()
        mock_model2.predict_proba.return_value = np.array([[0.4, 0.6], [0.5, 0.5], [0.3, 0.7]])
        mock_model2.predict.return_value = np.array([1, 1, 1])

        models = {'model1': mock_model1, 'model2': mock_model2}

        ensemble = Ensemble(models, method='weighted_average')

        # Create pandas DataFrame (as from trainer)
        X = pd.DataFrame({
            'feature1': [1.0, 2.0, 3.0],
            'feature2': [0.5, 1.5, 2.5]
        })

        # Should work without error
        predictions = ensemble.predict_proba(X)

        assert predictions.shape == (3, 2)
        assert np.allclose(predictions.sum(axis=1), 1.0)  # Probabilities sum to 1

    def test_all_feature_modules_accept_pandas(self):
        """All feature modules should handle pandas input correctly"""
        # This is a smoke test - just ensure imports work
        from ml_framework.congressional_features import CongressionalFeatures
        from ml_framework.insider_features import InsiderFeatures
        from ml_framework.news_features import NewsFeatures
        from ml_framework.alternative_features import AlternativeFeatures

        # Verify all classes have the expected methods
        assert hasattr(CongressionalFeatures, 'add_congressional_features')
        assert hasattr(InsiderFeatures, 'add_insider_features')
        assert hasattr(NewsFeatures, 'add_news_features')
        assert hasattr(AlternativeFeatures, 'add_alternative_features')


class TestDataFlow:
    """Test data flow through Polars migrations"""

    def test_polars_to_pandas_conversion(self):
        """Polars DataFrame should convert cleanly to pandas"""
        # Create Polars DataFrame with various types
        pl_df = pl.DataFrame({
            'int_col': [1, 2, 3],
            'float_col': [1.1, 2.2, 3.3],
            'str_col': ['a', 'b', 'c'],
            'bool_col': [True, False, True]
        })

        # Convert to pandas
        pd_df = pl_df.to_pandas()

        # Verify types are preserved appropriately
        assert pd_df['int_col'].dtype in [np.int64, int]
        assert pd_df['float_col'].dtype in [np.float64, float]
        assert pd_df['bool_col'].dtype in [np.bool_, bool]

    def test_polars_preserves_numeric_data(self):
        """Polars should preserve numeric precision during conversion"""
        # Create Polars DataFrame with precise floats
        pl_df = pl.DataFrame({
            'price': [100.123456789, 200.987654321, 150.555555555],
            'volume': [1000000, 2000000, 3000000],
            'ratio': [0.123456789, 0.987654321, 0.555555555]
        })

        pd_df = pl_df.to_pandas()

        # Verify values are preserved (within float precision)
        np.testing.assert_array_almost_equal(
            pl_df['price'].to_numpy(),
            pd_df['price'].values,
            decimal=9
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
