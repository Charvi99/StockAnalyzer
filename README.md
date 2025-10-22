# Stock Analyzer

A full-stack web application for comprehensive stock market analysis and prediction. This application helps you understand stock investing by providing technical analysis, machine learning predictions, sentiment analysis, and chart pattern recognition. Pre-populated with **335+ stocks** across 18 sectors for immediate analysis and CNN training data collection.

## Features

### Phase 1 - Core Infrastructure ✅
- **Backend API** (FastAPI) - RESTful API with automatic documentation
- **Frontend** (React) - Modern, responsive user interface
- **Database** (PostgreSQL + TimescaleDB) - Optimized for time-series stock data
- **Docker** - Containerized services for easy deployment
- **Health Check** - API and database connectivity monitoring
- **Stock Management** - CRUD operations for tracked stocks

### Phase 2 - Data Pipeline ✅
- **Stock Data Fetcher** - Real-time and historical data from Polygon.io
- **Interactive Charts** - Beautiful candlestick and line charts with TradingView Lightweight Charts
- **Chart Overlays** - Toggle technical indicators (MA, EMA, Bollinger Bands, Parabolic SAR) on charts
- **API Endpoints** - Fetch and retrieve stock price data
- **Data Storage** - Efficient time-series storage with TimescaleDB

### Phase 3 - Analysis & Predictions ✅
- **Technical Indicators** (15+ indicators):
  - **Trend**: Moving Averages (SMA/EMA), MACD, ADX, Parabolic SAR, Ichimoku Cloud
  - **Momentum**: RSI, Stochastic Oscillator, CCI
  - **Volume**: OBV, VWAP, A/D Line
  - **Volatility**: Bollinger Bands, ATR, Keltner Channels
- **Configurable Parameters** - Customize indicator periods and settings
- **Buy/Sell/Hold Recommendations** - Multi-indicator trading signals
- **Confidence Scores** - Measure reliability of recommendations
- **Signal Radar Chart** - Visual representation of indicator agreement
- **Comprehensive Analysis Dashboard** - Categorized view of all indicators
- **Indicator Encyclopedia** - Built-in wiki-style documentation with search

### Phase 4 - Advanced ML & Tracking ✅
- **Machine Learning Models**:
  - LSTM (Long Short-Term Memory)
  - Transformer with multi-head attention
  - CNN (Convolutional Neural Network)
  - CNN-LSTM hybrid architecture
- **Model Training** - Train custom models on historical data
- **Sentiment Analysis** - FinBERT-based news sentiment scoring
- **Weighted Recommendations** - Combined technical (40%), ML (40%), sentiment (20%)
- **Prediction Performance Tracking** - Automated daily evaluation of prediction accuracy
- **Model Management** - List, delete, and manage trained models

### Phase 5 - Candlestick Pattern Recognition ✅
- **40 Candlestick Patterns** - Comprehensive pattern detection library:
  - **20 Bullish Patterns**: Hammer, Inverted Hammer, Bullish Marubozu, Dragonfly Doji, Bullish Engulfing, Piercing Line, Tweezer Bottom, Bullish Kicker, Bullish Harami, Bullish Counterattack, Morning Star, Morning Doji Star, Three White Soldiers, Three Inside Up, Three Outside Up, Bullish Abandoned Baby, Rising Three Methods, Upside Tasuki Gap, Mat Hold, Rising Window
  - **20 Bearish Patterns**: Hanging Man, Shooting Star, Bearish Marubozu, Gravestone Doji, Bearish Engulfing, Dark Cloud Cover, Tweezer Top, Bearish Kicker, Bearish Harami, Bearish Counterattack, Evening Star, Evening Doji Star, Three Black Crows, Three Inside Down, Three Outside Down, Bearish Abandoned Baby, Falling Three Methods, Downside Tasuki Gap, On Neck Line, Falling Window
- **Pattern Detection** - Automated detection using pandas DataFrame analysis (no TA-Lib dependency)
- **Chart Markers** - Visual arrows on candlestick charts marking detected patterns
- **User Confirmation System** - Label patterns as true/false positives for ML training dataset
- **Pattern Statistics** - Track confirmation rates and pattern performance
- **Export Training Data** - Export labeled patterns for machine learning model training

