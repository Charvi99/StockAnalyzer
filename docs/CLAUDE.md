# Claude AI Assistant - Project Briefing Document

**READ THIS FIRST** before working on StockAnalyzer project.

**Last Updated**: 2025-11-13
**Project Phase**: Phase 8 (Advanced Features)
**Latest Completion**: ⚡ Dashboard Performance Optimization (45x Speedup with Indicator Cache)

---

## 🎯 PROJECT MISSION

**StockAnalyzer** is a professional swing trading analysis platform designed to:

2. **Detect chart patterns** with 85%+ accuracy using rule-based algorithms
3. **Provide risk management tools** for position sizing and portfolio monitoring
4. **Enable multi-timeframe analysis** (1h, 4h, 1d, 1w, 1mo) for pattern confirmation
5. **Support swing traders** with actionable insights and automated pattern detection

**Primary Goal**: Build the best pattern recognition dataset for CNN training, not just a trading tool.

---

## 🚀 QUICK START FOR AI ASSISTANTS

### What You Need to Know Immediately

#### Project Type
- **Full-stack web application** (FastAPI + React + PostgreSQL/TimescaleDB)
- **335+ stocks** across 18 sectors pre-populated
- **12 chart patterns** + **40 candlestick patterns** detection
- **Multi-timeframe support** with smart aggregation
- **Professional risk management** (trailing stops, portfolio heat monitoring)
- **Dividend & split signals** (5 signal types for event-driven trading) 🆕

#### Current Status
- ✅ **Phases 1-7 Complete** (see `COMPLETED_FEATURES.md`)
- 🚧 **Phase 8 In Progress** (CNN training, alerts, authentication)
- 📊 **~1,000+ patterns detected** across all stocks
- 🎯 **Goal**: 10,000+ labeled patterns for CNN training

#### Tech Stack
```
Frontend:  React 18 + TradingView Lightweight Charts
Backend:   FastAPI (Python 3.11) + SQLAlchemy
Database:  PostgreSQL 15 + TimescaleDB
ML:        PyTorch (CNN, LSTM, Transformer models)
Data:      Polygon.io API (free tier: 5 req/min)
DevOps:    Docker Compose (3-tier architecture)
```

---

## 📁 CRITICAL FILES & COMPONENTS

### ⚠️ IMPORTANT: Component Status

**OBSOLETE (DO NOT USE)**:
- ❌ `StockDetail.jsx` - Old component, replaced by StockDetailSideBySide.jsx

**CURRENT (USE THESE)**:
- ✅ `StockDetailSideBySide.jsx` - Main stock detail view (side-by-side layout)
- ✅ `StockList.jsx` - Dashboard with sector organization
- ✅ `OrderCalculator.jsx` - Position sizing and risk calculations
- ✅ `TrailingStopCalculator.jsx` - ATR-based trailing stops (490 lines)
- ✅ `PortfolioHeatMonitor.jsx` - Portfolio risk monitoring (630 lines)

### Backend Services (Most Important)
```
backend/app/services/
├── chart_patterns.py            # 12 chart pattern detection (core algorithm)
├── candlestick_patterns.py      # 40 candlestick patterns
├── technical_indicators.py      # 15+ technical indicators
├── order_calculator.py          # Position sizing + risk management
├── polygon_fetcher.py           # Data fetching from Polygon.io
├── timeframe_service.py         # Multi-timeframe aggregation
├── multi_timeframe_patterns.py  # Cross-timeframe pattern validation
└── dividend_split_detector.py   # Dividend & split signals (NEW - Phase 8)
```

### Shared Utilities
```
backend/app/utils/
└── risk_utils.py               # Shared risk calculations (ATR, position sizing, etc.)
```

### Database Models
```
backend/app/models/
├── stock.py                    # Stock, StockPrice models
├── chart_pattern.py            # ChartPattern model
└── candlestick_pattern.py      # CandlestickPattern model
```

---

## 🧠 ARCHITECTURE PRINCIPLES

