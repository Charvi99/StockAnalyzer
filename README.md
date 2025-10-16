# Stock Analyzer

A full-stack web application for stock market analysis and prediction. This application helps you understand stock investing by providing analysis, predictions, and tracking of prediction accuracy over time.

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
- **Interactive Charts** - Beautiful, responsive price charts with Recharts
- **API Endpoints** - Fetch and retrieve stock price data
- **Data Storage** - Efficient time-series storage with TimescaleDB

### Phase 3 - Analysis & Predictions ✅
- **Technical Indicators** - RSI, MACD, Bollinger Bands, Moving Averages
- **Buy/Sell/Hold Recommendations** - AI-powered trading signals
- **Confidence Scores** - Measure reliability of recommendations
- **Prediction Engine** - Machine learning-based price forecasting
- **Comprehensive Analysis Dashboard** - View all indicators at once

## Technology Stack

### Backend
- Python 3.11
- FastAPI - Modern web framework
- SQLAlchemy - ORM for database operations
- PostgreSQL - Relational database
- TimescaleDB - Time-series optimization
- Uvicorn - ASGI server

### Frontend
- React 18
- Axios - HTTP client
- Recharts - Data visualization (for future use)

### DevOps
- Docker & Docker Compose
- Git

## Project Structure

```
StockAnalyzer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── health.py      # Health check endpoint
│   │   │       └── stocks.py       # Stock CRUD endpoints
│   │   ├── db/
│   │   │   └── database.py         # Database connection
│   │   ├── models/
│   │   │   └── stock.py            # SQLAlchemy models
│   │   ├── schemas/
│   │   │   └── stock.py            # Pydantic schemas
│   │   ├── services/               # Business logic (future)
│   │   └── main.py                 # FastAPI application
│   ├── ml/                         # Machine learning (future)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/
│   │   │   └── StockList.jsx
│   │   ├── services/
│   │   │   └── api.js              # API client
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── index.js
│   ├── Dockerfile
│   └── package.json
├── database/
│   └── init.sql                     # Database schema
├── docker-compose.yml
└── README.md
```

## Getting Started

### Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Docker Compose
- Git

### Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd C:\Work\MyTools\StockAnalyzer
   ```

2. **Build and start all services:**
   ```bash
   docker-compose up --build
   ```

   This will start three services:
   - Database (PostgreSQL + TimescaleDB) on port 5432
   - Backend (FastAPI) on port 8000
   - Frontend (React) on port 3000

3. **Wait for all services to be healthy:**
   - The database needs to initialize (about 10-20 seconds)
   - The backend will start once the database is healthy
   - The frontend will start after the backend

### Accessing the Application

Once all services are running:

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs (Swagger UI)
- **Alternative API Docs:** http://localhost:8000/redoc (ReDoc)
- **Health Check:** http://localhost:8000/health

### 🔑 Polygon.io API Setup (Required for Real Data)

The application uses **Polygon.io** for stock market data (free tier: 5 requests/minute, unlimited daily requests).

**Quick Setup:**

1. Get your free API key: https://polygon.io/dashboard/signup
2. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` and add your API key:
   ```
   POLYGON_API_KEY=YOUR_KEY_HERE
   ```
4. Restart backend:
   ```bash
   docker-compose restart backend
   ```

**Why Polygon.io?** Professional-grade API with excellent free tier, no daily request limits, and reliable access.

📖 **Full setup guide:** See [POLYGON_SETUP.md](./POLYGON_SETUP.md)

## Usage

### API Endpoints

#### Health Check
```bash
GET /health
```
Returns API and database status.

#### Stock Management

**Get all stocks:**
```bash
GET /api/v1/stocks/
```

**Get stock by ID:**
```bash
GET /api/v1/stocks/{stock_id}
```

**Get stock by symbol:**
```bash
GET /api/v1/stocks/symbol/{symbol}
```

**Create a new stock:**
```bash
POST /api/v1/stocks/
Content-Type: application/json

{
  "symbol": "NVDA",
  "name": "NVIDIA Corporation",
  "sector": "Technology",
  "industry": "Semiconductors"
}
```

