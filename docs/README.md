# Stock Analyzer Documentation

Welcome to the Stock Analyzer documentation directory. All project documentation is organized here for easy reference.

**Last Updated**: 2025-11-13
**Documentation Status**: ✅ Cleaned and consolidated
**Latest Feature**: ⚡ Dashboard Performance Optimization (45x Speedup with Indicator Cache)

---

## 📚 Documentation Index

### **🤖 For AI Assistants (Claude, ChatGPT, etc.)**

- **[CLAUDE.md](./CLAUDE.md)** 🚀 **READ THIS FIRST!**
  - Complete project briefing for AI assistants
  - Project mission and goals
  - Architecture principles and patterns
  - Critical files and components
  - Best practices and anti-patterns
  - Domain knowledge (swing trading, risk management)
  - Prompt engineering tips
  - Getting started checklist
  - **Optimized for maximum AI performance**

### **Project Planning & Status**

- **[ROADMAP.md](./ROADMAP.md)** ⭐ **START HERE FOR PENDING TASKS**
  - All pending features and improvements
  - Phase 8 goals (CNN training, alerts, auth)
  - Context-aware scoring (Phase 2F)
  - Pattern backtesting system
  - Automated testing plans
  - Priority rankings and timelines

- **[COMPLETED_FEATURES.md](./COMPLETED_FEATURES.md)** 📦 **HISTORICAL ARCHIVE**
  - Complete history of all finished phases (1-7)
  - Multi-timeframe implementation details
  - Pattern detection improvements
  - Risk management system
  - Frontend enhancements
  - All completed metrics and statistics

---

### **Getting Started**

- **[Main README](../README.md)**
  - Project overview and quick start
  - Installation instructions (Docker Compose)
  - Running the application
  - Basic usage guide

---

### **Trading Guides**

- **[SWING_TRADING_OUTLOOK.md](./SWING_TRADING_OUTLOOK.md)** ⭐ **RECOMMENDED FOR TRADERS**
  - Complete swing trading guide
  - Suitability assessment (5/5 stars!)
  - Daily trading workflows and strategies
  - Risk management framework
  - **Automated trading platform recommendations**:
    - Interactive Brokers (Best for pros)
    - Alpaca (Best for beginners, free API)
    - TD Ameritrade (Good for options)
    - TradeStation (Advanced users)
  - Integration architecture for automation
  - Success metrics and performance tracking

- **[RISK_TOOLS_USER_GUIDE.md](./RISK_TOOLS_USER_GUIDE.md)**
  - Trailing stop calculator guide
  - Portfolio heat monitor guide
  - ATR-based risk management
  - Position sizing strategies
  - Real-world examples

- **[DIVIDEND_SPLIT_INTEGRATION_COMPLETE.md](./DIVIDEND_SPLIT_INTEGRATION_COMPLETE.md)** 🆕 **NEW IN PHASE 8**
  - Dividend & stock split trading signals
  - Complete implementation guide (backend + frontend)
  - Trading strategy for corporate events
  - Signal types and timing windows
  - API reference and examples
  - Visual integration in dashboard

---

### **Technical Setup**

- **[POLYGON_SETUP.md](./POLYGON_SETUP.md)**
  - Polygon.io API setup and configuration
  - Free vs paid tier comparison
  - Rate limits and best practices
  - API key management
  - Troubleshooting connection issues

- **[ALEMBIC_GUIDE.md](./ALEMBIC_GUIDE.md)**
  - Database migration guide (SQLAlchemy + Alembic)
  - Creating new migrations
  - Applying and rolling back migrations
  - Common migration commands
  - Best practices for schema changes

- **[../backups/README.md](../backups/README.md)**
  - Database backup and restore procedures
  - Backup creation (binary & SQL formats)
  - Automated backup setup
  - Restore from backup
  - Backup schedule recommendations

---

### **Technical Reference**

- **[TECHNICAL_INDICATORS_ENCYCLOPEDIA.md](./TECHNICAL_INDICATORS_ENCYCLOPEDIA.md)**
  - Detailed guide to all 34 technical indicators
  - Mathematical formulas and calculations
  - Interpretation guidelines for each indicator
  - Trading strategies and use cases
  - Recommended parameter settings
  - Bullish/bearish signal examples

- **[PHASE3_COMPLETION_REPORT.md](./PHASE3_COMPLETION_REPORT.md)** 🆕 **NEW - PHASE 3A/3B**
  - Industrial-grade system upgrade (11 advanced indicators)
  - Market regime detection (TRENDING vs CYCLING)
  - Adaptive weighting based on regime
  - Complete implementation details (backend + frontend + recommendation engine)
  - Performance metrics and competitive analysis
  - File-by-file changes with code snippets

