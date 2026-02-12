#!/usr/bin/env python3
"""
FETCH HISTORICAL STOCK DATA 2018-2020 FROM YAHOO FINANCE

Purpose: Fetch historical OHLCV data for 2018-2020 period to extend
         the dataset and include diverse market regimes (trade war, COVID).

Target Period: 2018-01-01 to 2020-12-31
Stocks to fetch: All stocks currently in database
Data Source: Yahoo Finance (free, no API key needed)

Usage:
    python scripts/fetch_historical_2018_2020_yahoo.py

Created: 2026-02-05
Author: ML Team
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text
import pandas as pd
import yfinance as yf

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass@db:5432/stockanalyzer')
engine = create_engine(DATABASE_URL)


def get_stock_list():
    """Get list of stocks from database"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, symbol
            FROM stocks
            ORDER BY symbol
        """))
        stocks = result.fetchall()

    print(f"Found {len(stocks)} stocks in database")
    return stocks


def fetch_yahoo_data(stock_id, symbol, start_date, end_date):
    """
    Fetch historical data from Yahoo Finance

    Returns: DataFrame with OHLCV data
    """
    try:
        # Fetch data from Yahoo Finance
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start_date, end=end_date, interval="1d")

        if hist is None or len(hist) == 0:
            print(f"    ⚠ No data found for {symbol}")
            return None

        # Reset index to make Date a column
        hist = hist.reset_index()

        # Rename columns to match our format
        # Yahoo uses 'Date', 'Open', 'High', 'Low', 'Close', 'Volume'
        hist = hist.rename(columns={
            'Date': 'timestamp',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })

        # Select required columns
        hist = hist[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()

        # Convert timestamp
        hist['timestamp'] = pd.to_datetime(hist['timestamp']).dt.tz_localize(None)

        # Add stock_id (convert to Python int to avoid numpy.int64 issues with psycopg2)
        hist['stock_id'] = int(stock_id)

        # Add timeframe (required by database schema)
        hist['timeframe'] = '1d'

        # Remove zero-volume days
        hist = hist[hist['volume'] > 0]

        print(f"    ✓ Fetched {len(hist)} records for {symbol}")
        return hist

    except Exception as e:
        print(f"    ❌ Error fetching {symbol}: {e}")
        return None


def save_to_database(df, table_name='stock_prices'):
    """
    Save DataFrame to database

    Args:
        df: DataFrame with stock price data
        table_name: Target table name
    """
    if df is None or len(df) == 0:
        return

    try:
        # Convert numpy types to Python native types for psycopg2
        stock_id = int(df['stock_id'].iloc[0])
        start_ts = df['timestamp'].min().to_pydatetime()
        end_ts = df['timestamp'].max().to_pydatetime()

        # Check for existing records to avoid duplicates
        with engine.connect() as conn:
            existing = conn.execute(text(f'''
                SELECT COUNT(*) FROM {table_name}
                WHERE stock_id = :stock_id
                AND timestamp >= :start
                AND timestamp <= :end
            '''), {
                'stock_id': stock_id,
                'start': start_ts,
                'end': end_ts
            })
            existing_count = existing.fetchone()[0]

            if existing_count > 0:
                # Filter out existing records
                existing_dates = conn.execute(text(f'''
                    SELECT timestamp FROM {table_name}
                    WHERE stock_id = :stock_id
                    AND timestamp >= :start
                    AND timestamp <= :end
                '''), {
                    'stock_id': stock_id,
                    'start': start_ts,
                    'end': end_ts
                })
                existing_dates_set = {row[0] for row in existing_dates}
                df = df[~df['timestamp'].isin(existing_dates_set)]

                if len(df) == 0:
                    print(f"    ℹ All records already exist, skipping")
                    return True

                print(f"    ⚠ Skipping {existing_count} existing records")

        # Save to database
        df.to_sql(
            table_name,
            engine,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=1000
        )
        print(f"    ✓ Saved {len(df)} new records to database")
        return True

    except Exception as e:
        print(f"    ❌ Error saving to database: {e}")
        return False


def fetch_all_stocks(start_date='2018-01-01', end_date='2020-12-31'):
    """
    Fetch historical data for all stocks in database

    Args:
        start_date: Start date (default: 2018-01-01)
        end_date: End date (default: 2020-12-31)
    """

    print("=" * 70)
    print("FETCHING HISTORICAL STOCK DATA (2018-2020) FROM YAHOO FINANCE")
    print("=" * 70)

    # Get stock list
    stocks = get_stock_list()

    if not stocks:
        print("❌ No stocks found in database")
        return

    print(f"\n📊 Target period: {start_date} to {end_date}")
    print(f"📈 Stocks to fetch: {len(stocks)}")
    print(f"🔄 Using Yahoo Finance (free, no API key needed)")

    # Fetch data for each stock
    success_count = 0
    failed_stocks = []

    print(f"\n🔄 Fetching data...")
    print("-" * 70)

    for i, (stock_id, symbol) in enumerate(stocks, 1):
        print(f"[{i}/{len(stocks)}] Fetching {symbol} (ID: {stock_id})...")

        # Handle special symbols for Yahoo Finance
        # Yahoo uses '-' instead of '.' for some stocks
        yahoo_symbol = symbol.replace('.', '-')

        df = fetch_yahoo_data(stock_id, yahoo_symbol, start_date, end_date)

        if df is not None and len(df) > 0:
            if save_to_database(df):
                success_count += 1
        else:
            print(f"    ❌ Failed to fetch {symbol}")
            failed_stocks.append(symbol)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"✅ Successfully fetched: {success_count}/{len(stocks)} stocks")
    print(f"❌ Failed: {len(failed_stocks)} stocks")

    if failed_stocks:
        print(f"\nFailed stocks:")
        for symbol in failed_stocks[:10]:
            print(f"  - {symbol}")
        if len(failed_stocks) > 10:
            print(f"  ... and {len(failed_stocks) - 10} more")


def verify_data():
    """Verify fetched data"""
    print("\n" + "=" * 70)
    print("VERIFYING DATA")
    print("=" * 70)

    with engine.connect() as conn:
        # Check date range
        result = conn.execute(text('''
            SELECT
                MIN(timestamp) as earliest,
                MAX(timestamp) as latest,
                COUNT(*) as records
            FROM stock_prices
            WHERE timestamp >= '2018-01-01' AND timestamp <= '2020-12-31'
        '''))
        row = result.fetchone()

        if row and row[0]:
            print(f"\n✅ Data found for 2018-2020:")
            print(f"   Date range: {row[0]} to {row[1]}")
            print(f"   Total records: {row[2]:,}")

            # Check by year
            result = conn.execute(text('''
                SELECT
                    EXTRACT(YEAR FROM timestamp) as year,
                    COUNT(*) as records
                FROM stock_prices
                WHERE timestamp >= '2018-01-01' AND timestamp <= '2020-12-31'
                GROUP BY EXTRACT(YEAR FROM timestamp)
                ORDER BY year
            '''))
            print(f"\n   Records by year:")
            for row in result:
                print(f"     {int(row[0])}: {row[1]:,} records")

            # Count unique stocks
            result = conn.execute(text('''
                SELECT COUNT(DISTINCT stock_id)
                FROM stock_prices
                WHERE timestamp >= '2018-01-01' AND timestamp <= '2020-12-31'
            '''))
            stock_count = result.fetchone()[0]
            print(f"\n   Stocks with 2018-2020 data: {stock_count}")
        else:
            print("\n❌ No data found for 2018-2020")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Fetch historical stock data 2018-2020 from Yahoo Finance',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/fetch_historical_2018_2020_yahoo.py
  python scripts/fetch_historical_2018_2020_yahoo.py --start-date 2018-01-01 --end-date 2020-12-31

This script:
  1. Gets all stocks from database
  2. Fetches 2018-2020 data from Yahoo Finance (free)
  3. Saves to stock_prices table
  4. Verifies the data

Note: No API key required (Yahoo Finance is free)
Rate limiting: None (but be respectful)
        """
    )

    parser.add_argument(
        '--start-date',
        type=str,
        default='2018-01-01',
        help='Start date (default: 2018-01-01)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        default='2020-12-31',
        help='End date (default: 2020-12-31)'
    )

    args = parser.parse_args()

    print(f"⏰ Start time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"📅 Target period: {args.start_date} to {args.end_date}")

    # Fetch data
    fetch_all_stocks(args.start_date, args.end_date)

    # Verify
    verify_data()

    print(f"\n✅ Completed at {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
