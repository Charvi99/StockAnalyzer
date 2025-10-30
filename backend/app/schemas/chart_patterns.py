"""
Pydantic schemas for chart pattern detection
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChartPatternDetectionRequest(BaseModel):
    """Request schema for detecting chart patterns"""
    days: Optional[int] = Field(default=None, ge=30, le=10000, description="Days of historical data to analyze (None = all available data)")
    min_pattern_length: int = Field(default=20, ge=10, le=100, description="Minimum candles for pattern formation")
    exclude_recent_days: int = Field(default=0, ge=0, le=365, description="Exclude patterns from last N days (useful for historical training data collection)")
    remove_overlaps: bool = Field(default=True, description="Remove overlapping patterns (keeps highest confidence)")
    overlap_threshold: float = Field(default=0.1, ge=0.0, le=1.0, description="Minimum overlap fraction to consider patterns as overlapping (default 0.1 = 10%)")
    exclude_patterns: Optional[List[str]] = Field(default=None, description="List of pattern names to exclude (e.g., ['Rounding Top', 'Rounding Bottom'])")
    peak_order: int = Field(default=5, ge=3, le=15, description="Peak detection sensitivity (3=very sensitive, 15=very strict)")
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum confidence score to keep patterns (0.0 = keep all)")
    min_r_squared: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum trendline R² quality (0.0 = no requirement)")


class ChartPatternDetected(BaseModel):
    """Schema for a detected chart pattern with multi-timeframe support"""
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

    # Multi-timeframe fields
    primary_timeframe: Optional[str] = Field(default='1d', description="Primary timeframe pattern detected on")
    detected_on_timeframes: Optional[List[str]] = Field(default=['1d'], description="List of timeframes this pattern appears on")
    confirmation_level: Optional[int] = Field(default=1, ge=1, le=3, description="Number of timeframes confirming this pattern (1-3)")
    base_confidence: Optional[float] = Field(default=None, description="Original confidence before multi-timeframe adjustment")
    adjusted_confidence: Optional[float] = Field(default=None, description="Confidence after multi-timeframe boost")
    alignment_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="How well pattern aligns across timeframes (0.0-1.0)")
    is_multi_timeframe_confirmed: Optional[bool] = Field(default=False, description="True if confirmed on 2+ timeframes")

    # Volume analysis fields (Phase 2E)
    volume_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Volume quality score (0.0-1.0)")
    volume_quality: Optional[str] = Field(default=None, description="Volume quality label (excellent/good/average/weak)")
    volume_ratio: Optional[float] = Field(default=None, description="Volume ratio at pattern completion (current/average)")
    vwap_position: Optional[str] = Field(default=None, description="Price position relative to VWAP (above/below)")


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
    # Multi-timeframe fields
    primary_timeframe: Optional[str] = '1d'
    detected_on_timeframes: Optional[List[str]] = ['1d']
    confirmation_level: Optional[int] = 1
    base_confidence: Optional[float] = None
    alignment_score: Optional[float] = None
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


class OHLCCandle(BaseModel):
    """Single OHLC candle for training data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class ChartPatternTrainingDataExport(BaseModel):
    """Schema for exporting labeled patterns for ML training with OHLC data"""
    # Pattern metadata
    pattern_id: int
    stock_symbol: str
    pattern_name: str
    pattern_type: str
    signal: str
    confidence_score: float
    key_points: Dict[str, Any]
    trendlines: Dict[str, Any]
    user_confirmed: bool
    label: str  # 'true_positive', 'false_positive', 'unknown'

    # Date ranges
    pattern_start_date: datetime
    pattern_end_date: datetime
    window_start_date: datetime
    window_end_date: datetime

    # OHLC data with padding
    ohlc_data: List[OHLCCandle]
    total_candles: int
    pattern_start_index: int  # Index in ohlc_data where pattern starts
    pattern_end_index: int    # Index in ohlc_data where pattern ends
    padding_before: int
    padding_after: int

    # Normalization metadata (for the entire window)
    price_min: float
    price_max: float
    volume_max: int