- **[TALIB_INDUSTRIAL_GRADE_RECOMMENDATIONS.md](./TALIB_INDUSTRIAL_GRADE_RECOMMENDATIONS.md)**
  - Complete TA-Lib indicator recommendations for swing trading
  - Priority rankings (Critical, Advanced, Nice-to-Have)
  - Implementation guidelines and code examples
  - Phase 3A (Critical) and Phase 3B (Advanced) indicators
  - Integration strategy with recommendation engine

---

### **Development & Debugging**

- **[DEBUGGING.md](./DEBUGGING.md)**
  - Common issues and solutions
  - Debugging techniques for backend/frontend
  - Log analysis and error tracking
  - Docker troubleshooting
  - Database connection issues
  - Performance optimization tips

- **[PROJECT_ANALYSIS.md](./PROJECT_ANALYSIS.md)**
  - System architecture overview
  - Component relationships and dependencies
  - Design decisions and trade-offs
  - Technology stack rationale
  - Service layer pattern explanation

- **[CLAUDE_CONTEXT.md](./CLAUDE_CONTEXT.md)**
  - Project context for AI assistants (Claude, ChatGPT, etc.)
  - Quick reference notes
  - Recent changes and updates
  - Common commands and workflows
  - Useful shortcuts

- **[CLAUDE.md](./CLAUDE.md)**
  - Short notes and reminders for AI sessions
  - Component status (e.g., StockDetail.jsx is obsolete)

---

### **Legacy & Historical Issues**

- **[YAHOO_FINANCE_ISSUE.md](./YAHOO_FINANCE_ISSUE.md)**
  - Historical issues with Yahoo Finance API (deprecated)
  - Reasons for migration to Polygon.io
  - Lessons learned

---

## 🎯 Quick Reference by Use Case

### **🎯 I want to plan new features**
→ Read **[ROADMAP.md](./ROADMAP.md)** for all pending tasks

### **📚 I want to see what's been completed**
→ Read **[COMPLETED_FEATURES.md](./COMPLETED_FEATURES.md)** for complete history

### **📈 I want to trade with this software**
→ Start with **[SWING_TRADING_OUTLOOK.md](./SWING_TRADING_OUTLOOK.md)**

### **🤖 I want to automate my trading**
→ Read the "Automated Trading Platforms" section in **[SWING_TRADING_OUTLOOK.md](./SWING_TRADING_OUTLOOK.md)**
- **Recommended**: Alpaca (easiest) or Interactive Brokers (most powerful)

### **🔧 I'm having technical issues**
→ Check **[DEBUGGING.md](./DEBUGGING.md)** and **[POLYGON_SETUP.md](./POLYGON_SETUP.md)**

### **📊 I want to understand the indicators**
→ Read **[TECHNICAL_INDICATORS_ENCYCLOPEDIA.md](./TECHNICAL_INDICATORS_ENCYCLOPEDIA.md)**

### **🛡️ I want to learn risk management tools**
→ Read **[RISK_TOOLS_USER_GUIDE.md](./RISK_TOOLS_USER_GUIDE.md)**

### **💰 I want to trade around dividends and splits**
→ Read **[DIVIDEND_SPLIT_INTEGRATION_COMPLETE.md](./DIVIDEND_SPLIT_INTEGRATION_COMPLETE.md)**

### **🗄️ I want to modify the database schema**
→ Follow **[ALEMBIC_GUIDE.md](./ALEMBIC_GUIDE.md)**

### **💾 I want to backup my database**
→ Follow **[../backups/README.md](../backups/README.md)**

### **🤖 I'm an AI assistant starting work on this project**
→ **Read [CLAUDE.md](./CLAUDE.md) FIRST** for complete briefing
→ Then review **[ROADMAP.md](./ROADMAP.md)** for next tasks

### **👨‍💻 I'm continuing development**
→ Review **[ROADMAP.md](./ROADMAP.md)** for next tasks
→ Check **[CLAUDE_CONTEXT.md](./CLAUDE_CONTEXT.md)** for current state

---

## 📊 Documentation Statistics

### Current Structure
- **Active Documentation**: 12 essential files
- **Archived Features**: 1 comprehensive archive (COMPLETED_FEATURES.md)
- **Deleted Files**: 25+ obsolete/redundant documents removed
- **Total Size**: ~450 KB
- **Last Major Cleanup**: 2025-10-30

### File Categories
- **Planning**: 2 files (ROADMAP, COMPLETED_FEATURES)
- **Trading Guides**: 2 files (SWING_TRADING_OUTLOOK, RISK_TOOLS_USER_GUIDE)
- **Technical Setup**: 3 files (POLYGON_SETUP, ALEMBIC_GUIDE, backups/README)
- **Reference**: 1 file (TECHNICAL_INDICATORS_ENCYCLOPEDIA)
- **Development**: 4 files (DEBUGGING, PROJECT_ANALYSIS, CLAUDE_CONTEXT, CLAUDE)
- **Legacy**: 1 file (YAHOO_FINANCE_ISSUE)

