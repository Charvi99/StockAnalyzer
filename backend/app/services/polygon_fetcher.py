"""
Polygon.io API fetcher service for stock market data
Official docs: https://polygon.io/docs/stocks/getting-started
"""

from polygon import RESTClient
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
import os
import time

logger = logging.getLogger(__name__)


class PolygonFetcher:
    """Fetches stock data from Polygon.io API"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Polygon fetcher

        Args:
            api_key: Polygon.io API key (if None, reads from env)
        """
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")

        if not self.api_key or self.api_key == "demo":
            logger.warning("⚠️ No Polygon API key set! Using demo key (very limited).")
            logger.warning("Get your free key at: https://polygon.io/")

        self.client = RESTClient(api_key=self.api_key)
        self.rate_limit_delay = 12  # seconds (5 requests/minute = 12s between requests for free tier)

    def _parse_period_to_dates(self, period: str) -> tuple:
        """
        Convert period string to start/end dates

        Args:
            period: Period string (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

        Returns:
            Tuple of (start_date, end_date) as datetime objects
        """
        end_date = datetime.now()

        period_map = {
            '1d': timedelta(days=1),
            '5d': timedelta(days=5),
            '1mo': timedelta(days=30),
            '3mo': timedelta(days=90),
            '6mo': timedelta(days=180),
            '1y': timedelta(days=365),
            '2y': timedelta(days=730),
            '5y': timedelta(days=1825),
            '10y': timedelta(days=3650),
            'ytd': None,  # Special handling
            'max': timedelta(days=7300)  # ~20 years
        }

        if period == 'ytd':
            start_date = datetime(end_date.year, 1, 1)
        elif period in period_map:
            start_date = end_date - period_map[period]
        else:
            logger.warning(f"Unknown period '{period}', defaulting to 1 year")
            start_date = end_date - timedelta(days=365)

        return start_date, end_date

    def _parse_interval(self, interval: str) -> tuple:
        """
        Convert interval string to Polygon timespan and multiplier

        Args:
            interval: Interval string (1h, 1d, 1wk, 1mo, daily, weekly, monthly, etc.)

        Returns:
            Tuple of (multiplier, timespan)
        """
        interval = interval.lower()

        interval_map = {
            # Intraday
            '1m': (1, 'minute'),
            '5m': (5, 'minute'),
            '15m': (15, 'minute'),
            '30m': (30, 'minute'),
            '1h': (1, 'hour'),
            '2h': (2, 'hour'),
            '4h': (4, 'hour'),
            # Daily and above
            '1d': (1, 'day'),
            'daily': (1, 'day'),
            '1wk': (1, 'week'),
            'weekly': (1, 'week'),
            '1mo': (1, 'month'),
            'monthly': (1, 'month'),
        }

        if interval in interval_map:
            return interval_map[interval]

        # Default to daily
        logger.warning(f"Unknown interval '{interval}', defaulting to daily")
        return (1, 'day')

    def fetch_stock_info(self, symbol: str) -> Optional[Dict]:
        """
        Fetch basic stock information from Polygon

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            Dictionary with stock info or None if not found
        """
        try:
            logger.info(f"Fetching stock info for {symbol} from Polygon.io")

            # Get ticker details
            ticker_details = self.client.get_ticker_details(symbol.upper())

            if not ticker_details:
                logger.warning(f"No info found for symbol: {symbol}")
                return None

            return {
                'symbol': symbol.upper(),
                'name': getattr(ticker_details, 'name', symbol.upper()),
                'sector': getattr(ticker_details, 'sic_description', None),
                'industry': getattr(ticker_details, 'description', None)
            }

        except Exception as e:
            logger.error(f"Error fetching info for {symbol} from Polygon: {str(e)}")
            return None

    def fetch_historical_data(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        max_retries: int = 3
    ) -> Optional[List[Dict]]:
        """
        Fetch historical stock price data from Polygon

        Args:
            symbol: Stock ticker symbol
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1d, 1wk, 1mo, daily, weekly, monthly)
            max_retries: Maximum number of retry attempts

        Returns:
            List of price data dictionaries or None if error
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching {period} {interval} data for {symbol} from Polygon.io")

                # Parse period and interval
                start_date, end_date = self._parse_period_to_dates(period)
                multiplier, timespan = self._parse_interval(interval)

                # Format dates for API (YYYY-MM-DD)
                from_date = start_date.strftime('%Y-%m-%d')
                to_date = end_date.strftime('%Y-%m-%d')

                # Fetch aggregates (bars/OHLC data)
                logger.info(f"Polygon query: {symbol} from {from_date} to {to_date}, {multiplier} {timespan}")

                aggs = self.client.get_aggs(
                    ticker=symbol.upper(),
                    multiplier=multiplier,
                    timespan=timespan,
                    from_=from_date,
                    to=to_date,
                    limit=50000  # Maximum results
                )

                if not aggs or len(aggs) == 0:
                    logger.warning(f"No data returned from Polygon for {symbol}")
                    return None

                # Convert to our format
                prices = []
                for bar in aggs:
                    # Polygon returns timestamps in milliseconds
                    timestamp = datetime.fromtimestamp(bar.timestamp / 1000)

                    prices.append({
                        'timestamp': timestamp,
                        'timeframe': interval,  # Include timeframe for multi-timeframe support
                        'open': float(bar.open),
                        'high': float(bar.high),
                        'low': float(bar.low),
                        'close': float(bar.close),
                        'volume': int(bar.volume),
                        'adjusted_close': float(bar.close)  # Polygon provides vwap, but we'll use close
                    })

                logger.info(f"✅ Successfully fetched {len(prices)} price records for {symbol}")
                return prices

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {symbol}: {str(e)}")

                # Check if it's a rate limit error
                if "rate limit" in str(e).lower() or "429" in str(e):
                    logger.warning(f"⏳ Rate limit hit. Waiting {self.rate_limit_delay} seconds...")
                    time.sleep(self.rate_limit_delay)

                if attempt < max_retries - 1:
                    wait_time = 2 ** (attempt + 1)
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ All {max_retries} attempts failed for {symbol}")
                    return None

        return None

    def get_latest_price(self, symbol: str) -> Optional[Dict]:
        """
        Get the most recent price for a stock

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with latest price info or None
        """
        try:
            logger.info(f"Fetching latest price for {symbol} from Polygon.io")

            # Get last trade
            last_trade = self.client.get_last_trade(symbol.upper())

            if not last_trade:
                logger.warning(f"No recent price found for {symbol}")
                return None

            # Convert timestamp from nanoseconds
            timestamp = datetime.fromtimestamp(last_trade.sip_timestamp / 1_000_000_000)

            return {
                'symbol': symbol.upper(),
                'price': float(last_trade.price),
                'timestamp': timestamp,
                'volume': int(getattr(last_trade, 'size', 0))
            }

        except Exception as e:
            logger.error(f"Error fetching latest price for {symbol} from Polygon: {str(e)}")
            return None

    def get_previous_close(self, symbol: str) -> Optional[Dict]:
        """
        Get the previous day's close price

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with previous close data or None
        """
        try:
            logger.info(f"Fetching previous close for {symbol} from Polygon.io")

            prev_close = self.client.get_previous_close(symbol.upper())

            if not prev_close or len(prev_close) == 0:
                logger.warning(f"No previous close found for {symbol}")
                return None

            bar = prev_close[0]
            timestamp = datetime.fromtimestamp(bar.timestamp / 1000)

            return {
                'timestamp': timestamp,
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': int(bar.volume),
                'adjusted_close': float(bar.close)
            }

        except Exception as e:
            logger.error(f"Error fetching previous close for {symbol} from Polygon: {str(e)}")
            return None
