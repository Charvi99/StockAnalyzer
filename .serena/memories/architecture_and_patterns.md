# StockAnalyzer - Architecture & Design Patterns

## Architecture Overview

### Multi-Layer Architecture
```
Frontend (React) → API Layer (FastAPI) → Services → Database (PostgreSQL + TimescaleDB)
                                        ↓
                                   External APIs (Polygon.io)
```

## Key Design Patterns

### 1. Service Layer Pattern
Business logic encapsulated in services:
- `PolygonFetcher`: External API integration
- `ChartPatternDetection`: Pattern detection algorithms
- `TechnicalIndicators`: Technical analysis
- `MLPredictor`: Machine learning operations
- `OrderCalculator`: Risk management and position sizing

### 2. Repository Pattern
SQLAlchemy models act as repositories for data access.

### 3. Schema Validation Pattern
Pydantic schemas for request/response validation and API documentation.

## Pattern Detection Architecture

### Chart Pattern Quality Scoring System
Multi-factor algorithm for reducing false positives:

1. **ATR (Average True Range)**: Volatility measurement
2. **Prior Trend Detection**: Validates reversal patterns
3. **Volume Profile Analysis**: Declining volume during consolidation
4. **Weighted Quality Algorithm**:
   - Trendline R² fit: 35% weight
   - Volume behavior: 25% weight
   - Prior trend strength: 20% weight
   - Base pattern confidence: 20% weight
5. **Thresholds**:
   - Minimum R² of 0.7 for trendlines
   - Overall quality score > 0.5 required

**Result**: 60-80% reduction in false positives

### Pattern Detection Flow
```
User Request
    ↓
API Endpoint (/detect-chart-patterns)
    ↓
ChartPatternDetection Service
    ↓
chart_patterns.py (scipy peak detection)
    ↓
Pattern Quality Scoring
    ↓
Trendline Calculation (linear regression)
    ↓
Pattern Objects (with confidence, R², trendlines)
    ↓
Database Storage
    ↓
Frontend Display
```

## Multi-Timeframe Architecture (Current)

### Smart Aggregation System
- **Base Data**: 1h bars stored in database
- **Aggregated Timeframes**: 2h, 4h, 1d, 1w, 1mo generated on-the-fly
- **Fallback Mechanism**: Legacy 1d data used if 1h not available
- **Benefits**: 51% storage savings vs storing all timeframes

### Timeframe Aggregation Logic
```python
# OHLC Aggregation Rules:
- Open = First bar's open
- High = Max of all highs
- Low = Min of all lows
- Close = Last bar's close
- Volume = Sum of all volumes
```

### Database Schema (Multi-Timeframe)
```sql
stock_prices (
    stock_id INT,
    timeframe VARCHAR(10),  -- '1h', '4h', '1d', etc.
    timestamp TIMESTAMP,
    open, high, low, close, volume,
    PRIMARY KEY (stock_id, timeframe, timestamp)
)
```

## Risk Management Architecture

### Shared Risk Utilities
Central location for all risk calculations in `risk_utils.py`:
- ATR calculation
- Position sizing
- Risk/reward ratios
- Trailing stop calculations
- Portfolio heat calculations

### Before/After Refactoring
**Before**: Duplicate risk calculations in OrderCalculator and RiskManager
**After**: Single source of truth in risk_utils.py, used by all services

## API Design Patterns

### RESTful Endpoints
- GET: Retrieve data
- POST: Create or trigger analysis
- PATCH: Update (e.g., confirm patterns)
- DELETE: Remove data

### Response Format
```json
{
  "success": true,
  "data": {...},
  "message": "Operation completed",
  "timestamp": "2025-10-30T..."
}
```

## Frontend Architecture

### Component Organization
```
App.jsx
└── StockList.jsx (Main Dashboard)
    ├── Sector Groups (Collapsible)
    │   └── StockCard.jsx (Individual Cards)
    └── StockDetailSideBySide.jsx (Modal)
        ├── Left Panel (Tabs)
        │   ├── Overview
        │   ├── Technical Analysis
        │   ├── Candlestick Patterns
        │   ├── Chart Patterns
        │   ├── Order Calculator
        │   └── Risk Tools (NEW)
        │       ├── TrailingStopCalculator
        │       └── PortfolioHeatMonitor
        └── Right Panel
            └── StockChart.jsx (TradingView)
```

### State Management
- Component-level state (useState)
- Prop drilling for data flow
- React.memo for performance optimization

**Future Enhancement**: Consider Redux Toolkit or Zustand for centralized state

## Data Flow Patterns

### Batch Operations Pattern
```javascript
// Progress Tracking Pattern
const [batchProgress, setBatchProgress] = useState({
  current: 0,
  total: 0,
  currentSymbol: ''
});

for (let i = 0; i < stocks.length; i++) {
  setBatchProgress({
    current: i + 1,
    total: stocks.length,
    currentSymbol: stock.symbol
  });
  // Perform operation
  await delay(100); // Rate limiting
}
```

## Performance Optimization Patterns

### 1. N+1 Query Prevention
Use eager loading (joinedload/selectinload) instead of loops.

### 2. React Memoization
Wrap expensive components with React.memo:
```javascript
export default React.memo(StockChart);
```

### 3. API Response Caching
TimescaleDB for time-series data optimization.

### 4. Debouncing
For user input (indicator parameters, search).

## Security Patterns

### 1. Environment Variables
Sensitive data (API keys) stored in .env file.

### 2. SQL Injection Prevention
SQLAlchemy parameterized queries.

### 3. CORS Configuration
Configured in FastAPI for frontend access.

## Testing Patterns (Future)

### Backend Testing
- Unit tests for services
- Integration tests for API endpoints
- Use pytest

### Frontend Testing
- Component tests with React Testing Library
- E2E tests with Cypress (future)

## Documentation Patterns

### 1. Inline Documentation
Docstrings in Python, JSDoc in JavaScript.

### 2. API Documentation
Auto-generated with FastAPI (Swagger/ReDoc).

### 3. User Documentation
Markdown files in /docs folder:
- README.md: Main documentation
- CLAUDE_CONTEXT.md: Project context for AI
- RISK_TOOLS_USER_GUIDE.md: Feature-specific guides
- TECHNICAL_INDICATORS_ENCYCLOPEDIA.md: Technical reference

## Error Handling Patterns

### Backend
```python
try:
    # Operation
except SpecificException as e:
    logger.error(f"Error: {e}")
    raise HTTPException(status_code=400, detail=str(e))
```

### Frontend
```javascript
try {
  // API call
} catch (error) {
  console.error('Error:', error);
  setError(error.message);
}
```

## Deployment Pattern

### Docker Compose
Three-tier architecture:
1. Database (PostgreSQL + TimescaleDB)
2. Backend (FastAPI)
3. Frontend (React)

Health checks ensure proper startup order.
