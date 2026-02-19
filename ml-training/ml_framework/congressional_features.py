"""
Congressional Trading Feature Engineering Module

This module creates 12 congressional trading features for ML training using data
from QuiverQuant's Basic plan ($10/month).

CONGRESSIONAL TRADING FEATURES (12):

BUY/SELL ACTIVITY (6):
  1. congress_bought_30d           - Did any congress member buy this stock?
  2. congress_sold_30d            - Did any congress member sell?
  3. congress_buy_count_30d       - Number of congress members buying
  4. congress_sell_count_30d      - Number of congress members selling
  5. congress_buy_volume_30d      - Total volume of purchases ($)
  6. congress_sell_volume_30d     - Total volume of sales ($)

RATIO FEATURES (3):
  7. congress_net_buy_ratio_30d   - (buys - sells) / total trades
  8. congress_buy_ratio_30d       - buys / total trades
  9. congress_activity_30d        - Total number of trades (buys + sells)

SPECIFIC FEATURES (3):
  10. senator_bought_30d           - Did a senator buy this stock?
  11. representative_bought_30d   - Did a representative buy?
  12. congress_avg_purchase_price_30d - Average purchase price

EXPECTED VALUE: Congressional trading has been shown to outperform the market
by 6-12% annually, making these features highly predictive.
"""

