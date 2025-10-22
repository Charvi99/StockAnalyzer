# Claude Context Backup - Stock Analyzer Project

**Last Updated**: 2025-10-22
**Project Version**: Phase 7 Complete
**Database**: 335+ stocks pre-populated

---

## 🎯 Project Overview

**Stock Analyzer** is a full-stack application for stock market analysis combining technical indicators, machine learning predictions, sentiment analysis, and chart pattern recognition. The project is optimized for collecting CNN training data from chart patterns.

### Key Metrics
- **Frontend**: React 18 with TradingView charts
- **Backend**: FastAPI with Python 3.11
- **Database**: PostgreSQL + TimescaleDB (SQLite capable for migrations)
- **Stocks**: 335+ pre-populated across 18 sectors
- **Patterns**: 40 candlestick + 12 chart patterns
- **ML Models**: LSTM, Transformer, CNN, CNN-LSTM

---

## 🗂️ Project Architecture

### Directory Structure
```
StockAnalyzer/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # API endpoints
│   │   │   ├── analysis.py    # Technical analysis & dashboard
│   │   │   ├── chart_patterns.py  # Chart pattern detection
│   │   │   ├── patterns.py    # Candlestick patterns
│   │   │   └── ...
│   │   ├── services/
│   │   │   ├── chart_patterns.py  # Pattern detection logic
│   │   │   ├── technical_indicators.py
│   │   │   └── ...
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   └── main.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── StockList.jsx      # Main dashboard
│       │   ├── StockCard.jsx      # Individual stock card
│       │   ├── ChartPatterns.jsx  # Pattern detection UI
│       │   └── ...
│       └── services/
│           └── api.js             # API client
├── populate_stocks.py            # 246 stocks
├── populate_stocks_batch2.py     # 94 more stocks
├── docker-compose.yml
└── README.md
```

---

## 🎨 Recent Enhancements (Phase 7)

### 1. Enhanced Dashboard (StockList.jsx)

**Features**:
- Sector-based organization with 18 color-coded themes
- Collapsible sector sections
- Toggle between grouped and grid views
- Batch operations (fetch data, detect patterns)
- Real-time progress tracking

**Key Components**:
```javascript
// Sector Configuration
const SECTOR_CONFIG = {
  'Technology': { color: '#667eea', icon: '💻', bgLight: '#eef2ff' },
  'Healthcare': { color: '#059669', icon: '⚕️', bgLight: '#d1fae5' },
  // ... 16 more sectors
};

// Batch Operations
- handleBatchFetch5Years() - Fetches 5Y data for all stocks
- handleBatchDetectPatterns() - Detects patterns for all stocks
```

**Location**: `frontend/src/components/StockList.jsx`

### 2. Enhanced Stock Cards (StockCard.jsx)

**Features**:
- Company name, sector badge, industry badge
- Colored top border matching sector
- Sector icon with symbol
- Retry buttons for failed analysis

**Location**: `frontend/src/components/StockCard.jsx`

### 3. Backend API Updates

**Changed Files**:
- `backend/app/schemas/analysis.py` - Added `name`, `sector`, `industry` fields to `RecommendationResponse`
- `backend/app/api/routes/analysis.py` - Updated `_get_recommendation_for_stock()` and `get_dashboard_analysis()` to include metadata

**Key Change**:
```python
# RecommendationResponse now includes:
name: Optional[str] = None
sector: Optional[str] = None
industry: Optional[str] = None
```

### 4. Chart Pattern Detection Optimizations

**Preset Parameters** (ChartPatterns.jsx):
```javascript
overlapThreshold: 5%          // Reduce overlapping patterns
excludeRoundingPatterns: true // Reduce noise
peakOrder: 4                  // Balanced sensitivity
minConfidence: 50%            // Quality threshold
```

**Purpose**: Optimize for CNN training data collection by reducing false positives by 60-80%

**Location**: `frontend/src/components/ChartPatterns.jsx`

---

## 🔧 Critical Bug Fixes

### Bug #1: Trendline start_idx Undefined (2025-10-22)

**Error**: `NameError: name 'start_idx' is not defined` in chart_patterns.py

**Root Cause**: Pattern detection methods using peak/trough iteration (not sliding windows) were calling `_calculate_trendline(..., start_idx)` without defining `start_idx`.

**Fix Applied**: Added `start_idx` definition in 6 methods:
```python
# Example in detect_head_and_shoulders()
for i in range(len(peaks_list) - 2):
    left_shoulder_idx = peaks_list[i]
    head_idx = peaks_list[i + 1]
    right_shoulder_idx = peaks_list[i + 2]
    start_idx = left_shoulder_idx  # ← ADDED THIS LINE
```

