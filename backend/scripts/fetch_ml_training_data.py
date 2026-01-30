"""
Fetch Historical Data for ML Training

This script fetches sufficient historical data for all tracked stocks
to prepare them for ML model training.

Usage:
    python fetch_ml_training_data.py --period 2y --interval 1d

Options:
    --period: Time period to fetch (1y, 2y, 3y, 5y, max) [default: 2y]
    --interval: Data interval (1d, 1h) [default: 1d]
    --batch-size: Number of stocks to fetch concurrently [default: 5]
    --delay: Delay between API calls in seconds [default: 0.5]
"""

import sys
import os
import time
import argparse
import logging
from datetime import datetime
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.services.stock_fetcher import StockDataFetcher

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass123@database:5432/stock_analyzer')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def fetch_stock_data(stock_id: int, symbol: str, period: str, interval: str, delay: float = 0.5) -> dict:
    """
    Fetch historical data for a single stock

    Args:
        stock_id: Stock ID
        symbol: Stock symbol
        period: Time period (1y, 2y, 3y, etc.)
        interval: Data interval (1d, 1h)
        delay: Delay after fetching (rate limiting)

    Returns:
        Dict with results
    """
    db = SessionLocal()
    try:
        result = StockDataFetcher.fetch_and_store(
            db=db,
            stock_id=stock_id,
            symbol=symbol,
            period=period,
            interval=interval
        )

        # Rate limiting
        if delay > 0:
            time.sleep(delay)

        return {
            'stock_id': stock_id,
            'symbol': symbol,
            'success': result.get('success', False),
            'records_fetched': result.get('records_fetched', 0),
            'records_saved': result.get('records_saved', 0),
            'message': result.get('message', '')
        }

    except Exception as e:
        logger.error(f"Error fetching {symbol}: {str(e)}")
        return {
            'stock_id': stock_id,
            'symbol': symbol,
            'success': False,
            'records_fetched': 0,
            'records_saved': 0,
            'message': str(e)
        }
    finally:
        db.close()


