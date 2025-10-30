# StockAnalyzer - Project Overview

## Project Type
Full-stack stock market analysis and prediction application for swing trading and CNN training data collection.

## Technology Stack
- **Backend**: FastAPI (Python 3.11), PostgreSQL + TimescaleDB, PyTorch
- **Frontend**: React 18, TradingView Lightweight Charts, Recharts
- **DevOps**: Docker Compose
- **Data Source**: Polygon.io API

## Key Features
1. **335+ Pre-populated Stocks** across 18 sectors
2. **Technical Analysis**: 15+ indicators (RSI, MACD, Bollinger Bands, etc.)
3. **Pattern Recognition**: 
   - 40 candlestick patterns
   - 12 chart patterns (H&S, triangles, wedges, etc.)
4. **Machine Learning**: LSTM, Transformer, CNN, CNN-LSTM models
5. **Sentiment Analysis**: FinBERT-based news sentiment
6. **Risk Management**: Trailing stops, portfolio heat monitoring
7. **Multi-Timeframe Support**: 1h, 4h, 1d, 1w, 1mo (smart aggregation from 1h base)

## Project Structure
```
StockAnalyzer/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # API endpoints
│   │   ├── services/          # Business logic
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   └── utils/             # Shared utilities
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/        # React components
│       └── services/api.js    # API client
├── database/init.sql
├── docs/                      # Documentation
└── docker-compose.yml
```

## Current Status (2025-10-30)
- **Phase 7 Complete**: Enhanced dashboard with sector organization and batch operations
- **Risk Management UI**: Complete with trailing stop calculator and portfolio heat monitor
- **Multi-Timeframe Infrastructure**: Implemented with smart aggregation
- **Database**: 335 stocks, mostly with daily data, 1 stock (AAPL) with 1h data
- **Pattern Quality System**: 60-80% false positive reduction

## Key Components

### Backend Services
- `polygon_fetcher.py`: Data fetching from Polygon.io
- `chart_patterns.py`: 12 chart pattern detection algorithms
- `candlestick_patterns.py`: 40 candlestick pattern detectors
- `technical_indicators.py`: Technical analysis calculations
- `ml_predictor.py`: ML model training and prediction
- `order_calculator.py`: Position sizing and risk calculations
- `risk_utils.py`: Shared risk management utilities

### Frontend Components
- `StockList.jsx`: Main dashboard with sector organization
- `StockDetailSideBySide.jsx`: Stock detail view (CURRENT - not StockDetail.jsx)
- `ChartPatterns.jsx`: Chart pattern detection UI
- `CandlestickPatterns.jsx`: Candlestick pattern UI
- `TrailingStopCalculator.jsx`: ATR-based trailing stops
- `PortfolioHeatMonitor.jsx`: Portfolio risk tracking
- `OrderCalculator.jsx`: Position sizing calculator

## Important URLs
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Database Schema
- `stocks`: Stock metadata (symbol, name, sector, industry)
- `stock_prices`: OHLCV data (TimescaleDB hypertable) with timeframe column
- `chart_patterns`: Detected chart patterns with trendlines
- `candlestick_patterns`: Detected candlestick patterns
- `predictions`: ML predictions
- `sentiment_scores`: News sentiment
- `prediction_performance`: Accuracy tracking

## Development Commands
```bash
# Start all services
docker-compose up

# Restart backend after changes
docker-compose restart backend

# View logs
docker-compose logs backend --tail=50

# Database population
python populate_stocks.py
python populate_stocks_batch2.py
```

## Next Phase (Phase 8)
1. Multi-timeframe pattern detection
2. CNN model training on collected patterns
3. Database indexing and caching
4. Performance optimization
5. Real-time updates (WebSockets)

## Important Notes
- StockDetail.jsx is OBSOLETE - use StockDetailSideBySide.jsx
- System is backward compatible with legacy 1d data
- Free Polygon.io tier: 5 requests/minute
- Pattern detection optimized for CNN training data collection
- Target: 10,000+ labeled patterns for CNN training