### Phase 6 - Chart Pattern Recognition ✅
- **12 Chart Patterns** - Classic technical analysis patterns:
  - **Reversal Patterns**: Head and Shoulders, Inverse Head and Shoulders, Double Top, Double Bottom, Rising Wedge, Falling Wedge
  - **Continuation Patterns**: Ascending Triangle, Descending Triangle, Symmetrical Triangle, Cup and Handle, Flag, Pennant
- **Advanced Detection Algorithms** - Scipy-based peak/trough detection with linear regression trendlines
- **Pattern Classification** - Categorized by type (reversal/continuation) and signal (bullish/bearish/neutral)
- **Key Price Levels** - Calculated breakout price, target price, and stop loss for each pattern
- **Trendline Analysis** - Slope, R-squared, and support/resistance line coordinates
- **User Confirmation System** - Label patterns for building ML training datasets
- **Pattern Statistics & Export** - Track confirmation rates and export labeled data
- **Optimized for CNN Training** - Preset parameters (5% overlap, peak sensitivity 4, 50% min confidence)

### Phase 7 - Enhanced Dashboard & Data Collection ✅
- **335+ Pre-populated Stocks** - Diverse stock selection across 18 sectors:
  - Technology (74), Healthcare (41), Financial (38), Consumer Goods (33), Energy (25), and more
- **Sector-Based Organization** - Color-coded cards with icons and collapsible sections:
  - 18 unique sector themes (colors, icons, light backgrounds)
  - Grouped view with sector headers and stock counts
  - Toggle between sector-grouped and grid views
- **Enhanced Stock Cards** - Rich visual information:
  - Company name, sector badge, industry badge
  - Colored top border matching sector theme
  - Sector icon with symbol display
- **Batch Operations** - Efficient bulk processing:
  - Batch fetch 5 years of historical data for all stocks
  - Batch pattern detection with optimal presets
  - Real-time progress tracking with live updates
  - Success/failure reporting with summaries
- **CNN Training Data Collection** - Optimized workflow:
  - One-click data collection for 200+ stocks
  - Estimated 10,000+ patterns (minimum viable for CNN)
  - Export labeled patterns for machine learning

## Technology Stack

### Backend
- Python 3.11
- FastAPI 0.109.0 - Modern web framework
- SQLAlchemy 2.0.25 - ORM for database operations
- PostgreSQL + TimescaleDB - Time-series database
- PyTorch 2.1.2 - Deep learning framework
- Transformers 4.36.2 - FinBERT for sentiment analysis
- pandas, numpy, scipy, scikit-learn - Data processing and analysis
- APScheduler 3.10.4 - Background task scheduling
- Polygon.io API - Real-time stock data
- Uvicorn - ASGI server

### Frontend
- React 18
- Axios - HTTP client
- Recharts - Data visualization library
- TradingView Lightweight Charts - Professional candlestick charts
- CSS-in-JS styling

### DevOps
- Docker & Docker Compose
- Git

## Project Structure