def main():
    """Main fetching pipeline"""
    parser = argparse.ArgumentParser(description='Fetch historical data for ML training')
    parser.add_argument('--period', default='2y', help='Time period (1y, 2y, 3y, 5y, max)')
    parser.add_argument('--interval', default='1d', help='Data interval (1d, 1h)')
    parser.add_argument('--batch-size', type=int, default=5, help='Concurrent fetches')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between API calls (seconds)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be fetched without fetching')
    args = parser.parse_args()

    print("=" * 80)
    print("📊 StockAnalyzer ML - Historical Data Fetcher")
    print("=" * 80)
    print(f"\n📋 Configuration:")
    print(f"   Period: {args.period}")
    print(f"   Interval: {args.interval}")
    print(f"   Batch Size: {args.batch_size}")
    print(f"   Delay: {args.delay}s")
    print(f"   Dry Run: {args.dry_run}")

    # Get all tracked stocks
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT id, symbol
            FROM stocks
            WHERE is_tracked = true
            ORDER BY symbol
        """))
        stocks = [{'id': row[0], 'symbol': row[1]} for row in result]
    finally:
        db.close()

    print(f"\n📈 Found {len(stocks)} tracked stocks")

    # Estimate time
    if args.interval == '1d':
        # Daily data: ~1 second per stock
        est_time = len(stocks) * 1 / args.batch_size / 60
    else:
        # Hourly data: ~2 seconds per stock
        est_time = len(stocks) * 2 / args.batch_size / 60

    print(f"⏱️  Estimated time: {est_time:.1f} minutes")

    if args.dry_run:
        print("\n🔍 Dry run - would fetch the following stocks:")
        for stock in stocks[:10]:
            print(f"   - {stock['symbol']} (ID: {stock['id']})")
        if len(stocks) > 10:
            print(f"   ... and {len(stocks) - 10} more")
        return

    # Confirm
    print(f"\n⚠️  This will fetch {args.period} of {args.interval} data for {len(stocks)} stocks")
    confirm = input(f"\nContinue? (yes/no): ")

    if confirm.lower() not in ['yes', 'y']:
        print("❌ Cancelled")
        return

    # Fetch data with progress tracking
    print(f"\n🚀 Starting data fetch...")
    print(f"{'='*80}")

    successful = 0
    failed = 0
    total_records = 0
    start_time = time.time()
    failed_stocks = []

    # Use ThreadPoolExecutor for concurrent fetching
    with ThreadPoolExecutor(max_workers=args.batch_size) as executor:
        # Submit all tasks
        future_to_stock = {
            executor.submit(fetch_stock_data, stock['id'], stock['symbol'], args.period, args.interval, args.delay): stock
            for stock in stocks
        }

        # Process completed tasks
        for i, future in enumerate(as_completed(future_to_stock), 1):
            stock = future_to_stock[future]
            try:
                result = future.result()

                if result['success']:
                    successful += 1
                    total_records += result['records_saved']
                    print(f"✅ [{i}/{len(stocks)}] {result['symbol']}: {result['records_saved']} records")
                else:
                    failed += 1
                    failed_stocks.append(result['symbol'])
                    print(f"❌ [{i}/{len(stocks)}] {result['symbol']}: {result['message']}")

            except Exception as e:
                failed += 1
                failed_stocks.append(stock['symbol'])
                print(f"❌ [{i}/{len(stocks)}] {stock['symbol']}: {str(e)}")

    # Summary
    elapsed_time = time.time() - start_time
    print(f"\n{'='*80}")
    print(f"📊 FETCH SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Successful: {successful}/{len(stocks)} ({100*successful/len(stocks):.1f}%)")
    print(f"❌ Failed: {failed}/{len(stocks)} ({100*failed/len(stocks):.1f}%)")
    print(f"📈 Total records fetched: {total_records:,}")
    print(f"⏱️  Time elapsed: {elapsed_time/60:.1f} minutes")

    if failed_stocks:
        print(f"\n⚠️  Failed stocks ({len(failed_stocks)}):")
        for symbol in failed_stocks[:20]:
            print(f"   - {symbol}")
        if len(failed_stocks) > 20:
            print(f"   ... and {len(failed_stocks) - 20} more")

    # Check data quality
    print(f"\n{'='*80}")
    print(f"🔍 DATA QUALITY CHECK")
    print(f"{'='*80}")

    db = SessionLocal()
    try:
        query = text("""
            SELECT
                COUNT(*) as total_stocks,
                COUNT(CASE WHEN data_count >= 60 THEN 1 END) as ml_ready,
                COUNT(CASE WHEN data_count >= 252 THEN 1 END) as one_year,
                COUNT(CASE WHEN data_count >= 504 THEN 1 END) as two_year,
                AVG(data_count) as avg_days
            FROM (
                SELECT stock_id, COUNT(*) as data_count
                FROM stock_prices
                WHERE timeframe = :timeframe
                GROUP BY stock_id
            ) subquery
        """)

        result = db.execute(query, {'timeframe': args.interval}).fetchone()

        print(f"\n📊 Results for {args.interval} timeframe:")
        print(f"   Total stocks: {result[0]}")
        print(f"   ML Ready (60+ days): {result[1]} ({100*result[1]/result[0]:.1f}%)")
        print(f"   1 Year+ (252+ days): {result[2]} ({100*result[2]/result[0]:.1f}%)")
        print(f"   2 Years+ (504+ days): {result[3]} ({100*result[3]/result[0]:.1f}%)")
        print(f"   Average days: {result[4]:.1f}")

        if result[1] >= 200:
            print(f"\n✅ SUFFICIENT DATA for ML training!")
        elif result[1] >= 100:
            print(f"\n⚠️  BORDERLINE - You have {result[1]} stocks with 60+ days (need 200+)")
        else:
            print(f"\n❌ INSUFFICIENT DATA - Only {result[1]} stocks with 60+ days (need 200+)")

    finally:
        db.close()

    print(f"\n{'='*80}")
    print(f"🎉 Done! You can now run feature engineering:")
    print(f"   docker-compose run --rm ml-training python /app/scripts/01_feature_engineering.py")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
