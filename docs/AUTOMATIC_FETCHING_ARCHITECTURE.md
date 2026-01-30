# Automatic Fetching Architecture - Scalable Data Pipeline

**Last Updated**: 2025-10-30
**Status**: Implementation Phase - Week 1 (Infrastructure Setup)
**Timeline**: 4 weeks total
**Owner**: Development Team

---

## 🎯 Executive Summary

This document describes the architecture for scaling StockAnalyzer from 335 stocks to 500+ stocks with automatic hourly data updates, while respecting Polygon.io free tier limits (5 requests/minute). The solution uses **Celery + Redis** for distributed task processing with a **priority-based queue system** and **incremental updates** to minimize API calls.

**Key Innovation**: Smart priority scoring ensures high-activity stocks update hourly while low-activity stocks update daily, spreading ~5,400 daily requests across 24 hours to fit within the 7,200 request/day free tier limit.

---

## 📋 Table of Contents

1. [Problem Statement](#-problem-statement)
2. [Solution Architecture](#-solution-architecture)
3. [Priority System](#-priority-system)
4. [Update Strategy](#-update-strategy)
5. [Docker Infrastructure](#-docker-infrastructure)
6. [Celery Configuration](#-celery-configuration)
7. [Database Schema](#-database-schema)
8. [Task Implementation](#-task-implementation)
9. [Priority Calculator](#-priority-calculator)
10. [New Polygon.io Features](#-new-polygonio-features)
11. [Performance Estimates](#-performance-estimates)
12. [Implementation Plan](#-implementation-plan)
13. [Monitoring & Observability](#-monitoring--observability)
14. [Error Handling](#-error-handling)
15. [Success Metrics](#-success-metrics)

---

## 🚨 Problem Statement

### Current Limitations

1. **Manual Fetching**: All data fetched manually via API endpoints or scripts
2. **No Scalability**: 500 stocks × 6 data types = 3,000 requests = 10 hours (at 5 req/min)
3. **Rate Limits**: Polygon.io free tier = 5 requests/minute = 300 requests/hour
4. **Full Recomputation**: Fetching entire history every time wastes 90%+ of bandwidth
5. **No Prioritization**: All stocks treated equally regardless of activity level

### Requirements

✅ **Automatic hourly updates** for active/high-volume stocks
✅ **Respect rate limits** (stay within Polygon.io free tier)
✅ **Priority-based** (popular stocks update more frequently)
✅ **Incremental updates** (only fetch new data since last update)
✅ **Background processing** (don't block API requests)
✅ **Scalable to 1,000+ stocks** (with paid tier)
✅ **Fault tolerant** (retry failed requests, circuit breakers)
✅ **Observable** (monitoring, logs, alerts)

### Success Criteria

- High-priority stocks: <1 hour data lag
- Medium-priority stocks: <4 hour data lag
- Low-priority stocks: <24 hour data lag
- 95%+ task success rate
- Zero manual intervention required

---

## 🏗️ Solution Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                 APScheduler (Celery Beat)                        │
│                                                                   │
│  Market Hours (9 AM - 4 PM ET):                                 │
│  ├─ Hourly: High-priority stocks (100)                          │
│  ├─ Every 4h: Medium-priority stocks (200)                      │
│  └─ Daily 5 PM: Low-priority stocks (200)                       │
│                                                                   │
│  Metadata Updates (Off-hours):                                  │
│  ├─ Daily 6 PM: Dividends, splits, short interest              │
│  ├─ Daily 7 PM: Pattern detection                               │
│  └─ Daily 3 AM: Priority recalculation                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Redis (Message Broker)                         │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐       │
│  │ Fetcher      │  │ Processor    │  │ Maintenance    │       │
│  │ Queue        │  │ Queue        │  │ Queue          │       │
│  │ Priority:10  │  │ Priority:6   │  │ Priority:2     │       │
│  └──────────────┘  └──────────────┘  └────────────────┘       │
│                                                                   │
│  Result Backend (Cache task results for 1 hour)                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               Celery Worker Pool (7 workers)                     │
│                                                                   │
│  ┌────────────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │ Fetcher Workers    │  │ Processor      │  │ Maintenance  │ │
│  │ (4 workers)        │  │ Workers        │  │ Worker       │ │
│  │                    │  │ (2 workers)    │  │ (1 worker)   │ │
│  │ - fetch_prices     │  │ - detect       │  │ - cleanup    │ │
│  │ - fetch_news       │  │   _patterns    │  │ - calculate  │ │
│  │ - fetch_dividends  │  │ - run_ml       │  │   _priorities│ │
│  │ - fetch_splits     │  │   _predictions │  │ - health     │ │
│  └────────────────────┘  └────────────────┘  └──────────────┘ │
│                                                                   │
│  Rate Limiting: 5 tasks/minute (Polygon API limit)              │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│          PostgreSQL + TimescaleDB (Data Storage)                 │
│                                                                   │
│  ┌───────────────────┐  ┌───────────────────┐  ┌──────────────┐│
│  │ Stock Prices      │  │ Stock Metadata    │  │ Priorities & ││
│  │ (time-series)     │  │ (dividends,       │  │ Tracking     ││
│  │                   │  │  splits, etc.)    │  │              ││
│  │ - StockPrice      │  │ - Dividend        │  │ - StockPriority││
│  │ - CandlestickBar  │  │ - Split           │  │ - StockData  ││
│  │                   │  │ - ShortInterest   │  │   Update     ││
│  │                   │  │ - News            │  │ - TaskExecution││
│  └───────────────────┘  └───────────────────┘  └──────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Component Descriptions

#### 1. **APScheduler (Celery Beat)** - Task Scheduler
- Schedules periodic tasks based on crontab expressions
- Market hours (9 AM - 4 PM ET) for price data
- Off-hours for metadata and maintenance
- Stores schedule in database for persistence

#### 2. **Redis** - Message Broker + Result Backend
- **Message Broker**: Routes tasks to appropriate worker queues
- **Result Backend**: Caches task results for 1 hour
- **Future Use**: Application-level caching (prices, patterns)
- Lightweight, fast, easy to scale

#### 3. **Celery Workers** - Async Task Execution
- **7 total workers** (4 fetcher + 2 processor + 1 maintenance)
- **Priority queues**: High-priority tasks processed first
- **Rate limiting**: Respects Polygon API limits (5 req/min)
- **Retry logic**: Exponential backoff for failed tasks
- **Graceful shutdown**: Finishes current task before exiting

#### 4. **PostgreSQL + TimescaleDB** - Data Persistence
- **Time-series optimization** for stock prices (TimescaleDB extension)
- **Relational data** for stocks, patterns, metadata
- **Priority tracking** for smart scheduling
- **Task execution logs** for monitoring

#### 5. **Flower** - Monitoring Dashboard (http://localhost:5555)
- Real-time worker status
- Task queue depths
- Success/failure rates
- Task duration metrics

---

## 📊 Priority System

### Priority Score Calculation

Each stock receives a **priority score (0-100)** calculated daily based on:

```python
priority_score = (
    volume_percentile * 0.3 +          # Trading volume relative to peers (30%)
    watchlist_count * 2.5 +            # User interest (25% per watchlist)
    active_patterns_count * 5.0 +      # Active chart patterns (50% per pattern)
    atr_percentile * 0.15 +            # Volatility (ATR percentile) (15%)
    (100 - staleness_factor) * 0.10    # Data freshness (10%)
)

# Clamp to 0-100
priority_score = max(0, min(100, priority_score))
```

### Priority Tier Assignment

| Score Range | Tier | Update Frequency | Stock Count (500 total) |
|-------------|------|------------------|--------------------------|
| **70-100** | High | Every hour (market hours) | ~100 (20%) |
| **40-69** | Medium | Every 4 hours | ~200 (40%) |
| **0-39** | Low | Daily (5 PM ET) | ~200 (40%) |

### Priority Factors Explained

**1. Volume Percentile (30% weight)**
- Calculate average daily volume (last 30 days)
- Rank all stocks by volume → percentile
- High-volume stocks = more institutional interest = higher priority

**2. Watchlist Count (25% per watchlist)**
- Number of users watching this stock
- Each watchlist add = +2.5 points to score
- User interest indicates importance

**3. Active Patterns Count (50% per pattern)**
- Count active chart patterns (confidence ≥ 60%)
- Detected in last 30 days, not yet completed
- Each pattern = +5 points to score
- Stocks with patterns need frequent updates

**4. ATR Percentile (15% weight)**
- Calculate 14-day ATR (Average True Range)
- Rank all stocks by ATR → percentile
- High volatility = more price movement = higher priority

**5. Staleness Factor (10% weight)**
- Hours since last update → staleness percentage
- 0 hours = 0% staleness = +10 points
- 24+ hours = 100% staleness = 0 points
- Incentivizes updating stale data

### Example Priority Calculations

**High-Priority Stock (Score: 85)**
- AAPL: High volume (95th percentile) = 28.5
- 2 users watching = 5.0
- 3 active patterns = 15.0
- High volatility (90th percentile) = 13.5
- Updated 2 hours ago = 9.2
- **Total: 71.2** → **High tier**

**Medium-Priority Stock (Score: 52)**
- MID_CAP_STOCK: Medium volume (60th percentile) = 18.0
- 1 user watching = 2.5
- 1 active pattern = 5.0
- Medium volatility (55th percentile) = 8.25
- Updated 6 hours ago = 7.5
- **Total: 41.25** → **Medium tier**

**Low-Priority Stock (Score: 25)**
- SMALL_CAP_STOCK: Low volume (20th percentile) = 6.0
- 0 users watching = 0
- 0 active patterns = 0
- Low volatility (30th percentile) = 4.5
- Updated 12 hours ago = 5.0
- **Total: 15.5** → **Low tier**

### Priority Recalculation Schedule

- **Daily at 3 AM ET** (maintenance window)
- After market close (captures day's volume/patterns)
- Before next trading day (ensures correct priorities)
- Takes ~30-60 seconds for 500 stocks

---

## 🔄 Update Strategy

### Incremental Update Philosophy

**Problem**: Fetching entire history wastes bandwidth
**Solution**: Only fetch data since last update timestamp

### Update Frequency Matrix

| Data Type | High Priority | Medium Priority | Low Priority | Incremental? |
|-----------|---------------|-----------------|--------------|--------------|
| **Prices (1h)** | Every hour (9-4 PM) | Every 4 hours | Daily (5 PM) | ✅ Yes |
| **Prices (1d)** | Daily | Daily | Daily | ✅ Yes |
| **News** | Every 2 hours | Every 8 hours | Weekly | ✅ Yes |
| **Dividends** | Weekly | Weekly | Monthly | ✅ Yes |
| **Splits** | Weekly | Weekly | Monthly | ✅ Yes |
| **Short Interest** | Weekly | Bi-weekly | Monthly | ✅ Yes |
| **Options Activity** | Hourly (market hours) | Daily | N/A | ✅ Yes |
| **Analyst Ratings** | Daily | Weekly | Monthly | ✅ Yes |
| **Market Status** | Hourly | Hourly | Hourly | ❌ No (lightweight) |
| **Pattern Detection** | After price update | After price update | Daily | N/A (internal) |

### Incremental Fetch Logic

```python
# Example: Incremental price fetch
def fetch_stock_prices(stock_id: int, timeframe: str = '1h'):
    # 1. Get last update timestamp
    last_update = db.query(StockDataUpdate).filter(
        StockDataUpdate.stock_id == stock_id,
        StockDataUpdate.data_type == f'prices_{timeframe}'
    ).first()

    # 2. Determine fetch range
    if last_update:
        from_date = last_update.last_update  # Only new data
    else:
        from_date = datetime.now() - timedelta(days=365)  # Initial: 1 year

    to_date = datetime.now()

    # 3. Fetch from Polygon (only new bars)
    prices = polygon_fetcher.fetch_bars(
        symbol=stock.symbol,
        timeframe=timeframe,
        from_timestamp=from_date,
        to_timestamp=to_date
    )

    # 4. Save only non-duplicate bars
    for price in prices:
        if not exists_in_db(price):
            save_to_db(price)

    # 5. Update tracking record
    update_tracking(stock_id, timeframe, to_date, len(prices))
```

### Request Volume Estimates

**Daily Request Budget (Polygon.io Free Tier)**:
- 5 requests/minute × 60 minutes × 24 hours = **7,200 requests/day** ✅

**Actual Daily Usage** (500 stocks):

```
HIGH PRIORITY (100 stocks):
  Prices (1h): 100 stocks × 16 hours (9 AM - 4 PM) = 1,600 requests
  News: 100 stocks × 12 fetches/day (every 2h) = 1,200 requests
  Options: 100 stocks × 8 fetches/day (hourly, market hours) = 800 requests
  Subtotal: 3,600 requests

MEDIUM PRIORITY (200 stocks):
  Prices (1h): 200 stocks × 6 fetches/day (every 4h) = 1,200 requests
  News: 200 stocks × 3 fetches/day (every 8h) = 600 requests
  Subtotal: 1,800 requests

LOW PRIORITY (200 stocks):
  Prices (1d): 200 stocks × 1 fetch/day = 200 requests
  Subtotal: 200 requests

METADATA (all 500 stocks, spread across week):
  Dividends: 500 ÷ 7 = ~70 requests/day
  Splits: 500 ÷ 7 = ~70 requests/day
  Short Interest: 500 ÷ 7 = ~70 requests/day
  Analyst Ratings: 500 ÷ 7 = ~70 requests/day
  Subtotal: ~280 requests/day

MARKET STATUS (global):
  Market status check: 24 requests/day (hourly)

───────────────────────────────────────────────────────────
GRAND TOTAL: ~5,904 requests/day
Percentage of free tier: 82% (5,904 / 7,200)
Safety margin: 18% (~1,300 requests for retries/spikes)
```

**✅ Fits within free tier with 18% safety margin**

### Spreading Requests Across 24 Hours

```
Hourly breakdown (average):
  5,904 requests ÷ 24 hours = 246 requests/hour
  246 requests/hour ÷ 60 minutes = 4.1 requests/minute

✅ WELL BELOW 5 requests/minute limit
```

---

## 🐳 Docker Infrastructure

### Updated docker-compose.yml

Add these services to your existing `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # ... existing services (db, backend, frontend) ...

  # ============================================
  # REDIS - Message Broker + Result Backend
  # ============================================
  redis:
    image: redis:7-alpine
    container_name: stock_analyzer_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: >
      redis-server
      --appendonly yes
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - stock_analyzer_network

  # ============================================
  # CELERY WORKER - Background Task Execution
  # ============================================
  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: stock_analyzer_celery_worker
    restart: unless-stopped
    command: >
      celery -A app.celery_app worker
      --loglevel=info
      --concurrency=7
      --queues=fetcher,processor,maintenance
      --max-tasks-per-child=100
    environment:
      - DATABASE_URL=postgresql://stockuser:stockpass@db:5432/stockanalyzer
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - POLYGON_API_KEY=${POLYGON_API_KEY}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
    networks:
      - stock_analyzer_network

  # ============================================
  # CELERY BEAT - Periodic Task Scheduler
  # ============================================
  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: stock_analyzer_celery_beat
    restart: unless-stopped
    command: >
      celery -A app.celery_app beat
      --loglevel=info
      --scheduler django_celery_beat.schedulers:DatabaseScheduler
    environment:
      - DATABASE_URL=postgresql://stockuser:stockpass@db:5432/stockanalyzer
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - db
      - redis
    volumes:
      - ./backend:/app
    networks:
      - stock_analyzer_network

  # ============================================
  # FLOWER - Celery Monitoring Dashboard
  # ============================================
  flower:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: stock_analyzer_flower
    restart: unless-stopped
    command: >
      celery -A app.celery_app flower
      --port=5555
      --url_prefix=flower
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis
      - celery_worker
    ports:
      - "5555:5555"
    networks:
      - stock_analyzer_network

volumes:
  # ... existing volumes ...
  redis_data:  # NEW

networks:
  stock_analyzer_network:
    driver: bridge
```

### Access Points After Setup

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8080
- **API Docs**: http://localhost:8080/docs
- **Flower Dashboard**: http://localhost:5555 ← **NEW**
- **Redis**: localhost:6379

---

## ⚙️ Celery Configuration

### backend/app/celery_app.py

Create new file `backend/app/celery_app.py`:

```python
"""
Celery application configuration for StockAnalyzer automatic data fetching
"""
from celery import Celery
from celery.schedules import crontab
import os

# Create Celery app
celery_app = Celery(
    'stockanalyzer',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    include=[
        'app.tasks.fetcher_tasks',
        'app.tasks.processor_tasks',
        'app.tasks.maintenance_tasks',
    ]
)

# ============================================
# CELERY CONFIGURATION
# ============================================
celery_app.conf.update(
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    # Timezone (US market timezone)
    timezone='America/New_York',
    enable_utc=True,

    # Task routing (different queues for different task types)
    task_routes={
        'app.tasks.fetcher_tasks.*': {'queue': 'fetcher'},
        'app.tasks.processor_tasks.*': {'queue': 'processor'},
        'app.tasks.maintenance_tasks.*': {'queue': 'maintenance'},
    },

    # Priority system (0-10, higher = more urgent)
    task_queue_max_priority=10,
    task_default_priority=5,

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time (better for rate limiting)
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (prevent memory leaks)

    # Task execution
    task_acks_late=True,  # Acknowledge task after completion, not before
    task_reject_on_worker_lost=True,  # Re-queue if worker dies

    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,

    # Result backend settings
    result_expires=3600,  # Task results expire after 1 hour
    result_backend_transport_options={
        'master_name': 'mymaster',
    },

    # Rate limiting (Polygon.io free tier: 5 requests/minute)
    task_annotations={
        'app.tasks.fetcher_tasks.fetch_stock_prices': {
            'rate_limit': '5/m'  # 5 tasks per minute
        },
        'app.tasks.fetcher_tasks.fetch_stock_news': {
            'rate_limit': '5/m'
        },
        'app.tasks.fetcher_tasks.fetch_stock_metadata': {
            'rate_limit': '5/m'
        },
    },
)

# ============================================
# CELERY BEAT SCHEDULE (Periodic Tasks)
# ============================================
celery_app.conf.beat_schedule = {
    # ────────────────────────────────────────
    # PRICE DATA FETCHING
    # ────────────────────────────────────────

    # High-priority stocks: Every hour during market hours (9 AM - 4 PM ET)
    'fetch-high-priority-stocks-hourly': {
        'task': 'app.tasks.fetcher_tasks.fetch_high_priority_stocks',
        'schedule': crontab(minute=0, hour='9-16'),  # Every hour, 9 AM - 4 PM
        'options': {'queue': 'fetcher', 'priority': 10}
    },

    # Medium-priority stocks: Every 4 hours
    'fetch-medium-priority-stocks-4hourly': {
        'task': 'app.tasks.fetcher_tasks.fetch_medium_priority_stocks',
        'schedule': crontab(minute=0, hour='*/4'),  # 12 AM, 4 AM, 8 AM, 12 PM, 4 PM, 8 PM
        'options': {'queue': 'fetcher', 'priority': 5}
    },

    # Low-priority stocks: Daily at 5 PM (after market close)
    'fetch-low-priority-stocks-daily': {
        'task': 'app.tasks.fetcher_tasks.fetch_low_priority_stocks',
        'schedule': crontab(minute=0, hour=17),  # 5:00 PM ET
        'options': {'queue': 'fetcher', 'priority': 3}
    },

    # ────────────────────────────────────────
    # NEWS & SENTIMENT
    # ────────────────────────────────────────

    # High-priority news: Every 2 hours
    'fetch-high-priority-news': {
        'task': 'app.tasks.fetcher_tasks.fetch_high_priority_news',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
        'options': {'queue': 'fetcher', 'priority': 7}
    },

    # Medium-priority news: Every 8 hours
    'fetch-medium-priority-news': {
        'task': 'app.tasks.fetcher_tasks.fetch_medium_priority_news',
        'schedule': crontab(minute=0, hour='*/8'),  # 12 AM, 8 AM, 4 PM
        'options': {'queue': 'fetcher', 'priority': 4}
    },

    # ────────────────────────────────────────
    # METADATA (Weekly batches)
    # ────────────────────────────────────────

    # Dividends: Weekly on Sunday
    'fetch-dividends-weekly': {
        'task': 'app.tasks.fetcher_tasks.fetch_dividends_batch',
        'schedule': crontab(minute=0, hour=0, day_of_week=0),  # Sunday 12:00 AM
        'options': {'queue': 'fetcher', 'priority': 3}
    },

    # Splits: Weekly on Monday
    'fetch-splits-weekly': {
        'task': 'app.tasks.fetcher_tasks.fetch_splits_batch',
        'schedule': crontab(minute=0, hour=0, day_of_week=1),  # Monday 12:00 AM
        'options': {'queue': 'fetcher', 'priority': 3}
    },

    # Short Interest: Weekly on Tuesday
    'fetch-short-interest-weekly': {
        'task': 'app.tasks.fetcher_tasks.fetch_short_interest_batch',
        'schedule': crontab(minute=0, hour=0, day_of_week=2),  # Tuesday 12:00 AM
        'options': {'queue': 'fetcher', 'priority': 3}
    },

    # Analyst Ratings (Benzinga): Weekly on Wednesday
    'fetch-analyst-ratings-weekly': {
        'task': 'app.tasks.fetcher_tasks.fetch_analyst_ratings_batch',
        'schedule': crontab(minute=0, hour=0, day_of_week=3),  # Wednesday 12:00 AM
        'options': {'queue': 'fetcher', 'priority': 3}
    },

    # ────────────────────────────────────────
    # MARKET STATUS
    # ────────────────────────────────────────

    # Market status: Every hour (lightweight, global check)
    'check-market-status-hourly': {
        'task': 'app.tasks.fetcher_tasks.fetch_market_status',
        'schedule': crontab(minute=0),  # Every hour on the hour
        'options': {'queue': 'fetcher', 'priority': 8}
    },

    # ────────────────────────────────────────
    # PATTERN DETECTION
    # ────────────────────────────────────────

    # High-priority pattern detection: 15 minutes after hourly price fetch
    'detect-patterns-high-priority': {
        'task': 'app.tasks.processor_tasks.detect_patterns_high_priority',
        'schedule': crontab(minute=15, hour='9-16'),  # 9:15 AM - 4:15 PM (15 min after price)
        'options': {'queue': 'processor', 'priority': 7}
    },

    # Medium-priority pattern detection: After 4-hour price fetch
    'detect-patterns-medium-priority': {
        'task': 'app.tasks.processor_tasks.detect_patterns_medium_priority',
        'schedule': crontab(minute=30, hour='*/4'),  # 30 min after price fetch
        'options': {'queue': 'processor', 'priority': 5}
    },

    # Low-priority pattern detection: Daily at 6 PM
    'detect-patterns-low-priority': {
        'task': 'app.tasks.processor_tasks.detect_patterns_low_priority',
        'schedule': crontab(minute=0, hour=18),  # 6:00 PM ET
        'options': {'queue': 'processor', 'priority': 3}
    },

    # ────────────────────────────────────────
    # MAINTENANCE TASKS
    # ────────────────────────────────────────

    # Recalculate stock priorities: Daily at 3 AM
    'recalculate-priorities-daily': {
        'task': 'app.tasks.maintenance_tasks.recalculate_all_priorities',
        'schedule': crontab(minute=0, hour=3),  # 3:00 AM ET
        'options': {'queue': 'maintenance', 'priority': 9}
    },

    # Cleanup old task logs: Daily at 2 AM
    'cleanup-old-tasks-daily': {
        'task': 'app.tasks.maintenance_tasks.cleanup_old_task_logs',
        'schedule': crontab(minute=0, hour=2),  # 2:00 AM ET
        'options': {'queue': 'maintenance', 'priority': 1}
    },

    # Cleanup old price data: Weekly on Saturday
    'cleanup-old-prices-weekly': {
        'task': 'app.tasks.maintenance_tasks.cleanup_old_price_data',
        'schedule': crontab(minute=0, hour=1, day_of_week=6),  # Saturday 1:00 AM
        'options': {'queue': 'maintenance', 'priority': 1}
    },
}

# ============================================
# CELERY SIGNALS (for monitoring/logging)
# ============================================
from celery.signals import task_prerun, task_postrun, task_failure, task_retry

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Log task start"""
    print(f"[TASK START] {task.name} [{task_id}]")

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, retval=None, **extra):
    """Log task completion"""
    print(f"[TASK SUCCESS] {task.name} [{task_id}] - Result: {retval}")

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, **extra):
    """Log task failure"""
    print(f"[TASK FAILURE] {sender.name} [{task_id}] - Error: {exception}")

@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, **extra):
    """Log task retry"""
    print(f"[TASK RETRY] {sender.name} [{task_id}] - Reason: {reason}")

# ============================================
# DEBUG TASK (for testing Celery setup)
# ============================================
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task to verify Celery is working"""
    print(f'Request: {self.request!r}')
    return {'status': 'ok', 'task_id': self.request.id}
```

---

## 🗄️ Database Schema Updates

### Alembic Migration: Add Priority and Tracking Tables

Create migration: `alembic revision --autogenerate -m "add priority and tracking tables"`

```sql
-- ============================================
-- STOCK PRIORITY TRACKING
-- ============================================
CREATE TABLE stock_priorities (
    stock_id INTEGER PRIMARY KEY REFERENCES stocks(id) ON DELETE CASCADE,
    priority_score DECIMAL(5,2) NOT NULL CHECK (priority_score >= 0 AND priority_score <= 100),
    priority_tier VARCHAR(10) NOT NULL CHECK (priority_tier IN ('high', 'medium', 'low')),

    -- Priority factors (for transparency/debugging)
    volume_percentile DECIMAL(5,2),
    watchlist_count INTEGER DEFAULT 0,
    active_patterns_count INTEGER DEFAULT 0,
    atr_percentile DECIMAL(5,2),
    staleness_days INTEGER DEFAULT 0,

    -- Metadata
    last_calculated TIMESTAMP NOT NULL DEFAULT NOW(),
    calculation_version INTEGER DEFAULT 1,  -- Increment when algorithm changes

    -- Indexes
    INDEX idx_priority_tier (priority_tier),
    INDEX idx_priority_score (priority_score DESC)
);

-- ============================================
-- TASK EXECUTION TRACKING (for monitoring)
-- ============================================
CREATE TABLE task_executions (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(255) UNIQUE NOT NULL,  -- Celery task ID
    task_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'started', 'success', 'failure', 'retry')),

    -- Execution timestamps
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,

    -- Task metadata
    worker_name VARCHAR(100),
    queue_name VARCHAR(50),
    priority INTEGER,

    -- Error tracking
    error_message TEXT,
    error_traceback TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Indexes
    INDEX idx_task_name (task_name),
    INDEX idx_status (status),
    INDEX idx_started_at (started_at DESC),
    INDEX idx_created_at (created_at DESC)
);

-- ============================================
-- STOCK DATA UPDATE TRACKING (incremental updates)
-- ============================================
CREATE TABLE stock_data_updates (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    data_type VARCHAR(50) NOT NULL,  -- 'prices_1h', 'prices_1d', 'news', 'dividends', 'splits', etc.

    -- Update timestamps
    last_update TIMESTAMP NOT NULL,
    next_scheduled_update TIMESTAMP,

    -- Update metadata
    records_fetched INTEGER DEFAULT 0,
    fetch_duration_seconds INTEGER,

    -- Error tracking
    last_error TEXT,
    consecutive_failures INTEGER DEFAULT 0,

    -- Metadata
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE (stock_id, data_type),

    -- Indexes
    INDEX idx_next_scheduled (next_scheduled_update),
    INDEX idx_stock_data_type (stock_id, data_type),
    INDEX idx_consecutive_failures (consecutive_failures DESC)
);

-- ============================================
-- TASK QUEUE STATISTICS (for monitoring dashboard)
-- ============================================
CREATE TABLE task_queue_stats (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Queue depths (current)
    fetcher_queue_depth INTEGER DEFAULT 0,
    processor_queue_depth INTEGER DEFAULT 0,
    maintenance_queue_depth INTEGER DEFAULT 0,

    -- Task counts (last hour)
    tasks_completed_last_hour INTEGER DEFAULT 0,
    tasks_failed_last_hour INTEGER DEFAULT 0,
    tasks_retried_last_hour INTEGER DEFAULT 0,

    -- Performance metrics (last hour)
    avg_task_duration_seconds DECIMAL(10,2),
    p50_task_duration_seconds DECIMAL(10,2),
    p95_task_duration_seconds DECIMAL(10,2),
    p99_task_duration_seconds DECIMAL(10,2),

    -- Worker health
    active_workers INTEGER DEFAULT 0,

    -- Indexes
    INDEX idx_timestamp (timestamp DESC)
);

-- ============================================
-- DIVIDENDS (new table for new Polygon endpoint)
-- ============================================
CREATE TABLE dividends (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,

    -- Dividend details
    cash_amount DECIMAL(10,4) NOT NULL,
    dividend_type VARCHAR(50),  -- 'CD' (cash), 'SC' (stock), etc.

    -- Important dates
    declaration_date DATE,
    ex_dividend_date DATE NOT NULL,
    record_date DATE,
    pay_date DATE,

    -- Metadata
    frequency INTEGER,  -- 1=Annual, 4=Quarterly, 12=Monthly
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE (stock_id, ex_dividend_date),

    -- Indexes
    INDEX idx_ex_dividend_date (ex_dividend_date DESC),
    INDEX idx_stock_ex_div (stock_id, ex_dividend_date DESC)
);

-- ============================================
-- STOCK SPLITS (new table for new Polygon endpoint)
-- ============================================
CREATE TABLE stock_splits (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,

    -- Split details
    execution_date DATE NOT NULL,
    split_from INTEGER NOT NULL,  -- e.g., 1 in a 2-for-1 split
    split_to INTEGER NOT NULL,    -- e.g., 2 in a 2-for-1 split

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE (stock_id, execution_date),

    -- Indexes
    INDEX idx_execution_date (execution_date DESC),
    INDEX idx_stock_execution (stock_id, execution_date DESC)
);

-- ============================================
-- SHORT INTEREST (new table for new Polygon endpoint)
-- ============================================
CREATE TABLE short_interest (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,

    -- Short interest details
    settlement_date DATE NOT NULL,
    short_interest_quantity BIGINT NOT NULL,
    short_interest_quantity_change BIGINT,
    short_interest_quantity_pct_change DECIMAL(10,4),

    -- Metadata
    market_code VARCHAR(10),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE (stock_id, settlement_date),

    -- Indexes
    INDEX idx_settlement_date (settlement_date DESC),
    INDEX idx_stock_settlement (stock_id, settlement_date DESC),
    INDEX idx_short_quantity (short_interest_quantity DESC)
);

-- ============================================
-- ANALYST RATINGS (new table for Benzinga data)
-- ============================================
CREATE TABLE analyst_ratings (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,

    -- Rating details
    date DATE NOT NULL,
    firm_name VARCHAR(100),
    analyst_name VARCHAR(100),

    -- Rating action
    rating_current VARCHAR(50),  -- 'Buy', 'Hold', 'Sell', etc.
    rating_prior VARCHAR(50),
    action VARCHAR(50),  -- 'Initiated', 'Upgraded', 'Downgraded', 'Maintained', 'Reiterated'

    -- Price targets
    price_target_current DECIMAL(10,2),
    price_target_prior DECIMAL(10,2),

    -- Metadata
    url TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Indexes
    INDEX idx_date (date DESC),
    INDEX idx_stock_date (stock_id, date DESC),
    INDEX idx_action (action)
);
```

### SQLAlchemy Models

Create new models in `backend/app/models/`:

#### backend/app/models/stock_priorities.py
```python
from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class StockPriority(Base):
    __tablename__ = 'stock_priorities'

    stock_id = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), primary_key=True)
    priority_score = Column(DECIMAL(5,2), nullable=False)
    priority_tier = Column(String(10), nullable=False)

    # Priority factors
    volume_percentile = Column(DECIMAL(5,2))
    watchlist_count = Column(Integer, default=0)
    active_patterns_count = Column(Integer, default=0)
    atr_percentile = Column(DECIMAL(5,2))
    staleness_days = Column(Integer, default=0)

    # Metadata
    last_calculated = Column(DateTime, nullable=False, server_default=func.now())
    calculation_version = Column(Integer, default=1)

class StockDataUpdate(Base):
    __tablename__ = 'stock_data_updates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False)
    data_type = Column(String(50), nullable=False)

    # Timestamps
    last_update = Column(DateTime, nullable=False)
    next_scheduled_update = Column(DateTime)

    # Metadata
    records_fetched = Column(Integer, default=0)
    fetch_duration_seconds = Column(Integer)

    # Error tracking
    last_error = Column(String)
    consecutive_failures = Column(Integer, default=0)

    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

class TaskExecution(Base):
    __tablename__ = 'task_executions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(255), unique=True, nullable=False)
    task_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)

    # Execution
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)

    # Task metadata
    worker_name = Column(String(100))
    queue_name = Column(String(50))
    priority = Column(Integer)

    # Error tracking
    error_message = Column(String)
    error_traceback = Column(String)
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
```

#### backend/app/models/dividends.py
```python
from sqlalchemy import Column, Integer, String, DECIMAL, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class Dividend(Base):
    __tablename__ = 'dividends'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False)

    # Dividend details
    cash_amount = Column(DECIMAL(10,4), nullable=False)
    dividend_type = Column(String(50))

    # Important dates
    declaration_date = Column(Date)
    ex_dividend_date = Column(Date, nullable=False)
    record_date = Column(Date)
    pay_date = Column(Date)

    # Metadata
    frequency = Column(Integer)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
```

#### backend/app/models/splits.py
```python
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class StockSplit(Base):
    __tablename__ = 'stock_splits'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False)

    # Split details
    execution_date = Column(Date, nullable=False)
    split_from = Column(Integer, nullable=False)
    split_to = Column(Integer, nullable=False)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
```

---

*Continue in next message due to length...*

**Status**: Document created, continuing with Task Implementation section...