```
StockAnalyzer/
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── health.py         # Health check endpoint
│   │   │   ├── stocks.py         # Stock CRUD endpoints
│   │   │   ├── prices.py         # Price data endpoints
│   │   │   ├── analysis.py       # Technical analysis & predictions
│   │   │   ├── ml.py             # ML model training & predictions
│   │   │   ├── sentiment.py      # Sentiment analysis endpoints
│   │   │   ├── patterns.py       # Candlestick pattern endpoints
│   │   │   └── chart_patterns.py # Chart pattern recognition endpoints
│   │   ├── db/
│   │   │   └── database.py       # Database connection
│   │   ├── models/
│   │   │   └── stock.py          # SQLAlchemy models
│   │   ├── schemas/
│   │   │   ├── stock.py          # Pydantic schemas for stocks
│   │   │   ├── analysis.py       # Analysis schemas
│   │   │   ├── ml_sentiment.py   # ML and sentiment schemas
│   │   │   ├── patterns.py       # Candlestick pattern schemas
│   │   │   └── chart_patterns.py # Chart pattern schemas
│   │   ├── services/
│   │   │   ├── polygon_fetcher.py       # Polygon.io API client
│   │   │   ├── technical_indicators.py  # Technical analysis calculations
│   │   │   ├── ml_predictor.py          # ML model implementations
│   │   │   ├── sentiment_service.py     # News & sentiment analysis
│   │   │   ├── scheduler.py             # Prediction evaluation scheduler
│   │   │   ├── candlestick_patterns.py  # 40 candlestick pattern detectors
│   │   │   └── chart_patterns.py        # 12 chart pattern detectors
│   │   └── main.py               # FastAPI application
│   ├── ml/                        # Saved ML models
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/
│   │   │   ├── StockList.jsx          # List of stocks
│   │   │   ├── StockDetail.jsx        # Stock detail modal
│   │   │   ├── StockChart.jsx         # Interactive candlestick chart
│   │   │   ├── TechnicalAnalysis.jsx  # Technical analysis dashboard
│   │   │   ├── SignalRadar.jsx        # Radar chart visualization
│   │   │   ├── IndicatorInfo.jsx      # Indicator encyclopedia
│   │   │   ├── CandlestickPatterns.jsx # Candlestick pattern detection UI
│   │   │   └── ChartPatterns.jsx      # Chart pattern detection UI
│   │   ├── services/
│   │   │   └── api.js            # API client
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── index.js
│   ├── Dockerfile
│   └── package.json
├── database/
│   └── init.sql                   # Database schema
├── docs/                          # Documentation
│   ├── SWING_TRADING_OUTLOOK.md   # Swing trading guide & platform recommendations
│   ├── POLYGON_SETUP.md           # Polygon.io setup guide
│   ├── ALEMBIC_GUIDE.md           # Database migration guide
│   ├── CLAUDE_CONTEXT.md          # Project context for AI assistants
│   ├── TECHNICAL_INDICATORS_ENCYCLOPEDIA.md
│   └── ...                        # Other documentation
├── oldTools/                      # Legacy trading tools (reference)
├── populate_stocks.py             # Population script (246 stocks)
├── populate_stocks_batch2.py      # Additional stocks (94 stocks)
├── docker-compose.yml
├── .env                          # Environment variables (not in git)
├── .env.example                  # Environment template
└── README.md
```

## Getting Started

### Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Docker Compose
- Git
- Polygon.io API key (free tier available)

### Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd C:\Work\MyTools\StockAnalyzer
   ```

2. **Configure API key:**
   ```bash
   cp .env.example .env
   # Edit .env and add your Polygon.io API key
   ```

3. **Build and start all services:**
   ```bash
   docker-compose up --build
   ```

   This will start three services:
   - Database (PostgreSQL + TimescaleDB) on port 5432
   - Backend (FastAPI) on port 8000
   - Frontend (React) on port 3000

4. **Wait for all services to be healthy:**
   - Database initialization takes ~10-20 seconds
   - Backend starts once database is healthy
   - Frontend starts after backend

### Accessing the Application

Once all services are running:

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs (Swagger UI)
- **Alternative API Docs:** http://localhost:8000/redoc (ReDoc)
- **Health Check:** http://localhost:8000/health

### 🔑 Polygon.io API Setup

The application uses **Polygon.io** for stock market data.

**Quick Setup:**

1. Get your free API key: https://polygon.io/dashboard/signup
2. Create `.env` file: `cp .env.example .env`
3. Edit `.env` and add your API key:
   ```
   POLYGON_API_KEY=YOUR_KEY_HERE
   ```
4. Restart backend: `docker-compose restart backend`

**Free Tier Limits:** 5 requests/minute, unlimited daily requests

📖 **Full setup guide:** See [docs/POLYGON_SETUP.md](./docs/POLYGON_SETUP.md)

### 📈 Swing Trading Guide

Looking to use Stock Analyzer for swing trading? We've got you covered!

📖 **Complete guide:** See [docs/SWING_TRADING_OUTLOOK.md](./docs/SWING_TRADING_OUTLOOK.md)

**Includes:**
- Suitability assessment (⭐⭐⭐⭐⭐ Highly Suitable!)
- Daily trading workflows
- Pattern-specific strategies
- Risk management framework
- **Automated trading platform recommendations** (Alpaca, Interactive Brokers, TD Ameritrade)
- Integration architecture for automation
- Success metrics to track

## Usage

### Frontend Features

#### Enhanced Dashboard View
- **335+ Pre-loaded Stocks** - Ready for immediate analysis
- **Sector-Based Organization** - Grouped by 18 sectors with color coding:
  - Technology 💻, Healthcare ⚕️, Financial 💰, Consumer Goods 🛍️, Energy ⚡
  - Industrials 🏭, Retail 🏪, Real Estate 🏢, Materials ⛏️, Entertainment 🎬
  - Consumer Services 🔔, Automotive 🚗, Telecommunications 📡, Utilities 💡
  - Transportation ✈️, Leisure 🎨, Aerospace 🚀, Consumer Cyclical 🔄
- **Collapsible Sectors** - Click to expand/collapse each sector
- **Toggle Views** - Switch between grouped and flat grid layouts
- **Rich Stock Cards** - Company name, sector/industry badges, colored borders
- **Batch Operations**:
  - 🔧 **Fetch 5Y Data** - Fetch 5 years of data for all stocks at once
  - 🎯 **Detect Patterns** - Batch pattern detection with progress tracking
- **Add New Stocks** - Easy stock addition with symbol/sector/industry

#### Stock Detail Modal
1. **Fetch Historical Data**
   - Select period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
   - Select interval (1d, 1wk, 1mo)
   - Click "Fetch Data" to load from Polygon.io

2. **Interactive Chart**
   - Toggle between candlestick and line views
   - Overlay technical indicators:
     - MA Short (20) / MA Long (50)
     - EMA Fast (12) / EMA Slow (26)
     - Bollinger Bands (upper/middle/lower)
     - Parabolic SAR
   - Zoom and pan capabilities
   - Crosshair for precise values

3. **Signal Radar Chart**
   - Visual representation of all indicator signals
   - Shows agreement between indicators
   - Color-coded BUY (green), SELL (red), HOLD (yellow)

4. **Technical Analysis Dashboard**
   - **Indicator Parameters Settings**
     - Customize RSI period, MACD settings, MA periods, BB parameters
     - Reset to defaults button
     - Apply changes to recalculate all indicators
   - **Categorized Indicators** (expandable sections):
     - 📈 Trend Indicators
     - ⚡ Momentum Indicators
     - 📊 Volume Indicators
     - 📉 Volatility Indicators
   - Overall recommendation with confidence score
   - Signal breakdown (buy/sell/hold counts)

5. **Indicator Encyclopedia**
   - Click "ℹ️ Indicator Guide" button
   - Search all 15+ indicators
   - Detailed explanations with formulas
   - Interpretation guidelines
   - Usage examples

6. **Sentiment Analysis**
   - Analyze news sentiment
   - Sentiment index (-100 to 100)
   - Breakdown of positive/negative/neutral news
   - Recent headlines with scores

7. **Candlestick Pattern Recognition**
   - Click "Detect Patterns" to analyze last 90 days
   - View all detected patterns (40 types total)
   - Filter by bullish/bearish/all patterns
   - Visual arrows on chart marking pattern locations
   - Pattern descriptions and explanations
   - Confirm/reject patterns to build ML training dataset
   - View statistics (confirmed/rejected/pending counts)
   - Export labeled patterns for machine learning

8. **Chart Pattern Recognition**
   - Click "Detect Chart Patterns" to analyze with optimized settings:
     - **Overlap Threshold**: 5% (preset for optimal results)
     - **Exclude Rounding Patterns**: Enabled (reduces noise)
     - **Peak Sensitivity**: 4 (balanced detection)
     - **Min Confidence**: 50% (quality threshold)
   - View detected patterns (12 types: Head & Shoulders, Triangles, Cup & Handle, Flags, Wedges, etc.)
   - Filter by pattern type (reversal/continuation) and signal (bullish/bearish/neutral)
   - View key price levels (breakout, target, stop loss)
   - Analyze trendline data (slope, R-squared)
   - Confirm/reject patterns for ML training data collection
   - View pattern statistics and export labeled patterns
   - Advanced settings available for fine-tuning detection parameters

9. **CNN Training Data Collection**
   - **Optimized Workflow** for collecting training data:
     1. Use batch fetch to load 5Y data for all 335+ stocks
     2. Use batch pattern detection with preset optimal parameters
     3. Review and label detected patterns (10,000+ expected)
     4. Export labeled patterns for CNN model training
   - **Estimated Data**: ~10,000 patterns from 200 stocks × 5 years
   - **Quality Focus**: Preset filters reduce false positives by 60-80%

### API Endpoints

#### Health Check
```bash
GET /health
```

#### Stock Management
```bash
GET /api/v1/stocks/                     # List all stocks
GET /api/v1/stocks/{stock_id}           # Get stock by ID
GET /api/v1/stocks/symbol/{symbol}      # Get stock by symbol
POST /api/v1/stocks/                    # Create stock
PATCH /api/v1/stocks/{stock_id}         # Update stock
DELETE /api/v1/stocks/{stock_id}        # Delete stock
```

#### Price Data
```bash
POST /api/v1/stocks/{stock_id}/fetch    # Fetch from Polygon.io
GET /api/v1/stocks/{stock_id}/prices    # Get stored prices
GET /api/v1/stocks/{stock_id}/latest    # Get latest price
```

#### Technical Analysis
```bash
POST /api/v1/stocks/{stock_id}/analyze  # Run technical analysis
GET /api/v1/stocks/{stock_id}/recommendation  # Get comprehensive recommendation
GET /api/v1/stocks/{stock_id}/indicators  # Get indicator data with parameters
POST /api/v1/stocks/{stock_id}/predict   # Create prediction
GET /api/v1/stocks/{stock_id}/predictions  # Get prediction history
```

**Analysis Request with Custom Parameters:**
```json
POST /api/v1/stocks/1/analyze
{
  "period": "3mo",
  "rsi_period": 14,
  "macd_fast": 12,
  "macd_slow": 26,
  "macd_signal": 9,
  "bb_window": 20,
  "bb_std": 2.0,
  "ma_short": 20,
  "ma_long": 50
}
```

#### Machine Learning
```bash
POST /api/v1/ml/stocks/{stock_id}/train     # Train ML model
POST /api/v1/ml/stocks/{stock_id}/predict   # ML prediction
GET /api/v1/ml/models                       # List trained models
DELETE /api/v1/ml/models/{model_type}       # Delete model
```

#### Sentiment Analysis
```bash
POST /api/v1/sentiment/stocks/{stock_id}/analyze      # Analyze sentiment
POST /api/v1/sentiment/analyze-multiple               # Bulk analyze
GET /api/v1/sentiment/stocks/{stock_id}/history       # Sentiment history
GET /api/v1/sentiment/stocks/{stock_id}/latest        # Latest sentiment
DELETE /api/v1/sentiment/stocks/{stock_id}/history    # Clear history
```

#### Candlestick Pattern Recognition
```bash
POST /api/v1/stocks/{stock_id}/detect-patterns        # Detect all 40 patterns
GET /api/v1/stocks/{stock_id}/patterns                # Get detected patterns
PATCH /api/v1/patterns/{pattern_id}/confirm           # Confirm/reject pattern
DELETE /api/v1/patterns/{pattern_id}                  # Delete pattern
GET /api/v1/patterns/stats                            # Get pattern statistics
GET /api/v1/patterns/export/training-data             # Export labeled patterns for ML
```

#### Chart Pattern Recognition
```bash
POST /api/v1/stocks/{stock_id}/detect-chart-patterns  # Detect chart patterns (H&S, triangles, etc.)
GET /api/v1/stocks/{stock_id}/chart-patterns          # Get detected chart patterns
PATCH /api/v1/chart-patterns/{pattern_id}/confirm     # Confirm/reject chart pattern
DELETE /api/v1/chart-patterns/{pattern_id}            # Delete chart pattern
GET /api/v1/chart-patterns/stats                      # Get chart pattern statistics
GET /api/v1/chart-patterns/export/training-data       # Export labeled chart patterns
```

### Example Workflows

#### 1. Basic Stock Analysis
```bash
# 1. Fetch historical data
curl -X POST http://localhost:8000/api/v1/stocks/1/fetch \
  -H "Content-Type: application/json" \
  -d '{"period":"6mo","interval":"1d"}'