### Service Layer Pattern
- **Controllers** (routes) → **Services** (business logic) → **Models** (data access)
- Keep business logic OUT of controllers
- Use shared utilities for common calculations

### DRY Principle (Don't Repeat Yourself)
- Risk calculations: Use `risk_utils.py` (shared)
- Pattern detection: Use `ChartPatternDetector` class
- Multi-timeframe: Use `TimeframeService`

### Backward Compatibility
- System supports both 1h data (new) and 1d data (legacy)
- Always check if 1h data exists before aggregating
- Fallback to 1d if 1h not available

### Top-Down Multi-Timeframe Approach
- **Daily (1d) patterns are primary** (institutional standard)
- **Hourly (1h) and 4h for confirmation** only
- Patterns without daily confirmation are filtered out
- This reduces false positives by 40-60%

---

## 📖 ESSENTIAL DOCUMENTATION (Read in Order)

### 1. **ROADMAP.md** (5 min read) ⭐
   - All pending tasks with priorities
   - Phase 8 goals and timeline
   - Next steps for development

### 2. **COMPLETED_FEATURES.md** (10 min skim)
   - What's been built (Phases 1-7)
   - Architecture decisions and trade-offs
   - Performance metrics and statistics

### 3. **CLAUDE_CONTEXT.md** (3 min read)
   - Recent changes and bug fixes
   - Common commands and workflows
   - Quick reference notes

### 4. **Project-Specific Guides** (as needed)
   - `SWING_TRADING_OUTLOOK.md` - Trading strategies
   - `RISK_TOOLS_USER_GUIDE.md` - Risk management
   - `DIVIDEND_SPLIT_INTEGRATION_COMPLETE.md` - Dividend/split signals (NEW - Phase 8)
   - `TECHNICAL_INDICATORS_ENCYCLOPEDIA.md` - Indicator reference
   - `ALEMBIC_GUIDE.md` - Database migrations

---

## 🎯 WORKING ON THIS PROJECT: BEST PRACTICES

### Before Writing Any Code

1. **Read ROADMAP.md** to understand pending tasks
2. **Check COMPLETED_FEATURES.md** to avoid re-implementing
3. **Review related service code** to understand existing patterns
4. **Use shared utilities** instead of duplicating code

### When Implementing Features

#### Pattern: Service-First Development
```python
# ✅ CORRECT: Business logic in service
class MyService:
    def do_something(self, param):
        # Business logic here
        return result

# ❌ WRONG: Business logic in controller
@router.post("/endpoint")
def endpoint(param):
    # Don't put business logic here!
    result = complex_calculation()  # ❌ Move to service
    return result
```

#### Pattern: Use Shared Utilities
```python
# ✅ CORRECT: Use shared utility
from app.utils.risk_utils import calculate_atr

atr = calculate_atr(prices, window=14)

# ❌ WRONG: Duplicate ATR calculation
def calculate_atr_again(prices):  # ❌ Already exists in risk_utils!
    # ... duplicate code
```

#### Pattern: Type Hints Always
```python
# ✅ CORRECT: Type hints + docstring
def calculate_position_size(
    account_size: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float
) -> dict:
    """
    Calculate position size based on risk parameters.

    Args:
        account_size: Total account capital
        risk_percent: Risk per trade (e.g., 1.0 for 1%)
        entry_price: Entry price for the trade
        stop_loss: Stop loss price

    Returns:
        dict with position_size, risk_amount, warnings
    """
    # Implementation
```

### When Debugging Issues

1. **Check Docker logs**: `docker-compose logs backend --tail=50`
2. **Check API docs**: http://localhost:8080/docs
3. **Check database**: Connect via psql or pgAdmin
4. **Check frontend console**: Browser DevTools → Console
5. **Read DEBUGGING.md** for common issues

### When Working with Database

- **Always use Alembic** for schema changes (see `ALEMBIC_GUIDE.md`)
- **Never modify database directly** in production
- **Test migrations** with `alembic upgrade head` before committing
- **Create rollback plan** with `alembic downgrade`

