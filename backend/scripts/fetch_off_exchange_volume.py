#!/usr/bin/env python3
"""
Fetch Off-Exchange Short Volume Data from Quiver Quant API (Basic Plan)

This script fetches off-exchange short volume data for all tracked stocks
using QuiverQuant's Basic plan ($10/month).

Off-exchange volume is trades that happen outside major exchanges (dark pools,
retail platforms, etc.). High off-exchange volume can indicate:
1. Institutional accumulation (bullish)
2. Retail short selling (potential squeeze candidate)
3. Dark pool activity

Usage:
    docker-compose exec backend python scripts/fetch_off_exchange_volume.py

Data fetched:
- Daily off-exchange volume
- Total volume
- Short interest percentage
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

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
        return list(result)
    finally:
        db.close()


def stock_id_from_symbol(symbol: str) -> int:
    """Get stock ID from symbol"""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT id
            FROM stocks
            WHERE symbol = :symbol
        """), {"symbol": symbol.upper()})
        row = result.fetchone()
        return row[0] if row else None
    finally:
        db.close()


def save_off_exchange_data_to_db(data: list, stock_id: int) -> int:
    """Save off-exchange volume data to database"""
    if not data:
        return 0

    db = SessionLocal()
    saved_count = 0

    try:
        for record in data:
            try:
                db.execute(text("""
                    INSERT INTO alternative_data (
                        stock_id, date, data_source,
                        off_exchange_volume, total_volume, short_interest,
                        raw_data
                    ) VALUES (
                        :stock_id, :date, 'off_exchange',
                        :off_exchange_volume, :total_volume, :short_interest,
                        :raw_data
                    )
                    ON CONFLICT (stock_id, date, data_source)
                    DO UPDATE SET
                        off_exchange_volume = EXCLUDED.off_exchange_volume,
                        total_volume = EXCLUDED.total_volume,
                        short_interest = EXCLUDED.short_interest,
                        raw_data = EXCLUDED.raw_data
                """), {
                    "stock_id": stock_id,
                    "date": record.get('date'),
                    "off_exchange_volume": record.get('off_exchange_volume', 0),
                    "total_volume": record.get('total_volume', 0),
                    "short_interest": record.get('short_interest', 0),
                    "raw_data": record.get('raw_data', {})
                })
                saved_count += 1

            except Exception as e:
                logger.debug(f"Error saving off-exchange data: {e}")
                continue

        db.commit()
        return saved_count

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error saving off-exchange data: {e}")
    finally:
        db.close()

    return saved_count


def fetch_off_exchange_data():
    """Main function to fetch off-exchange short volume data"""
    print("=" * 80)
    print(" " * 15)
    print("StockAnalyzer - Off-Exchange Short Volume Fetcher (Basic Plan)")
    print(" " * 15)
    print("=" * 80)

    # Check API key
    api_token = os.getenv("QUIVERQUANT_API_KEY")
    if not api_token or api_token == "your_api_key_here":
        print("\n❌ ERROR: QUIVERQUANT_API_KEY not set!")
        return

    # Initialize QuiverQuant client
    try:
        import quiverquant
        q = quiverquant.quiver(api_token)
        logger.info("✅ Connected to Quiver Quant API")
    except ImportError:
        print("\n❌ ERROR: quiverquant package not installed!")
        return
    except Exception as e:
        print(f"\n❌ ERROR: Failed to connect: {e}")
        return

    # Get all tracked stocks
    stocks = get_tracked_stocks()
    print(f"\n📊 Fetching off-exchange data for {len(stocks)} stocks")
    print(f"⏱️  Estimated time: ~{len(stocks) * 2} seconds")

    total_records = 0
    skipped = 0

    # Fetch off-exchange data for each stock
    for stock_id, symbol in tqdm(stocks, desc="Fetching stocks"):
        try:
            df = q.offexchange(symbol)

            if df is None or df.empty:
                skipped += 1
                continue

            # Convert to our format
            records = []
            for _, row in df.iterrows():
                records.append({
                    'date': row.get('Date'),
                    'off_exchange_volume': row.get('OffExchange', 0) if pd.notna(row.get('OffExchange')) else 0,
                    'total_volume': row.get('TotalVolume', 0) if pd.notna(row.get('TotalVolume')) else 0,
                    'short_interest': row.get('ShortInterest', 0) if pd.notna(row.get('ShortInterest')) else 0,
                    'raw_data': row.to_dict()
                })

            saved = save_off_exchange_data_to_db(records, stock_id)
            total_records += saved

        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            skipped += 1
            continue

    # Print summary
    print(f"\n{'='*80}")
    print(f"✅ Off-Exchange Data Fetch Complete!")
    print(f"{'='*80}")
    print(f"\n📊 Results:")
    print(f"   Total records saved: {total_records:,}")
    print(f"   Skipped stocks: {skipped}")
    print(f"\n💡 Next steps:")
    print(f"   1. Run feature engineering with off-exchange features")
    print(f"   2. Retrain ML model")
    print(f"   3. Expected AUC improvement: +2-4%")


def main():
    """Entry point"""
    fetch_off_exchange_data()


if __name__ == "__main__":
    main()