**Fixed Methods**:
1. `detect_head_and_shoulders()` - Line 410
2. `detect_inverse_head_and_shoulders()` - Line 506
3. `detect_double_top()` - Line 601
4. `detect_double_bottom()` - Line 687
5. `detect_rounding_top()` - Line 1409
6. `detect_triple_bottom()` - Line 1514

**Location**: `backend/app/services/chart_patterns.py`

### Bug #2: Dashboard Not Showing Company Info (2025-10-22)

**Symptoms**: Stock cards displayed N/A for name, sector, industry even though data was in database.

**Root Cause**: `RecommendationResponse` schema didn't include `name`, `sector`, `industry` fields, so API wasn't returning them.

**Fix Applied**:
1. Added fields to schema (`backend/app/schemas/analysis.py:178-180`)
2. Updated API to include data (`backend/app/api/routes/analysis.py:170-172`)
3. Updated error responses to include metadata (`backend/app/api/routes/analysis.py:212,215`)

---

## 📊 Database Information

### Population Scripts

**populate_stocks.py** (246 stocks):
- Technology (50+), Healthcare (30+), Financial (30+), etc.
- Run: `python populate_stocks.py`

**populate_stocks_batch2.py** (94 stocks):
- Additional semiconductors, biotechnology, financials, materials, etc.
- Run: `python populate_stocks_batch2.py`

**Total**: 335+ stocks across 18 sectors

### Key Tables

```sql
stocks              -- Stock metadata (symbol, name, sector, industry)
stock_prices        -- OHLCV data (TimescaleDB hypertable)
chart_patterns      -- Detected chart patterns with trendlines
candlestick_patterns -- Detected candlestick patterns
predictions         -- ML predictions
sentiment_scores    -- News sentiment
```

### Database Capacity

- **SQLite Max**: 281 TB
- **Current Data**: ~100 MB (335 stocks × ~750 records avg)
- **Projected**: 10M records = ~4 GB
- **Conclusion**: No capacity concerns for CNN training data collection

---

## 🎯 CNN Training Data Collection Workflow

### Goal
Collect 10,000+ labeled chart patterns for CNN model training.

### Strategy
1. **Use 200+ stocks with 5Y data**: ~50 patterns per stock = 10,000 patterns
2. **Optimized detection parameters**: Reduce false positives by 60-80%
3. **Batch operations**: Efficient data collection
4. **User labeling**: Confirm/reject patterns for quality

### Steps

#### 1. Batch Fetch Data
```javascript
// Click "🔧 Fetch 5Y Data" button in dashboard
// Fetches 5 years of daily data for all 335 stocks
// Progress bar shows live updates
// Takes ~11 minutes (335 stocks × 2 sec/stock)
```

#### 2. Batch Pattern Detection
```javascript
// Click "🎯 Detect Patterns" button (TO BE IMPLEMENTED)
// Uses optimal presets automatically:
//   - overlapThreshold: 5%
//   - excludeRoundingPatterns: true
//   - peakOrder: 4
//   - minConfidence: 50%
// Progress bar with pattern count tracking
```

#### 3. Review and Label
```javascript
// Open individual stock details
// View detected patterns on charts
// Confirm/reject each pattern
// Add notes for quality tracking
```

#### 4. Export Training Data
```javascript
// GET /api/v1/chart-patterns/export/training-data?confirmed_only=true
// Returns JSON with labeled patterns
// Includes: symbol, pattern_type, signal, confidence, trendlines
```

---

## 🚀 Common Commands

### Docker
```bash
# Start all services
docker-compose up

# Restart backend after code changes
docker-compose restart backend

# View backend logs
docker-compose logs backend --tail=50

# Stop everything
docker-compose down
```

### Database Population
```bash
# Populate initial stocks
python populate_stocks.py

# Add additional stocks
python populate_stocks_batch2.py
```

### Frontend Development
```bash
cd frontend
npm start       # Development server on port 3000
npm build       # Production build
```

---

## 🔑 Key API Endpoints

### Dashboard
```
GET /api/v1/analysis/dashboard
# Returns all tracked stocks with analysis data
# Includes: name, sector, industry, recommendations, patterns
```

### Chart Pattern Detection
```
POST /api/v1/stocks/{stock_id}/detect-chart-patterns
Body: {
  "days": null,               # Analyze all data
  "min_pattern_length": 20,
  "remove_overlaps": true,
  "exclude_patterns": ["Rounding Top", "Rounding Bottom"],
  "overlap_threshold": 0.05,
  "peak_order": 4,
  "min_confidence": 0.5,
  "min_r_squared": 0.0
}
```

### Batch Operations (Frontend)
```javascript
// Batch fetch - implemented
handleBatchFetch5Years()

// Batch pattern detection - TO BE IMPLEMENTED
handleBatchDetectPatterns()
```

---