---

## 🔧 COMMON TASKS & COMMANDS

### Start Development Environment
```bash
# Start all services
docker-compose up

# Restart backend after code changes
docker-compose restart backend

# View logs
docker-compose logs backend --tail=50 -f
docker-compose logs frontend --tail=50 -f
```

### Database Operations
```bash
# Create migration
cd backend
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Check current revision
alembic current
```

### Access Points
- Frontend: http://localhost:3000
- Backend API: http://localhost:8080
- API Docs: http://localhost:8080/docs
- Health Check: http://localhost:8080/health

---

## ⚠️ CRITICAL: WHAT TO AVOID

### Code Anti-Patterns

❌ **DON'T duplicate risk calculations**
```python
# ❌ WRONG
def calculate_atr_in_my_service():  # Already in risk_utils.py!
    ...
```

❌ **DON'T use StockDetail.jsx**
```javascript
// ❌ WRONG - This component is obsolete
import StockDetail from './StockDetail';

// ✅ CORRECT - Use this instead
import StockDetailSideBySide from './StockDetailSideBySide';
```

❌ **DON'T put business logic in controllers**
```python
# ❌ WRONG
@router.post("/endpoint")
def endpoint():
    # Complex calculation here  # ❌ Move to service!
    ...
```

❌ **DON'T modify database schema without Alembic**
```sql
-- ❌ WRONG - Don't run SQL directly
ALTER TABLE stocks ADD COLUMN new_field VARCHAR(50);

-- ✅ CORRECT - Use Alembic migration
alembic revision --autogenerate -m "add new_field to stocks"
```

❌ **DON'T break backward compatibility**
```python
# ❌ WRONG - Breaks existing 1d data
def get_prices(stock_id, timeframe='1h'):  # Must default to '1d'!
    ...

# ✅ CORRECT - Backward compatible
def get_prices(stock_id, timeframe='1d'):  # Default to legacy
    ...
```

### Trading Logic Anti-Patterns

❌ **DON'T treat 1h patterns as primary**
```python
# ❌ WRONG - Violates top-down approach
primary_patterns = get_patterns(timeframe='1h')  # Too noisy!

# ✅ CORRECT - Daily patterns are primary
primary_patterns = get_patterns(timeframe='1d')
confirmation = get_patterns(timeframe='1h')  # For entry timing only
```

❌ **DON'T include Rounding patterns by default**
```python
# ❌ WRONG - Rounding patterns have 60-80% false positive rate
all_patterns = detect_all_patterns()

# ✅ CORRECT - Exclude by default
patterns = detect_patterns(exclude=['Rounding Top', 'Rounding Bottom'])
```

---

## 🎓 DOMAIN KNOWLEDGE FOR THIS PROJECT

### Swing Trading (Target User)
- **Holding period**: 3-30 days (typically 1-2 weeks)
- **Risk per trade**: 1-2% of account
- **Win rate target**: 50-60% (with 2:1 R:R ratio)
- **Timeframe preference**: Daily charts (1d primary, 1h for entry timing)
- **Pattern preference**: Head & Shoulders, Double Tops/Bottoms, Triangles

### Pattern Detection Philosophy
- **Quality > Quantity**: 5-10 high-quality patterns better than 50 noisy ones
- **Multi-timeframe confirmation**: Patterns on 2+ timeframes = 40-60% fewer false positives
- **Volume matters**: Breakouts need 50%+ volume increase
- **Context matters**: Bullish patterns in uptrend = higher confidence

### Risk Management Principles
- **ATR-based stops**: 1-2x ATR below entry (gives trade room to breathe)
- **Portfolio heat**: Max 6% total risk across all positions
- **Position sizing**: Risk fixed % of account, not fixed $ amount
- **Trailing stops**: Lock in profits at 1.5x ATR, take partial at 3x ATR

---

## 📊 PERFORMANCE BENCHMARKS

