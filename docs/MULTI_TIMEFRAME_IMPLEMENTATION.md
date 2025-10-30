# Multi-Timeframe Infrastructure - Complete Implementation Guide

## Overview

This guide provides a **complete end-to-end implementation** for adding multi-timeframe support to StockAnalyzer, enabling:
- Storage of 1-minute, 5-minute, 15-minute, 1-hour, 4-hour, daily, and weekly data
- Efficient querying and caching
- Multi-timeframe pattern detection
- Frontend timeframe selection

---

## Current Architecture Analysis

### **Current State:**
- ✅ `stock_prices` table stores OHLCV data
- ✅ Primary key: `(timestamp, stock_id)`
- ✅ Works for daily data
- ❌ **No timeframe column** - can't distinguish 1H vs 1D data
- ❌ All queries assume daily data
- ❌ Polygon fetcher hardcoded to daily

### **Problem:**
If we fetch both 1H and 1D data for AAPL, they'll conflict:
```sql
-- Both would try to insert with same structure
INSERT INTO stock_prices (stock_id, timestamp, ...)
VALUES (1, '2025-10-29 10:00:00', ...);  -- 1H bar
VALUES (1, '2025-10-29 00:00:00', ...);  -- 1D bar
-- No way to tell them apart!
```

---

## Solution: Multi-Timeframe Database Architecture

### **Design Decisions:**

**Option 1: Single Table with Timeframe Column** ⭐ (RECOMMENDED)
```sql
stock_prices (
    stock_id,
    timestamp,
    timeframe,  -- NEW: '1m', '5m', '15m', '1h', '4h', '1d', '1w'
    open, high, low, close, volume
)
PRIMARY KEY (stock_id, timeframe, timestamp)
```

**Pros:**
- Simple schema
- Easy to query: `WHERE timeframe = '1h'`
- One table to manage
- TimescaleDB hypertable works perfectly

**Cons:**
- Large table (but TimescaleDB handles this)
- Need to always specify timeframe in queries

**Option 2: Separate Tables per Timeframe**
```sql
stock_prices_1h (stock_id, timestamp, ohlcv...)
stock_prices_4h (stock_id, timestamp, ohlcv...)
stock_prices_1d (stock_id, timestamp, ohlcv...)
```

**Pros:**
- Clear separation
- Smaller individual tables

**Cons:**
- 7+ tables to manage
- Duplicate code for each table
- Complex migrations
- Harder to query across timeframes

**Decision: Use Option 1** (Single table with timeframe column)

---

## Implementation Plan

### **Phase 1: Database Schema** (30 min)
### **Phase 2: Database Models** (30 min)
### **Phase 3: Migration Script** (20 min)
### **Phase 4: Polygon Fetcher** (45 min)
### **Phase 5: Backend API** (60 min)
### **Phase 6: Frontend** (60 min)

**Total Time: ~4 hours**

---

## Phase 1: Database Schema Update

### **Step 1.1: Create Migration SQL**

Create: `backend/app/alembic/versions/YYYYMMDD_add_multi_timeframe.py`

