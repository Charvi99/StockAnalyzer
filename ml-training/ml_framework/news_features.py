"""
News Sentiment Features Module (Polygon API)

This module creates 20 news sentiment features for ML training using data
from the Polygon.io news API with built-in sentiment analysis.

FEATURES (20 total):

AVG SENTIMENT (5 time windows):
  1. news_sentiment_avg_1d      - Last 24h average sentiment
  2. news_sentiment_avg_3d      - Last 3 days average sentiment
  3. news_sentiment_avg_7d      - Last 7 days average sentiment
  4. news_sentiment_avg_14d     - Last 14 days average sentiment
  5. news_sentiment_avg_30d     - Last 30 days average sentiment

TIME-WEIGHTED SENTIMENT (3 windows):
  6. news_sentiment_weighted_1d - Exponential decay (1d)
  7. news_sentiment_weighted_7d - Exponential decay (7d)
  8. news_sentiment_weighted_30d - Exponential decay (30d)

SEPARATE BULLISH/BEARISH (4 features):
  9. news_positive_ratio_7d     - Positive articles / total
  10. news_negative_ratio_7d     - Negative articles / total
  11. news_net_sentiment_7d      - (pos - neg) / total
  12. news_sentiment_consensus_7d - 1=unanimous, 0=mixed, -1=conflicted

VOLUME/INTENSITY (3 features):
  13. news_intensity_1d          - Articles per day (24h)
  14. news_intensity_7d          - Articles per day (7d avg)
  15. news_intensity_spike_7d    - Binary: volume > 2x avg

EXTREMES (2 features):
  16. news_sentiment_max_7d      - Most positive article
  17. news_sentiment_min_7d      - Most negative article

VOLATILITY/DISAGREEMENT (2 features):
  18. news_sentiment_std_7d      - Std dev (consensus vs disagreement)
  19. news_sentiment_trend_7d    - Change in sentiment (slope)

DATA AVAILABILITY:
  20. news_data_available        - Binary: have news data?

KEY DESIGN DECISIONS:

1. Market Hours Alignment:
   - News before 4:00 PM ET → affects SAME DAY
   - News after 4:00 PM ET → affects NEXT DAY
   - Prevents lookahead bias

2. Multi-Dimensional Aggregation:
   - Separate bullish/bearish counts (don't just average!)
   - Track consensus vs disagreement
   - Volume-weighted intensity

3. Time-Decay Weighting:
   - Recent news matters more (exponential decay)
   - Lambda = 0.25 (half-life ~2.75 days)

4. Multiple Rolling Windows:
   - 1d: Immediate reaction (noise)
   - 3d: Short-term digestion
   - 7d: Emerging trend
   - 14d: Stabilized direction
   - 30d: Fundamental view

5. Historical Gap Handling:
   - 2018-2019: Set features to 0, news_data_available=0
   - 2020-2025: Use Polygon sentiment from database

EXPECTED VALUE: News sentiment is a proven alpha signal
- Research shows news sentiment predicts +1-3% abnormal returns
- Polygon sentiment is high quality (NLP analysis)
- Multi-dimensional approach captures nuance

Usage:
    from ml_framework.news_features import NewsFeatures

    features_df = NewsFeatures.add_news_features(
        features_df=existing_features,
        stock_id=1,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2025, 1, 1)
    )
"""

import logging
import polars as pl
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


# ============================================================================
# FEATURE LIST
# ============================================================================

