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
    def get_insider_trades(stock_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Fetch SEC Form 4 corporate insider trades for a stock within date range

        Args:
            stock_id: Stock ID
            start_date: Start date (with buffer for lookback)
            end_date: End date

        Returns:
            DataFrame with SEC Form 4 insider trades (is_congressional=false)
        """
        # Need extra history for rolling window calculations
        query_start = start_date - timedelta(days=400)  # Buffer for 1y window

        query = text("""
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
            WHERE stock_id = :stock_id
              AND is_congressional = false
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

            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.tz_localize(None)
            return df

        except Exception as e:
            logger.debug(f"Error fetching insider trades for stock {stock_id}: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_stock_prices(stock_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Fetch stock prices for 52-week high/low calculations

        Args:
            stock_id: Stock ID
            start_date: Start date (with buffer)
            end_date: End date

        Returns:
            DataFrame with prices
        """
        # Need 1 year of history for 52-week high/low
        query_start = start_date - timedelta(days=400)

        query = text("""
            SELECT
                date_trunc('day', timestamp) as date,
                high,
                low,
                close
            FROM stock_prices
            WHERE stock_id = :stock_id
              AND timeframe = '1d'
              AND timestamp >= :start_date
              AND timestamp <= :end_date
            ORDER BY timestamp ASC
        """)

        try:
            df = pd.read_sql(
                query,
                engine,
                params={'stock_id': stock_id, 'start_date': query_start, 'end_date': end_date}
            )

            if df.empty:
                return pd.DataFrame()

            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            return df

        except Exception as e:
            logger.debug(f"Error fetching prices for stock {stock_id}: {e}")
            return pd.DataFrame()

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
        trades_df = InsiderFeatures.get_insider_trades(stock_id, start_date, end_date)

        # Fetch prices for 52-week high/low
        prices_df = InsiderFeatures.get_stock_prices(stock_id, start_date, end_date)

        if trades_df.empty:
            # Return empty DataFrame with correct structure
            feature_cols = [
                'insider_buy_count_30d', 'insider_sell_count_30d',
                'insider_buy_volume_30d', 'insider_net_buy_ratio_30d',
                'ceo_bought_30d', 'cto_bought_30d', 'cfo_bought_30d',
                'cluster_buying_30d',
                'insider_buy_at_52w_low',
                'insider_sentiment_30d',
                'insider_buy_value_30d', 'insider_sell_value_30d'
            ]
            return pd.DataFrame(index=feature_dates, columns=feature_cols)

        # Initialize features DataFrame
        features = pd.DataFrame(index=feature_dates)

        # =========================================================================
        # FEATURE 1-4: Buy/Sell Activity (30-day rolling)
        # =========================================================================

        # Group trades by date
        daily_trades = trades_df.groupby('trade_date').agg({
            'transaction_type': list,
            'shares': 'sum',
            'total_value': 'sum'
        })

        # Calculate daily buy/sell counts and volumes
        for date in feature_dates:
            lookback_end = date
            lookback_start = date - timedelta(days=30)

            # Filter trades in window
            window_trades = trades_df[
                (trades_df['trade_date'] >= lookback_start) &
                (trades_df['trade_date'] <= lookback_end)
            ]

            if window_trades.empty:
                features.loc[date, 'insider_buy_count_30d'] = 0
                features.loc[date, 'insider_sell_count_30d'] = 0
                features.loc[date, 'insider_buy_volume_30d'] = 0
                features.loc[date, 'insider_net_buy_ratio_30d'] = 0
                features.loc[date, 'ceo_bought_30d'] = 0
                features.loc[date, 'cto_bought_30d'] = 0
                features.loc[date, 'cfo_bought_30d'] = 0
                features.loc[date, 'cluster_buying_30d'] = 0
                features.loc[date, 'insider_buy_at_52w_low'] = 0
                features.loc[date, 'insider_sentiment_30d'] = 0
                features.loc[date, 'insider_buy_value_30d'] = 0
                features.loc[date, 'insider_sell_value_30d'] = 0
                continue

            # Count buys and sells
            buys = window_trades[window_trades['transaction_type'] == 'BUY']
            sells = window_trades[window_trades['transaction_type'] == 'SELL']

            buy_count = len(buys)
            sell_count = len(sells)
            buy_volume = buys['shares'].sum() if not buys.empty else 0

            # Net buy ratio
            total_trades = buy_count + sell_count
            if total_trades > 0:
                net_buy_ratio = (buy_count - sell_count) / total_trades
            else:
                net_buy_ratio = 0

            features.loc[date, 'insider_buy_count_30d'] = buy_count
            features.loc[date, 'insider_sell_count_30d'] = sell_count
            features.loc[date, 'insider_buy_volume_30d'] = buy_volume
            features.loc[date, 'insider_net_buy_ratio_30d'] = net_buy_ratio

            # =========================================================================
            # FEATURE 5-7: Executive Activity (CEO, CTO, CFO)
            # =========================================================================

            # Check for CEO activity (case-insensitive title matching)
            ceo_trades = window_trades[
                window_trades['insider_title'].str.contains(
                    'CEO|Chief Executive Officer',
                    case=False,
                    na=False
                )
            ]
            ceo_bought = int(
                not ceo_trades.empty and
                any(ceo_trades['transaction_type'] == 'BUY')
            )

            # Check for CTO activity
            cto_trades = window_trades[
                window_trades['insider_title'].str.contains(
                    'CTO|Chief Technology Officer',
                    case=False,
                    na=False
                )
            ]
            cto_bought = int(
                not cto_trades.empty and
                any(cto_trades['transaction_type'] == 'BUY')
            )

            # Check for CFO activity
            cfo_trades = window_trades[
                window_trades['insider_title'].str.contains(
                    'CFO|Chief Financial Officer',
                    case=False,
                    na=False
                )
            ]
            cfo_bought = int(
                not cfo_trades.empty and
                any(cfo_trades['transaction_type'] == 'BUY')
            )

            features.loc[date, 'ceo_bought_30d'] = ceo_bought
            features.loc[date, 'cto_bought_30d'] = cto_bought
            features.loc[date, 'cfo_bought_30d'] = cfo_bought

            # =========================================================================
            # FEATURE 8: Cluster Buying (3+ different insiders buying)
            # =========================================================================

            if not buys.empty:
                unique_insiders = buys['insider_name'].nunique()
                cluster_buying = int(unique_insiders >= 3)
            else:
                cluster_buying = 0

            features.loc[date, 'cluster_buying_30d'] = cluster_buying

            # =========================================================================
            # FEATURE 9: Insider Buy at 52-Week Low
            # =========================================================================

            # Get current 52-week high/low from price data
            if not prices_df.empty and not buys.empty:
                # Get 52-week range ending at this date
                price_history = prices_df.loc[:date]

                if len(price_history) >= 50:  # Need at least 50 trading days
                    week_52_high = price_history['high'].max()
                    week_52_low = price_history['low'].min()

                    # Check if any buy was near 52-week low (within 5%)
                    buys_in_window = buys[
                        buys['trade_date'] >= lookback_start
                    ]

                    if not buys_in_window.empty:
                        buy_near_low = 0
                        for _, trade in buys_in_window.iterrows():
                            buy_price = trade['price']
                            if buy_price and week_52_low > 0:
                                price_vs_low = (buy_price - week_52_low) / week_52_low
                                if price_vs_low <= 0.05:  # Within 5% of low
                                    buy_near_low = 1
                                    break

                        features.loc[date, 'insider_buy_at_52w_low'] = buy_near_low
                    else:
                        features.loc[date, 'insider_buy_at_52w_low'] = 0
                else:
                    features.loc[date, 'insider_buy_at_52w_low'] = 0
            else:
                features.loc[date, 'insider_buy_at_52w_low'] = 0

            # =========================================================================
            # FEATURE 10: Insider Sentiment (-100 to +100)
            # =========================================================================

            # Calculate sentiment based on volume-weighted buys vs sells
            buy_volume = buys['shares'].sum() if not buys.empty else 0
            sell_volume = sells['shares'].sum() if not sells.empty else 0
            total_volume = buy_volume + sell_volume

            if total_volume > 0:
                sentiment = ((buy_volume - sell_volume) / total_volume) * 100
            else:
                sentiment = 0

            features.loc[date, 'insider_sentiment_30d'] = sentiment

            # =========================================================================
            # FEATURE 11-12: Value Metrics ($ value of trades)
            # =========================================================================

            buy_value = buys['total_value'].sum() if not buys.empty else 0
            sell_value = sells['total_value'].sum() if not sells.empty else 0

            features.loc[date, 'insider_buy_value_30d'] = buy_value
            features.loc[date, 'insider_sell_value_30d'] = sell_value

        # Ensure all columns are numeric
        feature_cols = [
            'insider_buy_count_30d', 'insider_sell_count_30d',
            'insider_buy_volume_30d', 'insider_net_buy_ratio_30d',
            'ceo_bought_30d', 'cto_bought_30d', 'cfo_bought_30d',
            'cluster_buying_30d',
            'insider_buy_at_52w_low',
            'insider_sentiment_30d',
            'insider_buy_value_30d', 'insider_sell_value_30d'
        ]

        for col in feature_cols:
            if col in features.columns:
                features[col] = pd.to_numeric(features[col], errors='coerce')

        return features

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
                feature_cols = [
                    'insider_buy_count_30d', 'insider_sell_count_30d',
                    'insider_buy_volume_30d', 'insider_net_buy_ratio_30d',
                    'ceo_bought_30d', 'cto_bought_30d', 'cfo_bought_30d',
                    'cluster_buying_30d',
                    'insider_buy_at_52w_low',
                    'insider_sentiment_30d',
                    'insider_buy_value_30d', 'insider_sell_value_30d'
                ]
                for col in feature_cols:
                    features_df[col] = 0
                return features_df

            # Reset index to join
            insider_features = insider_features.reset_index()
            insider_features.rename(columns={'index': 'timestamp'}, inplace=True)

            # Ensure timestamp columns exist
            if 'timestamp' not in features_df.columns:
                features_df = features_df.reset_index()
                features_df.rename(columns={'index': 'timestamp'}, inplace=True)

            # Convert timestamps to datetime
            features_df['timestamp'] = pd.to_datetime(features_df['timestamp'])
            insider_features['timestamp'] = pd.to_datetime(insider_features['timestamp'])

            # Outer join to preserve all rows
            result = features_df.merge(
                insider_features,
                on='timestamp',
                how='left',
                suffixes=('', '_insider')
            )

            # Fill NaN values with 0 (no insider activity)
            insider_cols = [
                'insider_buy_count_30d', 'insider_sell_count_30d',
                'insider_buy_volume_30d', 'insider_net_buy_ratio_30d',
                'ceo_bought_30d', 'cto_bought_30d', 'cfo_bought_30d',
                'cluster_buying_30d',
                'insider_buy_at_52w_low',
                'insider_sentiment_30d',
                'insider_buy_value_30d', 'insider_sell_value_30d'
            ]

            for col in insider_cols:
                if col in result.columns:
                    result[col] = result[col].fillna(0)

            logger.info(f"Added {len(insider_cols)} SEC Form 4 insider features for stock {stock_id}")

            return result

        except Exception as e:
            logger.error(f"Error adding insider features for stock {stock_id}: {e}")
            # On error, add zero columns and continue
            feature_cols = [
                'insider_buy_count_30d', 'insider_sell_count_30d',
                'insider_buy_volume_30d', 'insider_net_buy_ratio_30d',
                'ceo_bought_30d', 'cto_bought_30d', 'cfo_bought_30d',
                'cluster_buying_30d',
                'insider_buy_at_52w_low',
                'insider_sentiment_30d',
                'insider_buy_value_30d', 'insider_sell_value_30d'
            ]
            for col in feature_cols:
                features_df[col] = 0
            return features_df


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