```python
"""add multi-timeframe support

Revision ID: add_multi_timeframe
Revises: <previous_revision>
Create Date: 2025-10-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_multi_timeframe'
down_revision = '<get from latest migration>'  # Check alembic/versions/
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add timeframe column (nullable initially)
    op.add_column('stock_prices',
        sa.Column('timeframe', sa.String(10), nullable=True)
    )

    # Step 2: Set existing data to '1d' (daily)
    op.execute("UPDATE stock_prices SET timeframe = '1d' WHERE timeframe IS NULL")

    # Step 3: Make timeframe NOT NULL
    op.alter_column('stock_prices', 'timeframe', nullable=False)

    # Step 4: Add CHECK constraint for valid timeframes
    op.create_check_constraint(
        'check_valid_timeframe',
        'stock_prices',
        "timeframe IN ('1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1mo')"
    )

    # Step 5: Drop old primary key
    op.drop_constraint('stock_prices_pkey', 'stock_prices', type_='primary')

    # Step 6: Create new composite primary key (stock_id, timeframe, timestamp)
    op.create_primary_key(
        'stock_prices_pkey',
        'stock_prices',
        ['stock_id', 'timeframe', 'timestamp']
    )

    # Step 7: Create indexes for performance
    # Index for querying by stock + timeframe
    op.create_index(
        'idx_stock_timeframe',
        'stock_prices',
        ['stock_id', 'timeframe', 'timestamp']
    )

    # Index for timeframe queries
    op.create_index(
        'idx_timeframe',
        'stock_prices',
        ['timeframe']
    )

    # Step 8: Update TimescaleDB hypertable (if using)
    # Recreate hypertable with new partitioning
    op.execute("""
        -- Convert back to regular table
        SELECT remove_continuous_aggregate_policy('stock_prices', if_exists => true);

        -- Drop old hypertable
        SELECT drop_chunks('stock_prices', older_than => interval '0 seconds', if_exists => true);

        -- Recreate hypertable with timeframe
        SELECT create_hypertable(
            'stock_prices',
            'timestamp',
            partitioning_column => 'timeframe',
            number_partitions => 10,
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        );
    """)

    print("✅ Multi-timeframe migration completed successfully")


def downgrade():
    # Reverse the migration
    # Step 1: Drop new constraints/indexes
    op.drop_constraint('check_valid_timeframe', 'stock_prices', type_='check')
    op.drop_index('idx_stock_timeframe', table_name='stock_prices')
    op.drop_index('idx_timeframe', table_name='stock_prices')

    # Step 2: Restore old primary key
    op.drop_constraint('stock_prices_pkey', 'stock_prices', type_='primary')
    op.create_primary_key(
        'stock_prices_pkey',
        'stock_prices',
        ['stock_id', 'timestamp']
    )

    # Step 3: Remove timeframe column
    op.drop_column('stock_prices', 'timeframe')

    print("⚠️ Multi-timeframe migration rolled back")
```

---

## Phase 2: Update Database Models

### **Step 2.1: Update StockPrice Model**

Edit: `backend/app/models/stock.py`

```python
class StockPrice(Base):
    __tablename__ = "stock_prices"

    # Composite primary key: (stock_id, timeframe, timestamp)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True)
    timeframe = Column(String(10), primary_key=True)  # NEW: '1m', '5m', '15m', '1h', '4h', '1d', '1w'
    timestamp = Column(TIMESTAMP, primary_key=True)

    id = Column(Integer, server_default=text("nextval('stock_prices_id_seq'::regclass)"))
    open = Column(DECIMAL(12, 4))
    high = Column(DECIMAL(12, 4))
    low = Column(DECIMAL(12, 4))
    close = Column(DECIMAL(12, 4))
    volume = Column(BigInteger)
    adjusted_close = Column(DECIMAL(12, 4))

    # Add constraint
    __table_args__ = (
        CheckConstraint(
            "timeframe IN ('1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1mo')",
            name="check_valid_timeframe"
        ),
    )

    # Relationship
    stock = relationship("Stock", back_populates="prices")
```

### **Step 2.2: Create Timeframe Enum**

Create: `backend/app/models/timeframe.py`

```python
from enum import Enum

class Timeframe(str, Enum):
    """Supported timeframes for OHLCV data"""

    # Intraday
    ONE_MINUTE = "1m"
    FIVE_MINUTE = "5m"
    FIFTEEN_MINUTE = "15m"
    THIRTY_MINUTE = "30m"
    ONE_HOUR = "1h"
    TWO_HOUR = "2h"
    FOUR_HOUR = "4h"

    # Daily and above
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1mo"

    @classmethod
    def is_intraday(cls, timeframe: str) -> bool:
        """Check if timeframe is intraday (< 1 day)"""
        return timeframe in [cls.ONE_MINUTE, cls.FIVE_MINUTE, cls.FIFTEEN_MINUTE,
                            cls.THIRTY_MINUTE, cls.ONE_HOUR, cls.TWO_HOUR, cls.FOUR_HOUR]

    @classmethod
    def to_polygon_params(cls, timeframe: str) -> tuple:
        """
        Convert timeframe to Polygon.io API parameters

        Returns: (multiplier, timespan)
        """
        timeframe_map = {
            cls.ONE_MINUTE: (1, 'minute'),
            cls.FIVE_MINUTE: (5, 'minute'),
            cls.FIFTEEN_MINUTE: (15, 'minute'),
            cls.THIRTY_MINUTE: (30, 'minute'),
            cls.ONE_HOUR: (1, 'hour'),
            cls.TWO_HOUR: (2, 'hour'),
            cls.FOUR_HOUR: (4, 'hour'),
            cls.ONE_DAY: (1, 'day'),
            cls.ONE_WEEK: (1, 'week'),
            cls.ONE_MONTH: (1, 'month'),
        }
        return timeframe_map.get(timeframe, (1, 'day'))

    @classmethod
    def get_default_lookback(cls, timeframe: str) -> int:
        """
        Get recommended lookback period (in days) for each timeframe
        """
        lookback_map = {
            cls.ONE_MINUTE: 7,      # 1 week for 1m bars
            cls.FIVE_MINUTE: 14,    # 2 weeks
            cls.FIFTEEN_MINUTE: 30, # 1 month
            cls.THIRTY_MINUTE: 60,  # 2 months
            cls.ONE_HOUR: 90,       # 3 months
            cls.TWO_HOUR: 180,      # 6 months
            cls.FOUR_HOUR: 365,     # 1 year
            cls.ONE_DAY: 1825,      # 5 years
            cls.ONE_WEEK: 3650,     # 10 years
            cls.ONE_MONTH: 7300,    # 20 years
        }
        return lookback_map.get(timeframe, 365)
```

