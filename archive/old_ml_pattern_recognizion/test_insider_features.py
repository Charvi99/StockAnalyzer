#!/usr/bin/env python3
"""Test SEC Form 4 Insider Features Module"""

import sys
sys.path.insert(0, '/app/ml-training')

from ml_framework.insider_features import InsiderFeatures
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import pandas as pd

DATABASE_URL = "postgresql://stockuser:stockpass123@database:5432/stock_analyzer"
engine = create_engine(DATABASE_URL)

print("=" * 80)
print("Testing SEC Form 4 Insider Features Module")
print("=" * 80)

# Get AAPL stock_id
with engine.connect() as conn:
    result = conn.execute(text("SELECT id FROM stocks WHERE symbol = 'AAPL'"))
    stock_id = result.fetchone()[0]

print(f"\nTesting with stock_id: {stock_id} (AAPL)")

# Check what data we have
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT
            COUNT(*) as total_trades,
            COUNT(*) FILTER (WHERE transaction_type = 'BUY') as buys,
            COUNT(*) FILTER (WHERE transaction_type = 'SELL') as sells,
            MIN(trade_date) as earliest,
            MAX(trade_date) as latest
        FROM insider_trades
        WHERE stock_id = :stock_id AND is_congressional = false
    """), {"stock_id": stock_id})

    data_info = result.fetchone()
    print(f"\nSEC Form 4 trades available:")
    print(f"  Total: {data_info[0]}")
    print(f"  Buys: {data_info[1]}")
    print(f"  Sells: {data_info[2]}")
    print(f"  Date range: {data_info[3]} to {data_info[4]}")

# Test feature calculation
end_date = datetime.now()
start_date = end_date - timedelta(days=60)

print(f"\nCalculating features from {start_date.date()} to {end_date.date()}")

feature_dates = pd.date_range(start_date, end_date, freq='D')
features = InsiderFeatures.calculate_features_for_stock(
    stock_id, start_date, end_date, feature_dates
)

print(f"\nFeatures shape: {features.shape}")
print(f"\nFeature columns ({len(features.columns)}):")
for i, col in enumerate(features.columns, 1):
    print(f"  {i:2}. {col}")

print(f"\nSample data (last 5 days):")
print(features.tail(5))

# Check non-zero values
non_zero_counts = (features != 0).sum()
print(f"\nNon-zero feature values:")
for col in features.columns:
    count = non_zero_counts.get(col, 0)
    if count > 0:
        print(f"  {col}: {count} non-zero values")

print("\n" + "=" * 80)
print("✅ SEC Form 4 Insider Features module working!")
print("=" * 80)