## 🐛 Known Issues & Limitations

### Current Issues
1. **Batch Pattern Detection**: Not yet implemented (was about to complete when context ended)
2. **Background Tasks**: Multiple docker-compose processes running (need cleanup)

### Rate Limits
- **Polygon.io Free Tier**: 5 requests/minute
- **Workaround**: 100ms delay between batch requests in frontend

### Performance
- **Batch Fetch**: ~2 seconds per stock (API limited)
- **Pattern Detection**: ~3 seconds per stock (computation)
- **Total Time for 335 stocks**: ~28 minutes for full data collection

---

## 💡 Design Decisions

### Why Sector-Based Organization?
- 335 stocks in one flat list is overwhelming
- Sector grouping provides logical organization
- Color coding enables quick visual identification
- Collapsible sections reduce clutter

### Why Batch Operations?
- Manual data collection for 335 stocks is impractical
- Batch operations enable CNN training data collection
- Progress tracking provides user feedback
- Error handling and reporting for debugging

### Why Preset Parameters?
- Optimal detection parameters reduce false positives
- New users don't need to understand complex parameters
- Advanced users can still access full controls
- Consistent results across different users

### Why SQLAlchemy + Pydantic?
- SQLAlchemy: Database ORM with migration support
- Pydantic: API schema validation and documentation
- Separation of concerns: models vs schemas
- Type safety and auto-generated API docs

---

## 🎓 Learning Resources

### Pattern Detection Algorithm
Located in: `backend/app/services/chart_patterns.py`

**Key Concepts**:
1. **Peak/Trough Detection**: Uses scipy's `find_peaks()` with prominence/distance filters
2. **Trendline Calculation**: Linear regression with R² quality scoring
3. **Pattern Matching**: Template matching for specific formations (H&S, triangles, etc.)
4. **Quality Scoring**: Multi-factor algorithm (R², volume, prior trend)

### Frontend State Management
Located in: `frontend/src/components/StockList.jsx`

**Key Patterns**:
```javascript
// State for batch operations
const [batchFetching, setBatchFetching] = useState(false);
const [batchProgress, setBatchProgress] = useState({
  current: 0,
  total: 0,
  currentSymbol: ''
});

// Update progress in loop
for (let i = 0; i < stocks.length; i++) {
  setBatchProgress({
    current: i + 1,
    total: stocks.length,
    currentSymbol: stock.symbol
  });
  // ... perform operation
  await new Promise(resolve => setTimeout(resolve, 100)); // Rate limiting
}
```

---

## 📝 Next Steps (Phase 8)

### Immediate Tasks
1. **Complete Batch Pattern Detection**:
   - Implement `handleBatchDetectPatterns()` in StockList.jsx
   - Add UI button and progress tracking
   - Test with 10-20 stocks first

2. **CNN Model Training**:
   - Collect 10,000+ labeled patterns
   - Design CNN architecture for pattern classification
   - Train model on labeled data
   - Evaluate accuracy and fine-tune

### Future Enhancements
3. **Performance Optimization**:
   - Add database indexes
   - Implement caching layer
   - Optimize React re-renders

4. **User Features**:
   - Real-time updates (WebSockets)
   - User authentication
   - Portfolio simulation
   - Email alerts

---

## 🔍 Quick Reference

### File Locations
- **Dashboard**: `frontend/src/components/StockList.jsx`
- **Stock Card**: `frontend/src/components/StockCard.jsx`
- **Pattern Detection UI**: `frontend/src/components/ChartPatterns.jsx`
- **Pattern Service**: `backend/app/services/chart_patterns.py`
- **Analysis Routes**: `backend/app/api/routes/analysis.py`
- **API Client**: `frontend/src/services/api.js`

### Important Functions
- `_get_recommendation_for_stock()` - Combines all analysis signals
- `detect_head_and_shoulders()` - Pattern detection example
- `_calculate_trendline()` - Linear regression with relative indices
- `handleBatchFetch5Years()` - Batch data fetching
- `getSectorConfig()` - Sector color/icon mapping

### Environment Variables
```bash
POLYGON_API_KEY=your_key_here
DATABASE_URL=postgresql://user:pass@localhost:5432/db
```

---

## ⚠️ Important Notes

1. **Always restart backend** after changing Python files
2. **Use `start_idx`** in pattern detection for trendline calculations
3. **Include metadata** (name, sector, industry) in all stock responses
4. **Rate limit API calls** to avoid overwhelming Polygon.io
5. **Test batch operations** with small sample first

---

## 📞 Project Contact

**Developer**: [Your Name]
**Last Session**: 2025-10-22
**Session Duration**: Multi-part conversation with context continuation
**Status**: Phase 7 Complete, Ready for Phase 8 (CNN Training)

---

**End of Context Document**