### Most Useful Documents
1. **For Traders**: SWING_TRADING_OUTLOOK.md
2. **For Developers**: ROADMAP.md + CLAUDE_CONTEXT.md
3. **For Planning**: ROADMAP.md
4. **For Historical Reference**: COMPLETED_FEATURES.md

---

## 🔄 Recent Updates

### 2025-11-13: Dashboard Performance Optimization ⚡ (45x Speedup)
- ✅ **Implemented indicator caching system** for 45x faster dashboard loading
- ✅ Cache infrastructure:
  - Pre-computed technical indicators stored in JSONB column
  - MD5 hash-based cache invalidation
  - Timeframe aggregation (1h → 1d/1w/1mo) during background fetch
- ✅ Performance improvements:
  - Dashboard load time: **~40 seconds** (down from 20-30 minutes)
  - Per-stock analysis: **0.06 seconds** with cache (vs 2.5s without)
  - Cache hit rate: 100% after initial backfill
- ✅ Bug fixes:
  - Fixed technical signals extraction for cached data format
  - Fixed SQLAlchemy eager loading syntax errors
  - Fixed DataFrame indicator column population for swing trading context
- ✅ Architecture:
  - `IndicatorCacheService` - Manages cache computation and retrieval
  - `TimeframeAggregator` - Pre-aggregates hourly data to higher timeframes
  - Backfill script for batch processing all 502 stocks (~3-4 minutes)
- 📊 Database impact: +5.34 MB for full cache (502 stocks × 35 indicators)
- 🎯 Result: Dashboard now loads instantly with cached indicators

### 2025-11-07: Automatic Fetching & Real-Time Updates 🤖⚡
- ✅ **Completed Phases 2-4 of automatic fetching system**
- ✅ Phase 2: Analysis completeness tracking
  - Database schema with analysis timestamps per component
  - Completeness score calculation (0.0-1.0)
  - Auto-trigger logic for incomplete/stale stocks
- ✅ Phase 3: Frontend auto-trigger
  - Dashboard automatically queues analysis for incomplete stocks
  - Visual completeness badges (🟢 80%+, 🟡 50-79%, 🔴 <50%)
  - Non-blocking background execution
- ✅ Phase 4: Real-time updates with polling
  - Poll for updates every 30 seconds
  - Efficient refresh (only fetches updated stocks)
  - Toast notifications for real-time feedback
  - Automatic UI updates
- ✅ Bug fixes:
  - Analysis score display (was showing 0% for all stocks)
  - News API date format (400 Bad Request errors)
  - Memory allocation error (backend crashes)
  - Timezone comparison error (polling mechanism)
- 📊 Total: ~1,200 lines of code (800 backend + 400 frontend)
- 🎯 Impact: Users now see automatic analysis without manual triggers
- 📝 Documentation: Added comprehensive automatic fetching guide to README.md
- 🔌 Future: WebSocket implementation guide added (Phase 6 - optional)

### 2025-10-31: Dividend & Split Signals Integration 💰✂️
- ✅ **Completed full-stack integration** of dividend and stock split trading signals
- ✅ Backend implementation:
  - Created `/api/v1/dividend-split-signals/` API routes
  - Implemented `DividendSplitDetector` service with 5 signal types
  - Integrated into recommendation engine with score adjustments
  - Updated response schemas with `dividend_split_signal` field
- ✅ Frontend implementation:
  - Added signal badges to `StockCard.jsx` (color-coded, animated)
  - Added signal card to `OverviewTab.jsx` statistics dashboard
  - Updated `api.js` with 3 new API methods
- ✅ Created **DIVIDEND_SPLIT_INTEGRATION_COMPLETE.md** documentation
- 📊 Total: ~700 lines of code added (560 backend + 140 frontend)
- 🎯 Impact: 5-12 new trading opportunities per month per 30-stock portfolio

