"""
Pydantic schemas for candlestick pattern detection
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


class PatternDetectionRequest(BaseModel):
    """Request to detect patterns"""
    days: int = Field(default=90, ge=1, le=1000, description="Number of days to analyze")


class CandleData(BaseModel):
    """Individual candle OHLCV data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class PatternBase(BaseModel):
    """Base pattern schema"""
    pattern_name: str
    pattern_type: str  # 'bullish', 'bearish', 'neutral'
    timestamp: datetime
    confidence_score: float = Field(ge=0.0, le=1.0)
    candle_data: Optional[Dict[str, Any]] = None


class PatternDetected(PatternBase):
    """Pattern detected from analysis"""
    pass


class PatternInDB(PatternBase):
    """Pattern stored in database"""
    id: int
    stock_id: int
    user_confirmed: Optional[bool] = None
    confirmed_at: Optional[datetime] = None
    confirmed_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PatternConfirmRequest(BaseModel):
    """Request to confirm/reject a pattern"""
    confirmed: bool = Field(description="True if pattern is confirmed, False if rejected")
    notes: Optional[str] = Field(default=None, max_length=500, description="Optional notes about the pattern")
    confirmed_by: str = Field(default="user", max_length=100, description="Who confirmed the pattern")


class PatternDetectionResponse(BaseModel):
    """Response from pattern detection"""
    stock_id: int
    symbol: str
    analysis_period: str
    total_patterns: int
    bullish_patterns: int
    bearish_patterns: int
    patterns: List[PatternDetected]
    message: str


class PatternListResponse(BaseModel):
    """List of patterns from database"""
    stock_id: int
    symbol: str
    total_patterns: int
    confirmed_count: int
    rejected_count: int
    pending_count: int
    patterns: List[PatternInDB]


class PatternStatsResponse(BaseModel):
    """Pattern statistics for ML training"""
    total_patterns: int
    confirmed_patterns: int
    rejected_patterns: int
    pending_patterns: int
    pattern_breakdown: Dict[str, int]
    bullish_count: int
    bearish_count: int
    avg_confidence: float


class TrainingDataExport(BaseModel):
    """Export format for ML training"""
    pattern_id: int
    stock_symbol: str
    pattern_name: str
    pattern_type: str
    timestamp: datetime
    confidence_score: float
    candle_data: Dict[str, Any]
    user_confirmed: bool
    label: str  # 'true_positive', 'false_positive', 'unknown'
