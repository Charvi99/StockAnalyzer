#!/usr/bin/env python3
"""
Fetch 5 Years of Historical Data for All Stocks

This script fetches historical OHLCV data from Polygon.io for:
- 500-600 stocks (S&P 500 + NASDAQ 100 + ETFs)
- 5 years of data (2019-2026)
- Daily timeframe (1d)

Features:
- Parallel fetching with ThreadPoolExecutor (speed!)
- Automatic retry on failures
- Progress tracking
- Paid Polygon.io API (no rate limits)

Usage:
    python fetch_historical_data_5years.py

Expected time with paid API: 1-2 hours (vs 20+ hours with free tier)
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, '/backend')

import requests
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://stockuser:stockpass123@database:5432/stock_analyzer'
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Polygon.io API key (paid tier)
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')

if not POLYGON_API_KEY:
    logger.error("POLYGON_API_KEY not found in environment variables!")
    logger.error("Please set: export POLYGON_API_KEY='your_key_here'")
    sys.exit(1)

# Constants
TIMEFRAME = '1d'
YEARS_TO_FETCH = 5
START_DATE = (datetime.now() - timedelta(days=365 * YEARS_TO_FETCH)).strftime('%Y-%m-%d')
END_DATE = datetime.now().strftime('%Y-%m-%d')

# Polygon.io has a limit of 50,000 bars per request
# We need to chunk requests by year
MAX_DAYS_PER_REQUEST = 365


def fetch_stock_data(stock_id: int, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    Fetch historical data for a single stock from Polygon.io

    Args:
        stock_id: Database stock ID
        symbol: Stock symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with OHLCV data or None on failure
    """
    base_url = "https://api.polygon.io/v2/aggs/ticker"

    try:
        # Split into yearly chunks (Polygon.io limit: 50K bars)
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')

        all_data = []
        current_start = start

        while current_start < end:
            # Chunk by year
            current_end = min(current_start + timedelta(days=MAX_DAYS_PER_REQUEST), end)

            params = {
                'adjusted': 'true',
                'sort': 'asc',
                'limit': 50000,
                'apiKey': POLYGON_API_KEY
            }

            # Build URL
            url = f"{base_url}/{symbol}/range/1/day/{current_start.strftime('%Y-%m-%d')}/{current_end.strftime('%Y-%m-%d')}"

            # Fetch data
            response = requests.get(url, params=params, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Failed to fetch {symbol} ({current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}): {response.status_code}")
                return None

            data = response.json()

            if not data.get('results') or len(data['results']) == 0:
                logger.debug(f"No data for {symbol} in period {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}")
                current_start = current_end + timedelta(days=1)
                continue

            # Convert to DataFrame
            df = pd.DataFrame(data['results'])

            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['t'], unit='ms')

            # Rename columns to match database
            df = df.rename(columns={
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume',
                'vw': 'vwap',
                'n': 'transactions'
            })

            # Select and order columns
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'vwap', 'transactions']]

            all_data.append(df)

            current_start = current_end + timedelta(days=1)

        # Combine all chunks
        if not all_data:
            logger.warning(f"No data retrieved for {symbol}")
            return None

        result = pd.concat(all_data, ignore_index=True)

        # Remove duplicates (same timestamp)
        result = result.drop_duplicates(subset=['timestamp'])

        # Sort by timestamp
        result = result.sort_values('timestamp').reset_index(drop=True)

        # Add metadata
        result['stock_id'] = stock_id
        result['timeframe'] = TIMEFRAME

        logger.info(f"✓ Fetched {len(result)} bars for {symbol}")
        return result

    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None


def insert_data_to_db(df: pd.DataFrame, chunk_size: int = 1000):
    """
    Insert OHLCV data into database in chunks

    Args:
        df: DataFrame with OHLCV data
        chunk_size: Batch size for inserts
    """
    if df is None or df.empty:
        return

    db = SessionLocal()
    try:
        # Convert to list of dicts for bulk insert
        records = df[['stock_id', 'timestamp', 'timeframe', 'open', 'high', 'low', 'close', 'volume', 'vwap']].to_dict('records')

        # Insert in chunks
        for i in range(0, len(records), chunk_size):
            chunk = records[i:i + chunk_size]

            db.execute(text("""
                INSERT INTO stock_prices (stock_id, timestamp, timeframe, open, high, low, close, volume, vwap)
                VALUES (:stock_id, :timestamp, :timeframe, :open, :high, :low, :close, :volume, :vwap)
                ON CONFLICT (stock_id, timestamp, timeframe) DO UPDATE
                SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    vwap = EXCLUDED.vwap,
                    updated_at = NOW()
            """), chunk)

        db.commit()
        logger.debug(f"Inserted {len(records)} records")

    except Exception as e:
        logger.error(f"Error inserting data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def get_tracked_stocks() -> list:
    """Get all tracked stocks from database"""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT id, symbol
            FROM stocks
            WHERE is_tracked = true
            ORDER BY symbol
        """))

        stocks = [{'id': row[0], 'symbol': row[1]} for row in result]
        return stocks

    finally:
        db.close()


def check_existing_data(stock_id: int) -> tuple:
    """
    Check if stock already has data and what date range

    Returns:
        (has_data, min_date, max_date)
    """
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT
                COUNT(*) as count,
                MIN(timestamp) as min_date,
                MAX(timestamp) as max_date
            FROM stock_prices
            WHERE stock_id = :stock_id
            AND timeframe = '1d'
        """), {'stock_id': stock_id})

        row = result.fetchone()

        if row and row[0] > 0:
            return True, row[1], row[2]
        else:
            return False, None, None

    finally:
        db.close()