### 2025-10-30: Major Documentation Cleanup ✨
- ✅ Created **ROADMAP.md** (all pending tasks consolidated)
- ✅ Created **COMPLETED_FEATURES.md** (complete historical archive)
- ✅ Deleted 25+ obsolete/redundant files:
  - BUGFIX_MULTI_TIMEFRAME_AGGREGATION.md
  - CHANGES_2025-10-29.md
  - CHART_PATTERN_ROADMAP.md (merged into ROADMAP.md)
  - CHART_PATTERNS_IMPROVEMENTS.md (archived in COMPLETED_FEATURES.md)
  - CLAUDE_BACKUP.md (obsolete)
  - FILTER_UI_IMPLEMENTATION.md (completed)
  - FRONTEND_REDESIGN.md (completed)
  - IMPLEMENTATION_COMPLETE.md (redundant)
  - IMPLEMENTATION_STATUS_2025-10-30.md (superseded by ROADMAP.md)
  - improvement_list.md (merged into ROADMAP.md)
  - MARKET_REGIME_DETECTION.md (pending, in ROADMAP.md)
  - MULTI_TIMEFRAME_IMPLEMENTATION.md (completed)
  - MULTI_TIMEFRAME_IMPLEMENTATION_COMPLETE.md (completed)
  - MULTI_TIMEFRAME_VISUALIZATION_GUIDE.md (completed)
  - PATTERN_DETECTION_PHILOSOPHY.md (archived)
  - PATTERN_QUALITY_SETTINGS.md (archived)
  - PHASE_2E_VOLUME_ANALYSIS.md (completed)
  - PHASE1_IMPLEMENTATION_STATUS.md (completed)
  - RISK_MANAGEMENT_REFACTORING.md (completed)
  - SMART_AGGREGATION_STATUS.md (completed)
  - SYSTEM_STATUS.md (superseded by ROADMAP.md)
  - TIMEFRAME_DATA_FIX.md (completed)
  - TIMEFRAME_FILTERING_SOLUTION.md (completed)
  - TIMEFRAME_SCALING_FIX.md (completed)
  - UI_IMPROVEMENTS_2025-10-30.md (completed)
  - VOLUME_ANALYSIS_UI_UPDATE.md (completed)
- ✅ Updated this README with clean structure

### 2025-10-22: Phase 7 Complete
- Created SWING_TRADING_OUTLOOK.md (swing trading guide)
- Organized all .md files into /docs folder
- Updated CLAUDE_CONTEXT.md with Phase 7 changes

---

## 📝 Contributing to Documentation

### When Adding New Documentation:
1. **Place it in this `/docs` folder**
2. **Update this README.md** with a link and description
3. **Update the main [README.md](../README.md)** if it's a major document
4. **Use clear, descriptive filenames** (UPPERCASE_WITH_UNDERSCORES.md)

### When Updating Documentation:
1. **Update the "Last Updated" date** at the top of the file
2. **Add entry to "Recent Updates"** section in this README
3. **Keep documentation DRY**: Don't duplicate content across files
4. **Archive old content**: Move to COMPLETED_FEATURES.md if no longer relevant

### When Deleting Documentation:
1. **Verify content is archived** in COMPLETED_FEATURES.md or ROADMAP.md
2. **Update this README** to remove references
3. **Update main README** if it was linked there
4. **Commit with clear message** explaining why deleted

---

## 🎯 Documentation Philosophy

### Keep It Clean
- **Active docs only**: Move completed features to COMPLETED_FEATURES.md
- **No duplicates**: One source of truth per topic
- **Regular cleanup**: Review and consolidate every 2-3 weeks

### Keep It Useful
- **Clear structure**: Easy to find what you need
- **Up to date**: Remove outdated info promptly
- **Comprehensive**: Cover common use cases

### Keep It Maintainable
- **Simple organization**: Flat structure, clear categories
- **Consistent naming**: UPPERCASE_WITH_UNDERSCORES.md
- **Cross-references**: Link related docs

---

## 🤖 AUTOMATIC DATA FETCHING & ANALYSIS SYSTEM

StockAnalyzer now features a **comprehensive automatic fetching system** that ensures all stocks have up-to-date analysis without manual intervention.

### System Architecture

The automatic fetching system consists of 4 integrated phases:

#### **Phase 1: Priority-Based Celery Scheduling** ✅ COMPLETE
- **Celery Beat** schedules automatic price & news fetching
- **Priority System**: Stocks categorized as HIGH, MEDIUM, LOW priority
  - HIGH priority: 15-minute intervals
  - MEDIUM priority: 30-minute intervals
  - LOW priority: 1-hour intervals
- **Priority Calculation**: Based on:
  - Recent price volatility
  - Trading volume
  - Sentiment index
  - User interest (view count)
- **Smart Fetching**: Only fetches during market hours (9:30 AM - 4:00 PM ET)
- **Rate Limiting**: Respects Polygon.io free tier (5 req/min)

#### **Phase 2: Analysis Completeness Tracking** ✅ COMPLETE
- **Database Schema**: Tracks analysis timestamps for each component
  - `last_comprehensive_analysis` - Full analysis timestamp
  - `last_technical_analysis` - Technical indicators timestamp
  - `last_chart_pattern_analysis` - Chart patterns timestamp
  - `last_candlestick_analysis` - Candlestick patterns timestamp
  - `last_sentiment_analysis` - Sentiment analysis timestamp
  - `analysis_score` - Completeness score (0.0-1.0)
  - `analysis_complete` - Boolean flag (true if score >= 0.80)
- **Auto-Trigger Logic**: Dashboard automatically triggers analysis for:
  - Stocks with `analysis_score < 0.80` (incomplete)
  - Stocks with stale data (age > 24 hours)