### Expected Performance
- **Pattern detection**: <2s per stock (including all timeframes)
- **API response time**: <500ms average
- **Database queries**: <100ms for price data
- **Frontend render**: <200ms for chart updates

### If Performance Degrades
1. Check database indexes (should exist on stock_id, timeframe, timestamp)
2. Check N+1 query issues (use joinedload/selectinload)
3. Profile with Python cProfile or React DevTools
4. Review DEBUGGING.md for optimization tips

---

## 🧪 TESTING GUIDELINES

### Manual Testing Checklist
- [ ] Test with AAPL (has 1h data) - verify all timeframes work
- [ ] Test with other stocks (have 1d data) - verify fallback works
- [ ] Test pattern detection across multiple timeframes
- [ ] Test risk calculators with various inputs
- [ ] Check browser console for errors
- [ ] Verify API responses in Swagger docs

### Automated Testing (Pending - See ROADMAP.md)
- Unit tests needed for services (pytest)
- Integration tests needed for API endpoints
- E2E tests needed for frontend (Cypress)

---

## 🎯 CURRENT PRIORITIES (Phase 8)

### ✅ COMPLETED IN PHASE 8

1. **Dashboard Performance Optimization (45x Speedup)** ✅ (2025-11-13)
   - Indicator caching system with JSONB storage
   - Timeframe pre-aggregation (1h → 1d/1w/1mo)
   - MD5 hash-based cache invalidation
   - Dashboard load: ~40 seconds (down from 20-30 minutes)
   - Per-stock analysis: 0.06s with cache vs 2.5s without
   - Services: `IndicatorCacheService`, `TimeframeAggregator`
   - Backfill script for batch processing

2. **Automatic Data Fetching & Real-Time Updates** ✅ (2025-11-07)
   - Phases 2-4 complete: Completeness tracking, auto-trigger, polling
   - Toast notifications for real-time updates
   - Analysis score display with color-coded badges
   - Critical bug fixes (memory leak, timezone, news API)
   - See comprehensive section above and README.md

3. **Dividend & Split Trading Signals** ✅ (2025-10-31)
   - Full-stack integration (backend + frontend)
   - 5 signal types: dividend_exit, dividend_entry, split_entry, split_exit, split_reentry
   - Visual badges in StockCard and OverviewTab
   - Recommendation engine integration
   - See `DIVIDEND_SPLIT_INTEGRATION_COMPLETE.md`

### HIGH PRIORITY
1. **CNN Training Pipeline** (export patterns for training)
2. **Pattern Backtesting System** (track historical win rates)
3. **Alert System** (email/webhook notifications)
4. **User Authentication** (multi-user support)

### MEDIUM PRIORITY
5. **Context-Aware Scoring** (Phase 2F - market phase detection)
6. **Parameter Validation** (frontend + backend)
7. **Automated Backend Tests** (pytest suite)

### LOW PRIORITY
8. **Caching Layer** (Redis - evaluate if needed)
9. **WebSocket Updates** (real-time pattern notifications)

**See ROADMAP.md for complete task list and timelines.**

---

## 💡 PROMPT ENGINEERING TIPS FOR THIS PROJECT

### When Asking Claude for Help

**✅ GOOD PROMPTS:**
- "Implement trailing stop calculator using the existing risk_utils.py"
- "Add a new chart pattern following the existing ChartPatternDetector pattern"
- "Debug why 1h patterns aren't showing - check TimeframeService logic"
- "Create Alembic migration to add new field to stocks table"

**❌ BAD PROMPTS:**
- "Build a trading bot" (too vague, not aligned with project goals)
- "Add ML pattern detection" (rejected - rule-based is better)
- "Create new ATR calculation" (already exists in risk_utils.py!)
- "Implement day trading features" (project is for swing trading)

### Provide Context
Always mention:
1. Which phase/feature you're working on
2. Which files you've already reviewed
3. What you've tried (if debugging)
4. Expected vs actual behavior