---

## Phase 3: Run Migration

### **Step 3.1: Generate Migration**

```bash
# If using Alembic
cd backend
alembic revision --autogenerate -m "add multi-timeframe support"

# Or create manually as shown above
```

### **Step 3.2: Review and Run**

```bash
# Review the generated migration
cat app/alembic/versions/*_add_multi_timeframe.py

# Run migration
alembic upgrade head

# Verify
docker-compose exec database psql -U stockanalyzer -d stockanalyzer -c "\d stock_prices"
```

Expected output:
```
Table "public.stock_prices"
Column      | Type         | Modifiers
------------+--------------+-----------
stock_id    | integer      | not null
timeframe   | varchar(10)  | not null  <-- NEW
timestamp   | timestamp    | not null
open        | decimal(12,4)|
high        | decimal(12,4)|
...

Indexes:
    "stock_prices_pkey" PRIMARY KEY (stock_id, timeframe, timestamp)
    "idx_stock_timeframe" btree (stock_id, timeframe, timestamp)
    "idx_timeframe" btree (timeframe)

Check constraints:
    "check_valid_timeframe" CHECK (timeframe IN ('1m', '5m', ...))
```

---

## Phase 4: Update Polygon Fetcher

### **Step 4.1: Enhance Polygon Fetcher**

Edit: `backend/app/services/polygon_fetcher.py`

```python
from app.models.timeframe import Timeframe

class PolygonFetcher:
    # ... existing code ...

    def fetch_historical_data_multi_timeframe(
        self,
        symbol: str,
        timeframe: str = "1d",
        lookback_days: int = None,
        max_retries: int = 3
    ) -> Optional[List[Dict]]:
        """
        Fetch historical data for specific timeframe

        Args:
            symbol: Stock ticker
            timeframe: Timeframe (1m, 5m, 15m, 1h, 4h, 1d, 1w)
            lookback_days: Days of history (auto-calculated if None)
            max_retries: Retry attempts

        Returns:
            List of OHLCV dictionaries with 'timeframe' field
        """
        # Get recommended lookback if not specified
        if lookback_days is None:
            lookback_days = Timeframe.get_default_lookback(timeframe)

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        # Convert timeframe to Polygon params
        multiplier, timespan = Timeframe.to_polygon_params(timeframe)

        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching {timeframe} data for {symbol} "
                          f"({lookback_days} days, {multiplier}{timespan})")

                # Fetch from Polygon
                aggs = self.client.get_aggs(
                    ticker=symbol.upper(),
                    multiplier=multiplier,
                    timespan=timespan,
                    from_=start_date.strftime('%Y-%m-%d'),
                    to=end_date.strftime('%Y-%m-%d'),
                    limit=50000
                )

                if not aggs or len(aggs) == 0:
                    logger.warning(f"No {timeframe} data for {symbol}")
                    return None

                # Convert to our format (with timeframe)
                prices = []
                for bar in aggs:
                    timestamp = datetime.fromtimestamp(bar.timestamp / 1000)

                    prices.append({
                        'timestamp': timestamp,
                        'timeframe': timeframe,  # NEW: Include timeframe
                        'open': float(bar.open),
                        'high': float(bar.high),
                        'low': float(bar.low),
                        'close': float(bar.close),
                        'volume': int(bar.volume),
                        'adjusted_close': float(bar.close)
                    })

                logger.info(f"✅ Fetched {len(prices)} {timeframe} bars for {symbol}")
                return prices

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")

                if attempt < max_retries - 1:
                    time.sleep(self.rate_limit_delay)
                else:
                    logger.error(f"Failed to fetch {timeframe} data for {symbol}")
                    return None

    def fetch_multiple_timeframes(
        self,
        symbol: str,
        timeframes: List[str] = ["1h", "4h", "1d"]
    ) -> Dict[str, List[Dict]]:
        """
        Fetch data for multiple timeframes

        Returns: {
            '1h': [...],
            '4h': [...],
            '1d': [...]
        }
        """
        results = {}

        for tf in timeframes:
            logger.info(f"Fetching {tf} data for {symbol}...")
            data = self.fetch_historical_data_multi_timeframe(symbol, tf)

            if data:
                results[tf] = data

            # Rate limiting (free tier: 5 requests/min)
            if len(timeframes) > 1:
                time.sleep(self.rate_limit_delay)

        return results
```