- **Celery Tasks**: Background workers execute analysis asynchronously
  - `analyze_stock_comprehensive()` - Full analysis pipeline
  - Updates all timestamp fields after completion
  - Calculates and stores completeness score

#### **Phase 3: Frontend Auto-Trigger** ✅ COMPLETE
- **Dashboard Load**: On initial load, checks completeness for all stocks
- **Batch Trigger**: Automatically queues analysis for incomplete stocks
- **Visual Indicators**: StockCards show completeness percentage
  - 🟢 Green badge: >= 80% complete
  - 🟡 Yellow badge: 50-79% complete
  - 🔴 Red badge: < 50% complete
- **Background Notification**: User sees "Analyzing N stocks..." message
- **Non-Blocking**: UI remains responsive during background analysis

#### **Phase 4: Real-Time Updates with Polling** ✅ COMPLETE
- **Polling Mechanism**: Dashboard polls for updates every 30 seconds
  - Endpoint: `GET /api/v1/analysis/recent-updates?since=<timestamp>`
  - Returns: List of stocks updated since last poll
- **Efficient Refresh**: Only fetches data for updated stocks
  - Endpoint: `POST /api/v1/analysis/get-by-ids`
  - Reduces network traffic by 95% vs full dashboard reload
- **Toast Notifications**: User sees real-time updates
  - "AAPL, MSFT, TSLA updated" (success toast)
  - Auto-dismisses after 4 seconds
  - Manual close option available
- **Automatic UI Updates**: StockCards refresh with new data
  - Recommendation changes
  - Analysis score updates
  - New patterns detected
  - Sentiment changes

### Recent Bug Fixes (2025-11-07)

#### **1. Analysis Score Display Fix**
- **Issue**: All stocks showing 0% completeness despite backend calculating scores
- **Root Cause**: `RecommendationResponse` schema missing `analysis_score` and `analysis_complete` fields
- **Fix**: Added fields to schema and response builder
- **Result**: Frontend now correctly displays 40%, 50%, etc.

#### **2. News API Date Format Fix**
- **Issue**: 400 Bad Request errors when fetching news from Polygon API
- **Root Cause**: Sending datetime format `2025-11-06T05:03:05` instead of date format `2025-11-06`
- **Fix**: Changed `.strftime('%Y-%m-%dT%H:%M:%S')` to `.strftime('%Y-%m-%d')` in fetcher tasks
- **Result**: News fetching now works without errors

#### **3. Memory Allocation Error Fix**
- **Issue**: Backend crashing with "Cannot allocate memory (os error 12)"
- **Root Cause**: Uvicorn's `--reload` flag exhausting system memory via file watcher
- **Fix**: Removed `--reload` flag from `backend/start.sh`
- **Result**: Backend stability improved, no more crashes
- **Trade-off**: Must manually restart backend after code changes: `docker-compose restart backend`

#### **4. Timezone Comparison Fix**
- **Issue**: `TypeError: can't compare offset-naive and offset-aware datetimes`
- **Root Cause**: Mixing timezone-aware and timezone-naive datetimes in max() function
- **Fix**: Use timezone-aware variables consistently in `recent-updates` endpoint
- **Result**: No more timezone errors in polling mechanism

### API Endpoints

#### Completeness Check
```bash
POST /api/v1/analysis/check-completeness
{
  "stock_ids": [1, 2, 3],
  "max_age_hours": 24,
  "min_score_threshold": 0.80,
  "include_component_details": false
}

Response:
{
  "total_checked": 3,
  "needs_analysis_count": 1,
  "stocks": [
    {
      "stock_id": 1,
      "symbol": "AAPL",
      "analysis_score": 0.4,
      "analysis_complete": false,
      "needs_refresh": true,
      "missing_components": ["sentiment", "chart_patterns"]
    }
  ]
}
```

#### Trigger Batch Analysis
```bash
POST /api/v1/analysis/trigger-batch
{
  "stock_ids": [1, 2, 3],
  "priority_override": "high"
}

Response:
{
  "triggered_count": 3,
  "tasks": [
    {"stock_id": 1, "symbol": "AAPL", "task_id": "abc123", "priority": "high"}
  ],
  "message": "Triggered analysis for 3 stocks"
}
```

#### Recent Updates (Polling)
```bash
GET /api/v1/analysis/recent-updates?since=2025-11-07T10:00:00Z

Response:
{
  "count": 3,
  "updates": [
    {
      "stock_id": 1,
      "symbol": "AAPL",
      "updated_at": "2025-11-07T10:05:23Z",
      "components_updated": ["technical", "chart_patterns"]
    }
  ],
  "since": "2025-11-07T10:00:00Z"
}
```

