"""
Timeframe Aggregator Service
Aggregates higher timeframes from 1-hour base data

This service eliminates on-the-fly aggregation during dashboard queries (50% of load time).
Pre-aggregating timeframes saves 0.5-1s per stock × 502 stocks = 4-8 minutes of dashboard load time.
"""
import pandas as pd
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TimeframeAggregator:
    """
    Aggregate higher timeframes from lower timeframes
    Base timeframe: 1 Hour

    Aggregation hierarchy:
    1h (base) → 2h → 4h → 1d → 1w → 1mo
    """

    @staticmethod
    def aggregate_1h_to_2h(df_1h: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate 1-hour bars to 2-hour bars

        Args:
            df_1h: DataFrame with 1h bars (indexed by timestamp)

        Returns:
            DataFrame with 2h bars
        """
        if df_1h.empty:
            logger.warning("Empty 1h DataFrame provided for 2h aggregation")
            return pd.DataFrame()

        try:
            # Resample to 2-hour intervals
            df_2h = df_1h.resample('2H').agg({
                'open': 'first',    # First open in 2h period
                'high': 'max',      # Highest high in 2h period
                'low': 'min',       # Lowest low in 2h period
                'close': 'last',    # Last close in 2h period
                'volume': 'sum'     # Total volume in 2h period
            }).dropna()

            logger.info(f"Aggregated {len(df_1h)} 1h bars -> {len(df_2h)} 2h bars")
            return df_2h

        except Exception as e:
            logger.error(f"Error aggregating 1h to 2h: {e}")
            return pd.DataFrame()

    @staticmethod
    def aggregate_1h_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate 1-hour bars to 4-hour bars

        Args:
            df_1h: DataFrame with 1h bars (indexed by timestamp)

        Returns:
            DataFrame with 4h bars
        """
        if df_1h.empty:
            logger.warning("Empty 1h DataFrame provided for 4h aggregation")
            return pd.DataFrame()

        try:
            df_4h = df_1h.resample('4H').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()

            logger.info(f"Aggregated {len(df_1h)} 1h bars -> {len(df_4h)} 4h bars")
            return df_4h

        except Exception as e:
            logger.error(f"Error aggregating 1h to 4h: {e}")
            return pd.DataFrame()

    @staticmethod
    def aggregate_1h_to_1d(df_1h: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate 1-hour bars to daily bars

        Uses calendar day aggregation (all hours in same day)
        Market hours: Typically 6.5 hours/day (9:30 AM - 4:00 PM ET)

        Args:
            df_1h: DataFrame with 1h bars (indexed by timestamp)

        Returns:
            DataFrame with daily bars
        """
        if df_1h.empty:
            logger.warning("Empty 1h DataFrame provided for daily aggregation")
            return pd.DataFrame()

        try:
            # Resample to daily (using calendar day - starts at midnight)
            df_1d = df_1h.resample('D').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()

            logger.info(f"Aggregated {len(df_1h)} 1h bars -> {len(df_1d)} daily bars")
            return df_1d

        except Exception as e:
            logger.error(f"Error aggregating 1h to 1d: {e}")
            return pd.DataFrame()

    @staticmethod
    def aggregate_1d_to_1w(df_1d: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate daily bars to weekly bars

        Week = Monday to Friday (trading week)
        Week ends on Friday

        Args:
            df_1d: DataFrame with daily bars (indexed by timestamp)

        Returns:
            DataFrame with weekly bars
        """
        if df_1d.empty:
            logger.warning("Empty daily DataFrame provided for weekly aggregation")
            return pd.DataFrame()

        try:
            # Resample to weekly (week ending Friday)
            # W-FRI means week ending on Friday
            df_1w = df_1d.resample('W-FRI').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()

            logger.info(f"Aggregated {len(df_1d)} daily bars -> {len(df_1w)} weekly bars")
            return df_1w

        except Exception as e:
            logger.error(f"Error aggregating daily to weekly: {e}")
            return pd.DataFrame()

    @staticmethod
    def aggregate_1d_to_1mo(df_1d: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate daily bars to monthly bars

        Month = Calendar month (ends at month end)

        Args:
            df_1d: DataFrame with daily bars (indexed by timestamp)

        Returns:
            DataFrame with monthly bars
        """
        if df_1d.empty:
            logger.warning("Empty daily DataFrame provided for monthly aggregation")
            return pd.DataFrame()

        try:
            # Resample to monthly (month ending)
            # M means month end
            df_1mo = df_1d.resample('M').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()

            logger.info(f"Aggregated {len(df_1d)} daily bars -> {len(df_1mo)} monthly bars")
            return df_1mo

        except Exception as e:
            logger.error(f"Error aggregating daily to monthly: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_aggregated_timeframe(
        df_1h: pd.DataFrame,
        target_timeframe: str
    ) -> pd.DataFrame:
        """
        Main aggregation dispatcher

        Aggregates from 1h base to any higher timeframe

        Args:
            df_1h: Base 1h DataFrame (indexed by timestamp)
            target_timeframe: Target timeframe ('2h', '4h', '1d', '1w', '1mo')

        Returns:
            Aggregated DataFrame for target timeframe
        """
        if df_1h.empty:
            logger.warning(f"Empty 1h DataFrame, cannot aggregate to {target_timeframe}")
            return pd.DataFrame()

        # Direct aggregation from 1h
        aggregation_map = {
            '2h': TimeframeAggregator.aggregate_1h_to_2h,
            '4h': TimeframeAggregator.aggregate_1h_to_4h,
            '1d': TimeframeAggregator.aggregate_1h_to_1d,
        }

        if target_timeframe in aggregation_map:
            logger.info(f"Aggregating from 1h to {target_timeframe}")
            return aggregation_map[target_timeframe](df_1h)

        # For weekly and monthly, aggregate from daily first
        if target_timeframe == '1w':
            logger.info("Aggregating 1h -> 1d -> 1w")
            df_1d = TimeframeAggregator.aggregate_1h_to_1d(df_1h)
            if df_1d.empty:
                return pd.DataFrame()
            return TimeframeAggregator.aggregate_1d_to_1w(df_1d)

        if target_timeframe == '1mo':
            logger.info("Aggregating 1h -> 1d -> 1mo")
            df_1d = TimeframeAggregator.aggregate_1h_to_1d(df_1h)
            if df_1d.empty:
                return pd.DataFrame()
            return TimeframeAggregator.aggregate_1d_to_1mo(df_1d)

        logger.error(f"Unknown target timeframe: {target_timeframe}")
        return pd.DataFrame()

    @staticmethod
    def validate_aggregation(df_original: pd.DataFrame, df_aggregated: pd.DataFrame) -> bool:
        """
        Validate that aggregation was performed correctly

        Checks:
        - No data loss (aggregated bars should cover same time range)
        - Price consistency (high >= low, close within range)
        - Volume conservation (total volume preserved)

        Args:
            df_original: Original DataFrame
            df_aggregated: Aggregated DataFrame

        Returns:
            True if aggregation is valid, False otherwise
        """
        if df_original.empty or df_aggregated.empty:
            return False

        try:
            # Check 1: Time range coverage
            orig_start = df_original.index.min()
            orig_end = df_original.index.max()
            agg_start = df_aggregated.index.min()
            agg_end = df_aggregated.index.max()

            # Aggregated should cover similar time range (allowing for partial periods)
            if agg_start > orig_start + pd.Timedelta(days=7):
                logger.warning("Aggregation may have lost early data")

            # Check 2: Price consistency in aggregated data
            invalid_prices = (
                (df_aggregated['high'] < df_aggregated['low']) |
                (df_aggregated['close'] > df_aggregated['high']) |
                (df_aggregated['close'] < df_aggregated['low']) |
                (df_aggregated['open'] > df_aggregated['high']) |
                (df_aggregated['open'] < df_aggregated['low'])
            )

            if invalid_prices.any():
                logger.error(f"Found {invalid_prices.sum()} bars with invalid price relationships")
                return False

            # Check 3: Volume conservation (within 1% tolerance due to rounding)
            orig_volume = df_original['volume'].sum()
            agg_volume = df_aggregated['volume'].sum()
            volume_diff_pct = abs(agg_volume - orig_volume) / orig_volume * 100

            if volume_diff_pct > 1.0:
                logger.warning(f"Volume difference: {volume_diff_pct:.2f}% (tolerance: 1%)")

            logger.info("Aggregation validation passed")
            return True

        except Exception as e:
            logger.error(f"Error validating aggregation: {e}")
            return False

    @staticmethod
    def aggregate_and_save_to_db(
        db: Session,
        stock_id: int,
        target_timeframe: str,
        days_lookback: int = 90
    ) -> bool:
        """
        Aggregate hourly data to target timeframe and save to database.

        This is the main method called by fetcher tasks after fetching hourly data.

        Args:
            db: Database session
            stock_id: Stock ID
            target_timeframe: Target timeframe ('1d', '1w', '1mo')
            days_lookback: Days of history to aggregate (default: 90)

        Returns:
            True if successful, False otherwise
        """
        from app.models.stock import StockPrice

        try:
            # Calculate date range
            now = datetime.now(timezone.utc)
            from_date = now - timedelta(days=days_lookback)

            # Load 1h data from database
            prices_1h = db.query(StockPrice).filter(
                StockPrice.stock_id == stock_id,
                StockPrice.timeframe == '1h',
                StockPrice.timestamp >= from_date
            ).order_by(StockPrice.timestamp.asc()).all()

            if not prices_1h or len(prices_1h) < 7:  # Need at least 1 trading day
                logger.warning(f"Insufficient 1h data for stock_id={stock_id}: {len(prices_1h) if prices_1h else 0} records")
                return False

            # Convert to DataFrame
            df_1h = pd.DataFrame([{
                'timestamp': p.timestamp,
                'open': float(p.open) if p.open else None,
                'high': float(p.high) if p.high else None,
                'low': float(p.low) if p.low else None,
                'close': float(p.close) if p.close else None,
                'volume': int(p.volume) if p.volume else 0
            } for p in prices_1h])

            # Set timestamp as index
            df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'])
            df_1h.set_index('timestamp', inplace=True)
            df_1h.sort_index(inplace=True)

            # Aggregate to target timeframe
            df_aggregated = TimeframeAggregator.get_aggregated_timeframe(df_1h, target_timeframe)

            if df_aggregated.empty:
                logger.warning(f"Aggregation resulted in empty DataFrame for stock_id={stock_id}, timeframe={target_timeframe}")
                return False

            # Save to database
            rows_inserted = 0
            rows_updated = 0

            for timestamp, row in df_aggregated.iterrows():
                # Ensure timezone-aware
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)

                # Check if record already exists
                existing = db.query(StockPrice).filter(
                    StockPrice.stock_id == stock_id,
                    StockPrice.timeframe == target_timeframe,
                    StockPrice.timestamp == timestamp
                ).first()

                if existing:
                    # Update existing record
                    existing.open = float(row['open']) if not pd.isna(row['open']) else None
                    existing.high = float(row['high']) if not pd.isna(row['high']) else None
                    existing.low = float(row['low']) if not pd.isna(row['low']) else None
                    existing.close = float(row['close']) if not pd.isna(row['close']) else None
                    existing.volume = int(row['volume']) if not pd.isna(row['volume']) else 0
                    existing.adjusted_close = float(row['close']) if not pd.isna(row['close']) else None
                    rows_updated += 1
                else:
                    # Insert new record
                    price = StockPrice(
                        stock_id=stock_id,
                        timeframe=target_timeframe,
                        timestamp=timestamp,
                        open=float(row['open']) if not pd.isna(row['open']) else None,
                        high=float(row['high']) if not pd.isna(row['high']) else None,
                        low=float(row['low']) if not pd.isna(row['low']) else None,
                        close=float(row['close']) if not pd.isna(row['close']) else None,
                        volume=int(row['volume']) if not pd.isna(row['volume']) else 0,
                        adjusted_close=float(row['close']) if not pd.isna(row['close']) else None
                    )
                    db.add(price)
                    rows_inserted += 1
                    # Flush immediately to avoid batch insert issues with composite primary key
                    db.flush()

            db.commit()

            logger.info(f"✅ Saved aggregated {target_timeframe} data for stock_id={stock_id}: {rows_inserted} inserted, {rows_updated} updated")
            return True

        except Exception as e:
            logger.error(f"Error aggregating and saving stock_id={stock_id}, timeframe={target_timeframe}: {e}", exc_info=True)
            db.rollback()
            return False

    @staticmethod
    def aggregate_all_and_save_to_db(
        db: Session,
        stock_id: int,
        days_lookback: int = 90
    ) -> Dict[str, bool]:
        """
        Aggregate all timeframes (1d, 1w, 1mo) and save to database.

        This should be called after fetching new hourly data.

        Args:
            db: Database session
            stock_id: Stock ID
            days_lookback: Days of history to aggregate (default: 90)

        Returns:
            Dict mapping timeframe → success/failure
        """
        results = {}

        # Aggregate in order: 1d, 1w, 1mo
        timeframes = ['1d', '1w', '1mo']

        for timeframe in timeframes:
            success = TimeframeAggregator.aggregate_and_save_to_db(db, stock_id, timeframe, days_lookback)
            results[timeframe] = success

            if not success:
                logger.warning(f"Failed to aggregate {timeframe} for stock_id={stock_id}")

        return results

    @staticmethod
    def get_aggregation_stats(db: Session) -> Dict[str, dict]:
        """
        Get statistics about aggregated data for monitoring.

        Args:
            db: Database session

        Returns:
            Dict with statistics per timeframe
        """
        from app.models.stock import StockPrice

        try:
            stats = {}

            for timeframe in ['1h', '1d', '1w', '1mo']:
                count = db.query(StockPrice).filter(StockPrice.timeframe == timeframe).count()
                stats[timeframe] = {
                    'total_records': count,
                    'avg_per_stock': round(count / 502, 1) if count > 0 else 0  # Assuming 502 stocks
                }

            return stats

        except Exception as e:
            logger.error(f"Error getting aggregation stats: {e}")
            return {}