import logging
import pandas as pd
import polars as pl
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://stockuser:stockpass123@database:5432/stock_analyzer'
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class CongressionalFeatures:
    """
    Create congressional trading features for ML training

    Uses data from QuiverQuant Basic plan ($10/mo) which includes:
    - All congressional trading data
    - Historical data access
    - Real-time updates
    """

    @staticmethod
    def get_congressional_trades(stock_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Fetch congressional trades for a stock within date range

        Args:
            stock_id: Stock ID
            start_date: Start date (with buffer for lookback)
            end_date: End date

        Returns:
            DataFrame with congressional trades
        """
        # Need extra history for rolling window calculations
        query_start = start_date - timedelta(days=400)  # Buffer for 1y window

        query = text("""
            SELECT
                date_trunc('day', trade_date) as trade_date,
                insider_name,
                transaction_type,
                total_value,
                price,
                raw_data
            FROM insider_trades
            WHERE stock_id = :stock_id
              AND is_congressional = true
              AND trade_date >= :start_date
              AND trade_date <= :end_date
            ORDER BY trade_date ASC
        """)

        try:
            df = pd.read_sql(
                query,
                engine,
                params={'stock_id': stock_id, 'start_date': query_start, 'end_date': end_date}
            )

            if df.empty:
                return pd.DataFrame()

            df['trade_date'] = pd.to_datetime(df['trade_date'])
            return df

        except Exception as e:
            logger.debug(f"Error fetching congressional trades for stock {stock_id}: {e}")
            return pd.DataFrame()

    @staticmethod
    def calculate_features_for_stock(
        stock_id: int,
        start_date: datetime,
        end_date: datetime,
        feature_dates: pd.DatetimeIndex
    ) -> pd.DataFrame:
        """
        Calculate all 12 congressional features for a stock

        Args:
            stock_id: Stock ID
            start_date: Start date
            end_date: End date
            feature_dates: Dates to calculate features for

        Returns:
            DataFrame with 12 congressional features indexed by date
        """
        # Fetch congressional trades
        trades_df = CongressionalFeatures.get_congressional_trades(stock_id, start_date, end_date)

        # Initialize features DataFrame
        features = pd.DataFrame(index=feature_dates)

        # Define feature columns
        feature_cols = [
            'congress_bought_30d', 'congress_sold_30d',
            'congress_buy_count_30d', 'congress_sell_count_30d',
            'congress_buy_volume_30d', 'congress_sell_volume_30d',
            'congress_net_buy_ratio_30d', 'congress_buy_ratio_30d',
            'congress_activity_30d',
            'senator_bought_30d', 'representative_bought_30d',
            'congress_avg_purchase_price_30d'
        ]

        for col in feature_cols:
            features[col] = 0

        if trades_df.empty:
            return features

        # Parse raw_data to check if it's a senator or representative
        trades_df['is_senator'] = trades_df['raw_data'].apply(
            lambda x: str(x).get('Senator', False) if isinstance(x, dict) else False
        )

        # Calculate features for each date
        for date in feature_dates:
            lookback_end = date
            lookback_start = date - timedelta(days=30)

            # Filter trades in window
            window_trades = trades_df[
                (trades_df['trade_date'] >= lookback_start) &
                (trades_df['trade_date'] <= lookback_end)
            ]

            if window_trades.empty:
                continue

            # Parse transaction types
            buy_trades = window_trades[window_trades['transaction_type'] == 'BUY']
            sell_trades = window_trades[window_trades['transaction_type'] == 'SELL']

            # Count trades
            buy_count = len(buy_trades)
            sell_count = len(sell_trades)
            total_count = buy_count + sell_trades

            # Calculate volumes
            buy_volume = buy_trades['total_value'].sum() if not buy_trades.empty else 0
            sell_volume = sell_trades['total_value'].sum() if not sell_trades.empty else 0

            # Binary features
            congress_bought = int(buy_count > 0)
            congress_sold = int(sell_count > 0)

            # Ratio features
            if total_count > 0:
                net_buy_ratio = (buy_count - sell_count) / total_count
                buy_ratio = buy_count / total_count
            else:
                net_buy_ratio = 0
                buy_ratio = 0

            # Senator/Representative specific
            senator_bought = int(buy_trades['is_senator'].any() if not buy_trades.empty else False)
            representative_bought = int(
                (buy_trades['is_senator'] == False).any() if not buy_trades.empty else False
            )

            # Average purchase price
            avg_purchase_price = 0
            if not buy_trades.empty:
                valid_prices = buy_trades[buy_trades['price'] > 0]
                if not valid_prices.empty:
                    avg_purchase_price = valid_prices['price'].mean()

            # Assign features
            features.loc[date, 'congress_bought_30d'] = congress_bought
            features.loc[date, 'congress_sold_30d'] = congress_sold
            features.loc[date, 'congress_buy_count_30d'] = buy_count
            features.loc[date, 'congress_sell_count_30d'] = sell_count
            features.loc[date, 'congress_buy_volume_30d'] = buy_volume
            features.loc[date, 'congress_sell_volume_30d'] = sell_volume
            features.loc[date, 'congress_net_buy_ratio_30d'] = net_buy_ratio
            features.loc[date, 'congress_buy_ratio_30d'] = buy_ratio
            features.loc[date, 'congress_activity_30d'] = total_count
            features.loc[date, 'senator_bought_30d'] = senator_bought
            features.loc[date, 'representative_bought_30d'] = representative_bought
            features.loc[date, 'congress_avg_purchase_price_30d'] = avg_purchase_price

        # Ensure all columns are numeric
        for col in feature_cols:
            if col in features.columns:
                features[col] = pd.to_numeric(features[col], errors='coerce')

        return features

    @staticmethod
    def add_congressional_features(
        features_df: pd.DataFrame,
        stock_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Add congressional features to existing features DataFrame

        Args:
            features_df: Existing features DataFrame with 'timestamp' column
            stock_id: Stock ID
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with congressional features added
        """
        if features_df is None or features_df.empty:
            return features_df

        # Get feature dates from existing DataFrame
        feature_dates = pd.to_datetime(features_df['timestamp'])

        # Calculate congressional features
        congressional_features = CongressionalFeatures.calculate_features_for_stock(
            stock_id, start_date, end_date, feature_dates
        )

        if congressional_features.empty:
            # Add empty columns with zeros
            feature_cols = [
                'congress_bought_30d', 'congress_sold_30d',
                'congress_buy_count_30d', 'congress_sell_count_30d',
                'congress_buy_volume_30d', 'congress_sell_volume_30d',
                'congress_net_buy_ratio_30d', 'congress_buy_ratio_30d',
                'congress_activity_30d',
                'senator_bought_30d', 'representative_bought_30d',
                'congress_avg_purchase_price_30d'
            ]
            for col in feature_cols:
                features_df[col] = 0
            return features_df

        # Reset index to join
        congressional_features = congressional_features.reset_index()
        congressional_features.rename(columns={'index': 'timestamp'}, inplace=True)

        # Join with existing features
        features_df['timestamp'] = pd.to_datetime(features_df['timestamp'])
        congressional_features['timestamp'] = pd.to_datetime(congressional_features['timestamp'])

        # Left join to preserve all rows
        result = features_df.merge(
            congressional_features,
            on='timestamp',
            how='left'
        )

        # Fill NaN values with 0 (no congressional activity)
        for col in feature_cols:
            if col in result.columns:
                result[col] = result[col].fillna(0)

        logger.info(f"Added 12 congressional features for stock {stock_id}")

        return result


def main():
    """Test congressional features calculation"""
    logging.basicConfig(level=logging.INFO)

    # Test with first stock
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT id FROM stocks WHERE is_tracked = true LIMIT 1"))
        stock_id = result.fetchone()[0]
    finally:
        db.close()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)

    features = CongressionalFeatures.calculate_features_for_stock(
        stock_id, start_date, end_date,
        pd.date_range(start_date, end_date, freq='D')
    )

    print("\n" + "=" * 80)
    print("CONGRESSIONAL FEATURES TEST")
    print("=" * 80)
    print(f"\nStock ID: {stock_id}")
    print(f"Date range: {start_date} to {end_date}")
    print(f"\nFeatures shape: {features.shape}")
    print(f"\nFeature columns:")
    for col in features.columns:
        print(f"  - {col}")
    print(f"\nSample data:")
    print(features.tail(10))
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
