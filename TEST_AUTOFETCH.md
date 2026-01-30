# Testing Auto-Fetching System

This guide will help you test the complete auto-fetching system with adaptive incremental updates.

---

## Prerequisites

Make sure Docker containers are running:
```bash
docker-compose up -d
```

---

## Step 1: Apply Database Migration

Add priority fields to the stocks table:

```bash
docker-compose exec backend alembic upgrade head
```

**Expected output**: `INFO  [alembic.runtime.migration] Running upgrade ... -> 20251030_priority`

---

## Step 2: Clear Price Data (Optional - for clean test)

⚠️ **WARNING**: This deletes all existing price data!

```bash
docker-compose exec database psql -U stockuser -d stock_analyzer -c "TRUNCATE TABLE stock_prices;"
```

**Expected output**: `TRUNCATE TABLE`

---

## Step 3: Set Default Priorities

Since there's no price data yet, assign default priorities:

```bash
docker-compose exec backend python backend/scripts/set_default_priorities.py even
```

**Expected output**:
```
Setting default priorities for 500 stocks
✅ Set priorities: 100 high, 200 medium, 200 low
📊 Final distribution:
   🔥 High: 100 stocks
   ⚡ Medium: 200 stocks
   📊 Low: 200 stocks
```

---

## Step 4: Test Single Stock Fetch (First Run)

Test with AAPL (should fetch 24h of data since table is empty):

```bash
docker-compose exec backend python -c "
from app.tasks.fetcher_tasks import test_fetch_single_stock
import json
result = test_fetch_single_stock.apply(args=['AAPL', '1h']).get()
print(json.dumps(result, indent=2))
"
```

**Expected output**:
```json
{
  "status": "success",
  "symbol": "AAPL",
  "timeframe": "1h",
  "from_date": "2025-10-29T14:00:00+00:00",  // 24h ago
  "to_date": "2025-10-30T14:00:00+00:00",    // now
  "last_timestamp": null,
  "bars_fetched": 24,
  "bars_inserted": 24,
  "bars_updated": 0
}
```

✅ **This proves**: No existing data → fetches 24h lookback

---

## Step 5: Test Single Stock Fetch (Second Run)

Run the same command again (should only fetch new data):

```bash
docker-compose exec backend python -c "
from app.tasks.fetcher_tasks import test_fetch_single_stock
import json
result = test_fetch_single_stock.apply(args=['AAPL', '1h']).get()
print(json.dumps(result, indent=2))
"
```

**Expected output**:
```json
{
  "status": "success",
  "symbol": "AAPL",
  "timeframe": "1h",
  "from_date": "2025-10-30T13:00:00+00:00",  // 1h before last bar
  "to_date": "2025-10-30T14:00:00+00:00",
  "last_timestamp": "2025-10-30T14:00:00+00:00",
  "bars_fetched": 2,
  "bars_inserted": 1,
  "bars_updated": 1  // Overlap bar (13:00) was updated
}
```

✅ **This proves**: Data exists → only fetches since last timestamp with 1h overlap

---

## Step 6: Test High-Priority Batch Fetch

Fetch all high-priority stocks (~100 stocks):

```bash
docker-compose exec backend python -c "
from app.tasks.fetcher_tasks import fetch_high_priority_stocks
result = fetch_high_priority_stocks.apply().get()
print(f'✅ Stocks processed: {result[\"stocks_processed\"]}')
print(f'✅ Success: {result[\"success_count\"]}')
print(f'❌ Errors: {result[\"error_count\"]}')
print(f'📊 Bars inserted: {result[\"total_bars_inserted\"]}')
print(f'📊 Bars updated: {result[\"total_bars_updated\"]}')
"
```

**Expected output**:
```
✅ Stocks processed: 100
✅ Success: 100
❌ Errors: 0
📊 Bars inserted: 2400  (100 stocks × 24 bars)
📊 Bars updated: 0
```

⏱️ **Time**: ~100 seconds (1s delay between requests)

