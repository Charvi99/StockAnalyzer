"""
Fetch Daily Data for ML Training (Bypasses Aggregation)

This script fetches daily data directly from Polygon.io,
bypassing the 1h aggregation system for ML purposes.

Usage:
    python fetch_ml_daily_data.py --period 3y
"""

import sys
import os
import time
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

# Import Polygon fetcher directly (bypass StockDataFetcher)
from app.services.polygon_fetcher import PolygonFetcher

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass123@database:5432/stock_analyzer')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

polygon_fetcher = PolygonFetcher()


def fetch_daily_and_store(stock_id: int, symbol: str, period: str, delay: float = 0.5) -> dict:
    """
    Fetch daily data directly from Polygon (bypasses aggregation)

    Args:
        stock_id: Stock ID
        symbol: Stock symbol
        period: Time period (1y, 2y, 3y, 5y)
        delay: Delay after fetching (rate limiting)

    Returns:
        Dict with results
    """
    db = SessionLocal()
    try:
        # Fetch 1d data directly from Polygon
        logger.info(f"Fetching {period} 1d data for {symbol}...")
        prices_data = polygon_fetcher.fetch_historical_data(
            symbol=symbol,
            period=period,
            interval='1d',
            max_retries=3
        )

        if not prices_data:
            return {
                'stock_id': stock_id,
                'symbol': symbol,
                'success': False,
                'records_fetched': 0,
                'records_saved': 0,
                'message': 'No data returned from Polygon'
            }

        # Save directly with timeframe='1d'
        # Use TimeframeService to save (it handles upserts)
        from app.services.timeframe_service import TimeframeService

        saved_count = TimeframeService.save_price_data(
            db=db,
            stock_id=stock_id,
            timeframe='1d',
            prices=prices_data
        )

        db.commit()

        # Rate limiting
        if delay > 0:
            time.sleep(delay)

        return {
            'stock_id': stock_id,
            'symbol': symbol,
            'success': True,
            'records_fetched': len(prices_data),
            'records_saved': saved_count,
            'message': f'Successfully fetched {len(prices_data)} records'
        }

    except Exception as e:
        logger.error(f"Error fetching {symbol}: {str(e)}")
        db.rollback()
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
    parser = argparse.ArgumentParser(description='Fetch daily data for ML training')
    parser.add_argument('--period', default='3y', help='Time period (1y, 2y, 3y, 5y, max)')
    parser.add_argument('--batch-size', type=int, default=5, help='Concurrent fetches')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between API calls (seconds)')
    args = parser.parse_args()

    print("=" * 80)
    print("📊 StockAnalyzer ML - Fetch Daily Data (Direct)")
    print("=" * 80)
    print(f"\n📋 Configuration:")
    print(f"   Period: {args.period}")
    print(f"   Interval: 1d (daily)")
    print(f"   Batch Size: {args.batch_size}")
    print(f"   Delay: {args.delay}s")
    print(f"   ⚠️  Bypasses aggregation - fetches 1d directly from Polygon")

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
    est_time = len(stocks) * 1 / args.batch_size / 60
    print(f"⏱️  Estimated time: {est_time:.1f} minutes")

    # Confirm
    print(f"\n⚠️  This will fetch {args.period} of 1d data for {len(stocks)} stocks")
    print(f"⚠️  This bypasses the 1h aggregation system")
    confirm = input(f"\nContinue? (yes/no): ")

    if confirm.lower() not in ['yes', 'y']:
        print("❌ Cancelled")
        return

    # Fetch data
    print(f"\n🚀 Starting data fetch...")
    print(f"{'='*80}")

    successful = 0
    failed = 0
    total_records = 0
    start_time = time.time()
    failed_stocks = []

    # Use ThreadPoolExecutor for concurrent fetching
    with ThreadPoolExecutor(max_workers=args.batch_size) as executor:
        future_to_stock = {
            executor.submit(fetch_daily_and_store, stock['id'], stock['symbol'], args.period, args.delay): stock
            for stock in stocks
        }

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
                COUNT(CASE WHEN data_count >= 756 THEN 1 END) as three_year,
                AVG(data_count) as avg_days
            FROM (
                SELECT stock_id, COUNT(*) as data_count
                FROM stock_prices
                WHERE timeframe = '1d'
                GROUP BY stock_id
            ) subquery
        """)

        result = db.execute(query).fetchone()

        print(f"\n📊 Results for 1d timeframe:")
        print(f"   Total stocks: {result[0]}")
        print(f"   ML Ready (60+ days): {result[1]} ({100*result[1]/result[0]:.1f}%)")
        print(f"   1 Year+ (252+ days): {result[2]} ({100*result[2]/result[0]:.1f}%)")
        print(f"   2 Years+ (504+ days): {result[3]} ({100*result[3]/result[0]:.1f}%)")
        print(f"   3 Years+ (756+ days): {result[4]} ({100*result[4]/result[0]:.1f}%)")
        print(f"   Average days: {result[5]:.1f}")

        if result[2] >= 300:
            print(f"\n✅ EXCELLENT for ML training! (300+ stocks with 1+ years)")
            print(f"   Run: docker-compose run --rm ml-training python /app/scripts/01_feature_engineering.py")
        elif result[2] >= 200:
            print(f"\n✅ SUFFICIENT DATA for ML training!")
            print(f"   Run: docker-compose run --rm ml-training python /app/scripts/01_feature_engineering.py")
        elif result[2] >= 100:
            print(f"\n⚠️  BORDERLINE - You have {result[2]} stocks with 1+ years (need 200+)")
        else:
            print(f"\n❌ INSUFFICIENT DATA - Only {result[2]} stocks with 1+ years (need 200+)")

    finally:
        db.close()

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
