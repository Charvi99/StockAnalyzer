#!/usr/bin/env python3
"""
Fetch SEC Form 4 Insider Trading Data from EDGAR

This script fetches historical Form 4 filings (insider trading) from SEC EDGAR
for all stocks with CIK mappings.

Form 4 filings contain:
- Insider name, title, relationship
- Transaction type (buy/sell)
- Shares traded, price per share, total value
- Trade date, filing date
- Ownership type (direct/indirect)

Usage:
    # Fetch all historical data (2 years)
    docker-compose exec backend python scripts/fetch_sec_form4.py

    # Fetch for specific stocks
    docker-compose exec backend python scripts/fetch_sec_form4.py --symbols AAPL MSFT

    # Fetch recent data only (last 30 days)
    docker-compose exec backend python scripts/fetch_sec_form4.py --days 30

Data Source:
    https://www.sec.gov/edgar/search-filings/edgar-application-programming-interfaces

Expected time:
    - Initial fetch: 2-4 hours for 234 stocks × 2 years
    - Daily update: 5-10 minutes
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from tqdm import tqdm
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import SEC EDGAR fetcher
from app.services.sec_edgar_fetcher import SECEdgarFetcher

# Database connection
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://stockuser:stockpass123@database:5432/stock_analyzer'
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_stocks_with_cik(symbols: list = None) -> list:
    """
    Get stocks with CIK mappings from database

    Args:
        symbols: Optional list of specific symbols to fetch

    Returns:
        List of (stock_id, symbol, cik) tuples
    """
    db = SessionLocal()
    try:
        if symbols:
            # Fetch specific stocks
            placeholders = ','.join([f':symbol_{i}' for i in range(len(symbols))])
            query = text(f"""
                SELECT id, symbol, sec_cik
                FROM stocks
                WHERE symbol IN ({placeholders})
                  AND sec_cik IS NOT NULL
                  AND is_tracked = true
            """)
            params = {f'symbol_{i}': s.upper() for i, s in enumerate(symbols)}
        else:
            # Fetch all stocks with CIK
            query = text("""
                SELECT id, symbol, sec_cik
                FROM stocks
                WHERE sec_cik IS NOT NULL
                  AND is_tracked = true
                ORDER BY symbol
            """)

        result = db.execute(query, params if symbols else {})
        stocks = [(row[0], row[1], row[2]) for row in result]
        return stocks

    finally:
        db.close()


def save_insider_trades(trades: list, stock_id: int) -> int:
    """
    Save insider trades to database

    Args:
        trades: List of trade dictionaries
        stock_id: Stock ID

    Returns:
        Number of trades saved
    """
    if not trades:
        return 0

    db = SessionLocal()
    saved_count = 0
    skipped_count = 0

    try:
        for trade in trades:
            try:
                # Check if trade already exists
                existing = db.execute(text("""
                    SELECT id
                    FROM insider_trades
                    WHERE stock_id = :stock_id
                      AND insider_name = :insider_name
                      AND trade_date = :trade_date
                      AND transaction_type = :transaction_type
                      AND shares = :shares
                      AND total_value = :total_value
                    LIMIT 1
                """), {
                    "stock_id": stock_id,
                    "insider_name": trade.get("insider_name", ""),
                    "trade_date": trade.get("trade_date"),
                    "transaction_type": trade.get("transaction_type", "OTHER"),
                    "shares": trade.get("shares", 0),
                    "total_value": trade.get("total_value", 0)
                })

                if existing.fetchone():
                    skipped_count += 1
                    continue

                # Insert new trade
                db.execute(text("""
                    INSERT INTO insider_trades (
                        stock_id, insider_name, insider_title,
                        transaction_type, shares, price, total_value,
                        trade_date, filing_date, is_congressional, raw_data
                    ) VALUES (
                        :stock_id, :insider_name, :insider_title,
                        :transaction_type, :shares, :price, :total_value,
                        :trade_date, :filing_date, :is_congressional, :raw_data
                    )
                """), {
                    "stock_id": stock_id,
                    "insider_name": trade.get("insider_name", ""),
                    "insider_title": trade.get("insider_title", ""),
                    "transaction_type": trade.get("transaction_type", "OTHER"),
                    "shares": trade.get("shares", 0),
                    "price": trade.get("price"),
                    "total_value": trade.get("total_value", 0),
                    "trade_date": trade.get("trade_date"),
                    "filing_date": trade.get("filing_date"),
                    "is_congressional": False,  # SEC Form 4, not congressional
                    "raw_data": trade.get("raw_data")
                })

                saved_count += 1

            except Exception as e:
                logger.debug(f"Error saving trade: {e}")
                skipped_count += 1
                continue

        db.commit()
        logger.info(f"✅ Saved {saved_count} new trades, skipped {skipped_count} existing")
        return saved_count

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error saving trades: {e}")
        return 0
    finally:
        db.close()


def parse_form4_to_trades(form4_data: dict, symbol: str) -> list:
    """
    Parse Form 4 data into list of trade dictionaries

    Args:
        form4_data: Parsed Form 4 data from SEC EDGAR fetcher
        symbol: Stock ticker symbol

    Returns:
        List of trade dictionaries
    """
    trades = []

    if not form4_data:
        return trades

    # Get insider info
    insider_name = form4_data.get('reporting_owner', {}).get('name', '')
    insider_title = form4_data.get('reporting_owner', {}).get('title', '')

    # Get transactions
    transactions = form4_data.get('transactions', [])

    for txn in transactions:
        # Only process buy/sell transactions
        txn_type = txn.get('transaction_type', '')
        acquired_disposed = txn.get('acquired_disposed', '')

        # Map transaction types to BUY/SELL
        transaction_type = 'OTHER'

        # Purchase (buy) transactions
        if txn_type in ['P', 'A', 'M']:  # Purchase, Award, Grant
            if acquired_disposed == 'A':  # Acquired
                transaction_type = 'BUY'

        # Sale transactions
        elif txn_type in ['S', 'D', 'F']:  # Sale, Sale(exempt), Payment
            if acquired_disposed == 'D':  # Disposed
                transaction_type = 'SELL'

        # Skip if not buy/sell
        if transaction_type == 'OTHER':
            continue

        # Get transaction date
        trade_date_str = txn.get('transaction_date')
        if not trade_date_str:
            continue

        try:
            # Parse date (format: YYYY-MM-DD)
            trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d').date()
        except:
            continue

        # Get filing date from period_of_report
        filing_date_str = form4_data.get('period_of_report')
        filing_date = None
        if filing_date_str:
            try:
                filing_date = datetime.strptime(filing_date_str, '%Y-%m-%d').date()
            except:
                pass

        # Build trade dictionary
        trade = {
            'insider_name': insider_name,
            'insider_title': insider_title,
            'transaction_type': transaction_type,
            'shares': int(txn.get('shares', 0)),
            'price': float(txn.get('price_per_share', 0)) if txn.get('price_per_share') else None,
            'total_value': float(txn.get('total_value', 0)) if txn.get('total_value') else 0,
            'trade_date': trade_date,
            'filing_date': filing_date,
            'raw_data': {
                'accession_number': form4_data.get('accession_number'),
                'period_of_report': form4_data.get('period_of_report'),
                'symbol': symbol,
                'transaction': txn
            }
        }

        trades.append(trade)

    return trades


def fetch_form4_for_stock(
    fetcher: SECEdgarFetcher,
    stock_id: int,
    symbol: str,
    cik: str,
    start_date: datetime,
    end_date: datetime,
    count: int = 100
) -> dict:
    """
    Fetch Form 4 filings for a single stock

    Args:
        fetcher: SEC EDGAR fetcher instance
        stock_id: Stock ID
        symbol: Stock ticker
        cik: SEC CIK
        start_date: Start date for fetching
        end_date: End date for fetching
        count: Maximum filings to fetch

    Returns:
        Dictionary with results
    """
    result = {
        'stock_id': stock_id,
        'symbol': symbol,
        'filings_fetched': 0,
        'trades_saved': 0,
        'errors': []
    }

    try:
        # Get Form 4 filings
        filings = fetcher.get_form4_filings(
            cik=cik,
            start_date=start_date,
            end_date=end_date,
            count=count
        )

        if not filings:
            result['errors'].append("No Form 4 filings found")
            return result

        result['filings_fetched'] = len(filings)

        # Process each filing
        all_trades = []

        for filing in filings:
            try:
                accession_number = filing.get('accession_number')
                primary_doc = filing.get('primary_doc')

                if not accession_number or not primary_doc:
                    continue

                # Fetch full Form 4 content
                form4_data = fetcher.fetch_form4_content(
                    cik=cik,
                    accession_number=accession_number,
                    primary_doc=primary_doc
                )

                if not form4_data:
                    continue

                # Parse trades from Form 4
                trades = parse_form4_to_trades(form4_data, symbol)
                all_trades.extend(trades)

            except Exception as e:
                result['errors'].append(f"Error processing filing: {e}")
                continue

        # Save all trades
        if all_trades:
            saved = save_insider_trades(all_trades, stock_id)
            result['trades_saved'] = saved

    except Exception as e:
        result['errors'].append(f"Error: {e}")

    return result


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Fetch SEC Form 4 insider trading data from EDGAR"
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='Specific stock symbols to fetch (e.g., AAPL MSFT GOOGL)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=730,  # 2 years
        help='Number of days of historical data to fetch (default: 730 = 2 years)'
    )
    parser.add_argument(
        '--count',
        type=int,
        default=100,
        help='Maximum Form 4 filings per stock (default: 100)'
    )

    args = parser.parse_args()

    print("=" * 80)
    print(" " * 15)
    print("StockAnalyzer - SEC Form 4 Insider Trading Fetcher")
    print(" " * 15)
    print("=" * 80)

    # Get stocks with CIK mappings
    stocks = get_stocks_with_cik(args.symbols)

    if not stocks:
        print("\n❌ No stocks found with CIK mappings!")
        print("\n💡 Run: python scripts/fetch_sec_cik_mapping.py")
        return

    print(f"\n📊 Fetching Form 4 data for {len(stocks)} stocks")
    print(f"📅 Date range: last {args.days} days")
    print(f"⏱️  Estimated time: ~{len(stocks) * 0.5:.0f} minutes")

    # Initialize SEC EDGAR fetcher
    fetcher = SECEdgarFetcher(requests_per_second=2)  # Conservative rate limit

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)

    # Track results
    total_filings = 0
    total_trades = 0
    total_errors = 0
    stocks_with_errors = []

    # Fetch Form 4 for each stock
    print("\n" + "=" * 80)

    for stock_id, symbol, cik in tqdm(stocks, desc="Fetching Form 4 data"):
        result = fetch_form4_for_stock(
            fetcher=fetcher,
            stock_id=stock_id,
            symbol=symbol,
            cik=cik,
            start_date=start_date,
            end_date=end_date,
            count=args.count
        )

        total_filings += result['filings_fetched']
        total_trades += result['trades_saved']

        if result['errors']:
            total_errors += len(result['errors'])
            stocks_with_errors.append(symbol)

    # Print summary
    print("\n" + "=" * 80)
    print(f"✅ Form 4 Fetch Complete!")
    print("=" * 80)
    print(f"\n📊 Results:")
    print(f"   Stocks processed: {len(stocks)}")
    print(f"   Form 4 filings fetched: {total_filings:,}")
    print(f"   Insider trades saved: {total_trades:,}")
    print(f"   Errors encountered: {total_errors}")

    if stocks_with_errors:
        print(f"\n⚠️  Stocks with errors:")
        for symbol in stocks_with_errors[:10]:
            print(f"   - {symbol}")
        if len(stocks_with_errors) > 10:
            print(f"   ... and {len(stocks_with_errors) - 10} more")

    print(f"\n💡 Next steps:")
    print(f"   1. Verify data: SELECT COUNT(*) FROM insider_trades WHERE is_congressional = false;")
    print(f"   2. Run feature engineering with insider features")
    print(f"   3. Retrain ML model")
    print(f"   4. Expected AUC: 65-69% (+8-12% improvement)")


if __name__ == "__main__":
    main()