---

## Step 7: Monitor in Flower Dashboard

Open http://localhost:5555 to see:
- Active tasks
- Task history
- Success/failure rates
- Task duration

---

## Step 8: Verify Data in Database

Check that data was stored correctly:

```bash
docker-compose exec database psql -U stockuser -d stock_analyzer -c "
SELECT
    timeframe,
    COUNT(*) as total_bars,
    COUNT(DISTINCT stock_id) as unique_stocks,
    MIN(timestamp) as earliest_bar,
    MAX(timestamp) as latest_bar
FROM stock_prices
GROUP BY timeframe
ORDER BY timeframe;
"
```

**Expected output**:
```
 timeframe | total_bars | unique_stocks |     earliest_bar     |      latest_bar
-----------+------------+---------------+----------------------+----------------------
 1h        |       2500 |           101 | 2025-10-29 14:00:00 | 2025-10-30 14:00:00
```

---

## Step 9: Test Incremental Update (Third Run)

Wait 1 hour and run the fetch again to see it only fetch 1 new bar per stock:

```bash
# Wait 1 hour...

docker-compose exec backend python -c "
from app.tasks.fetcher_tasks import fetch_high_priority_stocks
result = fetch_high_priority_stocks.apply().get()
print(f'📊 Bars inserted: {result[\"total_bars_inserted\"]}')
print(f'📊 Bars updated: {result[\"total_bars_updated\"]}')
"
```

**Expected output**:
```
📊 Bars inserted: 100  (1 new bar per stock)
📊 Bars updated: 100   (1 overlap bar per stock)
```

✅ **This proves**: Adaptive incremental fetching is working!

---

## Step 10: Calculate Real Priorities

Once you have price data, recalculate priorities based on actual statistics:

```bash
docker-compose exec backend python -c "
from app.tasks.maintenance_tasks import recalculate_all_priorities
result = recalculate_all_priorities.apply().get()
print(f'✅ High priority: {result[\"high_priority\"]} stocks')
print(f'✅ Medium priority: {result[\"medium_priority\"]} stocks')
print(f'✅ Low priority: {result[\"low_priority\"]} stocks')
"
```

This will reassign priorities based on:
- Volume
- Volatility
- Pattern count
- Recent activity

---

## Step 11: Restart Services

Restart to ensure all services pick up the new priorities:

```bash
docker-compose restart backend celery_worker celery_beat
```

---

## ✅ Success Criteria

- [x] Migration applied successfully
- [x] Default priorities set
- [x] First fetch gets 24h of data (no existing data)
- [x] Second fetch gets only new data (incremental)
- [x] Batch fetch processes all high-priority stocks
- [x] Data stored correctly in database
- [x] Flower dashboard shows tasks
- [x] Real priorities calculated from actual data

---

## 🚀 What Happens Next

The system will now automatically:
- **Every hour (9 AM - 4 PM)**: Fetch high-priority stocks
- **Every 4 hours**: Fetch medium-priority stocks
- **Daily at 5 PM**: Fetch low-priority stocks
- **Daily at 3 AM**: Recalculate all priorities

You can monitor everything in Flower: http://localhost:5555

---

## 📊 API Usage

With 500 stocks split into priorities:
- High (100 stocks): 17,600 calls/month
- Medium (200 stocks): 8,800 calls/month
- Low (200 stocks): 4,400 calls/month
- **Total: ~31,000 calls/month** (31% of your 100k limit!)

---

## 🐛 Troubleshooting

**Issue**: "No high-priority stocks found"
- **Fix**: Run `set_default_priorities.py` script

**Issue**: "No data returned from Polygon"
- **Fix**: Check your API key in `.env` file
- **Fix**: Verify stock symbol exists

**Issue**: Task fails with rate limit error
- **Fix**: Wait 60 seconds and retry (429 error)

**Issue**: Priorities don't change
- **Fix**: Run `recalculate_all_priorities` manually
