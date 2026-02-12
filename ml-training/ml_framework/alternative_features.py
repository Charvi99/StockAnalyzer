"""
Alternative Data Features Module (QuiverQuant Basic Plan - $10/mo)

This module implements features from alternative data sources that are
included in your QuiverQuant Basic plan:

1. Congressional Trading (12 features) - Political signals
2. Off-Exchange Short Volume (6 features) - Squeeze predictor
3. WallStreetBets Activity (8 features) - Retail sentiment

Total: 26 alternative features that can be combined with 28 technical features
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


# ============================================================================
# OFF-EXCHANGE SHORT VOLUME FEATURES (6 features)
# ============================================================================

"""
Off-exchange short volume is one of the strongest predictors of:
- Short squeezes (retail trading wars)
- High short interest + positive news = massive upside
- Institutional sentiment (smart money positioning)

Off-exchange volume = trades that happen outside major exchanges
High off-exchange volume can indicate:
1. Institutional accumulation (bullish)
2. Retail short selling (potential squeeze candidate)
3. Dark pool activity

FEATURES:
1. off_exchange_short_volume_30d    - Average off-exchange volume (30d)
2. off_exchange_short_ratio_30d     - Off-exchange / total volume ratio
3. off_exchange_trend_30d          - Trend in off-exchange volume
4. high_short_interest_30d           - Binary: Is short interest > 20%?
5. off_exchange_spike_30d          - Binary: Volume spike detected?
6. off_exchange_volatility_30d     - Volatility of off-exchange volume
"""

OFF_EXCHANGE_FEATURES = [
    'off_exchange_short_volume_30d',
    'off_exchange_short_ratio_30d',
    'off_exchange_trend_30d',
    'high_short_interest_30d',
    'off_exchange_spike_30d',
    'off_exchange_volatility_30d'
]


# ============================================================================
# WALLSTREETBETS ACTIVITY FEATURES (8 features)
# ============================================================================

"""
WallStreetBets (r/wallstreetbets) is the largest retail trading community.
High WSB activity can indicate:
- Retail sentiment shifts
- "Meme stock" phenomena
- Social media driven momentum
- Retail FOMO (Fear Of Missing Out)

