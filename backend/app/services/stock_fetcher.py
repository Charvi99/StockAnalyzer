from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from app.models.stock import Stock, StockPrice
from app.services.polygon_fetcher import PolygonFetcher
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
    def save_stock_prices(db: Session, stock_id: int, prices_data: List[Dict]) -> int:
        """
        Save stock prices to database

        Args:
            db: Database session
            stock_id: ID of the stock
            prices_data: List of price dictionaries

        Returns:
            Number of records saved
        """
        saved_count = 0

        try:
            for price_data in prices_data:
                # Check if price already exists
                existing = db.query(StockPrice).filter(
                    StockPrice.stock_id == stock_id,
                    StockPrice.timestamp == price_data['timestamp']
                ).first()

                if existing:
                    # Update existing record
                    existing.open = price_data['open']
                    existing.high = price_data['high']
                    existing.low = price_data['low']
                    existing.close = price_data['close']
                    existing.volume = price_data['volume']
                    existing.adjusted_close = price_data['adjusted_close']
                else:
                    # Create new record
                    new_price = StockPrice(
                        stock_id=stock_id,
                        timestamp=price_data['timestamp'],
                        open=price_data['open'],
                        high=price_data['high'],
                        low=price_data['low'],
                        close=price_data['close'],
                        volume=price_data['volume'],
                        adjusted_close=price_data['adjusted_close']
                    )
                    db.add(new_price)
                    saved_count += 1

            db.commit()
            logger.info(f"Saved {saved_count} new price records for stock_id {stock_id}")
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
        interval: str = "1d"
    ) -> Dict:
        """
        Fetch historical data and store in database (convenience method)

        Args:
            db: Database session
            stock_id: ID of the stock
            symbol: Stock ticker symbol
            period: Data period
            interval: Data interval

        Returns:
            Dictionary with operation results
        """
        # Fetch data
        prices_data = StockDataFetcher.fetch_historical_data(symbol, period, interval)

        if not prices_data:
            return {
                'success': False,
                'message': f'No data found for {symbol}',
                'records_fetched': 0,
                'records_saved': 0
            }

        # Save to database
        try:
            saved_count = StockDataFetcher.save_stock_prices(db, stock_id, prices_data)

            return {
                'success': True,
                'message': f'Successfully fetched and stored data for {symbol}',
                'records_fetched': len(prices_data),
                'records_saved': saved_count
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
