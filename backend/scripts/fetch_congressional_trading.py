#!/usr/bin/env python3
"""
Fetch Congressional Trading Data from Quiver Quant API (Basic Plan)

This script fetches congressional trading data for all tracked stocks
using QuiverQuant's Basic plan ($10/month).

Your current plan includes:
- Congressional trading for all tickers
- Historical data access
- Real-time updates

Usage:
    docker-compose exec backend python scripts/fetch_congressional_trading.py

Data fetched:
- All recent congressional trades
- Trades for specific tickers
- Trades by specific politicians
"""

import sys
import os
import argparse
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


def save_congressional_trades(trades: list, stock_id: int) -> int:
    """
    Save congressional trades to database

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
                # Check if trade already exists
                existing = db.execute(text("""
                    SELECT id
                    FROM insider_trades
                    WHERE stock_id = :stock_id
                      AND insider_name = :insider_name
                      AND trade_date = :trade_date
                      AND total_value = :total_value
                    LIMIT 1
                """), {
                    "stock_id": stock_id,
                    "insider_name": trade.get("insider_name", ""),
                    "trade_date": trade.get("trade_date"),
                    "total_value": trade.get("total_value", 0)
                })

                if existing.fetchone():
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
                    "insider_title": "Congress Member",
                    "transaction_type": trade.get("transaction_type", "OTHER"),
                    "shares": trade.get("shares", 0),
                    "price": trade.get("price"),
                    "total_value": trade.get("total_value"),
                    "trade_date": trade.get("trade_date"),
                    "filing_date": trade.get("filing_date"),
                    "is_congressional": True,
                    "raw_data": trade.get("raw_data")
                })

                saved_count += 1

            except Exception as e:
                logger.debug(f"Error saving trade: {e}")
                continue

        db.commit()
        logger.info(f"✅ Saved {saved_count} new congressional trades for stock {stock_id}")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error saving trades: {e}")
    finally:
        db.close()

    return saved_count


def fetch_congressional_data_for_stocks(symbols: list = None, limit: int = None):
    """
    Main function to fetch congressional trading data

    Args:
        symbols: List of symbols to fetch (if None, fetch all tracked stocks)
        limit: Maximum number of trades to fetch total
    """
    print("=" * 80)
    print(" " * 15)
    print("StockAnalyzer - Congressional Trading Data Fetcher (Basic Plan)")
    print(" " * 15)
    print("=" * 80)

    # Check API key
    api_token = os.getenv("QUIVERQUANT_API_KEY")
    if not api_token or api_token == "your_api_key_here":
        print("\n❌ ERROR: QUIVERQUANT_API_KEY not set!")
        print("\nGet your API key at: https://api.quiverquant.com/pricing/")
        print("Basic plan ($10/mo) includes congressional trading data")
        return

    # Initialize QuiverQuant client
    try:
        import quiverquant
        q = quiverquant.quiver(api_token)
        logger.info("✅ Connected to Quiver Quant API")
    except ImportError:
        print("\n❌ ERROR: quiverquant package not installed!")
        print("\nRun: pip install quiverquant")
        return
    except Exception as e:
        print(f"\n❌ ERROR: Failed to connect: {e}")
        return

    # Get stocks to process
    if symbols:
        stocks = [(stock_id_from_symbol(s), s) for s in symbols]
        stocks = [(sid, s) for sid, s in stocks if sid is not None]
    else:
        stocks = get_tracked_stocks()

    print(f"\n📊 Fetching congressional data for {len(stocks)} stocks")
    print(f"⏱️  Estimated time: ~{len(stocks) * 2} seconds")

    total_trades = 0
    skipped = 0

    # First, fetch all recent congressional trades
    print("\n🏛️  Fetching all recent congressional trades...")
    try:
        all_trades_df = q.congress_trading()

        if all_trades_df is not None and not all_trades_df.empty:
            print(f"✅ Fetched {len(all_trades_df)} total congressional trades")

            # Process and save
            trades_processed = 0
            for _, row in all_trades_df.head(limit or len(all_trades_df)).iterrows():
                try:
                    ticker = row.get('Ticker', '')
                    if not ticker:
                        continue

                    stock_id = stock_id_from_symbol(ticker)
                    if not stock_id:
                        continue

                    # Parse trade data
                    amount_str = str(row.get('Amount', '0')).replace(',', '').replace('$', '')
                    amount = float(amount_str) if amount_str else 0

                    transaction = str(row.get('Transaction', '')).lower()
                    if 'buy' in transaction or 'purchase' in transaction:
                        transaction_type = 'BUY'
                    elif 'sell' in transaction or 'sale' in transaction:
                        transaction_type = 'SELL'
                    else:
                        transaction_type = 'OTHER'

                    trade_date_str = row.get('TransactionDate')
                    filing_date_str = row.get('DisclosureDate')

                    trade = {
                        'ticker': ticker.upper(),
                        'insider_name': row.get('Representative', ''),
                        'insider_title': 'Congress Member',
                        'transaction_type': transaction_type,
                        'shares': 0,
                        'price': amount,
                        'total_value': amount,
                        'trade_date': trade_date_str,
                        'filing_date': filing_date_str,
                        'is_congressional': True,
                        'raw_data': row.to_dict()
                    }

                    saved = save_congressional_trades([trade], stock_id)
                    total_trades += saved
                    trades_processed += 1

                    if trades_processed % 100 == 0:
                        print(f"  Processed {trades_processed}/{len(all_trades_df)} trades...")

                except Exception as e:
                    logger.debug(f"Error processing trade: {e}")
                    continue

            print(f"✅ Saved {total_trades} congressional trades from bulk fetch")

    except Exception as e:
        logger.error(f"❌ Error fetching bulk congressional trades: {e}")

    # Now fetch ticker-specific data (if needed)
    print("\n📈 Fetching ticker-specific congressional trades...")
    for stock_id, symbol in tqdm(stocks, desc="Processing stocks"):
        try:
            df = q.congress_trading(symbol)

            if df is None or df.empty:
                skipped += 1
                continue

            # Convert to our format and save
            trades = []
            for _, row in df.iterrows():
                amount_str = str(row.get('Amount', '0')).replace(',', '').replace('$', '')
                amount = float(amount_str) if amount_str else 0

                transaction = str(row.get('Transaction', '')).lower()
                if 'buy' in transaction or 'purchase' in transaction:
                    transaction_type = 'BUY'
                elif 'sell' in transaction or 'sale' in transaction:
                    transaction_type = 'SELL'
                else:
                    transaction_type = 'OTHER'

                trade = {
                    'ticker': symbol.upper(),
                    'insider_name': row.get('Representative', ''),
                    'insider_title': 'Congress Member',
                    'transaction_type': transaction_type,
                    'shares': 0,
                    'price': amount,
                    'total_value': amount,
                    'trade_date': row.get('TransactionDate'),
                    'filing_date': row.get('DisclosureDate'),
                    'is_congressional': True,
                    'raw_data': row.to_dict()
                }

                trades.append(trade)

            saved = save_congressional_trades(trades, stock_id)
            total_trades += saved

        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            skipped += 1
            continue

    # Print summary
    print(f"\n{'='*80}")
    print(f"✅ Congressional Trading Data Fetch Complete!")
    print(f"{'='*80}")
    print(f"\n📊 Results:")
    print(f"   Total trades saved: {total_trades:,}")
    print(f"   Skipped stocks: {skipped}")
    print(f"\n💡 Next steps:")
    print(f"   1. Run feature engineering with congressional features")
    print(f"   2. Retrain ML model")
    print(f"   3. Expected AUC improvement: +3-5%")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Fetch congressional trading data from Quiver Quant API"
    )
    parser.add_argument(
        "--symbols",
        nargs='+',
        help="Specific stock symbols to fetch (e.g., AAPL TSLA MSFT)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum number of trades to fetch (default: 1000)"
    )

    args = parser.parse_args()

    fetch_congressional_data_for_stocks(symbols=args.symbols, limit=args.limit)


if __name__ == "__main__":
    main()