### Example Good Request
```
I'm working on Phase 8 (CNN training). I need to export detected patterns
to a format suitable for CNN training (images + labels).

I've reviewed:
- chart_patterns.py (pattern detection logic)
- StockChart.jsx (chart rendering)

I need help creating a service that:
1. Renders chart with pattern overlay
2. Saves as PNG image (256x256)
3. Generates label JSON (pattern type, coordinates, confidence)

Should this be a new service or extend existing ChartPatternDetection service?
```

---

## 🏁 GETTING STARTED CHECKLIST

**For New Claude Instance Starting Work:**

- [ ] Read this document (CLAUDE.md) - **YOU ARE HERE**
- [ ] Skim ROADMAP.md to see pending tasks
- [ ] Skim COMPLETED_FEATURES.md to understand what exists
- [ ] Review CLAUDE_CONTEXT.md for recent changes
- [ ] Explore codebase structure (backend/app/services/, frontend/src/components/)
- [ ] Start Docker environment: `docker-compose up`
- [ ] Access frontend: http://localhost:3000
- [ ] Review API docs: http://localhost:8080/docs
- [ ] Open a stock (e.g., AAPL) and explore the UI
- [ ] Ready to work! 🚀

---

## 🆘 NEED HELP?

### Documentation to Check
1. **ROADMAP.md** - Is this task already planned?
2. **COMPLETED_FEATURES.md** - Has this been implemented?
3. **DEBUGGING.md** - Is this a known issue?
4. **docs/README.md** - Where's the relevant doc?

### Common Issues
- **Backend not starting**: Check Docker logs, database connection
- **Frontend errors**: Check browser console, API connectivity
- **Pattern detection not working**: Check stock has data, timeframe exists
- **Database errors**: Check Alembic migrations applied
- **Polygon API errors**: Check rate limits (5 req/min), API key

### Still Stuck?
- Check git history: `git log --oneline -20`
- Review recent commits for similar changes
- Consult CLAUDE_CONTEXT.md for recent bug fixes

---

## 📝 FINAL NOTES

### Project Philosophy
- **Quality over quantity** (patterns, code, features)
- **Incremental development** (finish one phase before next)
- **User-focused** (swing traders are the target)
- **Data collection** (CNN training is primary goal)
- **Maintainability** (clean code, good docs, simple architecture)

### Success Metrics
- 10,000+ labeled patterns collected ✅
- 85%+ pattern classification accuracy (CNN goal)
- 70%+ trading win rate (backtested patterns)
- <2s pattern detection per stock
- Happy swing traders using the platform 📈

---

**You're ready to work on StockAnalyzer! 🚀**

**Remember:**
- Read ROADMAP.md for tasks
- Use shared utilities (risk_utils.py)
- Follow service layer pattern
- StockDetailSideBySide.jsx, not StockDetail.jsx
- Test with AAPL (has 1h data)
- Ask good questions with context

---

## 🤖 AUTOMATIC FETCHING SYSTEM (2025-11-07)

### ✅ COMPLETED IMPLEMENTATION

The automatic fetching and analysis system is now **FULLY OPERATIONAL** across all 4 phases:

#### **Phase 1: Priority-Based Celery Scheduling** ✅
- Celery Beat schedules automatic price & news fetching
- Priority system: HIGH (15 min), MEDIUM (30 min), LOW (1 hour)
- Smart fetching during market hours only (9:30 AM - 4:00 PM ET)
- Rate limiting for Polygon.io free tier (5 req/min)

**Files:**
- `backend/app/celery_app.py` - Celery Beat configuration
- `backend/app/tasks/fetcher_tasks.py` - Fetching tasks
- `backend/app/services/priority_calculator.py` - Priority calculation
- `backend/app/utils/market_hours.py` - Market hours checking

#### **Phase 2: Analysis Completeness Tracking** ✅
- Database tracks analysis timestamps per component
- Completeness score calculation (0.0-1.0)
- Auto-trigger logic for incomplete stocks (score < 0.80)
- Background Celery workers execute analysis

