from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api.routes import health, stocks, prices, analysis, ml, sentiment, patterns, chart_patterns, strategies, ml_predictions, risk_management
from app.services.scheduler import init_scheduler, shutdown_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup: Initialize scheduler
    logger.info("Starting Stock Analyzer API...")
    try:
        init_scheduler(schedule_type="daily")  # Schedule daily prediction evaluation
        logger.info("Scheduler initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize scheduler: {e}")

    yield

    # Shutdown: Clean up scheduler
    logger.info("Shutting down Stock Analyzer API...")
    try:
        shutdown_scheduler()
        logger.info("Scheduler shutdown successfully")
    except Exception as e:
        logger.warning(f"Failed to shutdown scheduler: {e}")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Stock Analyzer API",
    description="API for stock market analysis, ML predictions, and sentiment analysis",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(stocks.router, prefix="/api/v1")
app.include_router(prices.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(ml.router)  # ML routes already have prefix="/api/v1/ml"
app.include_router(ml_predictions.router, prefix="/api/v1", tags=["ml-predictions"])  # ML pattern predictions
app.include_router(sentiment.router)  # Sentiment routes already have prefix="/api/v1/sentiment"
app.include_router(patterns.router, prefix="/api/v1")  # Candlestick pattern detection
app.include_router(chart_patterns.router, prefix="/api/v1")  # Chart pattern detection
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["strategies"])  # Trading strategies
app.include_router(risk_management.router, tags=["risk-management"])  # PHASE 1.2: Risk management & position sizing


@app.get("/")
def root():
    """
    Root endpoint
    """
    return {
        "message": "Stock Analyzer API - Phase 6 with Chart Pattern Recognition & Trading Strategies",
        "version": "2.3.0",
        "docs": "/docs",
        "health": "/health",
        "features": [
            "Technical Analysis (RSI, MACD, Bollinger Bands, Moving Averages)",
            "ML Predictions (LSTM, Transformer, CNN, CNN-LSTM)",
            "Sentiment Analysis (News scraping and FinBERT)",
            "Integrated Recommendations",
            "Prediction Performance Tracking",
            "Candlestick Pattern Recognition (40 patterns - 20 bullish, 20 bearish)",
            "Chart Pattern Recognition (19 patterns - Head & Shoulders, Triangles, Wedges, Rounding, Channels, etc.)",
            "Pattern Confirmation for ML Training Data Collection",
            "Real-time ML Pattern Validation (LSTM + GRU models with 81%+ accuracy)",
            "Custom Trading Strategies Framework with 5 Built-in Strategies",
            "Strategy Backtesting & Performance Analysis"
        ]
    }
