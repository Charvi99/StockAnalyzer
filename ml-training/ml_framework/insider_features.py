"""
SEC Form 4 Insider Trading Feature Engineering Module

This module creates 12 corporate insider trading features for ML training using data
from SEC Form 4 filings (is_congressional = false).

These features capture trading patterns by corporate insiders (officers, directors,
executives) which have been shown to have predictive power for stock returns.

SEC FORM 4 INSIDER FEATURES (12):

BUY/SELL ACTIVITY (4):
  1. insider_buy_count_30d      - Number of insider buys in last 30 days
  2. insider_sell_count_30d     - Number of insider sells in last 30 days
  3. insider_buy_volume_30d     - Total volume of insider buys (shares)
  4. insider_net_buy_ratio_30d  - Net buy ratio (buys - sells) / total

EXECUTIVE ACTIVITY (3):
  5. ceo_bought_30d             - Binary: Did CEO buy in last 30 days?
  6. cto_bought_30d             - Binary: Did CTO/Chief Technology Officer buy?
  7. cfo_bought_30d             - Binary: Did CFO/Chief Financial Officer buy?

CLUSTER BUYING (1):
  8. cluster_buying_30d         - Binary: 3+ insiders bought in last 30 days

PRICE CONTEXT (1):
  9. insider_buy_at_52w_low     - Binary: Insider buys near 52-week low

SENTIMENT (1):
  10. insider_sentiment_30d     - Sentiment score (-100 to +100)

VALUE METRICS (2):
  11. insider_buy_value_30d     - Total $ value of insider buys
  12. insider_sell_value_30d    - Total $ value of insider sells

EXPECTED VALUE: Corporate insider purchases (especially by CEOs and cluster buying)
have been shown to predict positive abnormal returns, while large sales often precede
negative returns.
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


class InsiderFeatures:
    """
    Create SEC Form 4 corporate insider trading features for ML training

    Features are calculated from the insider_trades table (is_congressional=false)
    and joined with the existing feature DataFrame.

    These features capture trading patterns by corporate insiders (officers, directors,
    executives) from SEC Form 4 filings.
    """

    @staticmethod
    def get_insider_trades(stock_id: int, start_date: datetime, end_date: datetime) -> pl.DataFrame:
        """
        Fetch SEC Form 4 corporate insider trades for a stock within date range

        Args:
            stock_id: Stock ID
            start_date: Start date (with buffer for lookback)
            end_date: End date

        Returns:
            Polars DataFrame with SEC Form 4 insider trades (is_congressional=false)
        """
        # Need extra history for rolling window calculations
        query_start = start_date - timedelta(days=400)  # Buffer for 1y window

        # Format dates for SQL query
        query_start_str = query_start.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        # Use Polars native Postgres support with connectorx
        query = f"""
            SELECT
                date_trunc('day', trade_date) as trade_date,
                insider_name,
                insider_title,
                transaction_type,
                shares,
                price,
                total_value,
                is_congressional
            FROM insider_trades
            WHERE stock_id = {stock_id}
              AND is_congressional = false
              AND trade_date >= '{query_start_str}'
              AND trade_date <= '{end_date_str}'
            ORDER BY trade_date ASC
        """

        try:
            # Use Polars native Postgres support
            df = pl.read_database_uri(
                query=query,
                uri=DATABASE_URL
            )

            if df.is_empty():
                return pl.DataFrame()

            return df

        except Exception as e:
            logger.debug(f"Error fetching insider trades for stock {stock_id}: {e}")
            return pl.DataFrame()

    @staticmethod
    def get_stock_prices(stock_id: int, start_date: datetime, end_date: datetime) -> pl.DataFrame:
        """
        Fetch stock prices for 52-week high/low calculations

        Args:
            stock_id: Stock ID
            start_date: Start date (with buffer)
            end_date: End date

        Returns:
            Polars DataFrame with prices
        """
        # Need 1 year of history for 52-week high/low
        query_start = start_date - timedelta(days=400)

        # Format dates for SQL query
        query_start_str = query_start.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        # Use Polars native Postgres support with connectorx
        query = f"""
            SELECT
                date_trunc('day', timestamp) as date,
                high,
                low,
                close
            FROM stock_prices
            WHERE stock_id = {stock_id}
              AND timeframe = '1d'
              AND timestamp >= '{query_start_str}'
              AND timestamp <= '{end_date_str}'
            ORDER BY timestamp ASC
        """

        try:
            # Use Polars native Postgres support
            df = pl.read_database_uri(
                query=query,
                uri=DATABASE_URL
            )

            if df.is_empty():
                return pl.DataFrame()

            return df

        except Exception as e:
            logger.debug(f"Error fetching prices for stock {stock_id}: {e}")
            return pl.DataFrame()

    @staticmethod
    def calculate_features_for_stock(
        stock_id: int,
        start_date: datetime,
        end_date: datetime,
        feature_dates: pd.DatetimeIndex
    ) -> pd.DataFrame:
        """
        Calculate all 12 insider features for a stock

        Args:
            stock_id: Stock ID
            start_date: Start date
            end_date: End date
            feature_dates: Dates to calculate features for (from main feature engineering)

        Returns:
            DataFrame with 12 insider features indexed by date
        """
        # Fetch insider trades
        trades_pl = InsiderFeatures.get_insider_trades(stock_id, start_date, end_date)

        # Fetch prices for 52-week high/low
        prices_pl = InsiderFeatures.get_stock_prices(stock_id, start_date, end_date)

        # Define feature columns
        feature_cols = [
            'insider_buy_count_30d', 'insider_sell_count_30d',
            'insider_buy_volume_30d', 'insider_net_buy_ratio_30d',
            'ceo_bought_30d', 'cto_bought_30d', 'cfo_bought_30d',
            'cluster_buying_30d',
            'insider_buy_at_52w_low',
            'insider_sentiment_30d',
            'insider_buy_value_30d', 'insider_sell_value_30d'
        ]

        # Create features DataFrame with Polars (vectorized)
        dates_list = feature_dates.to_list()

        if trades_pl.is_empty():
            # Return empty DataFrame with zeros
            features = pl.DataFrame({
                'timestamp': dates_list,
                **{col: [0] * len(dates_list) for col in feature_cols}
            })
            return features.to_pandas().set_index('timestamp')

        # Build features for each date using Polars
        features_list = []

        for date in dates_list:
            lookback_end = date
            lookback_start = date - timedelta(days=30)

            # Filter trades in window (Polars filter)
            window_trades = trades_pl.filter(
                (pl.col('trade_date') >= lookback_start) &
                (pl.col('trade_date') <= lookback_end)
            )

            if window_trades.height == 0:
                features_list.append({
                    'timestamp': date,
                    **{col: 0 for col in feature_cols}
                })
                continue

            # Separate buy/sell trades
            buys = window_trades.filter(pl.col('transaction_type') == 'BUY')
            sells = window_trades.filter(pl.col('transaction_type') == 'SELL')

            # Count buys and sells
            buy_count = buys.height
            sell_count = sells.height

            # Calculate volumes
            buy_volume = buys.select(pl.col('shares').sum()).item() if buys.height > 0 else 0

            # Net buy ratio
            total_trades = buy_count + sell_count
            if total_trades > 0:
                net_buy_ratio = (buy_count - sell_count) / total_trades
            else:
                net_buy_ratio = 0

            # =========================================================================
            # FEATURE 5-7: Executive Activity (CEO, CTO, CFO)
            # =========================================================================

            # Check for CEO activity (case-insensitive title matching)
            ceo_trades = window_trades.filter(
                pl.col('insider_title').str.contains('CEO|Chief Executive Officer', literal=False)
            )
            ceo_bought = 1 if ceo_trades.height > 0 and ceo_trades.select(pl.col('transaction_type') == 'BUY').any().item() else 0

            # Check for CTO activity
            cto_trades = window_trades.filter(
                pl.col('insider_title').str.contains('CTO|Chief Technology Officer', literal=False)
            )
            cto_bought = 1 if cto_trades.height > 0 and cto_trades.select(pl.col('transaction_type') == 'BUY').any().item() else 0

            # Check for CFO activity
            cfo_trades = window_trades.filter(
                pl.col('insider_title').str.contains('CFO|Chief Financial Officer', literal=False)
            )
            cfo_bought = 1 if cfo_trades.height > 0 and cfo_trades.select(pl.col('transaction_type') == 'BUY').any().item() else 0

            # =========================================================================
            # FEATURE 8: Cluster Buying (3+ different insiders buying)
            # =========================================================================

            if buys.height > 0:
                unique_insiders = buys.select(pl.col('insider_name').n_unique()).item()
                cluster_buying = 1 if unique_insiders >= 3 else 0
            else:
                cluster_buying = 0

            # =========================================================================
            # FEATURE 9: Insider Buy at 52-Week Low
            # =========================================================================

            buy_near_low = 0

            if prices_pl.height > 0 and buys.height > 0:
                # Get 52-week range ending at this date
                price_history = prices_pl.filter(pl.col('date') <= date)

                if price_history.height >= 50:  # Need at least 50 trading days
                    week_52_high = price_history.select(pl.col('high').max()).item()
                    week_52_low = price_history.select(pl.col('low').min()).item()

                    # Check if any buy was near 52-week low (within 5%)
                    buys_in_window = buys.filter(pl.col('trade_date') >= lookback_start)

                    if buys_in_window.height > 0 and week_52_low > 0:
                        # Check each buy price
                        for buy_price in buys_in_window.select(pl.col('price')).to_series().to_list():
                            if buy_price and week_52_low > 0:
                                price_vs_low = (buy_price - week_52_low) / week_52_low
                                if price_vs_low <= 0.05:  # Within 5% of low
                                    buy_near_low = 1
                                    break

            # =========================================================================
            # FEATURE 10: Insider Sentiment (-100 to +100)
            # =========================================================================

            # Calculate sentiment based on volume-weighted buys vs sells
            buy_volume = buys.select(pl.col('shares').sum()).item() if buys.height > 0 else 0
            sell_volume = sells.select(pl.col('shares').sum()).item() if sells.height > 0 else 0
            total_volume = buy_volume + sell_volume

            if total_volume > 0:
                sentiment = ((buy_volume - sell_volume) / total_volume) * 100
            else:
                sentiment = 0

            # =========================================================================
            # FEATURE 11-12: Value Metrics ($ value of trades)
            # =========================================================================

            buy_value = buys.select(pl.col('total_value').sum()).item() if buys.height > 0 else 0
            sell_value = sells.select(pl.col('total_value').sum()).item() if sells.height > 0 else 0

            features_list.append({
                'timestamp': date,
                'insider_buy_count_30d': buy_count,
                'insider_sell_count_30d': sell_count,
                'insider_buy_volume_30d': buy_volume,
                'insider_net_buy_ratio_30d': net_buy_ratio,
                'ceo_bought_30d': ceo_bought,
                'cto_bought_30d': cto_bought,
                'cfo_bought_30d': cfo_bought,
                'cluster_buying_30d': cluster_buying,
                'insider_buy_at_52w_low': buy_near_low,
                'insider_sentiment_30d': sentiment,
                'insider_buy_value_30d': buy_value,
                'insider_sell_value_30d': sell_value
            })

        # Create Polars DataFrame and convert to pandas for compatibility
        features = pl.DataFrame(features_list)
        return features.to_pandas().set_index('timestamp')

    @staticmethod
    def add_insider_features(
        features_df: pd.DataFrame,
        stock_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Add insider features to existing features DataFrame

        Args:
            features_df: Existing features DataFrame with 'timestamp' column
            stock_id: Stock ID
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with insider features added
        """
        if features_df is None or features_df.empty:
            return features_df

        # Define feature columns
        feature_cols = [
            'insider_buy_count_30d', 'insider_sell_count_30d',
            'insider_buy_volume_30d', 'insider_net_buy_ratio_30d',
            'ceo_bought_30d', 'cto_bought_30d', 'cfo_bought_30d',
            'cluster_buying_30d',
            'insider_buy_at_52w_low',
            'insider_sentiment_30d',
            'insider_buy_value_30d', 'insider_sell_value_30d'
        ]

        try:
            # Get feature dates from existing DataFrame
            if 'timestamp' in features_df.columns:
                feature_dates = pd.to_datetime(features_df['timestamp'])
            else:
                # Try to get from index
                feature_dates = pd.to_datetime(features_df.index)
                features_df = features_df.reset_index()
                features_df.rename(columns={'index': 'timestamp'}, inplace=True)

            # Calculate insider features
            insider_features = InsiderFeatures.calculate_features_for_stock(
                stock_id, start_date, end_date, feature_dates
            )

            if insider_features.empty:
                # Add empty columns with zeros
                result = features_df.copy()
                for col in feature_cols:
                    result[col] = 0
                return result

            # Convert to Polars for faster merge
            features_pl = pl.from_pandas(features_df)
            insider_pl = pl.from_pandas(insider_features.reset_index())
            # After reset_index(), the column is already named 'timestamp' (from the index name)
            # No rename needed

            # Normalize timestamps
            features_pl = features_pl.with_columns(
                pl.col('timestamp').cast(pl.Datetime).dt.truncate('1d')
            )
            insider_pl = insider_pl.with_columns(
                pl.col('timestamp').cast(pl.Datetime).dt.truncate('1d')
            )

            # Left join to preserve all rows
            result = features_pl.join(
                insider_pl,
                on='timestamp',
                how='left'
            )

            # Fill NaN values with 0 (no insider activity)
            for col in feature_cols:
                if col in result.columns:
                    result = result.with_columns(pl.col(col).fill_null(0))

            logger.info(f"Added 12 SEC Form 4 insider features for stock {stock_id}")

            return result.to_pandas()

        except Exception as e:
            logger.error(f"Error adding insider features for stock {stock_id}: {e}")
            # On error, add zero columns and continue
            result = features_df.copy()
            for col in feature_cols:
                result[col] = 0
            return result


def main():
    """Test insider features calculation"""
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

    features = InsiderFeatures.calculate_features_for_stock(
        stock_id, start_date, end_date,
        pd.date_range(start_date, end_date, freq='D')
    )

    print("\n" + "=" * 80)
    print("INSIDER FEATURES TEST")
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