**Files:**
- `backend/alembic/versions/20251030_add_priority_system.py` - Migration
- `backend/app/models/stock.py` - Analysis tracking fields
- `backend/app/services/analysis_completeness.py` - Completeness service
- `backend/app/api/routes/analysis.py` - Check/trigger endpoints

**Database Schema:**
```python
# Stock model fields
last_comprehensive_analysis: datetime
last_technical_analysis: datetime
last_chart_pattern_analysis: datetime
last_candlestick_analysis: datetime
last_sentiment_analysis: datetime
analysis_score: float  # 0.0-1.0
analysis_complete: bool  # True if >= 0.80
```

#### **Phase 3: Frontend Auto-Trigger** ✅
- Dashboard automatically checks completeness on load
- Triggers analysis for incomplete/stale stocks
- Visual indicators (🟢 80%+, 🟡 50-79%, 🔴 <50%)
- Non-blocking background execution

**Files:**
- `frontend/src/components/StockList.jsx` - Auto-trigger logic
- `frontend/src/components/StockCard.jsx` - Completeness badges
- `frontend/src/services/api.js` - API methods

#### **Phase 4: Real-Time Updates with Polling** ✅
- Polls for updates every 30 seconds
- Efficient refresh (only fetches updated stocks)
- Toast notifications for real-time feedback
- Automatic UI updates

**Files:**
- `frontend/src/components/StockList.jsx` - Polling logic
- `frontend/src/components/Toast.jsx` - Toast notifications
- `frontend/src/components/Toast.css` - Toast styling

**API Endpoints:**
- `GET /api/v1/analysis/recent-updates?since=<timestamp>` - Check for updates
- `POST /api/v1/analysis/get-by-ids` - Fetch specific stocks
- `POST /api/v1/analysis/check-completeness` - Check completeness
- `POST /api/v1/analysis/trigger-batch` - Trigger analysis

### 🐛 CRITICAL BUG FIXES (2025-11-07)

#### 1. Analysis Score Display Fix
- **Issue**: All stocks showing 0% completeness
- **Fix**: Added `analysis_score` and `analysis_complete` fields to `RecommendationResponse`
- **Files**: `backend/app/schemas/analysis.py`, `backend/app/api/routes/analysis.py`

#### 2. News API Date Format Fix
- **Issue**: 400 Bad Request from Polygon News API
- **Fix**: Changed datetime format to date format (`'%Y-%m-%d'`)
- **Files**: `backend/app/tasks/fetcher_tasks.py` (lines 547, 684)

#### 3. Memory Allocation Error Fix
- **Issue**: Backend crashing with "Cannot allocate memory (os error 12)"
- **Fix**: Removed `--reload` flag from uvicorn (file watcher exhausting memory)
- **Files**: `backend/start.sh`
- **Trade-off**: Must manually restart backend: `docker-compose restart backend`

#### 4. Timezone Comparison Fix
- **Issue**: `TypeError: can't compare offset-naive and offset-aware datetimes`
- **Fix**: Use timezone-aware variables consistently in `max()` function
- **Files**: `backend/app/api/routes/analysis.py` (recent-updates endpoint)

### 📊 USER EXPERIENCE FLOW

**First Load:**
1. User opens dashboard
2. Dashboard loads basic stock info (2-5 seconds)
3. System checks completeness in background
4. Notification: "Analyzing 23 stocks in background..."
5. StockCards show yellow/red badges for incomplete stocks

**After 30 Seconds:**
6. System polls for updates
7. Finds 3 stocks completed analysis
8. Toast: "AAPL, MSFT, TSLA updated"
9. StockCards automatically refresh
10. Badges turn green as completeness increases

**Subsequent Loads:**
11. Most stocks have fresh analysis (< 24 hours)
12. Only 1-2 stocks need refresh
13. Dashboard loads faster
14. User sees mostly green badges

### 🔌 WEBSOCKET (Phase 6 - OPTIONAL)

The current polling system works well for most use cases, but WebSocket can be added for:
- Sub-second latency (vs 0-30 seconds with polling)
- 100+ concurrent users
- Frequent real-time updates

