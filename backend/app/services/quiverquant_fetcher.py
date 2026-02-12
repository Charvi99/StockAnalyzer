"""
Quiver Quant API fetcher service for insider trading data
Official docs: https://api.quantitativestats.com/docs
"""

import requests
import logging
import time
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class QuiverQuantFetcher:
    """
    Fetches insider trading data from Quiver Quant API

    Quiver Quant provides:
    - Corporate insider trading (Form 4 filings)
    - Congressional trading
    - Hedge fund 13F filings
    - Insider sentiment scores

    Free tier: 1,000 API calls/month
    API Docs: https://api.quantitativestats.com/docs
    """

    BASE_URL = "https://api.quiverquant.com/beta"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Quiver Quant fetcher

        Args:
            api_key: Quiver Quant API key (if None, reads from env)
        """
        self.api_key = api_key or os.getenv("QUIVERQUANT_API_KEY")

        if not self.api_key or self.api_key == "your_api_key_here":
            logger.warning("⚠️ No Quiver Quant API key set!")
            logger.warning("Get your free key at: https://www.quiverquant.com/")
            logger.warning("Free tier: 1,000 API calls/month")

        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

        # Rate limit: Free tier has limits, be conservative
        self.rate_limit_delay = 0.5  # seconds between requests

    def _make_request(self, endpoint: str, params: Optional[Dict] = None, max_retries: int = 3) -> Optional[Dict]:
        """
        Make API request with retry logic

        Args:
            endpoint: API endpoint path
            params: Query parameters
            max_retries: Maximum retry attempts

        Returns:
            Response JSON or None if failed
        """
        url = f"{self.BASE_URL}/{endpoint}"

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                # Rate limiting delay
                time.sleep(self.rate_limit_delay)

                return response.json()

            except requests.exceptions.HTTPError as e:
                if response.status_code == 401:
                    logger.error("❌ Invalid Quiver Quant API key")
                    return None
                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"⏳ Rate limit hit. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                elif response.status_code == 404:
                    logger.warning(f"Data not found for endpoint: {endpoint}")
                    return None
                else:
                    logger.warning(f"HTTP error on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        logger.error(f"❌ All {max_retries} attempts failed for {endpoint}")
        return None

    def fetch_live_insider_trades(self, ticker: str) -> Optional[List[Dict]]:
        """
        Fetch recent insider trading for a ticker

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            List of insider trade dictionaries or None

        Example response:
        [
            {
                "Date": "2024-01-15",
                "Ticker": "AAPL",
                "Name": "Cook Timothy",
                "Title": "CEO",
                "Transaction": "Sale",
                "Shares": "10000",
                "Price": "185.50",
                "FilingDate": "2024-01-17"
            },
            ...
        ]
        """
        logger.info(f"Fetching live insider trades for {ticker}")

        data = self._make_request(f"live-insider/{ticker}")

        if not data:
            return None

        # Parse and normalize response
        trades = []
        for item in data:
            try:
                # Parse shares (handle commas, strings, etc.)
                shares_str = str(item.get("Shares", "0")).replace(",", "")
                shares = int(float(shares_str))

                # Parse price
                price_str = str(item.get("Price", "0")).replace("$", "").replace(",", "")
                price = float(price_str) if price_str else None

                # Calculate total value
                total_value = shares * price if price and shares else None

                # Normalize transaction type
                transaction = item.get("Transaction", "").lower()
                if "buy" in transaction or "purchase" in transaction:
                    transaction_type = "BUY"
                elif "sell" in transaction or "sale" in transaction:
                    transaction_type = "SELL"
                elif "exercise" in transaction:
                    transaction_type = "OPTION_EXERCISE"
                else:
                    transaction_type = "OTHER"

                # Parse dates
                trade_date = self._parse_date(item.get("Date"))
                filing_date = self._parse_date(item.get("FilingDate"))

                trades.append({
                    "ticker": ticker.upper(),
                    "insider_name": item.get("Name", ""),
                    "insider_title": item.get("Title", ""),
                    "transaction_type": transaction_type,
                    "shares": shares,
                    "price": price,
                    "total_value": total_value,
                    "trade_date": trade_date,
                    "filing_date": filing_date,
                    "raw_data": item
                })

            except (ValueError, KeyError) as e:
                logger.debug(f"Error parsing trade data: {e}")
                continue

        logger.info(f"✅ Fetched {len(trades)} insider trades for {ticker}")
        return trades

    def fetch_historical_insider_trades(
        self,
        ticker: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[List[Dict]]:
        """
        Fetch historical insider trading for a ticker

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (default: 1 year ago)
            end_date: End date (default: today)

        Returns:
            List of insider trade dictionaries or None
        """
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        logger.info(f"Fetching historical insider trades for {ticker} from {start_date} to {end_date}")

        # Quiver Quant historical endpoint
        params = {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        }

        data = self._make_request(f"historical-insider/{ticker}", params=params)

        if not data:
            return None

        # Parse same as live trades
        trades = []
        for item in data:
            try:
                shares_str = str(item.get("Shares", "0")).replace(",", "")
                shares = int(float(shares_str))

                price_str = str(item.get("Price", "0")).replace("$", "").replace(",", "")
                price = float(price_str) if price_str else None

                total_value = shares * price if price and shares else None

                transaction = item.get("Transaction", "").lower()
                if "buy" in transaction or "purchase" in transaction:
                    transaction_type = "BUY"
                elif "sell" in transaction or "sale" in transaction:
                    transaction_type = "SELL"
                elif "exercise" in transaction:
                    transaction_type = "OPTION_EXERCISE"
                else:
                    transaction_type = "OTHER"

                trade_date = self._parse_date(item.get("Date"))
                filing_date = self._parse_date(item.get("FilingDate"))

                trades.append({
                    "ticker": ticker.upper(),
                    "insider_name": item.get("Name", ""),
                    "insider_title": item.get("Title", ""),
                    "transaction_type": transaction_type,
                    "shares": shares,
                    "price": price,
                    "total_value": total_value,
                    "trade_date": trade_date,
                    "filing_date": filing_date,
                    "raw_data": item
                })

            except (ValueError, KeyError) as e:
                logger.debug(f"Error parsing trade data: {e}")
                continue

        logger.info(f"✅ Fetched {len(trades)} historical insider trades for {ticker}")
        return trades

    def fetch_congressional_trades(self, ticker: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Fetch congressional trading data

        Args:
            ticker: Optional ticker filter (if None, returns all recent congressional trades)

        Returns:
            List of congressional trade dictionaries or None
        """
        if ticker:
            logger.info(f"Fetching congressional trades for {ticker}")
            endpoint = f"live-congress/{ticker}"
        else:
            logger.info("Fetching all recent congressional trades")
            endpoint = "live-congress"

        data = self._make_request(endpoint)

        if not data:
            return None

        # Parse congressional trades (similar structure to insider trades)
        trades = []
        for item in data:
            try:
                shares_str = str(item.get("Amount", "0")).replace(",", "").replace("$", "")
                # Congressional trades often show ranges like "$1000 - $15000"
                # Use the lower bound if range
                if "-" in shares_str:
                    shares_str = shares_str.split("-")[0].strip()

                amount = float(shares_str) if shares_str else None

                trade_date = self._parse_date(item.get("TransactionDate"))
                filing_date = self._parse_date(item.get("DisclosureDate"))

                transaction = item.get("Transaction", "").lower()
                if "buy" in transaction or "purchase" in transaction:
                    transaction_type = "BUY"
                elif "sell" in transaction or "sale" in transaction:
                    transaction_type = "SELL"
                else:
                    transaction_type = "OTHER"

                trades.append({
                    "ticker": item.get("Ticker", "").upper(),
                    "representative": item.get("Representative", ""),
                    "party": item.get("Party", ""),
                    "transaction_type": transaction_type,
                    "total_value": amount,
                    "trade_date": trade_date,
                    "filing_date": filing_date,
                    "is_congressional": True,
                    "raw_data": item
                })

            except (ValueError, KeyError) as e:
                logger.debug(f"Error parsing congressional trade: {e}")
                continue

        logger.info(f"✅ Fetched {len(trades)} congressional trades")
        return trades

    def fetch_insider_sentiment(self, ticker: str) -> Optional[Dict]:
        """
        Fetch insider sentiment score for a ticker

        Sentiment ranges from -100 (all selling) to +100 (all buying)

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with sentiment data or None

        Example response:
        {
            "Date": "2024-01-15",
            "Ticker": "AAPL",
            "Sentiment": "25.5",
            "Positive": "150000",
            "Negative": "50000"
        }
        """
        logger.info(f"Fetching insider sentiment for {ticker}")

        data = self._make_request(f"live-insider/{ticker}")

        if not data:
            return None

        # Calculate sentiment from recent trades
        buys = []
        sells = []

        for item in data:
            transaction = item.get("Transaction", "").lower()
            shares_str = str(item.get("Shares", "0")).replace(",", "")

            try:
                shares = int(float(shares_str))

                if "buy" in transaction or "purchase" in transaction:
                    buys.append(shares)
                elif "sell" in transaction or "sale" in transaction:
                    sells.append(shares)
            except (ValueError, KeyError):
                continue

        total_buy = sum(buys)
        total_sell = sum(sells)
        total_volume = total_buy + total_sell

        if total_volume == 0:
            sentiment = 0
        else:
            # Sentiment: -100 (all sell) to +100 (all buy)
            sentiment = ((total_buy - total_sell) / total_volume) * 100

        return {
            "ticker": ticker.upper(),
            "sentiment": round(sentiment, 2),
            "buy_volume": total_buy,
            "sell_volume": total_sell,
            "total_volume": total_volume,
            "buy_count": len(buys),
            "sell_count": len(sells)
        }

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse date string to datetime object

        Args:
            date_str: Date string in various formats

        Returns:
            Datetime object or None
        """
        if not date_str:
            return None

        # Try common date formats
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None
