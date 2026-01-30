# Polygon.io API Endpoints Reference

## Currently Used Endpoints

All endpoints are accessed through the `PolygonFetcher` class in `backend/app/services/polygon_fetcher.py`.

### 1. **get_ticker_details()** ✅
**Purpose:** Get basic stock information
**Returns:** Company name, sector, industry
**Usage:** Stock metadata for database population
**API Endpoint:** `/v3/reference/tickers/{ticker}`

```python
fetcher.fetch_stock_info('AAPL')
# Returns: {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': '...', 'industry': '...'}
```

---

### 2. **get_aggs()** ✅
**Purpose:** Fetch historical OHLC price data (bars/candles)
**Returns:** Time-series price data with open, high, low, close, volume
**Usage:** Primary endpoint for all historical price fetching
**API Endpoint:** `/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}`

**Supports all timeframes:**
- Intraday: 1m, 5m, 15m, 30m, 1h, 2h, 4h
- Daily and above: 1d, 1wk, 1mo

```python
fetcher.fetch_historical_data('AAPL', period='1y', interval='1h')
# Returns: List of price bars with timestamp, open, high, low, close, volume
```

**Used by:** Celery fetch tasks (high/medium/low priority)

---

### 3. **get_last_trade()** ✅
**Purpose:** Get the most recent trade for a stock
**Returns:** Latest trade price, timestamp, size
**Usage:** Real-time price updates
**API Endpoint:** `/v2/last/trade/{ticker}`

```python
fetcher.get_latest_price('AAPL')
# Returns: {'symbol': 'AAPL', 'price': 178.25, 'timestamp': ..., 'volume': ...}
```

---

### 4. **get_previous_close()** ✅
**Purpose:** Get previous trading day's close price
**Returns:** Previous day OHLC data
**Usage:** Daily comparisons, gap analysis
**API Endpoint:** `/v2/aggs/ticker/{ticker}/prev`

```python
fetcher.get_previous_close('AAPL')
# Returns: {'timestamp': ..., 'open': ..., 'high': ..., 'low': ..., 'close': ..., 'volume': ...}
```

---

### 5. **get_market_status()** ✅ 🆕
**Purpose:** Get real-time market status
**Returns:** Current status of all exchanges (NYSE, NASDAQ, OTC)
**Usage:** Determine if market is open before fetching data
**API Endpoint:** `/v1/marketstatus/now`

```python
fetcher.get_market_status()
# Returns: {
#   'market': 'stocks',
#   'exchanges': {'nyse': 'open', 'nasdaq': 'open', 'otc': 'closed'},
#   'early_hours': False,
#   'after_hours': False
# }
```

**Used by:** `market_hours.py` utility for smart fetch scheduling

---

### 6. **get_market_holidays()** ✅ 🆕
**Purpose:** Get upcoming market holidays and early close days
**Returns:** List of holidays with dates, names, exchange status
**Usage:** Prevent fetching on holidays, detect early close days
**API Endpoint:** `/v1/marketstatus/upcoming`

```python
fetcher.get_market_holidays()
# Returns: [
#   {'date': '2025-12-25', 'name': 'Christmas Day', 'status': 'closed', 'exchange': 'NYSE'},
#   {'date': '2025-12-24', 'name': 'Christmas Eve', 'status': 'early-close', ...},
#   ...
# ]
```

**Features:**
- 24-hour caching to minimize API calls
- Used by all Celery fetch tasks
- Automatically updated, no manual maintenance needed

---

## Additional Endpoints (Direct REST API Calls)

These endpoints use direct HTTP requests instead of the Polygon Python SDK.

### 7. **fetch_news()** 📰
**Purpose:** Fetch recent news articles for a stock
**API Endpoint:** `/v2/reference/news`
**Usage:** Sentiment analysis (future feature)

```python
fetcher.fetch_news('AAPL', limit=10)
# Returns: List of news articles with title, description, URL, published date
```

---

### 8. **fetch_dividends()** 💰
**Purpose:** Fetch dividend payment history
**API Endpoint:** `/v3/reference/dividends`
**Usage:** Fundamental analysis (future feature)

```python
fetcher.fetch_dividends('AAPL', limit=50)
# Returns: List of dividend payments with ex-date, pay date, amount
```

---

### 9. **fetch_splits()** ✂️
**Purpose:** Fetch stock split history
**API Endpoint:** `/v3/reference/splits`
**Usage:** Price adjustment, historical analysis

```python
fetcher.fetch_splits('AAPL', limit=50)
# Returns: List of stock splits with execution date, split ratio
```

---

## API Rate Limits

**Current Plan:** Stocks Starter
**Rate Limit:** 100 requests/minute
**Implementation:** 1-second delay between requests (`rate_limit_delay = 1`)

## Environment Configuration

```bash
# .env file
POLYGON_API_KEY=your_api_key_here
```

**Get your free API key:** https://polygon.io/

---

## Summary Statistics

- **Total Endpoints Used:** 9
- **Core Endpoints (SDK):** 6
- **Direct REST Calls:** 3
- **New in Latest Update:** 2 (market_status, market_holidays)
- **Primary Data Source:** `get_aggs()` - handles all historical price fetching

---

## Future Expansion Possibilities

Polygon.io offers many more endpoints that could enhance the system:

1. **Options Data** - Real-time options chains and Greeks
2. **Technical Indicators** - Pre-calculated SMA, EMA, RSI from Polygon
3. **Forex Data** - Currency pair analysis
4. **Crypto Data** - Cryptocurrency price tracking
5. **Screener API** - Built-in stock screening
6. **Snapshot API** - Bulk data for all tickers at once

---

**Last Updated:** 2025-10-31
**Documentation:** https://polygon.io/docs/stocks
