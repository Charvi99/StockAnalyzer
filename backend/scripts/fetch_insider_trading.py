#!/usr/bin/env python3
"""
Fetch Insider Trading Data from Quiver Quant API

This script fetches corporate insider trading data and congressional trades
for all tracked stocks in the database.

Usage:
    docker-compose exec backend python scripts/fetch_insider_trading.py [--historical]

Options:
    --historical    Fetch historical data (up to 1 year back)
    --congressional Fetch congressional trading data

Requirements:
    - QUIVERQUANT_API_KEY environment variable must be set
    - Free tier: 1,000 API calls/month
"""

import sys
import os
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Import services
from app.services.quiverquant_fetcher_v2 import QuiverQuantFetcher

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
    """
    Get all tracked stocks from database

    Returns:
        List of (stock_id, symbol) tuples
    """
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
    """
    Get stock ID from symbol

    Args:
        symbol: Stock ticker symbol

    Returns:
        Stock ID or None
    """
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

    try:
        for trade in trades:
            try:
                # Check if trade already exists (duplicate detection)
                existing = db.execute(text("""
                    SELECT id
                    FROM insider_trades
                    WHERE stock_id = :stock_id
                      AND insider_name = :insider_name
                      AND trade_date = :trade_date
                      AND shares = :shares
                      AND transaction_type = :transaction_type
                    LIMIT 1
                """), {
                    "stock_id": stock_id,
                    "insider_name": trade.get("insider_name", ""),
                    "trade_date": trade.get("trade_date"),
                    "shares": trade.get("shares", 0),
                    "transaction_type": trade.get("transaction_type", "")
                })

                if existing.fetchone():
                    continue  # Skip duplicates

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
                    "insider_title": trade.get("insider_title"),
                    "transaction_type": trade.get("transaction_type", "OTHER"),
                    "shares": trade.get("shares", 0),
                    "price": trade.get("price"),
                    "total_value": trade.get("total_value"),
                    "trade_date": trade.get("trade_date"),
                    "filing_date": trade.get("filing_date"),
                    "is_congressional": trade.get("is_congressional", False),
                    "raw_data": trade.get("raw_data")
                })

                saved_count += 1

            except Exception as e:
                logger.debug(f"Error saving trade: {e}")
                continue

        db.commit()
        logger.info(f"✅ Saved {saved_count} new insider trades for stock {stock_id}")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error saving trades: {e}")
    finally:
        db.close()

    return saved_count


def fetch_insider_data(historical: bool = False, congressional: bool = False):
    """
    Main function to fetch insider trading data

    Args:
        historical: Fetch historical data (up to 1 year back)
        congressional: Fetch congressional trading data
    """
    print("=" * 80)
    print(" " * 20)
    print("StockAnalyzer - Insider Trading Data Fetcher")
    print(" " * 20)
    print("=" * 80)

    # Check API key
    api_key = os.getenv("QUIVERQUANT_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("\n❌ ERROR: QUIVERQUANT_API_KEY not set!")
        print("\nGet your free API key at: https://www.quiverquant.com/")
        print("Free tier: 1,000 API calls/month")
        print("\nAdd to .env file:")
        print("QUIVERQUANT_API_KEY=your_api_key_here")
        print("\nThen add to docker-compose.yml:")
        print("QUIVERQUANT_API_KEY: ${QUIVERQUANT_API_KEY}")
        return

    # Initialize fetcher
    fetcher = QuiverQuantFetcher()

    # Get tracked stocks
    stocks = get_tracked_stocks()
    print(f"\n📊 Fetching data for {len(stocks)} tracked stocks")
    print(f"⏱️  Estimated time: ~{len(stocks) * 2} seconds")

    if historical:
        print("📅 Mode: Historical (up to 1 year)")
    else:
        print("📅 Mode: Recent trades")

    total_trades = 0
    skipped = 0

    # Fetch insider trades for each stock
    for stock_id, symbol in tqdm(stocks, desc="Fetching insider trades"):
        try:
            if historical:
                trades = fetcher.fetch_historical_insider_trades(symbol)
            else:
                trades = fetcher.fetch_live_insider_trades(symbol)

            if trades:
                saved = save_insider_trades(trades, stock_id)
                total_trades += saved
            else:
                skipped += 1

        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            skipped += 1
            continue

    # Fetch congressional trades if requested
    if congressional:
        print("\n🏛️  Fetching congressional trades...")
        try:
            congress_trades = fetcher.fetch_congressional_trades()

            if congress_trades:
                for trade in tqdm(congress_trades, desc="Saving congressional trades"):
                    symbol = trade.get("ticker", "")
                    if symbol:
                        stock_id = stock_id_from_symbol(symbol)
                        if stock_id:
                            saved = save_insider_trades([trade], stock_id)
                            total_trades += saved
        except Exception as e:
            logger.error(f"Error fetching congressional trades: {e}")

    # Print summary
    print(f"\n{'='*80}")
    print(f"✅ Insider Trading Data Fetch Complete!")
    print(f"{'='*80}")
    print(f"\n📊 Summary:")
    print(f"   Total trades saved: {total_trades:,}")
    print(f"   Stocks skipped: {skipped}")
    print(f"   API calls used: ~{len(stocks) + (1 if congressional else 0)}")
    print(f"\n💡 Next steps:")
    print(f"   1. Run: docker-compose run --rm ml-training python /app/train.py")
    print(f"   2. Features will include 12 insider-based features")
    print(f"\n📁 Data stored in: insider_trades table")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Fetch insider trading data from Quiver Quant API"
    )
    parser.add_argument(
        "--historical",
        action="store_true",
        help="Fetch historical data (up to 1 year back)"
    )
    parser.add_argument(
        "--congressional",
        action="store_true",
        help="Fetch congressional trading data"
    )

    args = parser.parse_args()

    fetch_insider_data(
        historical=args.historical,
        congressional=args.congressional
    )


if __name__ == "__main__":
    main()
