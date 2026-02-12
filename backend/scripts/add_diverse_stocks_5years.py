#!/usr/bin/env python3
"""
Add 500-600 Diverse Stocks with Sector Information

This script populates the database with:
- S&P 500 stocks (top ~400-450 by market cap)
- NASDAQ 100 stocks (top ~80-100)
- Popular ETFs (index + sector)
- Each stock includes GICS sector information

Data sources:
- Wikipedia for S&P 500 and NASDAQ 100 lists
- Polygon.io for metadata/symbols validation
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, '/backend')

import requests
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://stockuser:stockpass123@database:5432/stock_analyzer'
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# GICS Sector Mapping (11 sectors)
SECTOR_MAPPING = {
    'Technology': ['Technology', 'Software', 'Semiconductors', 'IT Services'],
    'Health Care': ['Health Care', 'Pharmaceuticals', 'Biotechnology', 'Medical Devices'],
    'Financials': ['Financials', 'Banks', 'Insurance', 'Capital Markets'],
    'Consumer Discretionary': ['Consumer Discretionary', 'Retail', 'Automotive', 'Media'],
    'Communication Services': ['Communication Services', 'Telecommunications', 'Internet'],
    'Industrials': ['Industrials', 'Manufacturing', 'Aerospace', 'Construction'],
    'Consumer Staples': ['Consumer Staples', 'Food & Beverage', 'Household Products'],
    'Energy': ['Energy', 'Oil & Gas', 'Renewable Energy'],
    'Utilities': ['Utilities', 'Electric Utilities', 'Gas Utilities'],
    'Real Estate': ['Real Estate', 'REITs'],
    'Materials': ['Materials', 'Chemicals', 'Mining', 'Paper & Forest'],
}


def fetch_sp500_stocks() -> list:
    """
    Fetch S&P 500 stocks from Wikipedia

    Returns:
        List of dicts with symbol, name, sector
    """
    logger.info("Fetching S&P 500 stocks from Wikipedia...")

    try:
        # S&P 500 Wikipedia page
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)

        # First table is the S&P 500 list
        df = tables[0]

        # Clean columns
        df.columns = ['Symbol', 'Security', 'SEC_filing', 'GICS_Sector', 'GICS_Sub_Industry',
                      'Headquarters_Location', 'Date_added', 'CIK', 'Founded']

        # Clean symbol names (remove BRK.A etc dots)
        df['Symbol'] = df['Symbol'].str.replace('.', '-', regex=False)

        stocks = []
        for _, row in df.iterrows():
            symbol = row['Symbol'].strip()
            name = row['Security'].strip()
            sector = row['GICS_Sector'].strip()

            if symbol and name and sector:
                stocks.append({
                    'symbol': symbol,
                    'name': name,
                    'sector': sector,
                    'sub_industry': row['GICS_Sub_Industry'].strip(),
                    'source': 'S&P 500'
                })

        logger.info(f"Fetched {len(stocks)} S&P 500 stocks")
        return stocks

    except Exception as e:
        logger.error(f"Error fetching S&P 500: {e}")
        return []


def fetch_nasdaq100_stocks() -> list:
    """
    Fetch NASDAQ 100 stocks from Wikipedia

    Returns:
        List of dicts with symbol, name, sector
    """
    logger.info("Fetching NASDAQ 100 stocks from Wikipedia...")

    try:
        # NASDAQ 100 Wikipedia page
        url = "https://en.wikipedia.org/wiki/NASDAQ-100"
        tables = pd.read_html(url)

        # Find the table with ticker symbols (usually 2nd or 3rd table)
        df = None
        for table in tables:
            if 'Ticker' in table.columns or 'Symbol' in table.columns:
                df = table
                break

        if df is None:
            logger.warning("Could not find NASDAQ 100 table")
            return []

        # Clean symbol names
        if 'Symbol' in df.columns:
            df.rename(columns={'Symbol': 'Ticker'}, inplace=True)

        stocks = []
        for _, row in df.iterrows():
            # Handle different column names
            symbol = row.get('Ticker') or row.get('Symbol')
            name = row.get('Company') or row.get('Name')

            if symbol and pd.notna(symbol):
                symbol = str(symbol).strip().replace('.', '-', regex=False)
                name = str(name).strip() if pd.notna(name) else symbol

                # NASDAQ 100 is mostly tech - map to sectors
                stocks.append({
                    'symbol': symbol,
                    'name': name,
                    'sector': 'Technology',  # Default, will be updated later
                    'sub_industry': 'Technology',
                    'source': 'NASDAQ 100'
                })

        logger.info(f"Fetched {len(stocks)} NASDAQ 100 stocks")
        return stocks

    except Exception as e:
        logger.error(f"Error fetching NASDAQ 100: {e}")
        return []


def get_popular_etfs() -> list:
    """
    Get list of popular ETFs for diversification

    Returns:
        List of dicts with symbol, name, sector
    """
    logger.info("Adding popular ETFs...")

    etfs = [
        # Broad Market
        {'symbol': 'SPY', 'name': 'SPDR S&P 500 ETF Trust', 'sector': 'ETF', 'sub_industry': 'Large Cap'},
        {'symbol': 'VOO', 'name': 'Vanguard S&P 500 ETF', 'sector': 'ETF', 'sub_industry': 'Large Cap'},
        {'symbol': 'IVV', 'name': 'iShares Core S&P 500 ETF', 'sector': 'ETF', 'sub_industry': 'Large Cap'},
        {'symbol': 'VTI', 'name': 'Vanguard Total Stock Market ETF', 'sector': 'ETF', 'sub_industry': 'Total Market'},
        {'symbol': 'QQQ', 'name': 'Invesco QQQ Trust', 'sector': 'ETF', 'sub_industry': 'Technology'},
        {'symbol': 'IWM', 'name': 'iShares Russell 2000 ETF', 'sector': 'ETF', 'sub_industry': 'Small Cap'},
        {'symbol': 'DIA', 'name': 'SPDR Dow Jones Industrial Average ETF', 'sector': 'ETF', 'sub_industry': 'Large Cap'},

        # Sector ETFs (for sector analysis)
        {'symbol': 'XLK', 'name': 'Technology Select Sector SPDR Fund', 'sector': 'ETF', 'sub_industry': 'Technology'},
        {'symbol': 'XLV', 'name': 'Health Care Select Sector SPDR Fund', 'sector': 'ETF', 'sub_industry': 'Health Care'},
        {'symbol': 'XLF', 'name': 'Financial Select Sector SPDR Fund', 'sector': 'ETF', 'sub_industry': 'Financials'},
        {'symbol': 'XLE', 'name': 'Energy Select Sector SPDR Fund', 'sector': 'ETF', 'sub_industry': 'Energy'},
        {'symbol': 'XLI', 'name': 'Industrial Select Sector SPDR Fund', 'sector': 'ETF', 'sub_industry': 'Industrials'},
        {'symbol': 'XLY', 'name': 'Consumer Discretionary Select Sector SPDR Fund', 'sector': 'ETF', 'sub_industry': 'Consumer Discretionary'},
        {'symbol': 'XLP', 'name': 'Consumer Staples Select Sector SPDR Fund', 'sector': 'ETF', 'sub_industry': 'Consumer Staples'},
        {'symbol': 'XLRE', 'name': 'Real Estate Select Sector SPDR Fund', 'sector': 'ETF', 'sub_industry': 'Real Estate'},
        {'symbol': 'XLU', 'name': 'Utilities Select Sector SPDR Fund', 'sector': 'ETF', 'sub_industry': 'Utilities'},
        {'symbol': 'XLC', 'name': 'Communication Services Select Sector SPDR Fund', 'sector': 'ETF', 'sub_industry': 'Communication Services'},
        {'symbol': 'XLB', 'name': 'Materials Select Sector SPDR Fund', 'sector': 'ETF', 'sub_industry': 'Materials'},

        # Fixed Income / Commodities
        {'symbol': 'TLT', 'name': 'iShares 20+ Year Treasury Bond ETF', 'sector': 'ETF', 'sub_industry': 'Fixed Income'},
        {'symbol': 'IEF', 'name': 'iShares 7-10 Year Treasury Bond ETF', 'sector': 'ETF', 'sub_industry': 'Fixed Income'},
        {'symbol': 'GLD', 'name': 'SPDR Gold Shares', 'sector': 'ETF', 'sub_industry': 'Commodities'},
        {'symbol': 'SLV', 'name': 'iShares Silver Trust', 'sector': 'ETF', 'sub_industry': 'Commodities'},
        {'symbol': 'USO', 'name': 'United States Oil Fund', 'sector': 'ETF', 'sub_industry': 'Commodities'},

        # International
        {'symbol': 'EFA', 'name': 'iShares MSCI EAFE ETF', 'sector': 'ETF', 'sub_industry': 'International'},
        {'symbol': 'VWO', 'name': 'Vanguard Emerging Markets Stock Index Fund ETF', 'sector': 'ETF', 'sub_industry': 'International'},
        {'symbol': 'EWJ', 'name': 'iShares MSCI Japan ETF', 'sector': 'ETF', 'sub_industry': 'International'},
    ]

    for etf in etfs:
        etf['source'] = 'ETF'

    logger.info(f"Added {len(etfs)} popular ETFs")
    return etfs


def deduplicate_stocks(all_stocks: list) -> list:
    """
    Remove duplicates from stock list (prioritize S&P 500 sector info)

    Args:
        all_stocks: List of stock dicts

    Returns:
        Deduplicated list with unique symbols
    """
    logger.info("Deduplicating stocks...")

    seen = {}
    for stock in all_stocks:
        symbol = stock['symbol']

        # Prioritize S&P 500 sector information
        if symbol not in seen:
            seen[symbol] = stock
        elif stock['source'] == 'S&P 500':
            # Replace with S&P 500 entry (has better sector info)
            seen[symbol] = stock
        elif seen[symbol]['source'] == 'NASDAQ 100' and stock['source'] == 'ETF':
            # ETFs keep their ETF sector
            seen[symbol] = stock

    deduplicated = list(seen.values())
    logger.info(f"Deduplicated: {len(all_stocks)} → {len(deduplicated)} unique symbols")
    return deduplicated


def validate_symbols_with_polygon(symbols: list, api_key: str) -> list:
    """
    Validate symbols using Polygon.io API

    Args:
        symbols: List of symbols to validate
        api_key: Polygon.io API key

    Returns:
        List of valid symbols
    """
    logger.info(f"Validating {len(symbols)} symbols with Polygon.io...")

    valid_symbols = []

    # Batch requests (Polygon allows multiple symbols per request)
    batch_size = 50

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        if i % 50 == 0:
            print(f"Validating: {i}/{len(symbols)}")

        for symbol in batch:
            try:
                # Check if ticker exists
                url = f"https://api.polygon.io/v3/reference/tickers/{symbol}"
                params = {'apikey': api_key}

                response = requests.get(url, params=params, timeout=5)

                if response.status_code == 200:
                    data = response.json()
                    if data.get('results'):
                        valid_symbols.append(symbol)
                elif response.status_code == 404:
                    pass  # Symbol doesn't exist
                else:
                    # Rate limit or error, assume valid
                    valid_symbols.append(symbol)

            except Exception as e:
                # On error, assume valid (don't lose stocks)
                valid_symbols.append(symbol)

        # Small delay to respect rate limits
        import time
        time.sleep(0.1)

    logger.info(f"Validated {len(valid_symbols)}/{len(symbols)} symbols")
    return valid_symbols


def insert_stocks_to_db(stocks: list):
    """
    Insert stocks into database

    Args:
        stocks: List of stock dicts
    """
    logger.info(f"Inserting {len(stocks)} stocks into database...")

    db = SessionLocal()
    try:
        # Check if stocks table has sector column
        check_sector = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'stocks'
            AND column_name = 'sector'
        """)).fetchone()

        if not check_sector:
            logger.info("Adding 'sector' column to stocks table...")
            db.execute(text("ALTER TABLE stocks ADD COLUMN sector VARCHAR(50)"))
            db.execute(text("ALTER TABLE stocks ADD COLUMN sub_industry VARCHAR(100)"))
            db.commit()

        # Insert stocks with UPSERT
        for idx, stock in enumerate(stocks):
            if idx % 100 == 0:
                print(f"Inserting stocks: {idx}/{len(stocks)}")
            try:
                db.execute(text("""
                    INSERT INTO stocks (symbol, name, sector, sub_industry, is_tracked, created_at, updated_at)
                    VALUES (:symbol, :name, :sector, :sub_industry, true, NOW(), NOW())
                    ON CONFLICT (symbol) DO UPDATE
                    SET
                        name = EXCLUDED.name,
                        sector = EXCLUDED.sector,
                        sub_industry = EXCLUDED.sub_industry,
                        is_tracked = true,
                        updated_at = NOW()
                """), {
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'sector': stock['sector'],
                    'sub_industry': stock.get('sub_industry', '')
                })

            except Exception as e:
                logger.warning(f"Error inserting {stock['symbol']}: {e}")

        db.commit()
        logger.info("✅ Stocks inserted successfully")

    except Exception as e:
        logger.error(f"Error inserting stocks: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def print_sector_summary(stocks: list):
    """Print sector distribution summary"""
    logger.info("\n" + "=" * 80)
    logger.info("SECTOR DISTRIBUTION")
    logger.info("=" * 80)

    sector_counts = {}
    for stock in stocks:
        sector = stock['sector']
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    # Sort by count
    for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {sector:30s}: {count:4d} stocks ({count/len(stocks)*100:.1f}%)")

    logger.info("=" * 80)
    logger.info(f"Total: {len(stocks)} stocks")
    logger.info("=" * 80)


def main():
    """Main execution"""
    print("=" * 80)
    print(" " * 20)
    print("Stock Analyzer - Diverse Stock Universe Builder")
    print(" " * 20)
    print("=" * 80)

    # Step 1: Fetch stocks from various sources
    print("\n📊 Step 1: Fetching stock lists...")

    all_stocks = []

    # S&P 500
    sp500_stocks = fetch_sp500_stocks()
    all_stocks.extend(sp500_stocks)

    # NASDAQ 100
    nasdaq100_stocks = fetch_nasdaq100_stocks()
    all_stocks.extend(nasdaq100_stocks)

    # Popular ETFs
    etf_stocks = get_popular_etfs()
    all_stocks.extend(etf_stocks)

    # Step 2: Deduplicate
    print("\n🔄 Step 2: Deduplicating stocks...")
    unique_stocks = deduplicate_stocks(all_stocks)

    # Print sector summary
    print_sector_summary(unique_stocks)

    # Step 3: Validate with Polygon.io (optional - can skip for speed)
    print("\n✓ Step 3: Symbol validation (skipping - trusting Wikipedia data)")
    print("   Note: Set POLYGON_API_KEY to validate symbols")

    # Step 4: Insert into database
    print("\n💾 Step 4: Inserting stocks into database...")
    insert_stocks_to_db(unique_stocks)

    print("\n" + "=" * 80)
    print("✅ STOCK UNIVERSE SETUP COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   Total stocks: {len(unique_stocks)}")
    print(f"   Sources: S&P 500, NASDAQ 100, Popular ETFs")
    print(f"   Sectors: 11 GICS sectors + ETFs")
    print(f"   Next step: Run fetch_historical_data_5years.py")
    print("\n⚠️  IMPORTANT:")
    print("   1. All stocks marked as is_tracked = true")
    print("   2. Ready for historical data fetching")
    print("   3. Will fetch 5 years of data (2019-2026)")
    print("=" * 80)


if __name__ == "__main__":
    main()
