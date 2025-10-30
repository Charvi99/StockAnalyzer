from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal
from decimal import Decimal


# Stock Schemas
class StockBase(BaseModel):
    symbol: str = Field(..., max_length=10)
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None


class StockCreate(StockBase):
    is_tracked: bool = Field(default=True, description="Whether this stock should be tracked")


class StockUpdate(BaseModel):
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    is_tracked: Optional[bool] = None


class StockResponse(StockBase):
    id: int
    is_tracked: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Stock Price Schemas
class StockPriceBase(BaseModel):
    timestamp: datetime
    timeframe: str = Field(default="1d", description="Timeframe: 1h, 2h, 4h, 1d, 1w, 1mo")
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Optional[int] = None
    adjusted_close: Optional[Decimal] = None


class StockPriceResponse(StockPriceBase):
    id: int
    stock_id: int

    class Config:
        from_attributes = True


# Prediction Schemas
class PredictionBase(BaseModel):
    target_date: datetime
    predicted_price: Optional[Decimal] = None
    predicted_change_percent: Optional[Decimal] = None
    confidence_score: Optional[Decimal] = None
    model_version: Optional[str] = None
    recommendation: Optional[Literal["BUY", "SELL", "HOLD"]] = None


class PredictionResponse(PredictionBase):
    id: int
    stock_id: int
    prediction_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# Health Check Schema
class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime
    database: str
    version: str


# Data Fetching Schemas
class FetchDataRequest(BaseModel):
    period: str = Field(default="1y", description="Data period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max")
    interval: str = Field(default="1h", description="Data interval (base timeframe only): 1h")


class FetchDataResponse(BaseModel):
    success: bool
    message: str
    records_fetched: int
    records_saved: int
    timeframe: Optional[str] = None


class StockPriceListResponse(BaseModel):
    stock_id: int
    symbol: str
    prices: list[StockPriceResponse]
    total_records: int
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class LatestPriceResponse(BaseModel):
    symbol: str
    price: float
    timestamp: datetime
    volume: int
