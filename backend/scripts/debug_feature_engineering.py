"""
Debug Feature Engineering Issues

This script tests feature engineering on a few stocks to see what's failing.
"""

import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import your existing services
from app.services.technical_indicators import TechnicalIndicators
from app.services.chart_patterns import ChartPatternDetector
from app.services.candlestick_patterns import CandlestickPatternDetector
from app.services.market_regime import MarketRegimeService
from app.services.volume_analyzer import VolumeAnalyzer

# Database connection
DATABASE_URL = 'postgresql://stockuser:stockpass123@database:5432/stock_analyzer'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_stock_prices(stock_id: int, timeframe: str = '1d', lookback_days: int = 200) -> pd.DataFrame:
    """Fetch price data for a stock"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)

    query = text("""
        SELECT timestamp, open, high, low, close, volume
        FROM stock_prices
        WHERE stock_id = :stock_id
          AND timeframe = :timeframe
          AND timestamp >= :start_date
          AND timestamp <= :end_date
        ORDER BY timestamp ASC
    """)

    df = pd.read_sql(
        query,
        engine,
        params={'stock_id': stock_id, 'timeframe': timeframe, 'start_date': start_date, 'end_date': end_date}
    )

    if df.empty:
        return None

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    return df


def test_stock(stock_id: int):
    """Test feature engineering for a single stock"""
    print(f"\n{'='*80}")
    print(f"Testing Stock ID: {stock_id}")
    print(f"{'='*80}")

    db = SessionLocal()

    try:
        # Get price data
        print("1. Fetching price data...")
        df = get_stock_prices(stock_id)

        if df is None:
            print("   ❌ No price data found")
            return False

        print(f"   ✅ Found {len(df)} days of data")

        if len(df) < 60:
            print(f"   ❌ Insufficient data (need 60+, have {len(df)})")
            return False

        # Test technical indicators
        print("2. Testing technical indicators...")
        try:
            indicators = TechnicalIndicators.calculate_all_indicators(df)

            if indicators is None or indicators.empty:
                print("   ❌ TechnicalIndicators returned None/Empty")
                return False

            print(f"   ✅ Technical indicators calculated: {len(indicators.columns)} columns")
            print(f"      Columns: {list(indicators.columns)[:5]}...")

        except Exception as e:
            print(f"   ❌ TechnicalIndicators failed: {e}")
            return False

        # Test chart patterns
        print("3. Testing chart patterns...")
        try:
            chart_detector = ChartPatternDetector(df)
            chart_patterns = chart_detector.detect_all_patterns()
            print(f"   ✅ Chart patterns detected: {len(chart_patterns)} patterns")
        except Exception as e:
            print(f"   ❌ Chart patterns failed: {e}")

        # Test candlestick patterns
        print("4. Testing candlestick patterns...")
        try:
            cs_detector = CandlestickPatternDetector(df)
            cs_patterns = cs_detector.detect_all_patterns()
            print(f"   ✅ Candlestick patterns detected: {len(cs_patterns)} patterns")
        except Exception as e:
            print(f"   ❌ Candlestick patterns failed: {e}")

        # Test market regime
        print("5. Testing market regime...")
        try:
            regime_service = MarketRegimeService(db)
            regime = regime_service.detect_market_regime(stock_id)
            print(f"   ✅ Market regime detected: {regime}")
        except Exception as e:
            print(f"   ❌ Market regime failed: {e}")

        print("\n✅ All tests passed for this stock!")
        return True

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        db.close()


def main():
    """Test a few stocks to see what's failing"""
    print("=" * 80)
    print("🔍 Feature Engineering Debug")
    print("=" * 80)

    # Get stocks with 60+ days of 1d data
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT stock_id
            FROM (
                SELECT stock_id, COUNT(*) as data_count
                FROM stock_prices
                WHERE timeframe = '1d'
                GROUP BY stock_id
                HAVING COUNT(*) >= 60
                ORDER BY data_count DESC
            ) subquery
            LIMIT 10
        """))
        stock_ids = [row[0] for row in result]
    finally:
        db.close()

    print(f"\n📊 Testing {len(stock_ids)} stocks with most data...")

    success_count = 0
    fail_count = 0

    for stock_id in stock_ids:
        if test_stock(stock_id):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*80}")
    print(f"📊 SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Successful: {success_count}/{len(stock_ids)}")
    print(f"❌ Failed: {fail_count}/{len(stock_ids)}")


if __name__ == "__main__":
    main()
