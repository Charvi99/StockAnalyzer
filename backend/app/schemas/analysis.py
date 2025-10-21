"""
Pydantic schemas for technical analysis and predictions
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
from decimal import Decimal


# Technical Indicator Schemas
class IndicatorValue(BaseModel):
    """Single indicator value"""
    value: Optional[float] = None
    signal: Optional[str] = None
    reason: Optional[str] = None


class IndicatorDetails(BaseModel):
    """Detailed indicator information"""
    value: Optional[float] = None
    signal: Optional[str] = None
    reason: Optional[str] = None
    upper: Optional[float] = None  # For Bollinger Bands
    middle: Optional[float] = None
    lower: Optional[float] = None
    macd: Optional[float] = None  # For MACD
    signal_line: Optional[float] = None
    histogram: Optional[float] = None
    ma_short: Optional[float] = None  # For Moving Averages
    ma_long: Optional[float] = None


class TechnicalAnalysisResponse(BaseModel):
    """Response for technical analysis"""
    stock_id: int
    symbol: str
    timestamp: datetime
    current_price: float

    # Indicator details
    indicators: Dict[str, IndicatorDetails]

    # Overall recommendation
    recommendation: str = Field(..., description="BUY, SELL, or HOLD")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    reason: str
    signal_counts: Dict[str, int]

    class Config:
        from_attributes = True


class AnalysisRequest(BaseModel):
    """Request parameters for analysis"""
    period: str = Field(default="3mo", description="Data period for analysis")
    rsi_period: int = Field(default=14, ge=2, le=100)
    macd_fast: int = Field(default=12, ge=2, le=50)
    macd_slow: int = Field(default=26, ge=2, le=100)
    macd_signal: int = Field(default=9, ge=2, le=50)
    bb_window: int = Field(default=20, ge=2, le=100)
    bb_std: float = Field(default=2.0, ge=0.5, le=5.0)
    ma_short: int = Field(default=20, ge=2, le=100)
    ma_long: int = Field(default=50, ge=2, le=200)


# Prediction Schemas
class PredictionCreate(BaseModel):
    """Schema for creating a prediction"""
    stock_id: int
    target_date: datetime
    predicted_price: Optional[Decimal] = None
    predicted_change_percent: Optional[Decimal] = None
    confidence_score: Optional[Decimal] = None
    model_version: Optional[str] = None
    recommendation: str = Field(..., pattern="^(BUY|SELL|HOLD)$")


class PredictionResponse(BaseModel):
    """Response schema for prediction"""
    id: int
    stock_id: int
    prediction_date: datetime
    target_date: datetime
    predicted_price: Optional[Decimal] = None
    predicted_change_percent: Optional[Decimal] = None
    confidence_score: Optional[Decimal] = None
    model_version: Optional[str] = None
    recommendation: str
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionWithStock(PredictionResponse):
    """Prediction with stock information"""
    symbol: str
    stock_name: str


class MLPredictionRequest(BaseModel):
    """Request for ML-based prediction"""
    model_type: str = Field(default="technical", description="Model type: technical, lstm, transformer")
    forecast_days: int = Field(default=5, ge=1, le=30, description="Number of days to forecast")
    use_sentiment: bool = Field(default=False, description="Include sentiment analysis")


class MLPredictionResponse(BaseModel):
    """Response for ML prediction"""
    stock_id: int
    symbol: str
    current_price: float
    predicted_price: Optional[float] = None
    predicted_change: Optional[float] = None
    confidence: float
    recommendation: str
    model_used: str
    forecast_horizon: int
    technical_indicators: Dict[str, IndicatorDetails]
    reason: str


# Historical Analysis Schemas
class HistoricalIndicator(BaseModel):
    """Historical indicator data point"""
    timestamp: datetime
    value: float


class HistoricalAnalysisResponse(BaseModel):
    """Response with historical indicator values"""
    stock_id: int
    symbol: str
    period: str
    indicators: Dict[str, List[HistoricalIndicator]]


# Performance Tracking Schemas
class PredictionPerformanceCreate(BaseModel):
    """Schema for creating performance record"""
    prediction_id: int
    actual_price: Decimal
    actual_change_percent: Decimal
    prediction_error: Decimal
    accuracy_score: Decimal


class PredictionPerformanceResponse(BaseModel):
    """Response for prediction performance"""
    id: int
    prediction_id: int
    actual_price: Decimal
    actual_change_percent: Decimal
    prediction_error: Decimal
    accuracy_score: Decimal
    evaluated_at: datetime

    class Config:
        from_attributes = True


class PerformanceStats(BaseModel):
    """Overall performance statistics"""
    total_predictions: int
    average_accuracy: float
    best_accuracy: float
    worst_accuracy: float
    correct_direction_percentage: float
    average_error: float


# Recommendation Schema
class RecommendationResponse(BaseModel):
    """Comprehensive recommendation response"""
    stock_id: int
    symbol: str
    current_price: Optional[float] = None
    timestamp: Optional[datetime] = None

    # Technical analysis
    technical_recommendation: Optional[str] = None
    technical_confidence: Optional[float] = None
    technical_signals: Optional[Dict[str, str]] = None

    # ML prediction (if available)
    ml_recommendation: Optional[str] = None
    ml_confidence: Optional[float] = None
    predicted_price: Optional[float] = None

    # Sentiment analysis (if available)
    sentiment_index: Optional[float] = None
    sentiment_positive: Optional[int] = None
    sentiment_negative: Optional[int] = None

    # Overall recommendation
    final_recommendation: Optional[str] = None
    overall_confidence: Optional[float] = None
    reasoning: Optional[List[str]] = None
    risk_level: Optional[str] = None  # LOW, MEDIUM, HIGH

    # Error field
    error: Optional[str] = None
