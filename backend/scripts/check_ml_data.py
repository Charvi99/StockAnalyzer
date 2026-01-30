"""
Check if ML training data is ready
"""

from sqlalchemy import create_engine, text
import pandas as pd

engine = create_engine('postgresql://stockuser:stockpass123@database:5432/stock_analyzer')

# Check if 1d data exists
query1 = "SELECT COUNT(*) FROM stock_prices WHERE timeframe = '1d'"
count_1d = pd.read_sql(query1, engine).iloc[0,0]

# Check if 1h data exists
query2 = "SELECT COUNT(*) FROM stock_prices WHERE timeframe = '1h'"
count_1h = pd.read_sql(query2, engine).iloc[0,0]

# Get data quality stats
query3 = '''
    SELECT
        timeframe,
        COUNT(DISTINCT stock_id) as total_stocks,
        COUNT(*) as total_records,
        COUNT(CASE WHEN record_count >= 60 THEN 1 END) as ml_ready
    FROM (
        SELECT stock_id, timeframe, COUNT(*) as record_count
        FROM stock_prices
        GROUP BY stock_id, timeframe
    ) subquery
    GROUP BY timeframe
'''

stats = pd.read_sql(query3, engine)

print("=" * 80)
print("📊 ML DATA CHECK")
print("=" * 80)
print(f"\n1d data points: {count_1d:,}")
print(f"1h data points: {count_1h:,}")

print("\n📈 Data by Timeframe:")
print(stats.to_string(index=False))

print("\n" + "=" * 80)
if count_1d > 100000:
    print("✅ 1d data available - ready for feature engineering!")
    print("   Run: cd /app/scripts && python 01_feature_engineering.py")
elif count_1d > 0:
    print("⚠️  Some 1d data exists, but may need more")
    print("   Current: {:,} records".format(count_1d))
else:
    print("⚠️  No 1d data - need to aggregate 1h to 1d first")
    print("   Run: docker-compose exec backend python scripts/aggregate_timeframes.py")

print("=" * 80)