NEWS_FEATURES = [
    # === AVG SENTIMENT (5 time windows) ===
    'news_sentiment_avg_1d',      # Last 24h
    'news_sentiment_avg_3d',      # Last 3 days
    'news_sentiment_avg_7d',      # Last 7 days
    'news_sentiment_avg_14d',     # Last 14 days
    'news_sentiment_avg_30d',     # Last 30 days

    # === TIME-WEIGHTED SENTIMENT (3 windows) ===
    'news_sentiment_weighted_1d', # Exponential decay (1d)
    'news_sentiment_weighted_7d', # Exponential decay (7d)
    'news_sentiment_weighted_30d',# Exponential decay (30d)

    # === SEPARATE BULLISH/BEARISH (4 features) ===
    'news_positive_ratio_7d',     # Positive / total
    'news_negative_ratio_7d',     # Negative / total
    'news_net_sentiment_7d',      # (pos - neg) / total
    'news_sentiment_consensus_7d', # 1=unanimous, 0=mixed, -1=conflicted

    # === VOLUME/INTENSITY (3 features) ===
    'news_intensity_1d',          # Articles per day (24h)
    'news_intensity_7d',          # Articles per day (7d avg)
    'news_intensity_spike_7d',    # Binary: volume > 2x avg

    # === EXTREMES (2 features) ===
    'news_sentiment_max_7d',      # Most positive article
    'news_sentiment_min_7d',      # Most negative article

    # === VOLATILITY/DISAGREEMENT (2 features) ===
    'news_sentiment_std_7d',      # Std dev (consensus vs disagreement)
    'news_sentiment_trend_7d',    # Change in sentiment (slope)

    # === DATA AVAILABILITY ===
    'news_data_available',        # Binary: have news data?
]


# ============================================================================
# NEWS FEATURES CLASS
# ============================================================================

