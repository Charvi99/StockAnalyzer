"""
Backfill Indicator Cache Script

One-time script to populate the indicator cache for all existing stocks.

This script:
1. Aggregates hourly data to daily/weekly/monthly timeframes
2. Calculates all 35 technical indicators
3. Caches results in database

Expected runtime: ~45 minutes for 502 stocks
Expected database size increase: +5.34 MB

Usage:
    cd backend
    python scripts/backfill_indicator_cache.py

    # With options:
    python scripts/backfill_indicator_cache.py --limit 10  # Test with 10 stocks only
    python scripts/backfill_indicator_cache.py --force     # Recalculate even if cache exists
"""

import sys
import os
import argparse
import logging
from datetime import datetime
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.database import SessionLocal
from app.models.stock import Stock
from app.services.timeframe_aggregator import TimeframeAggregator
from app.services.indicator_cache_service import IndicatorCacheService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('backfill_indicator_cache.log')
    ]
)
logger = logging.getLogger(__name__)


def backfill_stock(db, stock: Stock, force_refresh: bool = False) -> dict:
    """
    Backfill aggregated timeframes and indicator cache for a single stock.

    Args:
        db: Database session
        stock: Stock object
        force_refresh: Force recalculation even if cache exists

    Returns:
        dict with status and results
    """
    start_time = time.time()
    logger.info(f"\n{'='*80}")
    logger.info(f"Processing: {stock.symbol} (ID: {stock.id})")
    logger.info(f"{'='*80}")

    results = {
        'stock_id': stock.id,
        'symbol': stock.symbol,
        'aggregation': {},
        'cache': {},
        'duration_seconds': 0
    }

    try:
        # Step 1: Aggregate hourly data to daily/weekly/monthly
        logger.info(f"📊 Step 1/2: Aggregating timeframes for {stock.symbol}...")
        agg_results = TimeframeAggregator.aggregate_all_and_save_to_db(db, stock.id, days_lookback=90)

        results['aggregation'] = agg_results

        if any(agg_results.values()):
            logger.info(f"✅ Aggregation complete for {stock.symbol}: {agg_results}")
        else:
            logger.warning(f"⚠️ All aggregation failed for {stock.symbol} - may lack hourly data")

        # Step 2: Calculate and cache indicators for daily timeframe
        logger.info(f"💾 Step 2/2: Caching indicators for {stock.symbol}...")
        cache_success = IndicatorCacheService.calculate_and_cache(
            db,
            stock.id,
            timeframe='1d',
            force_refresh=force_refresh
        )

        results['cache']['1d'] = cache_success

        if cache_success:
            logger.info(f"✅ Cache complete for {stock.symbol}")
        else:
            logger.warning(f"⚠️ Cache failed for {stock.symbol} - may lack daily data")

        duration = time.time() - start_time
        results['duration_seconds'] = round(duration, 2)
        results['status'] = 'success' if cache_success else 'partial'

        logger.info(f"⏱️ Processing time for {stock.symbol}: {duration:.2f}s")
        return results

    except Exception as e:
        logger.error(f"❌ Error processing {stock.symbol}: {e}", exc_info=True)
        duration = time.time() - start_time
        results['duration_seconds'] = round(duration, 2)
        results['status'] = 'error'
        results['error'] = str(e)
        return results


