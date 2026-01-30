"""
Aggregate Hourly Data to Daily for ML Training

This script aggregates all 1h (hourly) data to 1d (daily) timeframe
for all stocks, preparing the database for ML feature engineering.

Usage:
    python aggregate_to_daily.py
"""

import sys
import os
import time
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.services.timeframe_aggregator import TimeframeAggregator
import logging

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


def main():
    """Aggregate all 1h data to 1d for all stocks"""
    print("=" * 80)
    print("📊 StockAnalyzer ML - Aggregate 1h → 1d")
    print("=" * 80)

    # Get all stocks with 1h data
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT DISTINCT stock_id
            FROM stock_prices
            WHERE timeframe = '1h'
            ORDER BY stock_id
        """))
        stock_ids = [row[0] for row in result]
    finally:
        db.close()

    print(f"\n📈 Found {len(stock_ids)} stocks with 1h data")
    print(f"⏱️  Estimated time: {len(stock_ids) * 2 / 60:.1f} minutes")

    confirm = input(f"\nAggregrate 1h → 1d for all {len(stock_ids)} stocks? (yes/no): ")
    if confirm.lower() not in ['yes', 'y']:
        print("❌ Cancelled")
        return

    print(f"\n🚀 Starting aggregation...")
    print(f"{'='*80}")

    successful = 0
    failed = 0
    start_time = time.time()

    for i, stock_id in enumerate(stock_ids, 1):
        try:
            db = SessionLocal()

            # Get stock symbol for display
            symbol_result = db.execute(text("SELECT symbol FROM stocks WHERE id = :id"), {'id': stock_id}).fetchone()
            symbol = symbol_result[0] if symbol_result else f"ID:{stock_id}"

            # Aggregate 1h → 1d, 1w, 1mo
            results = TimeframeAggregator.aggregate_all_and_save_to_db(
                db=db,
                stock_id=stock_id,
                days_lookback=3650  # 10 years lookback (will use all available data)
            )

            db.close()

            # Check if 1d aggregation succeeded
            if results.get('1d', 0) > 0:
                successful += 1
                print(f"✅ [{i}/{len(stock_ids)}] {symbol}: {results.get('1d', 0)} daily records created")
            else:
                failed += 1
                print(f"⚠️  [{i}/{len(stock_ids)}] {symbol}: No daily records created")

        except Exception as e:
            failed += 1
            print(f"❌ [{i}/{len(stock_ids)}] Stock ID {stock_id}: {str(e)}")
            if db:
                db.close()

    # Summary
    elapsed_time = time.time() - start_time
    print(f"\n{'='*80}")
    print(f"📊 AGGREGATION SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Successful: {successful}/{len(stock_ids)} ({100*successful/len(stock_ids):.1f}%)")
    print(f"❌ Failed: {failed}/{len(stock_ids)} ({100*failed/len(stock_ids):.1f}%)")
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
        print(f"   Average days: {result[4]:.1f}")

        if result[1] >= 200:
            print(f"\n✅ SUFFICIENT DATA for ML training!")
            print(f"   Run: docker-compose run --rm ml-training python /app/scripts/01_feature_engineering.py")
        elif result[1] >= 100:
            print(f"\n⚠️  BORDERLINE - You have {result[1]} stocks with 60+ days (need 200+)")
        else:
            print(f"\n❌ INSUFFICIENT DATA - Only {result[1]} stocks with 60+ days (need 200+)")

    finally:
        db.close()

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
