"""
Quiver Quant API fetcher using official quiverquant package

Official package documentation: https://pypi.org/project/quiverquant/
"""

import logging
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class QuiverQuantFetcher:
    """
    Fetches insider trading data using official quiverquant package

    The official package handles:
    - Authentication (no Cloudflare issues)
    - Rate limiting
    - Data parsing
    - Returns pandas DataFrames directly

    Installation: pip install quiverquant
    """

    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize Quiver Quant fetcher using official package

        Args:
            api_token: Quiver Quant API token (if None, reads from env)
        """
        self.api_token = api_token or os.getenv("QUIVERQUANT_API_KEY")

        if not self.api_token or self.api_token == "your_api_key_here":
            logger.warning("⚠️ No Quiver Quant API token set!")
            logger.warning("Get your token at: https://api.quiverquant.com/pricing/")
            logger.warning("Pricing starts at $10/month")
            self.quiver = None
        else:
            try:
                import quiverquant
                self.quiver = quiverquant.quiver(self.api_token)
                logger.info("✅ Connected to Quiver Quant API using official package")
            except ImportError:
                logger.error("❌ quiverquant package not installed!")
                logger.error("Run: pip install quiverquant")
                self.quiver = None
            except Exception as e:
                logger.error(f"❌ Failed to connect to Quiver Quant: {e}")
                self.quiver = None

    def fetch_live_insider_trades(self, ticker: str) -> Optional[List[Dict]]:
        """
        Fetch recent insider trading for a ticker

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            List of insider trade dictionaries or None

        Example response columns:
            - Date: Transaction date
            - Ticker: Stock symbol
            - Name: Insider name
            - Title: Insider's title
            - Transaction: Buy/Sell/Purchase/Sale
            - Shares: Number of shares
            - Price: Price per share
            - FilingDate: When the trade was filed
        """
        if not self.quiver:
            logger.warning("Quiver Quant not connected")
            return None

        try:
            logger.info(f"Fetching insider trades for {ticker}")

            # Use official package's insiders method
            df = self.quiver.insiders(ticker)

            if df is None or df.empty:
                logger.warning(f"No insider data found for {ticker}")
                return None

            # Convert DataFrame to list of dictionaries
            trades = []
            for _, row in df.iterrows():
                try:
                    # Parse shares
                    shares_str = str(row.get('Shares', '0')).replace(',', '').replace('$', '')
                    shares = int(float(shares_str)) if shares_str else 0

                    # Parse price
                    price_str = str(row.get('Price', '0')).replace(',', '').replace('$', '')
                    price = float(price_str) if price_str else None

                    # Calculate total value
                    total_value = shares * price if price and shares else None

                    # Normalize transaction type
                    transaction = str(row.get('Transaction', '')).lower()
                    if 'buy' in transaction or 'purchase' in transaction:
                        transaction_type = 'BUY'
                    elif 'sell' in transaction or 'sale' in transaction:
                        transaction_type = 'SELL'
                    elif 'exercise' in transaction:
                        transaction_type = 'OPTION_EXERCISE'
                    else:
                        transaction_type = 'OTHER'

                    # Parse dates
                    trade_date = self._parse_date(row.get('Date'))
                    filing_date = self._parse_date(row.get('FilingDate'))

                    trades.append({
                        'ticker': ticker.upper(),
                        'insider_name': row.get('Name', ''),
                        'insider_title': row.get('Title', ''),
                        'transaction_type': transaction_type,
                        'shares': shares,
                        'price': price,
                        'total_value': total_value,
                        'trade_date': trade_date,
                        'filing_date': filing_date,
                        'raw_data': row.to_dict()
                    })

                except (ValueError, KeyError) as e:
                    logger.debug(f"Error parsing trade: {e}")
                    continue

            logger.info(f"✅ Fetched {len(trades)} insider trades for {ticker}")
            return trades

        except Exception as e:
            logger.error(f"❌ Error fetching insider trades for {ticker}: {e}")
            return None

    def fetch_all_insider_trades(self, limit: int = 1000) -> Optional[List[Dict]]:
        """
        Fetch all recent insider trading across all stocks

        Args:
            limit: Maximum number of trades to fetch

        Returns:
            List of insider trade dictionaries or None
        """
        if not self.quiver:
            logger.warning("Quiver Quant not connected")
            return None

        try:
            logger.info("Fetching all recent insider trades")

            # Get all insider trades
            df = self.quiver.insiders()

            if df is None or df.empty:
                logger.warning("No insider data found")
                return None

            # Limit results
            df = df.head(limit)

            # Convert to list of dictionaries
            trades = []
            for _, row in df.iterrows():
                ticker = str(row.get('Ticker', ''))
                if not ticker:
                    continue

                shares_str = str(row.get('Shares', '0')).replace(',', '').replace('$', '')
                shares = int(float(shares_str)) if shares_str else 0

                price_str = str(row.get('Price', '0')).replace(',', '').replace('$', '')
                price = float(price_str) if price_str else None

                total_value = shares * price if price and shares else None

                transaction = str(row.get('Transaction', '')).lower()
                if 'buy' in transaction or 'purchase' in transaction:
                    transaction_type = 'BUY'
                elif 'sell' in transaction or 'sale' in transaction:
                    transaction_type = 'SELL'
                elif 'exercise' in transaction:
                    transaction_type = 'OPTION_EXERCISE'
                else:
                    transaction_type = 'OTHER'

                trade_date = self._parse_date(row.get('Date'))
                filing_date = self._parse_date(row.get('FilingDate'))

                trades.append({
                    'ticker': ticker.upper(),
                    'insider_name': row.get('Name', ''),
                    'insider_title': row.get('Title', ''),
                    'transaction_type': transaction_type,
                    'shares': shares,
                    'price': price,
                    'total_value': total_value,
                    'trade_date': trade_date,
                    'filing_date': filing_date,
                    'is_congressional': False,
                    'raw_data': row.to_dict()
                })

            logger.info(f"✅ Fetched {len(trades)} total insider trades")
            return trades

        except Exception as e:
            logger.error(f"❌ Error fetching all insider trades: {e}")
            return None

    def fetch_congressional_trades(self, ticker: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Fetch congressional trading data

        Args:
            ticker: Optional ticker filter (if None, returns all recent trades)

        Returns:
            List of congressional trade dictionaries or None
        """
        if not self.quiver:
            logger.warning("Quiver Quant not connected")
            return None

        try:
            if ticker:
                logger.info(f"Fetching congressional trades for {ticker}")
                df = self.quiver.congress_trading(ticker)
            else:
                logger.info("Fetching all congressional trades")
                df = self.quiver.congress_trading()

            if df is None or df.empty:
                logger.warning("No congressional trading data found")
                return None

            # Convert to list of dictionaries
            trades = []
            for _, row in df.iterrows():
                amount_str = str(row.get('Amount', '0')).replace(',', '').replace('$', '')
                amount = float(amount_str) if amount_str else None

                transaction = str(row.get('Transaction', '')).lower()
                if 'buy' in transaction or 'purchase' in transaction:
                    transaction_type = 'BUY'
                elif 'sell' in transaction or 'sale' in transaction:
                    transaction_type = 'SELL'
                else:
                    transaction_type = 'OTHER'

                trade_date = self._parse_date(row.get('TransactionDate'))
                filing_date = self._parse_date(row.get('DisclosureDate'))

                trades.append({
                    'ticker': row.get('Ticker', '').upper(),
                    'insider_name': row.get('Representative', ''),
                    'insider_title': 'Congress Member',
                    'transaction_type': transaction_type,
                    'shares': 0,  # Congressional trades don't always have shares
                    'price': amount,
                    'total_value': amount,
                    'trade_date': trade_date,
                    'filing_date': filing_date,
                    'is_congressional': True,
                    'raw_data': row.to_dict()
                })

            logger.info(f"✅ Fetched {len(trades)} congressional trades")
            return trades

        except Exception as e:
            logger.error(f"❌ Error fetching congressional trades: {e}")
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse date string to datetime object

        Args:
            date_str: Date string in various formats

        Returns:
            Datetime object or None
        """
        if not date_str or pd.isna(date_str):
            return None

        # If already a datetime object, return it
        if isinstance(date_str, datetime):
            return date_str

        # If it's a pandas Timestamp, convert it
        if hasattr(date_str, 'to_pydatetime'):
            return date_str.to_pydatetime()

        # Try common date formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(str(date_str), fmt)
            except (ValueError, TypeError):
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None


def main():
    """Test the QuiverQuant fetcher"""
    logging.basicConfig(level=logging.INFO)

    # Test with a few tickers
    fetcher = QuiverQuantFetcher()

    if fetcher.quiver:
        # Test AAPL
        print("\n" + "=" * 80)
        print("Testing AAPL Insider Trades")
        print("=" * 80)
        aapl_trades = fetcher.fetch_live_insider_trades('AAPL')
        if aapl_trades:
            for trade in aapl_trades[:5]:
                print(trade)

        # Test congressional trades
        print("\n" + "=" * 80)
        print("Testing Congressional Trades")
        print("=" * 80)
        congress_trades = fetcher.fetch_congressional_trades()
        if congress_trades:
            for trade in congress_trades[:5]:
                print(trade)


if __name__ == "__main__":
    main()