def main():
    """Main backfill function."""
    parser = argparse.ArgumentParser(description='Backfill indicator cache for all stocks')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of stocks to process (for testing)')
    parser.add_argument('--force', action='store_true', help='Force recalculation even if cache exists')
    parser.add_argument('--stock-id', type=int, default=None, help='Process specific stock ID only')
    parser.add_argument('--symbol', type=str, default=None, help='Process specific symbol only (e.g., AAPL)')
    args = parser.parse_args()

    logger.info("="*80)
    logger.info("INDICATOR CACHE BACKFILL SCRIPT")
    logger.info("="*80)
    logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Force refresh: {args.force}")

    if args.limit:
        logger.info(f"Limit: {args.limit} stocks")
    if args.stock_id:
        logger.info(f"Processing specific stock ID: {args.stock_id}")
    if args.symbol:
        logger.info(f"Processing specific symbol: {args.symbol}")

    logger.info("="*80)

    db = SessionLocal()
    script_start = time.time()

    try:
        # Get stocks to process
        query = db.query(Stock).filter(Stock.is_tracked == True)

        if args.stock_id:
            query = query.filter(Stock.id == args.stock_id)
        elif args.symbol:
            query = query.filter(Stock.symbol == args.symbol.upper())

        if args.limit:
            stocks = query.limit(args.limit).all()
        else:
            stocks = query.all()

        if not stocks:
            logger.error("No stocks found to process")
            return

        total_stocks = len(stocks)
        logger.info(f"\n📊 Found {total_stocks} stocks to process\n")

        # Process each stock
        results_list = []
        success_count = 0
        partial_count = 0
        error_count = 0

        for idx, stock in enumerate(stocks, 1):
            logger.info(f"\n{'#'*80}")
            logger.info(f"Progress: {idx}/{total_stocks} ({idx/total_stocks*100:.1f}%)")
            logger.info(f"{'#'*80}")

            result = backfill_stock(db, stock, force_refresh=args.force)
            results_list.append(result)

            if result['status'] == 'success':
                success_count += 1
            elif result['status'] == 'partial':
                partial_count += 1
            else:
                error_count += 1

            # Show progress every 10 stocks
            if idx % 10 == 0 or idx == total_stocks:
                elapsed = time.time() - script_start
                avg_time = elapsed / idx
                remaining = (total_stocks - idx) * avg_time
                logger.info(f"\n📈 Progress Summary:")
                logger.info(f"   Completed: {idx}/{total_stocks}")
                logger.info(f"   Success: {success_count}, Partial: {partial_count}, Errors: {error_count}")
                logger.info(f"   Elapsed: {elapsed/60:.1f} min, Estimated remaining: {remaining/60:.1f} min")

            # Small delay to avoid overwhelming the database
            time.sleep(0.1)

        # Final summary
        script_duration = time.time() - script_start
        logger.info("\n" + "="*80)
        logger.info("BACKFILL COMPLETE")
        logger.info("="*80)
        logger.info(f"Total stocks processed: {total_stocks}")
        logger.info(f"Success: {success_count}")
        logger.info(f"Partial: {partial_count}")
        logger.info(f"Errors: {error_count}")
        logger.info(f"Total duration: {script_duration/60:.1f} minutes")
        logger.info(f"Average time per stock: {script_duration/total_stocks:.2f} seconds")
        logger.info(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)

        # Get cache statistics
        logger.info("\n📊 Cache Statistics:")
        cache_stats = IndicatorCacheService.get_cache_stats(db)
        logger.info(f"   Total cached entries: {cache_stats.get('total_cached', 0)}")
        logger.info(f"   By timeframe: {cache_stats.get('by_timeframe', {})}")
        logger.info(f"   Oldest cache: {cache_stats.get('oldest_cache', 'N/A')}")
        logger.info(f"   Newest cache: {cache_stats.get('newest_cache', 'N/A')}")

        # Get aggregation statistics
        logger.info("\n📊 Aggregation Statistics:")
        agg_stats = TimeframeAggregator.get_aggregation_stats(db) if hasattr(TimeframeAggregator, 'get_aggregation_stats') else {}
        if agg_stats:
            for timeframe, stats in agg_stats.items():
                logger.info(f"   {timeframe}: {stats.get('total_records', 0)} records ({stats.get('avg_per_stock', 0):.1f} per stock)")

    except KeyboardInterrupt:
        logger.warning("\n\n⚠️ Script interrupted by user (Ctrl+C)")
        logger.info("Partial results saved to database")

    except Exception as e:
        logger.error(f"\n\n❌ Fatal error: {e}", exc_info=True)

    finally:
        db.close()
        logger.info("\nDatabase connection closed")
        logger.info("Log file: backfill_indicator_cache.log")


if __name__ == "__main__":
    main()