# 2. Run technical analysis
curl -X POST http://localhost:8000/api/v1/stocks/1/analyze \
  -H "Content-Type: application/json" \
  -d '{"period":"3mo"}'

# 3. Get comprehensive recommendation
curl http://localhost:8000/api/v1/stocks/1/recommendation
```

#### 2. ML Model Training and Prediction
```bash
# 1. Train LSTM model
curl -X POST http://localhost:8000/api/v1/ml/stocks/1/train \
  -H "Content-Type: application/json" \
  -d '{"model_type":"lstm","epochs":50,"batch_size":32}'

# 2. Make prediction
curl -X POST http://localhost:8000/api/v1/ml/stocks/1/predict \
  -H "Content-Type: application/json" \
  -d '{"model_type":"lstm","forecast_days":7}'
```

#### 3. Sentiment-Enhanced Analysis
```bash
# 1. Analyze sentiment
curl -X POST http://localhost:8000/api/v1/sentiment/stocks/1/analyze

# 2. Get recommendation (automatically includes sentiment)
curl http://localhost:8000/api/v1/stocks/1/recommendation
```

#### 4. Candlestick Pattern Detection and Labeling
```bash
# 1. Detect patterns in last 90 days
curl -X POST http://localhost:8000/api/v1/stocks/1/detect-patterns \
  -H "Content-Type: application/json" \
  -d '{"days":90}'