**Delete a stock:**
```bash
DELETE /api/v1/stocks/{stock_id}
```

### Testing with cURL

```bash
# Health check
curl http://localhost:8000/health

# Get all stocks
curl http://localhost:8000/api/v1/stocks/

# Get stock by symbol
curl http://localhost:8000/api/v1/stocks/symbol/AAPL

# Create a stock
curl -X POST http://localhost:8000/api/v1/stocks/ \
  -H "Content-Type: application/json" \
  -d '{"symbol":"NVDA","name":"NVIDIA Corporation","sector":"Technology","industry":"Semiconductors"}'
```

## Database Schema

The database includes the following tables:

- **stocks** - Tracked stock information
- **stock_prices** - Historical price data (TimescaleDB hypertable)
- **predictions** - ML model predictions
- **prediction_performance** - Accuracy tracking
- **technical_indicators** - Technical analysis data (future use)

Sample stocks are pre-loaded:
- AAPL (Apple Inc.)
- GOOGL (Alphabet Inc.)
- MSFT (Microsoft Corporation)
- TSLA (Tesla, Inc.)
- AMZN (Amazon.com Inc.)

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

### Phase 3 Usage - Technical Analysis

**Analyze a Stock:**
```bash
POST /api/v1/stocks/{stock_id}/analyze
Content-Type: application/json

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

**Get Comprehensive Recommendation:**
```bash
GET /api/v1/stocks/{stock_id}/recommendation
```

**Create ML Prediction:**
```bash
POST /api/v1/stocks/{stock_id}/predict
Content-Type: application/json

{
  "model_type": "technical",
  "forecast_days": 5,
  "use_sentiment": false
}
```

**Get Prediction History:**
```bash
GET /api/v1/stocks/{stock_id}/predictions?limit=10
```

### Using the Frontend

1. Open http://localhost:3000
2. Click "View Details" on any stock
3. Fetch historical data if needed
4. Click "Run Analysis" to see technical indicators
5. View BUY/SELL/HOLD recommendation with confidence scores

## Roadmap

### ✅ Phase 1: Core Infrastructure (Complete)
- Docker environment
- FastAPI backend with health check
- PostgreSQL with TimescaleDB
- React frontend
- Basic stock management

### ✅ Phase 2: Data Pipeline (Complete)
- Polygon.io integration for stock data
- Fetch and store historical stock data
- API endpoints for stock price history
- Interactive chart visualization

### ✅ Phase 3: Analysis & Predictions (Complete)
- Technical indicators (RSI, MACD, Bollinger Bands, Moving Averages)
- Buy/sell/hold recommendation engine
- Confidence scoring system
- Prediction storage and retrieval
- Frontend analysis dashboard

### Phase 4: Advanced ML & Tracking (Next)
- LSTM and Transformer models for predictions
- Scheduled jobs to evaluate prediction accuracy
- Compare predictions vs actual prices
- Performance metrics and reporting
- Model training interface

### Phase 5: Enhancement (Future)
- User authentication (JWT)
- Real-time updates (WebSockets)
- Sentiment analysis from news
- Portfolio simulation
- Email/notification alerts
- Mobile responsiveness

## Contributing

This is a personal learning project. Feel free to fork and modify for your own use.

## License

This project is for educational purposes.

## Troubleshooting

### Port Already in Use
If you see "port already in use" errors, change the ports in `docker-compose.yml`.

### Database Connection Issues
Make sure the database service is healthy before the backend starts:
```bash
docker-compose ps
```

### Frontend Can't Connect to Backend
Check that `REACT_APP_API_URL` in `docker-compose.yml` points to the correct backend URL.

### Permission Issues (Linux/Mac)
```bash
sudo chown -R $USER:$USER .
```

## Support

For issues or questions:
1. Check the logs: `docker-compose logs -f`
2. Verify all services are running: `docker-compose ps`
3. Test API directly: http://localhost:8000/docs