class NewsFeatures:
    """
    Create news sentiment features from Polygon API data

    Features are calculated from the news table which contains
    Polygon's built-in sentiment analysis from article insights.

    Key features:
    - Market hours alignment (after-hours → next day)
    - Time-decay weighting (recent news = more important)
    - Separate bullish/bearish signals
    - Multiple rolling windows (1d to 30d)
    - Historical gap handling (2018-2019 = no data)
    """

    @staticmethod
    def fetch_news_from_db(
        stock_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> pl.DataFrame:
        """
        Fetch news articles with Polygon sentiment from database

        Args:
            stock_id: Stock ID
            start_date: Start date (with buffer for rolling windows)
            end_date: End date

        Returns:
            DataFrame with columns:
            - news_date: Date of article (truncated to day)
            - publish_hour: Hour of publication (0-23)
            - sentiment: Polygon sentiment (positive/negative/neutral)
            - sentiment_score: Numeric score (-1.0 to +1.0)
            - publisher: Article publisher
        """
        # Add buffer for rolling windows
        query_start = start_date - timedelta(days=400)

        query = text("""
            SELECT
                date_trunc('day', published_utc) as news_date,
                EXTRACT(HOUR FROM published_utc) as publish_hour,
                sentiment,
                sentiment_score,
                publisher
            FROM news
            WHERE stock_id = :stock_id
              AND published_utc >= :start_date
              AND published_utc <= :end_date
              AND sentiment_score IS NOT NULL
            ORDER BY published_utc ASC
        """)

        try:
            df = pl.read_database_uri(
                query=query,
                uri=DATABASE_URL,
                execute_options={
                    'parameters': {
                        'stock_id': stock_id,
                        'start_date': query_start,
                        'end_date': end_date
                    }
                }
            )

            if df.is_empty():
                return pl.DataFrame()

            # Convert types
            df = df.with_columns([
                pl.col("news_date").str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S").cast(pl.Datetime),
                pl.col("publish_hour").cast(pl.Int32)
            ])

            logger.debug(f"Fetched {df.height} news articles for stock {stock_id}")
            return df

        except Exception as e:
            logger.error(f"Error fetching news for stock {stock_id}: {e}")
            return pl.DataFrame()

    @staticmethod
    def align_to_trading_day(news_df: pl.DataFrame) -> pl.DataFrame:
        """
        Align news to trading days based on publish time

        Market Hours Alignment:
        - News before 4:00 PM ET (16:00) → affects SAME trading day
        - News after 4:00 PM ET → affects NEXT trading day
        - Weekends → moved to Monday

        This prevents lookahead bias where we'd use tomorrow's news
        to predict today's price.

        Args:
            news_df: DataFrame with 'news_date' and 'publish_hour' columns

        Returns:
            DataFrame with added 'trading_day' column
        """
        if news_df.is_empty():
            return news_df

        # Initialize trading_day as news_date
        df = news_df.with_columns([
            pl.col("news_date").alias("trading_day")
        ])

        # After-hours news (4 PM or later) moves to next day
        df = df.with_columns([
            pl.when(pl.col("publish_hour") >= 16)
            .then(pl.col("trading_day") + pl.duration(days=1))
            .otherwise(pl.col("trading_day"))
            .alias("trading_day")
        ])

        # Move weekend news to Monday
        # Saturday (5) → +2 days = Monday
        # Sunday (6) → +1 day = Monday
        df = df.with_columns([
            pl.col("trading_day").dt.weekday().alias("day_of_week")
        ])

        df = df.with_columns([
            pl.when(pl.col("day_of_week") == 5)  # Saturday
            .then(pl.col("trading_day") + pl.duration(days=2))
            .when(pl.col("day_of_week") == 6)  # Sunday
            .then(pl.col("trading_day") + pl.duration(days=1))
            .otherwise(pl.col("trading_day"))
            .alias("trading_day")
        ])

        # Clean up temp column
        df = df.drop("day_of_week")

        return df

    @staticmethod
    def calculate_rolling_features(
        news_df: pl.DataFrame,
        feature_dates: pl.Datetime
    ) -> pl.DataFrame:
        """
        Calculate all 20 news sentiment features

        Args:
            news_df: DataFrame with news data (from fetch_news_from_db)
            feature_dates: Dates to calculate features for

        Returns:
            DataFrame with 20 news features indexed by date
        """
        # Convert feature_dates to list if it's a DatetimeIndex
        if hasattr(feature_dates, 'to_pydatetime'):
            feature_dates_list = list(feature_dates.to_pydatetime())
        elif hasattr(feature_dates, 'to_list'):
            feature_dates_list = feature_dates.to_list()
        else:
            feature_dates_list = list(feature_dates)

        # Initialize features DataFrame
        features = pl.DataFrame({
            "timestamp": feature_dates_list
        })

        # Initialize all features with zeros
        for feat in NEWS_FEATURES:
            features = features.with_columns([
                pl.lit(0.0).alias(feat)
            ])

        if news_df.is_empty():
            return features.with_columns([
                pl.lit(0).alias("news_data_available")
            ])

        # Align news to trading days
        news_df = NewsFeatures.align_to_trading_day(news_df)

        # Set data available flag
        features = features.with_columns([
            pl.lit(1).alias("news_data_available")
        ])

        # Define rolling windows
        windows = {
            '1d': timedelta(days=1),
            '3d': timedelta(days=3),
            '7d': timedelta(days=7),
            '14d': timedelta(days=14),
            '30d': timedelta(days=30),
        }

        # Convert to pandas for complex row-by-row processing
        # This maintains the same logic while allowing cleaner implementation
        news_df_pd = news_df.to_pandas()
        features_pd = features.to_pandas()
        features_pd = features_pd.set_index('timestamp')

        # Calculate features for each date
        for date in feature_dates_list:
            # Get window data for each time period
            window_data = {}
            for window_name, window_delta in windows.items():
                window_start = date - window_delta

                window_news = news_df_pd[
                    (news_df_pd['trading_day'] >= window_start) &
                    (news_df_pd['trading_day'] <= date)
                ].copy()

                window_data[window_name] = window_news

            # ============================================================
            # AVG SENTIMENT (5 time windows)
            # ============================================================
            for window_name in ['1d', '3d', '7d', '14d', '30d']:
                window_news = window_data[window_name]

                if not window_news.empty:
                    avg_sentiment = window_news['sentiment_score'].mean()
                    features_pd.loc[date, f'news_sentiment_avg_{window_name}'] = avg_sentiment

            # ============================================================
            # SEPARATE BULLISH/BEARISH (4 features) - 7d window
            # ============================================================
            window_news = window_data['7d']
            if not window_news.empty:
                positive = (window_news['sentiment_score'] > 0).sum()
                negative = (window_news['sentiment_score'] < 0).sum()
                neutral = (window_news['sentiment_score'] == 0).sum()
                total = len(window_news)

                if total > 0:
                    features_pd.loc[date, 'news_positive_ratio_7d'] = positive / total
                    features_pd.loc[date, 'news_negative_ratio_7d'] = negative / total
                    features_pd.loc[date, 'news_net_sentiment_7d'] = (positive - negative) / total

                    # Consensus: 1 = unanimous agreement, 0 = mixed, -1 = high disagreement
                    sentiment_std = window_news['sentiment_score'].std()
                    if not pd.isna(sentiment_std):
                        # Map std to [-1, 1]: std=0 → consensus=1, std=0.5+ → consensus=-1
                        consensus = max(-1, 1 - (sentiment_std * 2))
                        features_pd.loc[date, 'news_sentiment_consensus_7d'] = consensus
                        features_pd.loc[date, 'news_sentiment_std_7d'] = sentiment_std

                    # Extremes
                    features_pd.loc[date, 'news_sentiment_max_7d'] = window_news['sentiment_score'].max()
                    features_pd.loc[date, 'news_sentiment_min_7d'] = window_news['sentiment_score'].min()

                    # Trend: linear regression slope (sentiment trajectory)
                    if len(window_news) >= 3:
                        # Sort by trading day
                        sorted_news = window_news.sort_values('trading_day')
                        x = np.arange(len(sorted_news))
                        y = sorted_news['sentiment_score'].values

                        try:
                            slope = np.polyfit(x, y, 1)[0]
                            features_pd.loc[date, 'news_sentiment_trend_7d'] = slope
                        except:
                            pass

            # ============================================================
            # VOLUME/INTENSITY (3 features)
            # ============================================================
            for window_name in ['1d', '7d']:
                window_news = window_data[window_name]

                if not window_news.empty:
                    features_pd.loc[date, f'news_intensity_{window_name}'] = len(window_news)

            # Calculate intensity spike (requires historical context)
            if len(features_pd) > 7 and date != features_pd.index[0]:
                current_intensity = features_pd.loc[date, 'news_intensity_7d']

                # Get historical average (excluding current)
                historical_dates = features_pd[features_pd.index < date].index
                if len(historical_dates) > 0:
                    historical_avg = features_pd.loc[historical_dates, 'news_intensity_7d'].mean()

                    if not pd.isna(historical_avg) and historical_avg > 0:
                        # Spike: current intensity > 2x historical average
                        features_pd.loc[date, 'news_intensity_spike_7d'] = int(
                            current_intensity > historical_avg * 2
                        )

            # ============================================================
            # TIME-WEIGHTED SENTIMENT (3 windows) - Exponential decay
            # ============================================================
            for window_name in ['1d', '7d', '30d']:
                window_news = window_data[window_name]

                if not window_news.empty and len(window_news) >= 2:
                    # Calculate days ago for each article
                    days_ago = (date - window_news['trading_day']).dt.days

                    # Exponential decay weights: weight = e^(-lambda * days_ago)
                    # Lambda = 0.25 means half-life of ~2.75 days
                    lambda_decay = 0.25
                    weights = np.exp(-lambda_decay * days_ago)

                    # Weighted average
                    weighted_sentiment = (
                        (window_news['sentiment_score'] * weights).sum() / weights.sum()
                    )

                    features_pd.loc[date, f'news_sentiment_weighted_{window_name}'] = weighted_sentiment

        # Ensure all columns are numeric
        for col in features_pd.columns:
            features_pd[col] = pd.to_numeric(features_pd[col], errors='coerce').fillna(0)

        # Convert back to polars
        return pl.from_pandas(features_pd.reset_index())

    @staticmethod
    def add_news_features(
        features_df: pd.DataFrame,
        stock_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Add news sentiment features to existing features DataFrame

        This is the main entry point for adding news features to your
        feature engineering pipeline.

        Args:
            features_df: Existing features DataFrame with 'timestamp' column
            stock_id: Stock ID
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with 20 news features added
        """
        if features_df is None or features_df.empty:
            return features_df

        try:
            # Get feature dates from existing DataFrame
            if 'timestamp' in features_df.columns:
                feature_dates = pd.to_datetime(features_df['timestamp'])
            else:
                # Try to use index
                feature_dates = pd.to_datetime(features_df.index)
                features_df = features_df.reset_index()
                features_df.rename(columns={'index': 'timestamp'}, inplace=True)

            # ============================================================
            # HANDLE HISTORICAL GAP (2018-2019)
            # ============================================================
            polygon_cutoff = datetime(2020, 1, 1)

            # Check if this period is before Polygon availability
            if end_date < polygon_cutoff:
                # 2018-2019: No Polygon news available
                logger.info(f"Setting news features to 0 for 2018-2019 period (stock {stock_id})")

                for feat in NEWS_FEATURES:
                    features_df[feat] = 0

                features_df['news_data_available'] = 0
                return features_df

            # Adjust start_date for Polygon data availability
            adjusted_start = max(start_date, polygon_cutoff)

            # ============================================================
            # FETCH NEWS FROM DATABASE
            # ============================================================
            news_df = NewsFeatures.fetch_news_from_db(stock_id, adjusted_start, end_date)

            if news_df.is_empty():
                logger.warning(f"No news data found for stock {stock_id}")
                for feat in NEWS_FEATURES:
                    features_df[feat] = 0
                features_df['news_data_available'] = 0
                return features_df

            # ============================================================
            # CALCULATE FEATURES
            # ============================================================
            news_features = NewsFeatures.calculate_rolling_features(news_df, feature_dates)

            # Convert to pandas for merge (compatibility with existing code)
            news_features_pd = news_features.to_pandas()

            # Ensure timestamp column exists in features_df
            if 'timestamp' not in features_df.columns:
                features_df = features_df.reset_index()
                features_df.rename(columns={'index': 'timestamp'}, inplace=True)

            features_df['timestamp'] = pd.to_datetime(features_df['timestamp'])
            news_features_pd['timestamp'] = pd.to_datetime(news_features_pd['timestamp'])

            # ============================================================
            # MERGE FEATURES
            # ============================================================
            result = features_df.merge(
                news_features_pd,
                on='timestamp',
                how='left',
                suffixes=('', '_news')
            )

            # Fill NaN with 0 (for dates before first news)
            for feat in NEWS_FEATURES:
                if feat in result.columns:
                    result[feat] = result[feat].fillna(0)

            logger.info(f"Added {len(NEWS_FEATURES)} news sentiment features for stock {stock_id}")

            return result

        except Exception as e:
            logger.error(f"Error adding news features for stock {stock_id}: {e}")

            # On error, add zero columns and continue
            for feat in NEWS_FEATURES:
                features_df[feat] = 0

            features_df['news_data_available'] = 0
            return features_df


# ============================================================================
# MAIN FUNCTION (FOR TESTING)
# ============================================================================

def main():
    """Test news features calculation"""
    import pandas as pd

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test with first stock
    db = SessionLocal()
    try:
        result = db.execute(
            text("SELECT id FROM stocks WHERE is_tracked = true LIMIT 1")
        )
        stock_id = result.fetchone()[0]
    finally:
        db.close()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)

    print("\n" + "=" * 80)
    print("NEWS FEATURES TEST")
    print("=" * 80)
    print(f"\nStock ID: {stock_id}")
    print(f"Date range: {start_date.date()} to {end_date.date()}")

    # Fetch news
    news_df = NewsFeatures.fetch_news_from_db(stock_id, start_date, end_date)

    if news_df.is_empty():
        print("\n⚠️  No news data found for this stock")
        return

    print(f"\n📰 News data: {news_df.height} articles")
    print(f"\nSample news:")
    print(news_df.select(['news_date', 'publish_hour', 'sentiment', 'sentiment_score']).head(10))

    # Calculate features
    feature_dates = pd.date_range(start_date, end_date, freq='D')
    features = NewsFeatures.calculate_rolling_features(news_df, feature_dates)

    print(f"\n✅ Features calculated: {features.shape}")
    print(f"   Rows: {features.height}, Columns: {features.width}")

    print(f"\nFeature columns:")
    for i, col in enumerate(features.columns, 1):
        print(f"  {i:2d}. {col}")

    print(f"\nSample features (last 7 days):")
    print(features.tail(7))

    print(f"\nFeature statistics:")
    print(features.describe())

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
