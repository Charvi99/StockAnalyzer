"""
Pydantic schemas for ML and sentiment analysis endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


# ========================================
# ML Training Schemas
# ========================================

class MLTrainingRequest(BaseModel):
    """Request schema for training ML models"""
    model_type: str = Field(..., description="Model architecture: LSTM, Transformer, CNN, CNNLSTM")
    seq_length: int = Field(default=30, ge=10, le=100, description="Sequence length for time series")
    epochs: int = Field(default=50, ge=1, le=200, description="Number of training epochs")
    batch_size: int = Field(default=32, ge=1, le=128, description="Batch size for training")
    learning_rate: float = Field(default=0.001, gt=0.0, le=0.1, description="Learning rate")


class MLTrainingResponse(BaseModel):
    """Response schema for model training"""
    model_type: str
    best_val_loss: float
    final_val_accuracy: float
    epochs: int
    message: str


# ========================================
# ML Prediction Schemas
# ========================================

class MLPredictionRequest(BaseModel):
    """Request schema for ML predictions"""
    model_type: str = Field(default="LSTM", description="Model to use: LSTM, Transformer, CNN, CNNLSTM")
    seq_length: int = Field(default=30, ge=10, le=100, description="Sequence length")


class MLPredictionResponse(BaseModel):
    """Response schema for ML predictions"""
    signal: str = Field(..., description="Trading signal: BUY, SELL, or HOLD")
    confidence: float = Field(..., description="Confidence score (0-1)")
    probabilities: Dict[str, float] = Field(..., description="Probabilities for each class")
    model_type: str
    current_price: Optional[float] = None
    timestamp: datetime


# ========================================
# Sentiment Analysis Schemas
# ========================================

class SentimentRequest(BaseModel):
    """Request schema for sentiment analysis"""
    limit_per_ticker: int = Field(default=50, ge=1, le=100, description="Number of news articles to fetch")
    threshold: float = Field(default=0.9, ge=0.0, le=1.0, description="Confidence threshold for sentiment")


class NewsArticle(BaseModel):
    """Schema for a single news article with sentiment"""
    Ticker: str
    Datetime: datetime
    Headline: str
    Summary: str
    Source: str
    URL: str
    SCORE_PROB: float
    SCORE_SENT: str


class SentimentAnalysisResponse(BaseModel):
    """Response schema for sentiment analysis"""
    ticker: str
    sentiment_index: float = Field(..., description="Sentiment index from -100 to 100")
    positive_count: int
    negative_count: int
    neutral_count: int
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    total_articles: int
    trend: str = Field(..., description="Trend: Rise, Fall, or Neutral")
    news: List[NewsArticle] = Field(default_factory=list)
    timestamp: datetime


class MultipleSentimentRequest(BaseModel):
    """Request schema for analyzing multiple tickers"""
    tickers: List[str] = Field(..., min_items=1, max_items=10, description="List of ticker symbols")
    limit_per_ticker: int = Field(default=50, ge=1, le=100, description="Number of news articles per ticker")
    threshold: float = Field(default=0.9, ge=0.0, le=1.0, description="Confidence threshold")


class TickerSentiment(BaseModel):
    """Sentiment summary for a single ticker"""
    ticker: str
    sentiment_index: float
    positive_count: int
    negative_count: int
    neutral_count: int
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    total_articles: int
    trend: str


class MultipleSentimentResponse(BaseModel):
    """Response schema for multiple ticker sentiment analysis"""
    tickers: List[TickerSentiment]
    news: List[NewsArticle] = Field(default_factory=list)
    total_articles_analyzed: int
    timestamp: datetime


# ========================================
# Sentiment Score Database Schema
# ========================================

class SentimentScoreCreate(BaseModel):
    """Schema for creating sentiment scores"""
    stock_id: int
    sentiment_index: float
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    total_articles: int = 0
    trend: str


class SentimentScoreResponse(BaseModel):
    """Schema for sentiment score response"""
    id: int
    stock_id: int
    timestamp: datetime
    sentiment_index: float
    positive_count: int
    negative_count: int
    neutral_count: int
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    total_articles: int
    trend: str
    created_at: datetime

    class Config:
        from_attributes = True


# ========================================
# Integrated Analysis Schemas
# ========================================

class IntegratedAnalysisResponse(BaseModel):
    """Combined technical, ML, and sentiment analysis"""
    stock_id: int
    symbol: str
    current_price: float

    # Technical Analysis
    technical_recommendation: str
    technical_confidence: float

    # ML Prediction
    ml_signal: Optional[str] = None
    ml_confidence: Optional[float] = None
    ml_probabilities: Optional[Dict[str, float]] = None

    # Sentiment Analysis
    sentiment_index: Optional[float] = None
    sentiment_trend: Optional[str] = None

    # Final Integrated Recommendation
    final_recommendation: str
    final_confidence: float
    reasoning: List[str]
    risk_level: str

    timestamp: datetime


# ========================================
# Prediction Performance Schemas
# ========================================

class PredictionPerformanceCreate(BaseModel):
    """Schema for creating prediction performance records"""
    prediction_id: int
    actual_price: float
    actual_change_percent: float
    prediction_error: float
    accuracy_score: float


class PredictionPerformanceResponse(BaseModel):
    """Schema for prediction performance response"""
    id: int
    prediction_id: int
    actual_price: float
    actual_change_percent: float
    prediction_error: float
    accuracy_score: float
    evaluated_at: datetime

    class Config:
        from_attributes = True


class ModelPerformanceStats(BaseModel):
    """Aggregate performance statistics for a model"""
    model_type: str
    total_predictions: int
    avg_accuracy: float
    avg_error: float
    correct_direction_pct: float
    last_evaluated: datetime