**Implementation Ready:**
- Backend: FastAPI native WebSocket support
- Frontend: Custom `useWebSocket` hook
- Fallback: Keep polling as backup

**See README.md for complete WebSocket implementation guide.**

---

## ORIGINAL AUTOFETCHING ROADMAP (06.11.2025)

  **NOTE: The roadmap below has been COMPLETED. Kept for reference only.**

  PHASE 1: Database Schema & Analysis Tracking (2-3 hours) ✅ DONE

  1.1 Create Alembic Migration (backend/alembic/versions/)
  - Add analysis tracking fields to Stock model
  - Create indexes on timestamp fields for performance
  - Set default values (NULL for existing stocks)

  alembic revision -m "add_analysis_tracking_fields"

  1.2 Update Stock Model (backend/app/models/stock.py)
  - Add new columns to Stock class
  - Update relationships if needed

  1.3 Create Analysis Completeness Service (backend/app/services/analysis_completeness.py)
  - check_stock_completeness() - Calculates completeness score
  - get_missing_analysis_types() - Returns list of missing components
  - should_trigger_analysis() - Decision logic
  - update_analysis_timestamps() - Helper to update after analysis completes

  1.4 Update Celery Task (backend/app/tasks/analysis_tasks.py)
  - Modify analyze_stock_comprehensive() to update analysis timestamps after each step
  - Update analysis_complete flag and analysis_score at the end

  Files to Create:
  - backend/alembic/versions/YYYYMMDD_add_analysis_tracking.py
  - backend/app/services/analysis_completeness.py

  Files to Modify:
  - backend/app/models/stock.py
  - backend/app/tasks/analysis_tasks.py

  ---
  PHASE 2: Completeness Check API (1-2 hours)

  2.1 Create New Endpoint (backend/app/api/routes/analysis.py)
  - POST /api/v1/analysis/check-completeness - Batch check for stock IDs
  - Returns: [{stock_id, analysis_score, missing_components, needs_refresh}]

  2.2 Create Trigger Endpoint (backend/app/api/routes/analysis.py)
  - POST /api/v1/analysis/trigger-batch - Triggers analysis for multiple stocks
  - Queues Celery tasks with priority based on stock.priority
  - Returns: {triggered_count, task_ids: [{stock_id, task_id}]}

  2.3 Add Response Schema (backend/app/schemas/analysis.py)
  class AnalysisCompletenessResponse(BaseModel):
      stock_id: int
      analysis_score: float  # 0.0 to 1.0
      missing_components: List[str]
      needs_refresh: bool
      last_analysis: Optional[datetime]

  Files to Modify:
  - backend/app/api/routes/analysis.py (add ~80 lines)
  - backend/app/schemas/analysis.py (add ~15 lines)

  ---
  PHASE 3: Frontend Auto-Trigger (2-3 hours)

  3.1 Add API Methods (frontend/src/services/api.js)
  export const checkAnalysisCompleteness = async (stockIds, maxAgeHours = 24) => {
    const response = await api.post('/api/v1/analysis/check-completeness', {
      stock_ids: stockIds,
      max_age_hours: maxAgeHours
    });
    return response.data;
  };

  export const triggerBatchAnalysis = async (stockIds) => {
    const response = await api.post('/api/v1/analysis/trigger-batch', {
      stock_ids: stockIds
    });
    return response.data;
  };

  3.2 Modify Dashboard Load (frontend/src/components/StockList.jsx)
  - After loading basic stocks, check completeness
  - Trigger analysis for stocks with score < 0.8 or age > 24 hours
  - Show notification: "Analyzing N stocks in background..."
  - Add state for tracking triggered analyses

  const [triggeredAnalyses, setTriggeredAnalyses] = useState([]);
  const [analysisQueueSize, setAnalysisQueueSize] = useState(0);

  3.3 Update StockCard UI (frontend/src/components/StockCard.jsx)
  - Add visual indicator for stocks currently being analyzed
  - Show completeness score badge (optional)
  - Pulsing animation for stocks in analysis queue

  Files to Modify:
  - frontend/src/services/api.js (add ~20 lines)
  - frontend/src/components/StockList.jsx (modify ~50 lines in fetchDashboardData)
  - frontend/src/components/StockCard.jsx (add ~30 lines for analysis indicator)

  ---
  PHASE 4: Real-Time Updates (Polling Approach) (2-3 hours)

  4.1 Create Updates Endpoint (backend/app/api/routes/analysis.py)
  - GET /api/v1/analysis/recent-updates - Returns stocks updated since timestamp
  - Query parameter: since (ISO timestamp)
  - Returns: [{stock_id, symbol, updated_at, components_updated}]

  4.2 Create Fetch-By-IDs Endpoint (backend/app/api/routes/analysis.py)
  - POST /api/v1/analysis/get-by-ids - Fetch analysis for specific stock IDs
  - More efficient than re-fetching entire dashboard
  - Returns: RecommendationResponse[] for specified IDs only

  4.3 Implement Polling (frontend/src/components/StockList.jsx)
  - Enhance existing auto-refresh logic
  - Poll /recent-updates every 30 seconds
  - If updates found, fetch only those stocks with /get-by-ids
  - Merge updates into stocks array (preserve scroll position)
  - Show toast notification: "3 stocks updated"

  4.4 Add to StockDetail (frontend/src/components/StockDetailSideBySide.jsx)
  - Poll for current stock specifically
  - Auto-refresh recommendation, patterns, sentiment when updated
  - Show notification: "New analysis available"

  Files to Modify:
  - backend/app/api/routes/analysis.py (add ~60 lines, 2 new endpoints)
  - frontend/src/components/StockList.jsx (modify existing useEffect, ~40 lines)
  - frontend/src/components/StockDetailSideBySide.jsx (add useEffect for polling, ~50 lines)

  ---
  PHASE 5: Enhanced UI & Notifications (2 hours)

  5.1 Analysis Progress Dashboard
  - Top-right corner widget showing:
    - "X stocks analyzing"
    - Progress bar
    - Last refresh timestamp
  - Clicking opens modal with detailed queue status

  5.2 Toast Notifications
  - Install react-toastify or similar
  - Show notifications for:
    - "Analysis started for 15 stocks"
    - "3 stocks updated with new analysis"
    - "All analyses complete"

  5.3 Completeness Indicators
  - Badge on StockCard showing completeness score
  - Color-coded: Green (>0.8), Yellow (0.5-0.8), Red (<0.5)
  - Tooltip showing missing components

  Files to Create:
  - frontend/src/components/AnalysisProgressWidget.jsx
  - frontend/src/components/AnalysisProgressWidget.css

  Files to Modify:
  - frontend/src/components/StockList.jsx (integrate widget)
  - frontend/src/components/StockCard.jsx (add badges)
  - frontend/package.json (add react-toastify dependency)

  ---
  PHASE 6 (OPTIONAL): Server-Sent Events (3-4 hours)

  Note: Only implement if polling approach proves insufficient or inefficient.

  6.1 Install SSE Libraries
  - Backend: pip install sse-starlette
  - Frontend: Native EventSource API (built-in)

  6.2 Create SSE Endpoint (backend/app/api/routes/analysis.py)
  - GET /api/v1/analysis/stream - SSE endpoint
  - Publishes events when analysis completes
  - Uses Redis pub/sub or database polling

  6.3 Redis Pub/Sub Integration (backend/app/tasks/analysis_tasks.py)
  - After successful analysis, publish event to Redis
  - Channel: analysis_complete
  - Payload: {stock_id, symbol, timestamp}

  6.4 Frontend SSE Client (frontend/src/components/StockList.jsx)
  - Replace polling with EventSource
  - Subscribe on mount, unsubscribe on unmount
  - Handle reconnection logic

**Good luck and happy coding! 💻**