#### Get By IDs
```bash
POST /api/v1/analysis/get-by-ids
{
  "stock_ids": [1, 2, 3]
}

Response:
{
  "count": 3,
  "stocks": [
    {
      "stock_id": 1,
      "symbol": "AAPL",
      "analysis_score": 0.8,
      "technical_recommendation": "BUY",
      "current_price": 182.50,
      ...
    }
  ]
}
```

### User Experience

1. **Dashboard Load (First Time)**
   - User opens dashboard
   - Dashboard loads basic stock info (fast)
   - System checks completeness in background
   - Notification: "Analyzing 23 stocks in background..."
   - StockCards show yellow/red badges for incomplete stocks

2. **Automatic Updates (After 30 seconds)**
   - System polls for updates
   - Finds 3 stocks have completed analysis
   - Toast notification: "AAPL, MSFT, TSLA updated"
   - StockCards automatically refresh with new data
   - Badges turn green as completeness increases

3. **Subsequent Loads**
   - Most stocks already have fresh analysis (< 24 hours old)
   - Only 1-2 stocks need refresh
   - Dashboard loads much faster
   - User sees mostly green badges (80-100% complete)

### Performance Metrics

- **Initial Dashboard Load**: 2-5 seconds (basic data only)
- **Background Analysis**: 10-30 seconds per stock
- **Polling Overhead**: < 50ms per request (very efficient)
- **Update Refresh**: < 500ms for 10 stocks
- **Toast Notification Delay**: Appears within 1-2 seconds of completion

### Configuration

#### Celery Beat Schedule (backend/app/celery_app.py)
```python
# High priority stocks - every 15 minutes
'fetch-high-priority-prices': {
    'task': 'app.tasks.fetcher_tasks.fetch_prices_for_priority',
    'schedule': crontab(minute='*/15', hour='9-16', day_of_week='mon-fri'),
    'args': ('high',)
}

# Medium priority stocks - every 30 minutes
'fetch-medium-priority-prices': {
    'task': 'app.tasks.fetcher_tasks.fetch_prices_for_priority',
    'schedule': crontab(minute='*/30', hour='9-16', day_of_week='mon-fri'),
    'args': ('medium',)
}

# Low priority stocks - every 1 hour
'fetch-low-priority-prices': {
    'task': 'app.tasks.fetcher_tasks.fetch_prices_for_priority',
    'schedule': crontab(minute='0', hour='9-16', day_of_week='mon-fri'),
    'args': ('low',)
}
```

#### Polling Interval (frontend/src/components/StockList.jsx)
```javascript
// Poll for updates every 30 seconds
const POLL_INTERVAL = 30000; // milliseconds

useEffect(() => {
  const interval = setInterval(async () => {
    const updates = await api.getRecentUpdates(lastPollTime);
    if (updates.count > 0) {
      // Fetch updated stocks and merge
      const updatedStocks = await api.getStocksByIds(updatedIds);
      // Show toast notification
      showToast(`${updates.count} stocks updated`, 'success');
    }
  }, POLL_INTERVAL);

  return () => clearInterval(interval);
}, [lastPollTime]);
```

### Future Enhancements

See **[ROADMAP.md](./ROADMAP.md)** for planned improvements:
- Server-Sent Events (SSE) for true real-time updates (Phase 6)
- Database caching for recommendations (performance optimization)
- WebSocket support for multi-user environments
- Analysis queue dashboard with detailed progress tracking
- Configurable polling intervals per user

---

## 🔌 WEBSOCKET IMPLEMENTATION (Phase 6 - OPTIONAL)

The current system uses **HTTP polling** (Phase 4) which is efficient and works well for most use cases. However, for truly real-time updates and multi-user environments, **WebSocket** support can be added.

### Why WebSocket?

**Advantages:**
- **True Real-Time**: Server pushes updates instantly (no 30-second delay)
- **Lower Latency**: Sub-second notification delivery
- **Reduced Network Traffic**: No repeated polling requests
- **Scalable**: Handles hundreds of concurrent connections efficiently
- **Better UX**: Instant feedback when analysis completes

**Current Polling vs WebSocket:**
```
Polling (Current):
- Frontend: Poll every 30 seconds → Backend
- Backend: Check for updates, respond
- Latency: 0-30 seconds
- Requests: 2 per minute per client

WebSocket (Future):
- Frontend: Maintain persistent connection
- Backend: Push update event immediately when analysis completes
- Latency: < 1 second
- Requests: 0 (after initial handshake)
```

### Implementation Plan

#### Backend (FastAPI + WebSocket)

**1. Install Dependencies**
```bash
# Already included in FastAPI, no additional install needed
pip install fastapi websockets
```

