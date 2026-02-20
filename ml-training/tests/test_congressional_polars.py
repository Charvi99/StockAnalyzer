"""
Test that congressional_features.py Polars migration produces same results.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch
import polars as pl


class TestCongressionalFeaturesMigration:
    """Test congressional features Polars migration"""

    def test_empty_trades_returns_correct_columns(self):
        """Test that empty trades returns correct columns with zeros"""
        from ml_framework.congressional_features import CongressionalFeatures

        with patch.object(CongressionalFeatures, 'get_congressional_trades', return_value=pl.DataFrame()):
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 1, 31)
            feature_dates = pd.date_range(start_date, end_date, freq='D')

            result = CongressionalFeatures.calculate_features_for_stock(1, start_date, end_date, feature_dates)

            assert len(result) == 31
            expected_cols = [
                'congress_bought_30d', 'congress_sold_30d', 'congress_buy_count_30d', 'congress_sell_count_30d',
                'congress_buy_volume_30d', 'congress_sell_volume_30d', 'congress_net_buy_ratio_30d',
                'congress_buy_ratio_30d', 'congress_activity_30d', 'senator_bought_30d',
                'representative_bought_30d', 'congress_avg_purchase_price_30d'
            ]
            for col in expected_cols:
                assert col in result.columns
                assert (result[col] == 0).all()

    def test_feature_values_are_numeric(self):
        """Test that all feature values are numeric types"""
        from ml_framework.congressional_features import CongressionalFeatures

        mock_trades = pl.DataFrame({
            'trade_date': [datetime(2024, 1, 5), datetime(2024, 1, 15)],
            'insider_name': ['Rep. Smith', 'Sen. Jones'],
            'transaction_type': ['BUY', 'SELL'],
            'total_value': [10000, 5000],
            'price': [100.0, 50.0],
            'raw_data': [{'Senator': True}, {'Senator': False}]
        })

        with patch.object(CongressionalFeatures, 'get_congressional_trades', return_value=mock_trades):
            result = CongressionalFeatures.calculate_features_for_stock(
                1,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                pd.date_range('2024-01-01', '2024-01-31')
            )

            for col in result.columns:
                assert result[col].dtype in [np.float64, np.int64, float, int, 'float64', 'int64']

    def test_calculates_correct_buy_sell_counts(self):
        """Test that buy/sell counts are calculated correctly"""
        from ml_framework.congressional_features import CongressionalFeatures

        mock_trades = pl.DataFrame({
            'trade_date': [
                datetime(2024, 1, 5),
                datetime(2024, 1, 10),
                datetime(2024, 1, 15),
            ],
            'insider_name': ['Rep. Smith', 'Sen. Jones', 'Rep. Johnson'],
            'transaction_type': ['BUY', 'BUY', 'SELL'],
            'total_value': [10000, 15000, 5000],
            'price': [100.0, 50.0, 25.0],
            'raw_data': [{'Senator': False}, {'Senator': True}, {'Senator': False}]
        })

        with patch.object(CongressionalFeatures, 'get_congressional_trades', return_value=mock_trades):
            result = CongressionalFeatures.calculate_features_for_stock(
                1,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                pd.date_range('2024-01-01', '2024-01-31')
            )

            # On Jan 20, all 3 trades should be in the 30-day window
            jan_20_result = result.loc[pd.Timestamp('2024-01-20')]
            assert jan_20_result['congress_buy_count_30d'] == 2
            assert jan_20_result['congress_sell_count_30d'] == 1
            assert jan_20_result['congress_buy_volume_30d'] == 25000  # 10000 + 15000
            assert jan_20_result['congress_sell_volume_30d'] == 5000

    def test_senator_vs_representative_features(self):
        """Test senator vs representative feature differentiation"""
        from ml_framework.congressional_features import CongressionalFeatures

        mock_trades = pl.DataFrame({
            'trade_date': [datetime(2024, 1, 10)],
            'insider_name': ['Sen. Jones'],
            'transaction_type': ['BUY'],
            'total_value': [10000],
            'price': [100.0],
            'raw_data': [{'Senator': True}]
        })

        with patch.object(CongressionalFeatures, 'get_congressional_trades', return_value=mock_trades):
            result = CongressionalFeatures.calculate_features_for_stock(
                1,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                pd.date_range('2024-01-01', '2024-01-31')
            )

            jan_20_result = result.loc[pd.Timestamp('2024-01-20')]
            assert jan_20_result['senator_bought_30d'] == 1
            assert jan_20_result['representative_bought_30d'] == 0

    def test_ratio_features_calculation(self):
        """Test net buy ratio and buy ratio calculations"""
        from ml_framework.congressional_features import CongressionalFeatures

        # 2 buys, 1 sell = 3 total trades
        mock_trades = pl.DataFrame({
            'trade_date': [
                datetime(2024, 1, 5),
                datetime(2024, 1, 10),
                datetime(2024, 1, 15),
            ],
            'insider_name': ['A', 'B', 'C'],
            'transaction_type': ['BUY', 'BUY', 'SELL'],
            'total_value': [10000, 15000, 5000],
            'price': [100.0, 50.0, 25.0],
            'raw_data': [{'Senator': False}, {'Senator': False}, {'Senator': False}]
        })

        with patch.object(CongressionalFeatures, 'get_congressional_trades', return_value=mock_trades):
            result = CongressionalFeatures.calculate_features_for_stock(
                1,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                pd.date_range('2024-01-01', '2024-01-31')
            )

            jan_20_result = result.loc[pd.Timestamp('2024-01-20')]
            # net_buy_ratio = (2 - 1) / 3 = 1/3
            assert abs(jan_20_result['congress_net_buy_ratio_30d'] - 1/3) < 0.001
            # buy_ratio = 2 / 3
            assert abs(jan_20_result['congress_buy_ratio_30d'] - 2/3) < 0.001
            # activity = 3 total trades
            assert jan_20_result['congress_activity_30d'] == 3


class TestAddCongressionalFeatures:
    """Test add_congressional_features function"""

    def test_adds_columns_to_existing_dataframe(self):
        """Test that add_congressional_features adds 12 columns to input DataFrame"""
        from ml_framework.congressional_features import CongressionalFeatures

        features_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', '2024-01-10', freq='D'),
            'feature1': range(1, 11)
        })

        with patch.object(CongressionalFeatures, 'get_congressional_trades', return_value=pl.DataFrame()):
            result = CongressionalFeatures.add_congressional_features(
                features_df,
                1,
                datetime(2024, 1, 1),
                datetime(2024, 1, 10)
            )

            assert 'feature1' in result.columns
            congress_cols = [
                'congress_bought_30d', 'congress_sold_30d', 'congress_buy_count_30d', 'congress_sell_count_30d',
                'congress_buy_volume_30d', 'congress_sell_volume_30d', 'congress_net_buy_ratio_30d',
                'congress_buy_ratio_30d', 'congress_activity_30d', 'senator_bought_30d',
                'representative_bought_30d', 'congress_avg_purchase_price_30d'
            ]
            for col in congress_cols:
                assert col in result.columns
            assert len(result) == 10

    def test_preserves_existing_features(self):
        """Test that existing features are preserved"""
        from ml_framework.congressional_features import CongressionalFeatures

        features_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', '2024-01-05', freq='D'),
            'existing_feature': [1, 2, 3, 4, 5]
        })

        with patch.object(CongressionalFeatures, 'get_congressional_trades', return_value=pl.DataFrame()):
            result = CongressionalFeatures.add_congressional_features(
                features_df,
                1,
                datetime(2024, 1, 1),
                datetime(2024, 1, 5)
            )

            assert 'existing_feature' in result.columns
            assert list(result['existing_feature']) == [1, 2, 3, 4, 5]

    def test_handles_empty_input_dataframe(self):
        """Test that empty input DataFrame is handled correctly"""
        from ml_framework.congressional_features import CongressionalFeatures

        empty_df = pd.DataFrame()
        result = CongressionalFeatures.add_congressional_features(
            empty_df,
            1,
            datetime(2024, 1, 1),
            datetime(2024, 1, 5)
        )

        assert result.empty
