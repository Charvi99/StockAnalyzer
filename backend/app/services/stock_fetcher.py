from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from app.models.stock import Stock, StockPrice
from app.services.polygon_fetcher import PolygonFetcher
from app.services.timeframe_service import TimeframeService
from app.config.timeframe_config import TimeframeConfig
import logging

logger = logging.getLogger(__name__)

# Initialize Polygon.io fetcher
polygon = PolygonFetcher()


class StockDataFetcher:
    """Service for fetching stock data from Polygon.io"""

    @staticmethod
    def fetch_stock_info(symbol: str) -> Optional[Dict]:
        """
        Fetch basic stock information

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            Dictionary with stock info or None if not found
        """
        logger.info(f"Fetching stock info for {symbol} from Polygon.io")
        return polygon.fetch_stock_info(symbol)

    @staticmethod
    def fetch_historical_data(
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        max_retries: int = 3
    ) -> Optional[List[Dict]]:
        """
        Fetch historical stock price data with retry logic

        Args:
            symbol: Stock ticker symbol
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1d, 1wk, 1mo, daily, weekly, monthly)
            max_retries: Maximum number of retry attempts

        Returns:
            List of price data dictionaries or None if error
        """
        logger.info(f"Fetching {period} {interval} data for {symbol} from Polygon.io")
        return polygon.fetch_historical_data(symbol, period, interval, max_retries)

    @staticmethod
    def save_stock_prices(db: Session, stock_id: int, prices_data: List[Dict], timeframe: str = "1d") -> int:
        """
        Save stock prices to database with timeframe support

        Args:
            db: Database session
            stock_id: ID of the stock
            prices_data: List of price dictionaries (must include 'timeframe' or use timeframe param)
            timeframe: Default timeframe if not in price_data (default: "1d")

        Returns:
            Number of records saved
        """
        # Use TimeframeService for saving (handles upserts properly)
        try:
            # Extract timeframe from first record if available, otherwise use parameter
            tf = prices_data[0].get('timeframe', timeframe) if prices_data else timeframe

            saved_count = TimeframeService.save_price_data(
                db=db,
                stock_id=stock_id,
                timeframe=tf,
                prices=prices_data
            )

            return saved_count

        except Exception as e:
            db.rollback()
            logger.error(f"Error saving prices to database: {str(e)}")
            raise

    @staticmethod
    def fetch_and_store(
        db: Session,
        stock_id: int,
        symbol: str,
        period: str = "1y",
        interval: str = "1h"  # Changed default to 1h (base timeframe)
    ) -> Dict:
        """
        Fetch historical data and store in database (convenience method)

        Args:
            db: Database session
            stock_id: ID of the stock
            symbol: Stock ticker symbol
            period: Data period
            interval: Data interval (default: 1h for smart aggregation)

        Returns:
            Dictionary with operation results
        """
        # Validate interval for base timeframe
        if interval not in TimeframeConfig.ALL_TIMEFRAMES:
            logger.warning(f"Interval {interval} not in configured timeframes, using 1h")
            interval = TimeframeConfig.BASE_TIMEFRAME

        # Only fetch base timeframe (1h), not aggregated timeframes
        if TimeframeConfig.is_aggregated(interval):
            return {
                'success': False,
                'message': f'{interval} is aggregated from {TimeframeConfig.BASE_TIMEFRAME}. Only fetch base timeframe.',
                'records_fetched': 0,
                'records_saved': 0
            }

        # Fetch data
        logger.info(f"Fetching {period} {interval} data for {symbol}")
        prices_data = StockDataFetcher.fetch_historical_data(symbol, period, interval)

        if not prices_data:
            return {
                'success': False,
                'message': f'No data found for {symbol}',
                'records_fetched': 0,
                'records_saved': 0
            }

        # Save to database with timeframe
        try:
            saved_count = StockDataFetcher.save_stock_prices(
                db, stock_id, prices_data, timeframe=interval
            )

            return {
                'success': True,
                'message': f'Successfully fetched and stored {interval} data for {symbol}',
                'records_fetched': len(prices_data),
                'records_saved': saved_count,
                'timeframe': interval
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error storing data: {str(e)}',
                'records_fetched': len(prices_data),
                'records_saved': 0
            }

    @staticmethod
    def get_latest_price(symbol: str) -> Optional[Dict]:
        """
        Get the most recent price for a stock

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with latest price info or None
        """
        logger.info(f"Fetching latest price for {symbol} from Polygon.io")
        return polygon.get_latest_price(symbol)