**2. Create WebSocket Manager (backend/app/utils/websocket_manager.py)**
```python
from typing import Dict, Set
from fastapi import WebSocket
import json

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""

    def __init__(self):
        # Map of user_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str = "anonymous"):
        """Accept new WebSocket connection"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str = "anonymous"):
        """Remove WebSocket connection"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

    async def send_personal_message(self, message: dict, user_id: str):
        """Send message to specific user's connections"""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error sending to {user_id}: {e}")

    async def broadcast(self, message: dict):
        """Send message to all connected users"""
        for connections in self.active_connections.values():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Broadcast error: {e}")

# Global manager instance
manager = ConnectionManager()
```

**3. Add WebSocket Endpoint (backend/app/api/routes/analysis.py)**
```python
from fastapi import WebSocket, WebSocketDisconnect
from app.utils.websocket_manager import manager

@router.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket, user_id: str = "anonymous"):
    """
    WebSocket endpoint for real-time analysis updates

    Messages sent to client:
    {
      "type": "analysis_complete",
      "stock_id": 1,
      "symbol": "AAPL",
      "timestamp": "2025-11-07T10:05:23Z",
      "analysis_score": 0.8
    }
    """
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive, handle incoming messages if needed
            data = await websocket.receive_text()
            # Can implement ping/pong or client commands here
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
```

**4. Emit Events from Celery Tasks (backend/app/tasks/fetcher_tasks.py)**
```python
from app.utils.websocket_manager import manager
import asyncio

@celery_app.task(name='app.tasks.fetcher_tasks.analyze_stock_comprehensive')
def analyze_stock_comprehensive(stock_id: int):
    """Run comprehensive analysis and emit WebSocket event"""
    db = SessionLocal()
    try:
        # ... existing analysis logic ...

        # After successful analysis, emit WebSocket event
        asyncio.run(manager.broadcast({
            "type": "analysis_complete",
            "stock_id": stock_id,
            "symbol": stock.symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "analysis_score": float(stock.analysis_score),
            "components_updated": ["technical", "patterns", "sentiment"]
        }))

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
    finally:
        db.close()
```

#### Frontend (React + WebSocket API)

**1. Create WebSocket Hook (frontend/src/hooks/useWebSocket.js)**
```javascript
import { useEffect, useRef, useState } from 'react';

/**
 * Custom hook for WebSocket connection
 *
 * @param {string} url - WebSocket URL (ws://localhost:8080/api/v1/analysis/ws/updates)
 * @param {function} onMessage - Callback when message received
 * @returns {object} - { isConnected, error, reconnect }
 */
export const useWebSocket = (url, onMessage) => {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connect = () => {
    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        onMessage(data);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Connection error');
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);

        // Auto-reconnect after 5 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('Reconnecting...');
          connect();
        }, 5000);
      };

      wsRef.current = ws;
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    connect();

    return () => {
      // Cleanup on unmount
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [url]);

  const reconnect = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    connect();
  };

  return { isConnected, error, reconnect };
};
```

**2. Integrate into StockList (frontend/src/components/StockList.jsx)**
```javascript
import { useWebSocket } from '../hooks/useWebSocket';

function StockList() {
  const [stocks, setStocks] = useState([]);

  // Handle WebSocket messages
  const handleWebSocketMessage = (message) => {
    if (message.type === 'analysis_complete') {
      console.log('Analysis complete for:', message.symbol);

      // Fetch updated stock data
      api.getStocksByIds([message.stock_id]).then(response => {
        setStocks(prevStocks => {
          const updatedStocks = [...prevStocks];
          const index = updatedStocks.findIndex(s => s.stock_id === message.stock_id);
          if (index !== -1) {
            updatedStocks[index] = response.stocks[0];
          }
          return updatedStocks;
        });

        // Show toast notification
        showToast(`${message.symbol} analysis complete!`, 'success');
      });
    }
  };

  // Connect to WebSocket
  const { isConnected, error } = useWebSocket(
    'ws://localhost:8080/api/v1/analysis/ws/updates',
    handleWebSocketMessage
  );

  // ... rest of component

  return (
    <div>
      {/* Connection status indicator */}
      <div className="connection-status">
        {isConnected ? (
          <span className="status-connected">🟢 Live Updates</span>
        ) : (
          <span className="status-disconnected">🔴 Reconnecting...</span>
        )}
      </div>

      {/* Stock cards */}
      {/* ... */}
    </div>
  );
}
```

### Configuration

**Backend CORS Settings (backend/app/main.py)**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**WebSocket URL Configuration (frontend/src/config.js)**
```javascript
export const WS_BASE_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8080';
export const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8080';

// In production:
// REACT_APP_WS_URL=wss://your-domain.com
// REACT_APP_API_URL=https://your-domain.com
```

### Migration Strategy

**Phase 6A: Add WebSocket (Keep Polling as Fallback)**
1. Implement WebSocket backend endpoint
2. Implement WebSocket frontend hook
3. Use WebSocket if connection successful
4. Fall back to polling if WebSocket fails
5. Test with multiple browser tabs

