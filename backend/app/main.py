from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api.routes import health, stocks, prices, analysis, ml, sentiment
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
app.include_router(sentiment.router)  # Sentiment routes already have prefix="/api/v1/sentiment"


@app.get("/")
def root():
    """
    Root endpoint
    """
    return {
        "message": "Stock Analyzer API - Phase 4 with ML & Sentiment Analysis",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "features": [
            "Technical Analysis (RSI, MACD, Bollinger Bands, Moving Averages)",
            "ML Predictions (LSTM, Transformer, CNN, CNN-LSTM)",
            "Sentiment Analysis (News scraping and FinBERT)",
            "Integrated Recommendations",
            "Prediction Performance Tracking"
        ]
    }
