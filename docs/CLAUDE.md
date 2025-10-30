# Claude AI Assistant - Project Briefing Document

**READ THIS FIRST** before working on StockAnalyzer project.

**Last Updated**: 2025-10-30
**Project Phase**: Phase 8 (Advanced Features)

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
├── chart_patterns.py           # 12 chart pattern detection (core algorithm)
├── candlestick_patterns.py     # 40 candlestick patterns
├── technical_indicators.py     # 15+ technical indicators
├── order_calculator.py         # Position sizing + risk management
├── polygon_fetcher.py          # Data fetching from Polygon.io
├── timeframe_service.py        # Multi-timeframe aggregation
└── multi_timeframe_patterns.py # Cross-timeframe pattern validation
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
2. **Check API docs**: http://localhost:8000/docs
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
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

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

### HIGH PRIORITY
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
- [ ] Review API docs: http://localhost:8000/docs
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

**Good luck and happy coding! 💻**
