"""
Timeframe Service for multi-timeframe data operations
With smart aggregation from 1h base timeframe
"""
from sqlalchemy.orm import Session
from app.models.stock import StockPrice
from app.models.timeframe import Timeframe
from app.config.timeframe_config import TimeframeConfig
from app.services.timeframe_aggregator import TimeframeAggregator
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class TimeframeService:
    """Service for multi-timeframe data operations"""

    @staticmethod
    def get_price_data(
        db: Session,
        stock_id: int,
        timeframe: str = "1d",
        lookback_days: int = None,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> pd.DataFrame:
        """
        Get price data for specific timeframe

        Args:
            db: Database session
            stock_id: Stock ID
            timeframe: Timeframe (1m, 5m, 1h, 4h, 1d, etc.)
            lookback_days: Days of history (overrides start_date if provided)
            start_date: Start date for data fetch
            end_date: End date for data fetch (default: now)

        Returns:
            DataFrame with OHLCV data indexed by timestamp
        """
        # Calculate date range
        if end_date is None:
            end_date = datetime.now()

        if lookback_days is not None:
            start_date = end_date - timedelta(days=lookback_days)
        elif start_date is None:
            # Use default lookback for timeframe
            lookback_days = Timeframe.get_default_lookback(timeframe)
            start_date = end_date - timedelta(days=lookback_days)

        # Query database
        logger.info(f"Fetching {timeframe} data for stock_id={stock_id} from {start_date} to {end_date}")

        prices = db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id,
            StockPrice.timeframe == timeframe,
            StockPrice.timestamp >= start_date,
            StockPrice.timestamp <= end_date
        ).order_by(StockPrice.timestamp).all()

        # Convert to DataFrame
        if not prices:
            logger.warning(f"No {timeframe} data found for stock_id={stock_id}")
            return pd.DataFrame()

        df = pd.DataFrame([{
            'timestamp': p.timestamp,
            'open': float(p.open),
            'high': float(p.high),
            'low': float(p.low),
            'close': float(p.close),
            'volume': int(p.volume)
        } for p in prices])

        df.set_index('timestamp', inplace=True)
        logger.info(f"Loaded {len(df)} {timeframe} bars for stock_id={stock_id}")

        return df

    @staticmethod
    def get_price_data_smart(
        db: Session,
        stock_id: int,
        timeframe: str = "1d",
        lookback_days: int = None
    ) -> pd.DataFrame:
        """
        Smart data fetching with automatic aggregation (backward compatible)

        Strategy:
        1. If timeframe is 1h, fetch 1h data directly
        2. If timeframe is aggregated (2h, 4h, 1d, 1w, 1mo):
           a. Try to fetch 1h data and aggregate (preferred)
           b. If no 1h data, fall back to direct fetch (backward compatibility)

        This is the RECOMMENDED method for getting timeframe data.

        Args:
            db: Database session
            stock_id: Stock ID
            timeframe: Target timeframe
            lookback_days: Days of history (uses default if None)

        Returns:
            DataFrame with requested timeframe data
        """
        # Use default lookback if not specified
        if lookback_days is None:
            lookback_days = TimeframeConfig.get_default_lookback(timeframe)

        # Check if this timeframe should be aggregated
        if TimeframeConfig.is_aggregated(timeframe):
            logger.info(f"Attempting to aggregate {timeframe} from 1h data for stock_id={stock_id}")

            # Try to fetch 1h base data
            df_1h = TimeframeService.get_price_data(
                db, stock_id, '1h', lookback_days=lookback_days
            )

            if not df_1h.empty:
                # We have 1h data, use smart aggregation
                logger.info(f"Found {len(df_1h)} 1h bars, aggregating to {timeframe}")

                # Aggregate to target timeframe
                df_aggregated = TimeframeAggregator.get_aggregated_timeframe(
                    df_1h, timeframe
                )

                # Validate aggregation
                if not df_aggregated.empty:
                    is_valid = TimeframeAggregator.validate_aggregation(df_1h, df_aggregated)
                    if not is_valid:
                        logger.warning(f"Aggregation validation failed for {timeframe}")

                return df_aggregated
            else:
                # No 1h data available, fall back to direct fetch (backward compatibility)
                logger.info(f"No 1h data found for stock_id={stock_id}, falling back to direct {timeframe} fetch")
                df_direct = TimeframeService.get_price_data(
                    db, stock_id, timeframe, lookback_days=lookback_days
                )

                if not df_direct.empty:
                    logger.info(f"Found {len(df_direct)} {timeframe} bars via direct fetch (legacy data)")
                else:
                    logger.warning(f"No {timeframe} data found for stock_id={stock_id} (neither 1h nor direct)")

                return df_direct

        else:
            # Fetch directly from database (1h or future intraday timeframes)
            logger.info(f"Fetching {timeframe} directly from database for stock_id={stock_id}")
            return TimeframeService.get_price_data(
                db, stock_id, timeframe, lookback_days=lookback_days
            )

    @staticmethod
    def get_multiple_timeframes(
        db: Session,
        stock_id: int,
        timeframes: List[str] = ["1h", "4h", "1d"],
        lookback_days: int = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Get data for multiple timeframes

        Args:
            db: Database session
            stock_id: Stock ID
            timeframes: List of timeframes to fetch
            lookback_days: Days of history (applied to all timeframes)

        Returns:
            Dictionary mapping timeframe to DataFrame
            Example: {'1h': DataFrame, '4h': DataFrame, '1d': DataFrame}
        """
        result = {}

        for tf in timeframes:
            df = TimeframeService.get_price_data(
                db, stock_id, tf, lookback_days=lookback_days
            )
            if not df.empty:
                result[tf] = df
            else:
                logger.warning(f"No data for timeframe={tf}, stock_id={stock_id}")

        return result

    @staticmethod
    def save_price_data(
        db: Session,
        stock_id: int,
        timeframe: str,
        prices: List[Dict]
    ) -> int:
        """
        Save price data to database (upsert: update if exists, insert if new)

        Args:
            db: Database session
            stock_id: Stock ID
            timeframe: Timeframe string
            prices: List of price dictionaries with keys:
                    'timestamp', 'open', 'high', 'low', 'close', 'volume'

        Returns:
            Number of records saved
        """
        if not prices:
            logger.warning("No prices to save")
            return 0

        saved_count = 0
        updated_count = 0

        for price_data in prices:
            # Check if exists
            existing = db.query(StockPrice).filter(
                StockPrice.stock_id == stock_id,
                StockPrice.timeframe == timeframe,
                StockPrice.timestamp == price_data['timestamp']
            ).first()

            if existing:
                # Update existing record
                existing.open = price_data['open']
                existing.high = price_data['high']
                existing.low = price_data['low']
                existing.close = price_data['close']
                existing.volume = price_data['volume']
                existing.adjusted_close = price_data.get('adjusted_close', price_data['close'])
                updated_count += 1
            else:
                # Insert new record
                new_price = StockPrice(
                    stock_id=stock_id,
                    timeframe=timeframe,
                    timestamp=price_data['timestamp'],
                    open=price_data['open'],
                    high=price_data['high'],
                    low=price_data['low'],
                    close=price_data['close'],
                    volume=price_data['volume'],
                    adjusted_close=price_data.get('adjusted_close', price_data['close'])
                )
                db.add(new_price)
                saved_count += 1

        # Commit changes
        db.commit()

        logger.info(f"Saved {saved_count} new, updated {updated_count} existing {timeframe} bars for stock_id={stock_id}")
        return saved_count + updated_count

    @staticmethod
    def get_available_timeframes(
        db: Session,
        stock_id: int
    ) -> List[str]:
        """
        Get list of timeframes that have data for this stock

        Args:
            db: Database session
            stock_id: Stock ID

        Returns:
            List of timeframe strings sorted by duration (shortest first)
        """
        result = db.query(StockPrice.timeframe).filter(
            StockPrice.stock_id == stock_id
        ).distinct().all()

        timeframes = [row[0] for row in result]

        # Sort by timeframe duration (shortest first)
        timeframes.sort(key=Timeframe.get_sorting_order)

        return timeframes

    @staticmethod
    def get_latest_timestamp(
        db: Session,
        stock_id: int,
        timeframe: str
    ) -> Optional[datetime]:
        """
        Get the most recent timestamp for this stock/timeframe

        Args:
            db: Database session
            stock_id: Stock ID
            timeframe: Timeframe string

        Returns:
            Latest timestamp or None if no data
        """
        result = db.query(StockPrice.timestamp).filter(
            StockPrice.stock_id == stock_id,
            StockPrice.timeframe == timeframe
        ).order_by(StockPrice.timestamp.desc()).first()

        return result[0] if result else None

    @staticmethod
    def count_bars(
        db: Session,
        stock_id: int,
        timeframe: str
    ) -> int:
        """
        Count number of bars for stock/timeframe

        Args:
            db: Database session
            stock_id: Stock ID
            timeframe: Timeframe string

        Returns:
            Number of bars
        """
        count = db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id,
            StockPrice.timeframe == timeframe
        ).count()

        return count

    @staticmethod
    def delete_timeframe_data(
        db: Session,
        stock_id: int,
        timeframe: str
    ) -> int:
        """
        Delete all data for specific stock/timeframe

        Args:
            db: Database session
            stock_id: Stock ID
            timeframe: Timeframe string

        Returns:
            Number of records deleted
        """
        count = db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id,
            StockPrice.timeframe == timeframe
        ).delete()

        db.commit()

        logger.info(f"Deleted {count} {timeframe} bars for stock_id={stock_id}")
        return count