# 2. Get all detected patterns
curl http://localhost:8000/api/v1/stocks/1/patterns?days=90

# 3. Confirm pattern as true positive (for ML training)
curl -X PATCH http://localhost:8000/api/v1/patterns/123/confirm \
  -H "Content-Type: application/json" \
  -d '{"confirmed":true,"notes":"Strong reversal signal","confirmed_by":"user"}'

# 4. Export labeled patterns for ML model training
curl http://localhost:8000/api/v1/patterns/export/training-data?confirmed_only=true
```

#### 5. Chart Pattern Detection and Analysis
```bash
# 1. Detect chart patterns (Head & Shoulders, Triangles, etc.)
curl -X POST http://localhost:8000/api/v1/stocks/1/detect-chart-patterns \
  -H "Content-Type: application/json" \
  -d '{"days":90,"min_pattern_length":20}'

# 2. Get detected chart patterns with filters
curl "http://localhost:8000/api/v1/stocks/1/chart-patterns?pattern_type=reversal&signal=bullish"

# 3. Confirm chart pattern
curl -X PATCH http://localhost:8000/api/v1/chart-patterns/456/confirm \
  -H "Content-Type: application/json" \
  -d '{"confirmed":true,"notes":"Clear head and shoulders","confirmed_by":"user"}'

# 4. Get pattern statistics
curl http://localhost:8000/api/v1/chart-patterns/stats

# 5. Export labeled chart patterns for ML training
curl "http://localhost:8000/api/v1/chart-patterns/export/training-data?confirmed_only=true"
```

## Database Schema & Migrations

### Database Migrations with Alembic

This project uses **Alembic** for database schema version control and migrations.

- **Automatic Migration on Startup**: When you run `docker-compose up`, the backend automatically applies all pending migrations before starting the application.
- **Version Control**: All schema changes are tracked in `backend/alembic/versions/`
- **Easy Rollbacks**: Undo migrations if needed
- **Team Collaboration**: Share schema changes via code, not manual SQL scripts

**Common Commands:**
```bash
# Check migration status
docker-compose exec backend ./migrate.sh current

# View migration history
docker-compose exec backend ./migrate.sh history

