# Polygon.io Market Hours Integration

## Overview

The StockAnalyzer system now uses **Polygon.io's real-time market status and holidays API** instead of hardcoded holiday lists. This ensures accurate, up-to-date market status checking and prevents unnecessary data fetching during market closures.

## What Changed

### Before
- Hardcoded US market holidays for 2024-2025
- Hardcoded early close days
- Manual updates required each year
- No real-time market status checking

### After
- Real-time market status from Polygon.io API
- Automatic holiday detection from Polygon
- 24-hour caching to minimize API calls
- Fallback to time-based checking if API unavailable

## Key Features

### 1. Real-Time Market Status
The system can now query Polygon.io for the current market status:
```python
from app.utils.market_hours import is_market_open

# Check if market is currently open (uses Polygon API)
is_open = is_market_open(use_polygon=True)
```

### 2. Automatic Holiday Detection
Market holidays are fetched from Polygon and cached for 24 hours:
```python
from app.utils.market_hours import is_market_holiday

# Check if today is a market holiday
if is_market_holiday():
    print("Market is closed for holiday")
```

### 3. Smart Caching
- Holidays are cached for 24 hours to minimize API calls
- Cache refreshes automatically when expired
- Graceful fallback if Polygon API is unavailable

## Implementation Details

### New Methods in `polygon_fetcher.py`

#### `get_market_status()`
Fetches current market status from Polygon.io:
```python
{
    'market': 'stocks',
    'serverTime': '2025-10-31T10:30:00Z',
    'exchanges': {
        'nyse': 'open',
        'nasdaq': 'open'
    },
    'early_hours': False,
    'after_hours': False
}
```

#### `get_market_holidays()`
Fetches upcoming market holidays:
```python
[
    {
        'date': '2025-12-25',
        'name': 'Christmas Day',
        'status': 'closed',
        'exchange': 'NYSE'
    },
    ...
]
```

### Updated Functions in `market_hours.py`

#### `is_market_open(check_time, include_extended, use_polygon)`
- Now accepts `use_polygon` parameter (default: True)
- Queries Polygon for real-time NYSE/NASDAQ status
- Falls back to time-based checking if Polygon unavailable

#### `is_market_holiday(check_date)`
- Fetches holidays from Polygon API
- Uses 24-hour cache to minimize API calls
- Returns True if date is a market holiday

#### `get_market_status_info()`
- Enhanced to include Polygon real-time data
- Returns comprehensive status including exchange-level details
- Used by `/market-status` API endpoint

## API Endpoints

### `/health/market-status`
Returns comprehensive market status:
```json
{
  "status": "open",
  "is_open": true,
  "is_holiday": false,
  "is_weekend": false,
  "is_early_close": false,
  "status_detail": "Regular Trading Hours",
  "current_time_et": "2025-10-31 10:30:00 EST",
  "market_open_time": "09:30",
  "market_close_time": "16:00",
  "polygon": {
    "exchanges": {
      "nyse": "open",
      "nasdaq": "open"
    },
    "server_time": "2025-10-31T10:30:00Z",
    "early_hours": false,
    "after_hours": false
  }
}
```

## Benefits

### 1. Always Accurate
- No manual updates needed for holidays
- Automatically knows about special market closures
- Real-time exchange status

### 2. Efficient
- 24-hour caching minimizes API calls
- Only 1-2 Polygon API calls per day per instance
- Graceful degradation if API unavailable

### 3. Future-Proof
- Works for any future year automatically
- Handles exchange-specific holidays
- Includes early close detection

## Usage in Celery Tasks

All three fetch tasks now check market status before fetching:

```python
@celery_app.task(bind=True, max_retries=3)
def fetch_high_priority_stocks(self):
    # Check if market allows fetching (uses Polygon)
    market_check = should_fetch_data(priority='high')

    if not market_check['should_fetch']:
        logger.info(f"⏸️ Skipping fetch - {market_check['reason']}")
        return {
            'status': 'skipped',
            'reason': market_check['reason']
        }

    # Proceed with fetch...
```

## Testing

To test the market status integration:

```bash
# Test market status endpoint
curl http://localhost:8080/health/market-status

# Check Celery logs during weekend/holiday
# Should see: "⏸️ Skipping fetch - Market closed - Weekend"
```

## Configuration

No additional configuration needed! The system uses the existing `POLYGON_API_KEY` environment variable.

## Fallback Behavior

If Polygon API is unavailable:
1. Uses time-based checking (9:30 AM - 4:00 PM ET)
2. Weekend detection still works
3. Holiday cache used if available
4. Logs warning and continues normally

## Future Enhancements

Potential improvements:
1. Display market status badge in frontend dashboard
2. Show countdown to market open/close
3. Alert users when market opens
4. Pre-market and after-hours trading indicators

## Files Modified

1. `backend/app/services/polygon_fetcher.py` - Added market status/holidays methods
2. `backend/app/utils/market_hours.py` - Integrated Polygon API
3. `backend/app/tasks/fetcher_tasks.py` - Uses market hours checking
4. `backend/app/api/routes/health.py` - Enhanced market-status endpoint

---

**Last Updated:** 2025-10-31
**Polygon API Version:** v3 (Market Reference Data)
