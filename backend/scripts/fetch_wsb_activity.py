#!/usr/bin/env python3
"""
Fetch WallStreetBets Activity Data from Quiver Quant API (Basic Plan)

This script fetches WallStreetBets discussion activity for all tracked stocks
using QuiverQuant's Basic plan ($10/month).

Usage:
    docker-compose exec backend python scripts/fetch_wsb_activity.py

Data fetched:
- Recent WSB mentions for all stocks
- WSB mentions for specific tickers
- Mention counts, sentiment scores, activity scores
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


def save_wsb_activity_to_db(trades: list, stock_id: int) -> int:
    """Save WSB activity to database"""
    if not trades:
        return 0

    db = SessionLocal()
    saved_count = 0

    try:
        for trade in trades:
            try:
                db.execute(text("""
                    INSERT INTO alternative_data (
                        stock_id, date, data_source,
                        mention_count, sentiment_score, activity_score,
                        discussion_rank, positivity_ratio, raw_data
                    ) VALUES (
                        :stock_id, :date, 'wallstreetbets',
                        :mention_count, :sentiment_score, :activity_score,
                        :discussion_rank, :positivity_ratio, :raw_data
                    )
                    ON CONFLICT (stock_id, date, data_source)
                    DO UPDATE SET
                        mention_count = EXCLUDED.mention_count,
                        sentiment_score = EXCLUDED.sentiment_score,
                        activity_score = EXCLUDED.activity_score,
                        discussion_rank = EXCLUDED.discussion_rank,
                        positivity_ratio = EXCLUDED.positivity_ratio,
                        raw_data = EXCLUDED.raw_data
                """), {
                    "stock_id": stock_id,
                    "date": trade.get('date'),
                    "mention_count": trade.get('mention_count', 0),
                    "sentiment_score": trade.get('sentiment_score', 0),
                    "activity_score": trade.get('activity_score', 0),
                    "discussion_rank": trade.get('discussion_rank', 999),
                    "positivity_ratio": trade.get('positivity_ratio', 0),
                    "raw_data": trade.get('raw_data', {})
                })
                saved_count += 1

            except Exception as e:
                logger.debug(f"Error saving WSB activity: {e}")
                continue

        db.commit()
        return saved_count

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error saving WSB activity: {e}")
    finally:
        db.close()

    return saved_count


def fetch_wsb_activity():
    """Main function to fetch WSB activity"""
    print("=" * 80)
    print(" " * 20)
    print("StockAnalyzer - WallStreetBets Activity Fetcher (Basic Plan)")
    print(" " * 20)
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
    print(f"\n📊 Fetching WSB activity for {len(stocks)} stocks")
    print(f"⏱️  Estimated time: ~{len(stocks) * 3} seconds")

    total_trades = 0
    skipped = 0

    # Fetch WSB data for each stock
    for stock_id, symbol in tqdm(stocks, desc="Fetching stocks"):
        try:
            df = q.wallstreetbets(symbol)

            if df is None or df.empty:
                skipped += 1
                continue

            # Convert to our format
            trades = []
            for _, row in df.iterrows():
                trades.append({
                    'date': row.get('Date'),
                    'mention_count': row.get('Mentions', 0) if pd.notna(row.get('Mentions')) else 0,
                    'sentiment_score': row.get('Sentiment', 0) if pd.notna(row.get('Sentiment')) else 0,
                    'activity_score': row.get('ActivityScore', 0) if pd.notna(row.get('ActivityScore')) else 0,
                    'discussion_rank': row.get('Rank', 999) if pd.notna(row.get('Rank')) else 999,
                    'positivity_ratio': row.get('Positivity', 0) if pd.notna(row.get('Positivity')) else 0,
                    'raw_data': row.to_dict()
                })

            saved = save_wsb_activity_to_db(trades, stock_id)
            total_trades += saved

        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            skipped += 1
            continue

    # Print summary
    print(f"\n{'='*80}")
    print(f"✅ WallStreetBets Data Fetch Complete!")
    print(f"{'='*80}")
    print(f"\n📊 Results:")
    print(f"   Total activity records saved: {total_trades:,}")
    print(f"   Skipped stocks: {skipped}")
    print(f"\n💡 Next steps:")
    print(f"   1. Run feature engineering with WSB features")
    print(f"   2. Retrain ML model")
    print(f"   3. Expected AUC improvement: +2-4%")


def main():
    """Entry point"""
    fetch_wsb_activity()


if __name__ == "__main__":
    main()