---

## Phase 5: Backend API Updates

### **Step 5.1: Create Timeframe Service**

Create: `backend/app/services/timeframe_service.py`

```python
from sqlalchemy.orm import Session
from app.models.stock import StockPrice
from app.models.timeframe import Timeframe
from typing import List, Dict
from datetime import datetime, timedelta
import pandas as pd

class TimeframeService:
    """Service for multi-timeframe data operations"""

    @staticmethod
    def get_price_data(
        db: Session,
        stock_id: int,
        timeframe: str = "1d",
        lookback_days: int = None
    ) -> pd.DataFrame:
        """
        Get price data for specific timeframe

        Args:
            db: Database session
            stock_id: Stock ID
            timeframe: Timeframe (1m, 5m, 1h, 4h, 1d, etc.)
            lookback_days: Days of history (default from Timeframe enum)

        Returns:
            DataFrame with OHLCV data
        """
        # Get default lookback if not specified
        if lookback_days is None:
            lookback_days = Timeframe.get_default_lookback(timeframe)

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=lookback_days)

        # Query database
        prices = db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id,
            StockPrice.timeframe == timeframe,
            StockPrice.timestamp >= cutoff_date
        ).order_by(StockPrice.timestamp).all()

        # Convert to DataFrame
        if not prices:
            return pd.DataFrame()

        df = pd.DataFrame([{
            'timestamp': p.timestamp,
            'open': float(p.open),
            'high': float(p.high),
            'low': float(p.low),
            'close': float(p.close),
            'volume': int(p.volume)
        } for p in prices])

        df.set_index('timestamp', inplace=True)
        return df

    @staticmethod
    def get_multiple_timeframes(
        db: Session,
        stock_id: int,
        timeframes: List[str] = ["1h", "4h", "1d"]
    ) -> Dict[str, pd.DataFrame]:
        """
        Get data for multiple timeframes

        Returns: {
            '1h': DataFrame,
            '4h': DataFrame,
            '1d': DataFrame
        }
        """
        result = {}
        for tf in timeframes:
            df = TimeframeService.get_price_data(db, stock_id, tf)
            if not df.empty:
                result[tf] = df
        return result

    @staticmethod
    def save_price_data(
        db: Session,
        stock_id: int,
        timeframe: str,
        prices: List[Dict]
    ) -> int:
        """
        Save price data to database

        Returns: Number of records saved
        """
        saved_count = 0

        for price_data in prices:
            # Check if exists
            existing = db.query(StockPrice).filter(
                StockPrice.stock_id == stock_id,
                StockPrice.timeframe == timeframe,
                StockPrice.timestamp == price_data['timestamp']
            ).first()

            if existing:
                # Update
                existing.open = price_data['open']
                existing.high = price_data['high']
                existing.low = price_data['low']
                existing.close = price_data['close']
                existing.volume = price_data['volume']
                existing.adjusted_close = price_data.get('adjusted_close', price_data['close'])
            else:
                # Insert
                new_price = StockPrice(
                    stock_id=stock_id,
                    timeframe=timeframe,
                    timestamp=price_data['timestamp'],
                    open=price_data['open'],
                    high=price_data['high'],
                    low=price_data['low'],
                    close=price_data['close'],
                    volume=price_data['volume'],
                    adjusted_close=price_data.get('adjusted_close', price_data['close'])
                )
                db.add(new_price)
                saved_count += 1

        db.commit()
        return saved_count
```

---

**This is Part 1 of the implementation guide. Would you like me to continue with:**
- **Part 2**: API Endpoints, Frontend Integration, Testing?
- Or start implementing Phase 1 (Database Migration) now?

Let me know and I'll proceed!