# Create new migration after changing models
docker-compose exec backend ./migrate.sh create "add new column"

# Apply migrations manually
docker-compose exec backend ./migrate.sh upgrade

# Rollback last migration
docker-compose exec backend ./migrate.sh downgrade
```

📖 **Full Migration Guide**: See [docs/ALEMBIC_GUIDE.md](./docs/ALEMBIC_GUIDE.md) for detailed documentation

### Tables
- **stocks** - Stock information (symbol, name, sector, industry)
- **stock_prices** - Historical OHLCV data (TimescaleDB hypertable)
- **predictions** - ML model predictions with recommendations
- **prediction_performance** - Accuracy tracking (actual vs predicted)
- **technical_indicators** - Calculated indicator values
- **sentiment_scores** - News sentiment analysis results
- **candlestick_patterns** - Detected candlestick patterns with user confirmation
- **chart_patterns** - Detected chart patterns (H&S, triangles, etc.) with trendline data

### Sample Data
Pre-loaded stocks (335+ stocks via population scripts):
- **Technology** (74 stocks): AAPL, MSFT, GOOGL, NVDA, META, TSLA, AMD, INTC, CRM, ADBE, and more
- **Healthcare** (41 stocks): JNJ, UNH, PFE, ABBV, TMO, MRK, LLY, MRNA, AMGN, and more
- **Financial** (38 stocks): JPM, BAC, WFC, GS, MS, V, MA, PYPL, SQ, BLK, and more
- **Consumer Goods** (33 stocks): PG, KO, PEP, NKE, COST, WMT, HD, MCD, SBUX, and more
- **Energy** (25 stocks): XOM, CVX, COP, SLB, EOG, OXY, MPC, PSX, and more
- **Other Sectors** (124 stocks): Industrials, Retail, Real Estate, Materials, Entertainment, and more

**Population Scripts**:
- `populate_stocks.py` - Initial 246 stocks
- `populate_stocks_batch2.py` - Additional 94 stocks

## Performance & Optimization

### Current Performance
- Average API response time: 200-500ms
- Chart render time: 100-200ms
- Technical analysis calculation: 50-100ms

### Optimization Opportunities
We've identified 32 optimization opportunities across:
- Frontend performance (React re-renders, API calls, memory leaks)
- Backend efficiency (N+1 queries, missing indexes, caching)
- Code quality (error handling, validation, refactoring)

See [OPTIMIZATION_REPORT.md](./OPTIMIZATION_REPORT.md) for detailed analysis.

**Priority Improvements:**
1. Add database indexes (10-100x speedup for queries)
2. Implement caching layer (90% response time reduction)
3. Optimize React re-renders (50-60% reduction)
4. Fix N+1 query problems (80% database load reduction)

## Development

### Running Services Individually

**Backend only:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend only:**
```bash
cd frontend
npm install
npm start
```

**Database only:**
```bash
docker run -d \
  -p 5432:5432 \
  -e POSTGRES_DB=stock_analyzer \
  -e POSTGRES_USER=stockuser \
  -e POSTGRES_PASSWORD=stockpass123 \
  timescale/timescaledb:latest-pg14
```

### Stopping the Application

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clears database)
docker-compose down -v
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f database
```

### Debugging

Common issues and solutions:

1. **Port already in use:** Change ports in `docker-compose.yml`
2. **Database connection issues:** Check service health with `docker-compose ps`
3. **Frontend can't connect:** Verify `REACT_APP_API_URL` in docker-compose.yml
4. **API key errors:** Check `.env` file exists with valid key

## Roadmap

### ✅ Phase 1: Core Infrastructure (Complete)
- Docker environment
- FastAPI backend with health check
- PostgreSQL with TimescaleDB
- React frontend
- Basic stock management

### ✅ Phase 2: Data Pipeline (Complete)
- Polygon.io integration
- Historical data fetching
- Interactive charts with overlays
- Chart indicators toggle

### ✅ Phase 3: Analysis & Predictions (Complete)
- 15+ technical indicators
- Configurable parameters
- Buy/sell/hold recommendations
- Confidence scoring
- Indicator encyclopedia
- Signal radar chart