FEATURES:
1. wsb_mention_count_30d          - Number of WSB mentions in 30 days
2. wsb_sentiment_30d               - Average sentiment score
3. wsb_activity_score_30d         - Combined activity score
4. wsb_momentum_30d               - Change in mention count
5. wsb_discussion_rank_30d        - Popularity ranking
6. wsb_positivity_ratio_30d       - Positive mentions / total
7. wsb_consensus_30d             - General sentiment (bullish/bearish/neutral)
8. wsb_hype_level_30d             - Binary: Is hype level high?
"""

WSB_FEATURES = [
    'wsb_mention_count_30d',
    'wsb_sentiment_30d',
    'wsb_activity_score_30d',
    'wsb_momentum_30d',
    'wsb_discussion_rank_30d',
    'wsb_positivity_ratio_30d',
    'wsb_consensus_30d',
    'wsb_hype_level_30d'
]


class AlternativeFeatures:
    """
    Calculate alternative data features from QuiverQuant Basic plan

    Includes:
    - Congressional Trading (12 features)
    - Off-Exchange Short Volume (6 features)
    - WallStreetBets Activity (8 features)
    """

    @staticmethod
    def get_alternative_data(stock_id: int, start_date: datetime, end_date: datetime) -> dict:
        """
        Fetch all alternative data for a stock

        Args:
            stock_id: Stock ID
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with DataFrames for each data source
        """
        # Get stock symbol
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT symbol FROM stocks WHERE id = :stock_id"), {"stock_id": stock_id})
            symbol = result.fetchone()[0]
        finally:
            db.close()

        query_start = start_date - timedelta(days=400)

        # Fetch off-exchange short volume
        off_exchange_df = None
        try:
            query = text("""
                SELECT date_trunc('day', date) as date,
                       off_exchange_volume,
                       total_volume,
                       short_interest
                FROM alternative_data
                WHERE stock_id = :stock_id
                  AND date >= :start_date
                  AND date <= :end_date
                ORDER BY date ASC
            """)
            off_exchange_df = pd.read_sql(
                query,
                engine,
                params={'stock_id': stock_id, 'start_date': query_start, 'end_date': end_date}
            )
            if not off_exchange_df.empty:
                off_exchange_df['date'] = pd.to_datetime(off_exchange_df['date'])
        except Exception as e:
            logger.debug(f"Error fetching off-exchange data: {e}")

        # Fetch WSB activity
        wsb_df = None
        try:
            query = text("""
                SELECT date_trunc('day', date) as date,
                       mention_count,
                       sentiment_score,
                       activity_score,
                       discussion_rank,
                       positivity_ratio
                FROM alternative_data
                WHERE stock_id = :stock_id
                  AND data_source = 'wallstreetbets'
                  AND date >= :start_date
                  AND date <= :end_date
                ORDER BY date ASC
            """)
            wsb_df = pd.read_sql(
                query,
                engine,
                params={'stock_id': stock_id, 'start_date': query_start, 'end_date': end_date}
            )
            if not wsb_df.empty:
                wsb_df['date'] = pd.to_datetime(wsb_df['date'])
        except Exception as e:
            logger.debug(f"Error fetching WSB data: {e}")

        return {
            'off_exchange': off_exchange_df,
            'wsb': wsb_df,
            'symbol': symbol
        }

    @staticmethod
    def calculate_off_exchange_features(
        data_df: pd.DataFrame,
        feature_dates: pd.DatetimeIndex
    ) -> pd.DataFrame:
        """
        Calculate off-exchange short volume features

        Args:
            data_df: DataFrame with off-exchange data
            feature_dates: Dates to calculate features for

        Returns:
            DataFrame with 6 off-exchange features
        """
        features = pd.DataFrame(index=feature_dates)

        # Initialize with zeros
        for col in OFF_EXCHANGE_FEATURES:
            features[col] = 0

        if data_df is None or data_df.empty:
            return features

        for date in feature_dates:
            lookback_start = date - timedelta(days=30)

            # Get data in window
            window_data = data_df[
                (data_df['date'] >= lookback_start) &
                (data_df['date'] <= date)
            ]

            if window_data.empty:
                continue

            # Feature 1: Average off-exchange volume
            features.loc[date, 'off_exchange_short_volume_30d'] = window_data['off_exchange_volume'].mean()

            # Feature 2: Off-exchange ratio
            total_vol = window_data['total_volume'].sum()
            off_exch_vol = window_data['off_exchange_volume'].sum()
            if total_vol > 0:
                features.loc[date, 'off_exchange_short_ratio_30d'] = off_exch_vol / total_vol
            else:
                features.loc[date, 'off_exchange_short_ratio_30d'] = 0

            # Feature 3: Trend (linear regression slope)
            if len(window_data) >= 7:
                x = np.arange(len(window_data))
                y = window_data['off_exchange_volume'].values
                try:
                    slope = np.polyfit(x, y, 1)[0]
                    mean_vol = y.mean()
                    if mean_vol > 0:
                        features.loc[date, 'off_exchange_trend_30d'] = slope / mean_vol  # Normalized trend
                except:
                    pass

            # Feature 4: High short interest (binary)
            if 'short_interest' in window_data.columns:
                avg_short_interest = window_data['short_interest'].mean()
                if not pd.isna(avg_short_interest):
                    features.loc[date, 'high_short_interest_30d'] = int(avg_short_interest > 0.20)  # 20% threshold
                else:
                    features.loc[date, 'high_short_interest_30d'] = 0
            else:
                features.loc[date, 'high_short_interest_30d'] = 0

            # Feature 5: Volume spike detection (3x recent average)
            if len(window_data) >= 7:
                recent_vol = window_data['off_exchange_volume'].iloc[-5:].mean()
                if recent_vol > 0:
                    current_vol = window_data['off_exchange_volume'].iloc[-1]
                    features.loc[date, 'off_exchange_spike_30d'] = int(current_vol > recent_vol * 3)
                else:
                    features.loc[date, 'off_exchange_spike_30d'] = 0
            else:
                features.loc[date, 'off_exchange_spike_30d'] = 0

            # Feature 6: Volatility of off-exchange volume
            if len(window_data) >= 10:
                features.loc[date, 'off_exchange_volatility_30d'] = window_data['off_exchange_volume'].std()
            else:
                features.loc[date, 'off_exchange_volatility_30d'] = 0

        # Ensure numeric
        for col in OFF_EXCHANGE_FEATURES:
            features[col] = pd.to_numeric(features[col], errors='coerce')

        return features

    @staticmethod
    def calculate_wsb_features(
        data_df: pd.DataFrame,
        feature_dates: pd.DatetimeIndex
    ) -> pd.DataFrame:
        """
        Calculate WallStreetBets activity features

        Args:
            data_df: DataFrame with WSB data
            feature_dates: Dates to calculate features for

        Returns:
            DataFrame with 8 WSB features
        """
        features = pd.DataFrame(index=feature_dates)

        # Initialize with zeros
        for col in WSB_FEATURES:
            features[col] = 0

        if data_df is None or data_df.empty:
            return features

        for date in feature_dates:
            lookback_start = date - timedelta(days=30)

            # Get data in window
            window_data = data_df[
                (data_df['date'] >= lookback_start) &
                (data_df['date'] <= date)
            ]

            if window_data.empty:
                continue

            # Feature 1: Mention count
            features.loc[date, 'wsb_mention_count_30d'] = window_data['mention_count'].sum()

            # Feature 2: Average sentiment
            features.loc[date, 'wsb_sentiment_30d'] = window_data['sentiment_score'].mean()

            # Feature 3: Activity score
            features.loc[date, 'wsb_activity_score_30d'] = window_data['activity_score'].mean()

            # Feature 4: Momentum (change in mentions)
            if len(window_data) >= 7:
                recent_mentions = window_data['mention_count'].iloc[-7:].sum()
                older_mentions = window_data['mention_count'].iloc[:-7].sum() if len(window_data) >= 14 else recent_mentions
                if older_mentions > 0:
                    momentum = (recent_mentions - older_mentions) / older_mentions
                else:
                    momentum = 0
                features.loc[date, 'wsb_momentum_30d'] = momentum
            else:
                features.loc[date, 'wsb_momentum_30d'] = 0

            # Feature 5: Discussion rank (inverted - lower is better)
            avg_rank = window_data['discussion_rank'].mean()
            if not pd.isna(avg_rank):
                features.loc[date, 'wsb_discussion_rank_30d'] = avg_rank
            else:
                features.loc[date, 'wsb_discussion_rank_30d'] = 999  # Default for no data

            # Feature 6: Positivity ratio
            features.loc[date, 'wsb_positivity_ratio_30d'] = window_data['positivity_ratio'].mean()

            # Feature 7: Consensus (sentiment classification)
            avg_sentiment = window_data['sentiment_score'].mean()
            if not pd.isna(avg_sentiment):
                if avg_sentiment > 0.3:
                    features.loc[date, 'wsb_consensus_30d'] = 2  # Bullish
                elif avg_sentiment < -0.3:
                    features.loc[date, 'wsb_consensus_30d'] = 0  # Bearish
                else:
                    features.loc[date, 'wsb_consensus_30d'] = 1  # Neutral
            else:
                features.loc[date, 'wsb_consensus_30d'] = 1

            # Feature 8: Hype level (binary)
            mentions = features.loc[date, 'wsb_mention_count_30d']
            momentum = features.loc[date, 'wsb_momentum_30d']
            features.loc[date, 'wsb_hype_level_30d'] = int((mentions > 100) and (momentum > 0.5))

        # Ensure numeric
        for col in WSB_FEATURES:
            features[col] = pd.to_numeric(features[col], errors='coerce')

        return features

    @staticmethod
    def add_alternative_features(
        features_df: pd.DataFrame,
        stock_id: int,
        start_date: datetime,
        end_date: datetime,
        include_off_exchange: bool = True,
        include_wsb: bool = True
    ) -> pd.DataFrame:
        """
        Add alternative data features to existing DataFrame

        Args:
            features_df: Existing features DataFrame
            stock_id: Stock ID
            start_date: Start date
            end_date: End date
            include_off_exchange: Include off-exchange features
            include_wsb: Include WSB features

        Returns:
            DataFrame with alternative features added
        """
        if features_df is None or features_df.empty:
            return features_df

        feature_dates = pd.to_datetime(features_df['timestamp'])

        # Get alternative data
        alt_data = AlternativeFeatures.get_alternative_data(stock_id, start_date, end_date)

        # Add off-exchange features
        if include_off_exchange:
            off_exch_features = AlternativeFeatures.calculate_off_exchange_features(
                alt_data['off_exchange'],
                feature_dates
            )

            if not off_exch_features.empty:
                off_exch_features = off_exch_features.reset_index()
                off_exch_features.rename(columns={'index': 'timestamp'}, inplace=True)
                off_exch_features['timestamp'] = pd.to_datetime(off_exch_features['timestamp'])

                features_df['timestamp'] = pd.to_datetime(features_df['timestamp'])
                off_exch_features['timestamp'] = pd.to_datetime(off_exch_features['timestamp'])

                # Join
                features_df = features_df.merge(
                    off_exch_features,
                    on='timestamp',
                    how='left',
                    suffixes=('', '_offex')
                )

                # Fill NaN with 0
                for col in OFF_EXCHANGE_FEATURES:
                    if col in features_df.columns:
                        features_df[col] = features_df[col].fillna(0)

                logger.info(f"Added 6 off-exchange features for stock {stock_id}")

        # Add WSB features
        if include_wsb:
            wsb_features = AlternativeFeatures.calculate_wsb_features(
                alt_data['wsb'],
                feature_dates
            )

            if not wsb_features.empty:
                wsb_features = wsb_features.reset_index()
                wsb_features.rename(columns={'index': 'timestamp'}, inplace=True)
                wsb_features['timestamp'] = pd.to_datetime(wsb_features['timestamp'])

                features_df['timestamp'] = pd.to_datetime(features_df['timestamp'])
                wsb_features['timestamp'] = pd.to_datetime(wsb_features['timestamp'])

                # Join
                features_df = features_df.merge(
                    wsb_features,
                    on='timestamp',
                    how='left',
                    suffixes=('', '_wsb')
                )

                # Fill NaN with 0
                for col in WSB_FEATURES:
                    if col in features_df.columns:
                        features_df[col] = features_df[col].fillna(0)

                logger.info(f"Added 8 WSB features for stock {stock_id}")

        return features_df


def main():
    """Test alternative features"""
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

    print("\n" + "=" * 80)
    print("ALTERNATIVE FEATURES TEST")
    print("=" * 80)
    print(f"\nStock ID: {stock_id}")
    print(f"Date range: {start_date} to {end_date}")

    alt_data = AlternativeFeatures.get_alternative_data(stock_id, start_date, end_date)

    print(f"\nOff-exchange data: {len(alt_data['off_exchange']) if alt_data['off_exchange'] is not None else 0} rows")
    print(f"WSB data: {len(alt_data['wsb']) if alt_data['wsb'] is not None else 0} rows")

    if alt_data['off_exchange'] is not None and not alt_data['off_exchange'].empty:
        print("\nOff-exchange sample:")
        print(alt_data['off_exchange'].head())

    if alt_data['wsb'] is not None and not alt_data['wsb'].empty:
        print("\nWSB sample:")
        print(alt_data['wsb'].head())

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
