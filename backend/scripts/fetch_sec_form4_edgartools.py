#!/usr/bin/env python3
"""
Fetch SEC Form 4 Insider Trading Data using edgartools library

This script fetches historical Form 4 filings (insider trading) from SEC EDGAR
using the edgartools Python library, which handles all the complex parsing.

Usage:
    # Fetch all historical data (2 years)
    docker-compose exec backend python scripts/fetch_sec_form4_edgartools.py

    # Fetch for specific stocks
    docker-compose exec backend python scripts/fetch_sec_form4_edgartools.py --symbols AAPL MSFT

    # Fetch recent data only (last 30 days)
    docker-compose exec backend python scripts/fetch_sec_form4_edgartools.py --days 30

Expected time:
    - Initial fetch: 2-3 hours for 234 stocks × 2 years
    - Daily update: 5-10 minutes
"""

import sys
import os
import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from tqdm import tqdm
import pandas as pd
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

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
    """Get stocks with CIK mappings from database"""
    db = SessionLocal()
    try:
        if symbols:
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


def save_insider_trades(trades: list, stock_id: int) -> dict:
    """Save insider trades to database"""
    if not trades:
        return {'saved': 0, 'skipped': 0}

    db = SessionLocal()
    saved_count = 0
    skipped_count = 0

    try:
        for i, trade in enumerate(trades):
            try:
                # Check if trade already exists
                params = {
                    "stock_id": stock_id,
                    "insider_name": trade.get("insider_name", ""),
                    "trade_date": trade.get("trade_date"),
                    "transaction_type": trade.get("transaction_type", "OTHER"),
                    "shares": trade.get("shares", 0),
                    "total_value": trade.get("total_value", 0)
                }

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
                """), params)

                result = existing.fetchone()
                if result:
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
                    "is_congressional": False,
                    "raw_data": json.dumps(trade)
                })

                saved_count += 1

            except Exception as e:
                logger.warning(f"Error saving trade: {e}")
                skipped_count += 1
                continue

        db.commit()
        logger.info(f"✅ Saved {saved_count} new trades, skipped {skipped_count} existing")
        return {'saved': saved_count, 'skipped': skipped_count}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error saving trades: {e}")
        return {'saved': 0, 'skipped': 0}
    finally:
        db.close()


def parse_form4_transactions(xml_content: str, filing_date: str) -> list:
    """
    Parse Form 4 XML content to extract transaction data.

    Args:
        xml_content: XML content from Form 4 filing
        filing_date: Date the filing was submitted

    Returns:
        List of transaction dictionaries
    """
    transactions = []

    # Extract reporting owner info
    insider_name = ''
    name_match = re.search(r'<rptOwnerName>([^<]+)</rptOwnerName>', xml_content)
    if not name_match:
        name_match = re.search(r'<reportingOwner><reportingOwnerId><rptOwnerName>([^<]+)</rptOwnerName>', xml_content, re.DOTALL)
    if name_match:
        insider_name = name_match.group(1).strip()

    insider_title = ''
    title_match = re.search(r'<rptOwnerTitle>([^<]+)</rptOwnerTitle>', xml_content)
    if not title_match:
        title_match = re.search(r'<reportingOwner><reportingOwnerRelationship><rptOwnerTitle>([^<]+)</rptOwnerTitle>', xml_content, re.DOTALL)
    if title_match:
        insider_title = title_match.group(1).strip()

    # Split into individual non-derivative transactions
    txn_pattern = r'<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>'
    txn_matches = re.findall(txn_pattern, xml_content, re.DOTALL)

    for txn_block in txn_matches:
        txn = {}

        # Extract transaction date
        date_match = re.search(r'<transactionDate>\s*<value>(\d{4}-\d{2}-\d{2})</value>', txn_block)
        if date_match:
            txn['trade_date'] = date_match.group(1)

        # Extract transaction code
        code_match = re.search(r'<transactionCode>\s*<value>([^<]+)</value>', txn_block)
        if not code_match:
            code_match = re.search(r'<transactionCode>([^<]+)</transactionCode>', txn_block)
        if code_match:
            txn['transaction_code'] = code_match.group(1).strip()

        # Extract shares
        shares_match = re.search(r'<transactionShares>\s*<value>([^<]+)</value>', txn_block)
        if shares_match:
            try:
                txn['shares'] = int(float(shares_match.group(1).strip()))
            except:
                pass

        # Extract price per share (might be empty or have footnotes)
        price_match = re.search(r'<transactionPricePerShare>\s*<value>([^<]+)</value>', txn_block)
        if price_match:
            try:
                txn['price'] = float(price_match.group(1).strip())
            except:
                pass

        # Extract acquired/disposed code
        acq_disp_match = re.search(r'<transactionAcquiredDisposedCode>\s*<value>([^<]+)</value>', txn_block)
        if acq_disp_match:
            txn['acquired_disposed'] = acq_disp_match.group(1).strip()

        # Calculate total value
        if 'shares' in txn and 'price' in txn:
            txn['total_value'] = txn['shares'] * txn['price']
        else:
            txn['total_value'] = 0

        # Add insider info
        txn['insider_name'] = insider_name
        txn['insider_title'] = insider_title
        txn['filing_date'] = filing_date

        # Determine transaction type (BUY/SELL/OTHER)
        if 'transaction_code' in txn and 'acquired_disposed' in txn:
            code = txn['transaction_code']
            acq_disp = txn['acquired_disposed']

            # P=Purch, A=Acquired, M=Grant/Award (usually options exercises)
            # S=Sale, D=Disposed, F=Payment/Tax withholding
            if code in ['P', 'A', 'M'] and acq_disp == 'A':
                txn['transaction_type'] = 'BUY'
            elif code in ['S', 'D'] and acq_disp == 'D':
                txn['transaction_type'] = 'SELL'
            else:
                txn['transaction_type'] = 'OTHER'

        transactions.append(txn)

    return transactions


def fetch_form4_for_stock(
    stock_id: int,
    symbol: str,
    cik: str,
    start_date: datetime,
    end_date: datetime,
    max_filings: int = None
) -> dict:
    """
    Fetch Form 4 filings for a single stock using edgartools

    Args:
        stock_id: Stock ID
        symbol: Stock ticker
        cik: SEC CIK (with leading zeros)
        start_date: Start date for fetching
        end_date: End date for fetching
        max_filings: Maximum number of filings to process (None = all)

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
        # Import edgar (not edgartools!)
        from edgar import Company, set_identity

        # Set User-Agent (required by SEC)
        set_identity("StockAnalyzer stock-analyzer@example.com")

        # Clean CIK - remove leading zeros
        cik_clean = cik.lstrip('0') if cik else ''

        if not cik_clean:
            result['errors'].append("Empty CIK")
            return result

        # Create company object
        company = Company(cik_clean)

        # Get Form 4 filings
        logger.debug(f"Fetching Form 4 for {symbol} (CIK: {cik_clean})")

        try:
            # Get Form 4 filings
            filings = company.get_filings(form='4')

            if not filings or len(filings) == 0:
                result['errors'].append("No Form 4 filings found")
                return result

            # Convert to pandas to filter by date
            df = filings.to_pandas()

            # Filter by date range if specified
            if start_date:
                df['filing_date'] = pd.to_datetime(df['filing_date'])
                df = df[df['filing_date'] >= pd.Timestamp(start_date)]

            if end_date:
                df['filing_date'] = pd.to_datetime(df['filing_date'])
                df = df[df['filing_date'] <= pd.Timestamp(end_date)]

            if len(df) == 0:
                result['errors'].append("No Form 4 filings in date range")
                return result

            result['filings_fetched'] = len(df)

            # Limit filings if specified
            if max_filings and len(df) > max_filings:
                df = df.head(max_filings)

            # Extract and save transactions from each filing
            all_trades = []

            for idx, row in df.iterrows():
                try:
                    accession_no = row['accession_number']
                    filing_date = str(row['filing_date'])[:10]  # YYYY-MM-DD

                    # Get the filing object
                    filing = filings[idx]

                    # Get XML content
                    xml_content = filing.xml()

                    # Parse transactions
                    trades = parse_form4_transactions(str(xml_content), filing_date)

                    # Add filing metadata to each trade
                    for trade in trades:
                        trade['accession_number'] = accession_no

                    all_trades.extend(trades)

                except Exception as e:
                    result['errors'].append(f"Error processing filing {row.get('accession_number', 'unknown')}: {e}")
                    continue

            # Save all trades
            if all_trades:
                # Filter to only BUY and SELL transactions
                buy_sell_trades = [t for t in all_trades if t.get('transaction_type') in ['BUY', 'SELL']]

                save_result = save_insider_trades(buy_sell_trades, stock_id)
                result['trades_saved'] = save_result['saved']

        except Exception as e:
            result['errors'].append(f"Error fetching filings: {e}")

    except ImportError as e:
        result['errors'].append(f"edgar library not installed: {e}")

    except Exception as e:
        result['errors'].append(f"Unexpected error: {e}")

    return result


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Fetch SEC Form 4 insider trading data using edgartools"
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
        '--max-filings',
        type=int,
        default=None,
        help='Maximum filings per stock to process (default: all)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: only process first 3 stocks with 10 filings each'
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

    # Test mode: limit stocks
    if args.test:
        stocks = stocks[:3]
        max_filings = 10
        print(f"\n🧪 TEST MODE: Processing {len(stocks)} stocks with max {max_filings} filings each")
    else:
        max_filings = args.max_filings

    print(f"\n📊 Fetching Form 4 data for {len(stocks)} stocks")
    print(f"📅 Date range: last {args.days} days")
    if max_filings:
        print(f"📄 Max filings per stock: {max_filings}")

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)

    # Track results
    total_filings = 0
    total_trades = 0
    total_errors = 0
    stocks_with_errors = []
    stocks_with_no_data = []

    print("\n" + "=" * 80)

    # Fetch Form 4 for each stock
    for stock_id, symbol, cik in tqdm(stocks, desc="Fetching Form 4 data"):
        result = fetch_form4_for_stock(
            stock_id=stock_id,
            symbol=symbol,
            cik=cik,
            start_date=start_date,
            end_date=end_date,
            max_filings=max_filings
        )

        total_filings += result['filings_fetched']
        total_trades += result['trades_saved']

        if result['errors']:
            total_errors += len(result['errors'])
            stocks_with_errors.append((symbol, result['errors'][:2]))  # Store first 2 errors

        if result['filings_fetched'] == 0:
            stocks_with_no_data.append(symbol)

    # Print summary
    print("\n" + "=" * 80)
    print(f"✅ Form 4 Fetch Complete!")
    print("=" * 80)
    print(f"\n📊 Results:")
    print(f"   Stocks processed: {len(stocks)}")
    print(f"   Form 4 filings fetched: {total_filings:,}")
    print(f"   Insider trades saved: {total_trades:,}")
    print(f"   Errors encountered: {total_errors}")

    if stocks_with_no_data:
        print(f"\n⚠️  Stocks with no Form 4 data ({len(stocks_with_no_data)}):")
        for symbol in stocks_with_no_data[:10]:
            print(f"   - {symbol}")
        if len(stocks_with_no_data) > 10:
            print(f"   ... and {len(stocks_with_no_data) - 10} more")

    if stocks_with_errors:
        print(f"\n⚠️  Stocks with errors ({len(stocks_with_errors)}):")
        for symbol, errors in stocks_with_errors[:10]:
            print(f"   - {symbol}: {errors[0][:60]}...")
        if len(stocks_with_errors) > 10:
            print(f"   ... and {len(stocks_with_errors) - 10} more")

    print(f"\n💡 Next steps:")
    print(f"   1. Verify data: SELECT COUNT(*) FROM insider_trades WHERE is_congressional = false;")
    print(f"   2. Check samples: SELECT * FROM insider_trades WHERE is_congressional = false ORDER BY trade_date DESC LIMIT 10;")
    print(f"   3. Run feature engineering with insider features")
    print(f"   4. Retrain ML model")
    print(f"   5. Expected AUC: 65-69% (+8-12% improvement)")


if __name__ == "__main__":
    main()
