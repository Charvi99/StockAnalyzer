#!/usr/bin/env python3
"""
Fetch SEC CIK Mappings from EDGAR

This script downloads the complete SEC company ticker to CIK mapping
and stores it in the database.

CIK (Central Index Key) is the SEC's unique identifier for companies.
Required for fetching SEC filings.

Usage:
    docker-compose exec backend python scripts/fetch_sec_cik_mapping.py

Data Source:
    https://www.sec.gov/Files/edgar/data/company_tickers.json
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import logging
import re
import time
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

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


# SEC EDGAR endpoints
# We use the browse-edgar CGI endpoint to look up CIKs by ticker
SEC_EDGAR_BROWSE_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
USER_AGENT = "StockAnalyzer stock-analyzer@example.com"


def fetch_sec_cik_by_ticker(ticker: str) -> dict:
    """
    Fetch SEC CIK for a single ticker using EDGAR browse endpoint

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dictionary with cik and title, or None if not found
    """
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html'
    }

    params = {
        'action': 'getcompany',
        'CIK': ticker.upper(),
        'owner': 'exclude',
        'count': '1'
    }

    try:
        response = requests.get(SEC_EDGAR_BROWSE_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        # Extract CIK from HTML response (format: CIK=0000320193)
        cik_match = re.search(r'CIK=(\d{10})', response.text)

        if not cik_match:
            return None

        cik = cik_match.group(1)

        # Try to extract company name
        title_match = re.search(r'<span class="companyName">([^<]+)</span>', response.text)
        title = title_match.group(1).strip() if title_match else ticker

        return {
            'cik': cik,
            'title': title
        }

    except Exception as e:
        logger.debug(f"Error fetching CIK for {ticker}: {e}")
        return None


def fetch_sec_tickers() -> dict:
    """
    Fetch SEC company ticker to CIK mapping (no longer available as bulk file)
    This is now a placeholder - we look up CIKs individually

    Returns:
        Empty dictionary (use fetch_sec_cik_by_ticker instead)
    """
    print("NOTE: SEC no longer provides bulk ticker-to-CIK mapping file")
    print("CIKs will be looked up individually for each stock")
    return {}


def update_stocks_with_cik() -> int:
    """
    Update stocks table with CIK mappings using individual lookups

    Returns:
        Number of stocks updated
    """
    db = SessionLocal()
    updated_count = 0
    not_found = []

    try:
        # Get all tracked stocks that don't have CIK yet
        result = db.execute(text("""
            SELECT id, symbol, sec_cik
            FROM stocks
            WHERE is_tracked = true
        """))

        stocks = result.fetchall()
        total_stocks = len(stocks)

        print(f"\n📊 Looking up CIKs for {total_stocks} stocks...")
        print(f"⏱️  This will take ~{total_stocks * 0.5:.0f} seconds\n")

        from tqdm import tqdm

        for stock_id, symbol, existing_cik in tqdm(stocks, desc="Fetching CIKs"):
            # Skip if already has CIK
            if existing_cik:
                updated_count += 1
                continue

            # Look up CIK for this ticker
            ticker = symbol.upper()
            time.sleep(0.5)  # Rate limiting: 2 requests per second
            result = fetch_sec_cik_by_ticker(ticker)

            if result:
                cik = result['cik']
                title = result['title']

                # Update stock with CIK
                db.execute(text("""
                    UPDATE stocks
                    SET sec_cik = :cik,
                        official_name = :title
                    WHERE id = :stock_id
                """), {
                    "stock_id": stock_id,
                    "cik": cik,
                    "title": title
                })

                updated_count += 1
            else:
                not_found.append(ticker)

        db.commit()
        print(f"\n✅ Updated {updated_count} stocks with CIK mappings")

        if not_found:
            print(f"\n⚠️  CIK not found for {len(not_found)} stocks:")
            for ticker in not_found[:10]:
                print(f"   - {ticker}")
            if len(not_found) > 10:
                print(f"   ... and {len(not_found) - 10} more")

        # Show some examples
        print("\n📊 Sample CIK mappings:")
        result = db.execute(text("""
            SELECT symbol, sec_cik, official_name
            FROM stocks
            WHERE sec_cik IS NOT NULL
            LIMIT 10
        """))

        for row in result:
            print(f"  {row[0]:<6} CIK: {row[1]} - {row[2][:50] if row[2] else 'N/A'}...")

        return updated_count

    except Exception as e:
        db.rollback()
        print(f"❌ Error updating stocks: {e}")
        import traceback
        traceback.print_exc()
        return 0
    finally:
        db.close()


def check_cik_coverage() -> dict:
    """
    Check CIK coverage in database

    Returns:
        Statistics dictionary
    """
    db = SessionLocal()

    try:
        # Count total tracked stocks
        result = db.execute(text("""
            SELECT COUNT(*) FROM stocks WHERE is_tracked = true
        """))
        total_stocks = result.fetchone()[0]

        # Count stocks with CIK
        result = db.execute(text("""
            SELECT COUNT(*) FROM stocks
            WHERE is_tracked = true AND sec_cik IS NOT NULL
        """))
        with_cik = result.fetchone()[0]

        coverage = {
            'total_stocks': total_stocks,
            'with_cik': with_cik,
            'coverage_pct': (with_cik / total_stocks * 100) if total_stocks > 0 else 0
        }

        return coverage

    finally:
        db.close()


def main():
    """Main function"""
    print("=" * 80)
    print(" " * 20)
    print("StockAnalyzer - SEC CIK Mapping Fetcher")
    print(" " * 20)
    print("=" * 80)

    # Check current coverage
    print("\n📊 Current CIK coverage:")
    coverage = check_cik_coverage()
    print(f"   Total tracked stocks: {coverage['total_stocks']}")
    print(f"   With CIK mapping: {coverage['with_cik']}")
    print(f"   Coverage: {coverage['coverage_pct']:.1f}%")

    # Update database with individual lookups
    print("\n💾 Updating database with CIK mappings...")
    updated = update_stocks_with_cik()

    # Check new coverage
    print("\n📊 New CIK coverage:")
    new_coverage = check_cik_coverage()
    print(f"   Total tracked stocks: {new_coverage['total_stocks']}")
    print(f"   With CIK mapping: {new_coverage['with_cik']}")
    print(f"   Coverage: {new_coverage['coverage_pct']:.1f}%")

    print(f"\n{'='*80}")
    print(f"✅ CIK Mapping Complete!")
    print(f"{'='*80}")
    print(f"\n📊 Results:")
    print(f"   Stocks updated: {updated}")
    print(f"   Coverage improvement: {new_coverage['coverage_pct'] - coverage['coverage_pct']:+.1f}%")
    print(f"\n💡 Next steps:")
    print(f"   1. Run: python scripts/fetch_sec_form4.py")
    print(f"   2. This will fetch insider trading data for all stocks")
    print(f"   3. Expected time: 2-4 hours for initial fetch")


if __name__ == "__main__":
    main()