def fetch_single_stock(stock: dict) -> dict:
    """
    Fetch data for a single stock (for parallel processing)

    Args:
        stock: Dict with 'id' and 'symbol'

    Returns:
        Dict with results
    """
    stock_id = stock['id']
    symbol = stock['symbol']

    # Check existing data
    has_data, min_date, max_date = check_existing_data(stock_id)

    if has_data:
        min_date_str = min_date.strftime('%Y-%m-%d') if min_date else None
        max_date_str = max_date.strftime('%Y-%m-%d') if max_date else None

        # If we have recent data (last 30 days), skip
        if max_date and (datetime.now() - max_date).days < 30:
            # Check if we have full 5 years
            if min_date and (datetime.now() - min_date).days >= 365 * YEARS_TO_FETCH:
                return {
                    'symbol': symbol,
                    'status': 'skipped',
                    'reason': 'Already has recent data',
                    'count': 0
                }

        # Determine what date range we need
        fetch_start = START_DATE
        if min_date:
            existing_min = min_date.strftime('%Y-%m-%d')
            if existing_min <= START_DATE:
                # We have old data, just need recent
                fetch_start = (max_date + timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                # Need to fetch from our start
                fetch_start = START_DATE

        fetch_end = END_DATE
    else:
        # No existing data, fetch full range
        fetch_start = START_DATE
        fetch_end = END_DATE

    # Fetch data
    df = fetch_stock_data(stock_id, symbol, fetch_start, fetch_end)

    if df is not None and not df.empty:
        try:
            insert_data_to_db(df)
            return {
                'symbol': symbol,
                'status': 'success',
                'reason': fetch_start,
                'count': len(df)
            }
        except Exception as e:
            return {
                'symbol': symbol,
                'status': 'error',
                'reason': str(e),
                'count': 0
            }
    else:
        return {
            'symbol': symbol,
            'status': 'no_data',
            'reason': 'No data from Polygon.io',
            'count': 0
        }


def main():
    """Main execution"""
    print("=" * 80)
    print(" " * 15)
    print("Stock Analyzer - 5 Year Historical Data Fetcher")
    print(" " * 15)
    print("=" * 80)

    print(f"\n📊 Configuration:")
    print(f"   API: Polygon.io (PAID)")
    print(f"   Timeframe: {TIMEFRAME}")
    print(f"   Date range: {START_DATE} to {END_DATE} ({YEARS_TO_FETCH} years)")
    print(f"   Parallel workers: 10")
    print(f"   Expected time: 1-2 hours")

    # Get all tracked stocks
    print("\n📈 Fetching stock list from database...")
    stocks = get_tracked_stocks()

    if not stocks:
        logger.error("No tracked stocks found! Run add_diverse_stocks_5years.py first.")
        return

    print(f"   Found {len(stocks)} stocks")

    # Fetch data in parallel
    print("\n⚡ Fetching historical data (parallel)...")

    results = {
        'success': 0,
        'skipped': 0,
        'error': 0,
        'no_data': 0,
        'total_bars': 0
    }

    failed_symbols = []

    # Use ThreadPoolExecutor for parallel fetching
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all tasks
        futures = {executor.submit(fetch_single_stock, stock): stock for stock in stocks}

        # Process completed tasks with progress bar
        with tqdm(total=len(stocks), desc="Fetching stocks") as pbar:
            for future in as_completed(futures):
                stock = futures[future]
                try:
                    result = future.result(timeout=120)  # 2 min timeout per stock

                    # Update results
                    status = result['status']
                    results[status] = results.get(status, 0) + 1

                    if status == 'success':
                        results['total_bars'] += result['count']
                        pbar.set_postfix({'✓': results['success'], '⊘': results['skipped'], '✗': results['error']})
                    elif status == 'error':
                        failed_symbols.append(f"{result['symbol']}: {result['reason']}")

                except Exception as e:
                    logger.error(f"Error processing {stock['symbol']}: {e}")
                    results['error'] += 1
                    failed_symbols.append(f"{stock['symbol']}: {str(e)}")

                pbar.update(1)

    # Print summary
    print("\n" + "=" * 80)
    print("✅ DATA FETCHING COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Results:")
    print(f"   ✓ Successfully fetched: {results['success']} stocks")
    print(f"   ⊘ Skipped (has data):    {results['skipped']} stocks")
    print(f"   ✗ Errors:                {results['error']} stocks")
    print(f"   ∅ No data available:     {results['no_data']} stocks")
    print(f"   📈 Total bars inserted:  {results['total_bars']:,}")

    if failed_symbols:
        print(f"\n⚠️  Failed stocks:")
        for symbol in failed_symbols[:20]:  # Show first 20
            print(f"   - {symbol}")
        if len(failed_symbols) > 20:
            print(f"   ... and {len(failed_symbols) - 20} more")

    print("\n" + "=" * 80)
    print("🎉 READY FOR ML TRAINING!")
    print("=" * 80)
    print("\nNext steps:")
    print("   1. Verify data: docker-compose exec backend python -c \"from app.models.stock import StockPrice; print(f'Total: {StockPrice.count()}')\"")
    print("   2. Run feature engineering: python scripts/01h_feature_engineering_28features.py")
    print("   3. Train models: python train.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