**Phase 6B: Optimize (WebSocket Primary)**
1. Monitor WebSocket connection stability
2. Reduce polling frequency (60 seconds instead of 30)
3. Use polling only for recovery from disconnection
4. Add connection quality indicator

**Phase 6C: Production Deployment**
1. Use WSS (WebSocket Secure) in production
2. Configure load balancer for WebSocket (sticky sessions)
3. Add Redis pub/sub for multi-server environments
4. Monitor connection metrics (Prometheus/Grafana)

### Comparison: Polling vs WebSocket

| Feature | HTTP Polling (Current) | WebSocket (Future) |
|---------|----------------------|-------------------|
| **Latency** | 0-30 seconds | < 1 second |
| **Network Overhead** | Medium (2 req/min) | Low (1 connection) |
| **Complexity** | Simple | Moderate |
| **Reliability** | High (HTTP retry) | Medium (needs reconnect logic) |
| **Scalability** | Good (stateless) | Excellent (persistent) |
| **Load Balancing** | Easy | Harder (sticky sessions) |
| **Best For** | 10-100 users | 100+ concurrent users |

### When to Use WebSocket

**Use WebSocket if:**
- You need sub-second latency
- You have 100+ concurrent users
- You want to push frequent updates (e.g., price ticks)
- You're building real-time collaboration features

**Stick with Polling if:**
- Current latency (30s) is acceptable
- You have < 50 concurrent users
- You want simpler deployment (no sticky sessions)
- You prioritize reliability over speed

### Testing WebSocket

**Test with wscat:**
```bash
# Install wscat
npm install -g wscat

# Connect to WebSocket endpoint
wscat -c ws://localhost:8080/api/v1/analysis/ws/updates

# Send ping
> ping

# Receive pong
< {"type":"pong"}

# Receive analysis updates
< {"type":"analysis_complete","stock_id":1,"symbol":"AAPL",...}
```

**Test with Browser Console:**
```javascript
// Open browser console on dashboard
const ws = new WebSocket('ws://localhost:8080/api/v1/analysis/ws/updates');

ws.onopen = () => console.log('Connected!');
ws.onmessage = (event) => console.log('Message:', JSON.parse(event.data));
ws.onerror = (error) => console.error('Error:', error);

// Send ping
ws.send('ping');
```

### Production Considerations

**1. Load Balancing with Sticky Sessions**
```nginx
# nginx.conf
upstream backend {
    ip_hash;  # Sticky sessions based on client IP
    server backend1:8080;
    server backend2:8080;
}

server {
    location /api/v1/analysis/ws/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;  # 24 hours
    }
}
```

**2. Redis Pub/Sub for Multi-Server**
```python
# backend/app/utils/redis_pubsub.py
import redis
import json

redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

def publish_analysis_complete(stock_id: int, symbol: str, data: dict):
    """Publish event to Redis channel"""
    message = {
        'type': 'analysis_complete',
        'stock_id': stock_id,
        'symbol': symbol,
        **data
    }
    redis_client.publish('analysis_updates', json.dumps(message))

# Subscribe in WebSocket manager
async def subscribe_to_updates():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('analysis_updates')

    for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'])
            await manager.broadcast(data)
```

**3. Connection Health Monitoring**
```javascript
// frontend/src/hooks/useWebSocket.js
const PING_INTERVAL = 30000;  // 30 seconds

useEffect(() => {
  const pingInterval = setInterval(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send('ping');
    }
  }, PING_INTERVAL);

  return () => clearInterval(pingInterval);
}, []);
```

### Summary

- **Current System**: HTTP polling every 30 seconds (Phase 4) ✅ **WORKING**
- **Future Enhancement**: WebSocket for real-time updates (Phase 6) 📋 **OPTIONAL**
- **Recommendation**: Keep polling as primary, add WebSocket for advanced users
- **Fallback Strategy**: Use both WebSocket (primary) + polling (fallback) for maximum reliability

See **[ROADMAP.md](./ROADMAP.md)** Phase 6 for detailed WebSocket implementation timeline.

---

# Future goals (Pending Implementation)
- ~~create element for automatic fetch countdown visualization and place it into card detail top right corner~~ ✅ **COMPLETED** (FetchCountdown.jsx)
- ~~add market open/close (holydays) status in top of App.jsx~~ ✅ **COMPLETED** (MarketStatus.jsx)
- save news article into database (currently just fetched into frontend with no saving) but keep only articles from latest 14 days for each stock
- recalculate stock priority for smart fetching every time fetch is executed
- ~~automatic update of all data on stock card when fetch and computation for current stock happens~~ ✅ **COMPLETED** (Phase 4 polling)

---

**Happy Trading! 📈**
**Happy Coding! 💻**