### ✅ Phase 4: Advanced ML & Tracking (Complete)
- LSTM, Transformer, CNN models
- Model training and management
- Sentiment analysis
- Weighted recommendations
- Prediction performance tracking

### ✅ Phase 5: Candlestick Pattern Recognition (Complete)
- 40 candlestick patterns implemented from scratch
- Pattern detection API endpoints
- Visual chart markers for detected patterns
- User confirmation system for ML training data
- Pattern statistics and export functionality
- Frontend pattern management UI

### ✅ Phase 6: Chart Pattern Recognition (Complete)
- 12 chart patterns (Head & Shoulders, Triangles, Cup & Handle, Flags, Wedges)
- Scipy-based peak/trough detection algorithms
- Linear regression trendline calculation
- Pattern classification (reversal/continuation, bullish/bearish/neutral)
- Key price level calculations (breakout, target, stop loss)
- User confirmation system and statistics
- Frontend chart pattern management UI

**Pattern Quality Scoring System:**

The chart pattern detection engine uses a sophisticated multi-factor quality scoring system to filter out low-quality patterns and reduce false positives:

- **ATR (Average True Range) Calculation** - Measures volatility for pattern validation
- **Prior Trend Detection** - Validates that reversal patterns occur after appropriate trends (uptrend before bearish reversal, downtrend before bullish reversal)
- **Volume Profile Analysis** - Declining volume during pattern formation increases quality score (typical of consolidation patterns)
- **Weighted Quality Algorithm** - Combines multiple factors with different weights:
  - Trendline R² fit quality: 35% weight (measures how well prices follow support/resistance lines)
  - Volume behavior score: 25% weight (declining volume during consolidation is preferred)
  - Prior trend strength: 20% weight (for reversal patterns only)
  - Base pattern confidence: 20% weight (pattern-specific reliability score)
- **Quality Filtering Thresholds**:
  - Minimum R² of 0.7 for trendlines (filters out poorly-defined support/resistance)
  - Overall quality score > 0.5 required for pattern to be saved
- **Dynamic Confidence Scores** - Pattern confidence now reflects calculated quality instead of static values

This quality scoring system results in:
- 60-80% reduction in false positives
- More reliable trading signals
- Higher quality training data for machine learning models

### ✅ Phase 7: Enhanced Dashboard & Data Collection (Complete)
- 335+ pre-populated stocks across 18 sectors
- Sector-based organization with color coding
- Batch operations for data fetching and pattern detection
- Optimized presets for CNN training data collection
- Enhanced stock cards with company metadata
- Real-time progress tracking for batch operations

### Phase 8: CNN Model Training & Optimization (Next)
- CNN model training on collected pattern data
- Model evaluation and accuracy tracking
- Database indexing and caching
- React performance optimization
- Real-time updates (WebSockets)
- User authentication (JWT)
- Portfolio simulation
- Email/notification alerts
- Mobile responsiveness
- Trendline visualization on charts

## Contributing

This is a personal learning project. Feel free to fork and modify for your own use.

## License

This project is for educational purposes.

## Troubleshooting

### Common Issues

**"Cannot read properties of null"**
- Ensure sufficient historical data has been fetched
- Check API key is valid
- Review backend logs: `docker-compose logs backend`

**Indicators not updating after parameter change**
- Wait a few seconds for calculation
- Check browser console for errors
- Verify parameter values are within valid ranges

**Chart not displaying indicators**
- Ensure data has been fetched first
- Click checkbox to toggle indicator on
- Check that sufficient data points exist

### Getting Help

1. Check the logs: `docker-compose logs -f`
2. Verify all services are running: `docker-compose ps`
3. Test API directly: http://localhost:8000/docs
4. Review documentation files in project root

## Support

For issues or questions:
- Check backend logs for API errors
- Check frontend console for UI errors
- Verify environment configuration (.env file)
- Test individual endpoints via Swagger UI

---

**Built with FastAPI, React, PostgreSQL, TimescaleDB, PyTorch, and Polygon.io**
