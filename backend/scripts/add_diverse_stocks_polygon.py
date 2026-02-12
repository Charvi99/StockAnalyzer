#!/usr/bin/env python3
"""
Add 500-600 Diverse Stocks using Polygon.io API

Uses Polygon.io's stock screener API to get:
- S&P 500 stocks
- Large cap stocks
- Multiple sectors

Requirements:
- Paid Polygon.io API key (needed for screener API)
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

# Polygon.io API key
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')

if not POLYGON_API_KEY:
    logger.error("POLYGON_API_KEY not found in environment variables!")
    sys.exit(1)


# GICS Sector Mapping
SECTOR_MAPPING = {
    'Technology': ['Technology', 'Software', 'Semiconductors', 'IT Services', 'Internet'],
    'Health Care': ['Health Care', 'Pharmaceuticals', 'Biotechnology', 'Medical Devices', 'Healthcare'],
    'Financials': ['Financials', 'Banks', 'Insurance', 'Capital Markets', 'Finance'],
    'Consumer Discretionary': ['Consumer Discretionary', 'Retail', 'Automotive', 'Media', 'Leisure'],
    'Communication Services': ['Communication Services', 'Telecommunications', 'Telecom'],
    'Industrials': ['Industrials', 'Manufacturing', 'Aerospace', 'Construction', 'Industrial'],
    'Consumer Staples': ['Consumer Staples', 'Food & Beverage', 'Household Products'],
    'Energy': ['Energy', 'Oil & Gas', 'Renewable Energy', 'Petroleum'],
    'Utilities': ['Utilities', 'Electric Utilities', 'Gas Utilities'],
    'Real Estate': ['Real Estate', 'REIT'],
    'Materials': ['Materials', 'Chemicals', 'Mining', 'Paper & Forest'],
}

SECTOR_KEYWORDS = {
    'Technology': ['tech', 'software', 'semiconductor', 'internet', 'cloud', 'data', 'network'],
    'Health Care': ['pharm', 'medical', 'health', 'biotech', 'drug', 'hospital'],
    'Financials': ['bank', 'financial', 'insurance', 'credit', 'payment', 'capital'],
    'Consumer Discretionary': ['retail', 'auto', 'consumer', 'media', 'entertainment', 'leisure'],
    'Communication Services': ['telecom', 'communication', 'wireless', 'broadband'],
    'Industrials': ['industrial', 'manufactur', 'aerospace', 'construction', 'machinery'],
    'Consumer Staples': ['food', 'beverage', 'household', 'tobacco', 'grocery'],
    'Energy': ['oil', 'gas', 'energy', 'petroleum', 'renewable', 'solar', 'wind'],
    'Utilities': ['utility', 'electric', 'water', 'gas utility'],
    'Real Estate': ['real estate', 'reit', 'property'],
    'Materials': ['chemical', 'mining', 'material', 'metal', 'paper'],
}

def map_sector(description: str, sector: str = None) -> str:
    """Map description to GICS sector"""
    if sector:
        sector_lower = sector.lower()
        for gics_sector, keywords in SECTOR_KEYWORDS.items():
            if any(kw in sector_lower for kw in keywords):
                return gics_sector

    if description:
        desc_lower = description.lower()
        for gics_sector, keywords in SECTOR_KEYWORDS.items():
            if any(kw in desc_lower for kw in keywords):
                return gics_sector

    return 'Unknown'


def fetch_polygon_stocks() -> list:
    """
    Fetch stocks from Polygon.io screener API

    Returns:
        List of stock dicts
    """
    logger.info("Fetching stocks from Polygon.io...")

    base_url = "https://api.polygon.io/v3/reference/tickers"

    params = {
        'type': 'CS',  # Common Stock
        'market': 'stocks',
        'active': 'true',
        'limit': 1000,
        'apiKey': POLYGON_API_KEY,
        'sort': 'market_cap',
        'order': 'desc',
    }

    all_stocks = []
    url = base_url

    # Fetch multiple pages
    page_count = 0
    max_pages = 20  # Get up to 20,000 stocks

    while page_count < max_pages:
        response = requests.get(url, params=params, timeout=30)

        if response.status_code != 200:
            logger.error(f"API error: {response.status_code}")
            break

        data = response.json()

        if not data.get('results'):
            break

        for item in data['results']:
            try:
                # Filter for US stocks only
                if item.get('locale') != 'us':
                    continue

                # Get basic info
                symbol = item.get('ticker')
                name = item.get('name')
                description = item.get('description', '')
                market_cap = item.get('market_cap', 0)

                # Filter for stocks with meaningful market cap
                if not symbol or not name or market_cap < 100000000:  # > $100M
                    continue

                # Skip preferred stocks and units
                if any(x in symbol.upper() for x in ['-P', '-U', '-R', '-WS', '-WT']):
                    continue

                # Map sector
                sector = map_sector(
                    description,
                    item.get('sector_name')
                )

                all_stocks.append({
                    'symbol': symbol,
                    'name': name,
                    'sector': sector,
                    'sub_industry': item.get('sector_name', 'Unknown')[:100],
                    'market_cap': market_cap,
                    'source': 'Polygon.io'
                })

            except Exception as e:
                continue

        logger.info(f"Fetched page {page_count + 1}, total stocks so far: {len(all_stocks)}")

        # Check if there's a next page
        next_url = data.get('next_url')
        if not next_url:
            break

        url = next_url + f"&apiKey={POLYGON_API_KEY}"
        page_count += 1

    logger.info(f"✓ Fetched {len(all_stocks)} stocks from Polygon.io")
    return all_stocks


def get_popular_etfs() -> list:
    """Get list of popular ETFs"""
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

        # Sector ETFs
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


def select_top_diverse_stocks(all_stocks: list, target_count: int = 500) -> list:
    """
    Select top stocks with sector diversification

    Args:
        all_stocks: List of all stocks
        target_count: Target number of stocks

    Returns:
        List of selected stocks
    """
    logger.info(f"Selecting top {target_count} diverse stocks...")

    # Sort by market cap
    sorted_stocks = sorted(all_stocks, key=lambda x: x.get('market_cap', 0), reverse=True)

    # Select stocks with sector diversity
    selected = []
    sector_counts = {sector: 0 for sector in SECTOR_MAPPING.keys()}
    sector_counts['Unknown'] = 0
    sector_counts['ETF'] = 0

    # First pass: Get top from each sector
    for stock in sorted_stocks:
        sector = stock['sector']

        # Ensure we get at least some from each sector
        if sector_counts[sector] < 50:  # Max 50 per sector initially
            selected.append(stock)
            sector_counts[sector] += 1

            if len(selected) >= target_count:
                break

    logger.info(f"Selected {len(selected)} stocks")
    return selected


def deduplicate_stocks(all_stocks: list) -> list:
    """Remove duplicates"""
    logger.info("Deduplicating stocks...")

    seen = {}
    for stock in all_stocks:
        symbol = stock['symbol']
        if symbol not in seen:
            seen[symbol] = stock

    deduplicated = list(seen.values())
    logger.info(f"Deduplicated: {len(all_stocks)} → {len(deduplicated)} unique symbols")
    return deduplicated


def insert_stocks_to_db(stocks: list):
    """Insert stocks into database"""
    logger.info(f"Inserting {len(stocks)} stocks into database...")

    db = SessionLocal()
    try:
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
                    'sub_industry': stock.get('sub_industry', '')[:100]
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
    """Print sector distribution"""
    logger.info("\n" + "=" * 80)
    logger.info("SECTOR DISTRIBUTION")
    logger.info("=" * 80)

    sector_counts = {}
    for stock in stocks:
        sector = stock['sector']
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {sector:30s}: {count:4d} stocks ({count/len(stocks)*100:.1f}%)")

    logger.info("=" * 80)
    logger.info(f"Total: {len(stocks)} stocks")
    logger.info("=" * 80)


def main():
    """Main execution"""
    print("=" * 80)
    print(" " * 20)
    print("Stock Analyzer - Diverse Stock Universe Builder (Polygon.io)")
    print(" " * 20)
    print("=" * 80)

    # Step 1: Fetch from Polygon.io
    print("\n📊 Step 1: Fetching stocks from Polygon.io...")
    polygon_stocks = fetch_polygon_stocks()

    # Step 2: Add ETFs
    print("\n📊 Step 2: Adding popular ETFs...")
    etf_stocks = get_popular_etfs()

    # Combine
    all_stocks = polygon_stocks + etf_stocks

    # Step 3: Select top diverse stocks
    print("\n🔄 Step 3: Selecting top diverse stocks...")
    selected_stocks = select_top_diverse_stocks(all_stocks, target_count=500)

    # Add ETFs back in
    selected_stocks = [s for s in selected_stocks if s['source'] != 'ETF'] + etf_stocks

    # Step 4: Deduplicate
    print("\n🔄 Step 4: Deduplicating...")
    unique_stocks = deduplicate_stocks(selected_stocks)

    # Print summary
    print_sector_summary(unique_stocks)

    # Step 5: Insert into database
    print("\n💾 Step 5: Inserting stocks into database...")
    insert_stocks_to_db(unique_stocks)

    print("\n" + "=" * 80)
    print("✅ STOCK UNIVERSE SETUP COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   Total stocks: {len(unique_stocks)}")
    print(f"   Sources: Polygon.io API + ETFs")
    print(f"   Sectors: 11 GICS sectors + ETFs")
    print(f"   Next step: Run fetch_historical_data_5years.py")
    print("\n⚠️  IMPORTANT:")
    print("   1. All stocks marked as is_tracked = true")
    print("   2. Ready for historical data fetching")
    print("   3. Will fetch 5 years of data (2019-2026)")
    print("=" * 80)


if __name__ == "__main__":
    main()
