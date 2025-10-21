"""
Pydantic schemas for chart pattern detection
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChartPatternDetectionRequest(BaseModel):
    """Request schema for detecting chart patterns"""
    days: int = Field(default=90, ge=30, le=730, description="Days of historical data to analyze")
    min_pattern_length: int = Field(default=20, ge=10, le=100, description="Minimum candles for pattern formation")


class ChartPatternDetected(BaseModel):
    """Schema for a detected chart pattern"""
    pattern_name: str
    pattern_type: str  # reversal, continuation
    signal: str  # bullish, bearish, neutral
    start_date: datetime
    end_date: datetime
    breakout_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    confidence_score: float
    key_points: Dict[str, Any]
    trendlines: Dict[str, Any]


class ChartPatternDetectionResponse(BaseModel):
    """Response schema for pattern detection"""
    stock_id: int
    symbol: str
    analysis_period: str
    total_patterns: int
    reversal_patterns: int
    continuation_patterns: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    patterns: List[ChartPatternDetected]
    message: str


class ChartPatternInDB(BaseModel):
    """Schema for chart pattern stored in database"""
    id: int
    stock_id: int
    pattern_name: str
    pattern_type: str
    signal: str
    start_date: datetime
    end_date: datetime
    breakout_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    confidence_score: float
    key_points: Optional[Dict[str, Any]] = None
    trendlines: Optional[Dict[str, Any]] = None
    user_confirmed: Optional[bool] = None
    confirmed_at: Optional[datetime] = None
    confirmed_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChartPatternListResponse(BaseModel):
    """Response schema for listing chart patterns"""
    stock_id: int
    symbol: str
    total_patterns: int
    confirmed_count: int
    rejected_count: int
    pending_count: int
    patterns: List[ChartPatternInDB]


class ChartPatternConfirmRequest(BaseModel):
    """Request schema for confirming/rejecting a pattern"""
    confirmed: bool = Field(description="True = confirm, False = reject")
    confirmed_by: str = Field(default="user", max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)


class ChartPatternStatsResponse(BaseModel):
    """Response schema for pattern statistics"""
    total_patterns: int
    confirmed_patterns: int
    rejected_patterns: int
    pending_patterns: int
    pattern_breakdown: Dict[str, int]  # Pattern name -> count
    reversal_count: int
    continuation_count: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    avg_confidence: float


class ChartPatternTrainingDataExport(BaseModel):
    """Schema for exporting labeled patterns for ML training"""
    pattern_id: int
    stock_symbol: str
    pattern_name: str
    pattern_type: str
    signal: str
    start_date: datetime
    end_date: datetime
    confidence_score: float
    key_points: Dict[str, Any]
    trendlines: Dict[str, Any]
    user_confirmed: bool
    label: str  # 'true_positive', 'false_positive', 'unknown'
