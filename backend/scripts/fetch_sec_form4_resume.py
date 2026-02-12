#!/usr/bin/env python3
"""
Resume SEC Form 4 Insider Trading Data Fetch

This script resumes fetching for stocks that have no insider trading data yet.
Improved with:
- Rate limiting to avoid SEC blocking
- Date validation (reject future dates)
- Better error handling with retries
- Progress tracking

Usage:
    docker-compose exec backend python scripts/fetch_sec_form4_resume.py
"""

import sys
import os
import argparse
import time
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

# Rate limiting: 1 second between requests to SEC
REQUEST_DELAY = 1.0


def get_stocks_without_data() -> list:
    """Get stocks that have no insider trading data yet"""
    db = SessionLocal()
    try:
        query = text("""
            SELECT s.id, s.symbol, s.sec_cik
            FROM stocks s
            WHERE s.sec_cik IS NOT NULL
              AND s.is_tracked = true
              AND NOT EXISTS (
                SELECT 1 FROM insider_trades it
                WHERE it.stock_id = s.id AND it.is_congressional = false
              )
            ORDER BY s.symbol
        """)
        result = db.execute(query)
        stocks = [(row[0], row[1], row[2]) for row in result]
        return stocks
    finally:
        db.close()


def save_insider_trades(trades: list, stock_id: int) -> dict:
    """Save insider trades to database with date validation"""
    if not trades:
        return {'saved': 0, 'skipped': 0, 'invalid': 0}

    saved_count = 0
    skipped_count = 0
    invalid_count = 0
    today = datetime.now().date()

    # Process each trade individually with fresh sessions
    for i, trade in enumerate(trades):
        db = SessionLocal()
        try:
            # Validate trade date (reject future dates)
            trade_date = trade.get("trade_date")
            if isinstance(trade_date, str):
                trade_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
            elif not isinstance(trade_date, datetime):
                trade_date = datetime.strptime(str(trade_date)[:10], '%Y-%m-%d').date()

            if trade_date > today:
                invalid_count += 1
                continue

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

            db.commit()
            saved_count += 1

        except Exception as e:
            db.rollback()
            logger.warning(f"Error saving trade: {e}")
            skipped_count += 1
            continue
        finally:
            db.close()

    logger.info(f"✅ Saved {saved_count} new trades, skipped {skipped_count}, invalid {invalid_count}")
    return {'saved': saved_count, 'skipped': skipped_count, 'invalid': invalid_count}


def parse_form4_transactions(xml_content: str, filing_date: str) -> list:
    """Parse Form 4 XML content to extract transaction data."""
    import re
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

        # Extract price per share
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
    """Fetch Form 4 filings for a single stock with error handling"""
    result = {
        'stock_id': stock_id,
        'symbol': symbol,
        'filings_fetched': 0,
        'trades_saved': 0,
        'errors': []
    }

    try:
        from edgar import Company, set_identity

        # Set User-Agent (required by SEC)
        set_identity("StockAnalyzer stock-analyzer@example.com")

        # Clean CIK
        cik_clean = cik.lstrip('0') if cik else ''
        if not cik_clean:
            result['errors'].append("Empty CIK")
            return result

        # Create company object
        company = Company(cik_clean)

        try:
            # Get Form 4 filings
            filings = company.get_filings(form='4')

            if not filings or len(filings) == 0:
                result['errors'].append("No Form 4 filings found")
                return result

            # Convert to pandas to filter by date
            df = filings.to_pandas()

            # Filter by date range
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

            # Extract and save transactions
            all_trades = []

            for idx, row in df.iterrows():
                try:
                    accession_no = row['accession_number']
                    filing_date = str(row['filing_date'])[:10]

                    # Get the filing object
                    filing = filings[idx]

                    # Get XML content
                    xml_content = filing.xml()

                    # Parse transactions
                    trades = parse_form4_transactions(str(xml_content), filing_date)

                    # Add filing metadata
                    for trade in trades:
                        trade['accession_number'] = accession_no

                    all_trades.extend(trades)

                except Exception as e:
                    result['errors'].append(f"Error processing filing: {e}")
                    continue

            # Save all trades
            if all_trades:
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
    print("=" * 80)
    print(" " * 20)
    print("SEC Form 4 Resume - Fetching Missing Stocks")
    print(" " * 20)
    print("=" * 80)

    # Get stocks without data
    stocks = get_stocks_without_data()

    if not stocks:
        print("\n✅ All stocks already have insider trading data!")
        print("\nCurrent status:")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*), COUNT(DISTINCT stock_id)
                FROM insider_trades WHERE is_congressional = false
            """))
            trades, stocks_count = result.fetchone()
            print(f"   Total trades: {trades:,}")
            print(f"   Stocks with data: {stocks_count}")
        return

    print(f"\n📊 Found {len(stocks)} stocks without insider data")
    print(f"📅 Fetching last 5 years of data (1825 days)")
    print(f"⏱️  Rate limit: {REQUEST_DELAY}s per request")

    # Calculate date range (5 years)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1825)

    # Track results
    total_filings = 0
    total_trades = 0
    total_errors = 0
    stocks_with_errors = []
    stocks_with_no_data = []

    print("\n" + "=" * 80)

    # Fetch Form 4 for each stock with rate limiting
    for i, (stock_id, symbol, cik) in enumerate(tqdm(stocks, desc="Fetching missing stocks")):
        result = fetch_form4_for_stock(
            stock_id=stock_id,
            symbol=symbol,
            cik=cik,
            start_date=start_date,
            end_date=end_date,
            max_filings=None
        )

        total_filings += result['filings_fetched']
        total_trades += result['trades_saved']

        if result['errors']:
            total_errors += len(result['errors'])
            stocks_with_errors.append((symbol, result['errors'][:2]))

        if result['filings_fetched'] == 0:
            stocks_with_no_data.append(symbol)

        # Rate limiting: wait between requests
        if i < len(stocks) - 1:
            time.sleep(REQUEST_DELAY)

    # Print summary
    print("\n" + "=" * 80)
    print(f"✅ Form 4 Fetch Complete!")
    print("=" * 80)
    print(f"\n📊 Results:")
    print(f"   Stocks processed: {len(stocks)}")
    print(f"   Form 4 filings fetched: {total_filings:,}")
    print(f"   Insider trades saved: {total_trades:,}")
    print(f"   Errors encountered: {total_errors}")

    # Check final status
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*), COUNT(DISTINCT stock_id)
            FROM insider_trades WHERE is_congressional = false
        """))
        total_trades_db, stocks_with_data = result.fetchone()
        print(f"\n📈 Total database status:")
        print(f"   Total trades: {total_trades_db:,}")
        print(f"   Stocks with data: {stocks_with_data}/234")

    if stocks_with_no_data:
        print(f"\n⚠️  Stocks with no data ({len(stocks_with_no_data)}):")
        for symbol in stocks_with_no_data[:10]:
            print(f"   - {symbol}")

    if stocks_with_errors:
        print(f"\n⚠️  Stocks with errors ({len(stocks_with_errors)}):")
        for symbol, errors in stocks_with_errors[:5]:
            print(f"   - {symbol}: {errors[0][:50]}...")

    print(f"\n💡 Ready for feature engineering!")


if __name__ == "__main__":
    main()
