"""
Risk Management API Endpoints - Phase 1.2
Provides ATR-based stop-loss, take-profit, and position sizing calculations
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field
from decimal import Decimal

from app.db.database import get_db
from app.models.stock import Stock
from app.services.timeframe_service import TimeframeService
from app.services.risk_management import RiskManager, calculate_risk_metrics_for_pattern

router = APIRouter()


class RiskCalculationRequest(BaseModel):
    """Request model for risk calculations"""
    entry_price: float = Field(..., description="Entry price for the trade")
    direction: str = Field(..., description="Trade direction: 'long' or 'short'")
    atr_stop_multiplier: float = Field(2.0, description="ATR multiplier for stop-loss")
    atr_target_multiplier: float = Field(3.0, description="ATR multiplier for take-profit")
    account_capital: Optional[float] = Field(10000, description="Account capital for position sizing")
    risk_per_trade_percent: Optional[float] = Field(1.0, description="Risk percentage per trade")


class PositionSizingRequest(BaseModel):
    """Request model for position sizing only"""
    entry_price: float
    stop_loss: float
    account_capital: float = 10000
    risk_per_trade_percent: float = 1.0
    max_position_value_percent: float = 20.0


class TrailingStopRequest(BaseModel):
    """Request model for trailing stop calculation"""
    entry_price: float
    current_price: float
    direction: str = 'long'
    trailing_atr_multiplier: float = 1.0


@router.get("/api/stocks/{stock_id}/risk-management")
async def get_risk_management_data(
    stock_id: int,
    entry_price: Optional[float] = None,
    direction: str = 'long',
    atr_stop_multiplier: float = 2.0,
    atr_target_multiplier: float = 3.0,
    account_capital: float = 10000,
    risk_per_trade_percent: float = 1.0,
    timeframe: str = '1d',
    db: Session = Depends(get_db)
):
    """
    Get comprehensive risk management data for a stock

    Returns ATR, stop-loss, take-profit, and position sizing recommendations
    """
    # Get stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Get price data using TimeframeService
    df = TimeframeService.get_price_data_smart(
        db=db,
        stock_id=stock_id,
        timeframe=timeframe,
        lookback_days=200
    )

    if df.empty or len(df) < 14:
        raise HTTPException(
            status_code=400,
            detail="Insufficient price data for risk calculation (need at least 14 periods)"
        )

    # Initialize risk manager
    risk_manager = RiskManager(df)

    # Use current price if entry_price not provided
    if entry_price is None:
        entry_price = float(df['close'].iloc[-1])

    # Calculate stop-loss and take-profit
    stops_targets = risk_manager.calculate_stop_loss_take_profit(
        entry_price=entry_price,
        direction=direction,
        atr_stop_multiplier=atr_stop_multiplier,
        atr_target_multiplier=atr_target_multiplier
    )

    # Calculate position sizing
    position_sizing = risk_manager.calculate_position_size(
        account_capital=account_capital,
        risk_per_trade_percent=risk_per_trade_percent,
        entry_price=entry_price,
        stop_loss=stops_targets['stop_loss']
    )

    return {
        'stock_symbol': stock.symbol,
        'stock_name': stock.name,
        'timeframe': timeframe,
        'current_price': round(float(df['close'].iloc[-1]), 2),
        'entry_price': entry_price,
        'direction': direction,
        **stops_targets,
        **position_sizing
    }


@router.post("/api/risk-management/calculate-stops")
async def calculate_stops(
    stock_id: int,
    request: RiskCalculationRequest,
    timeframe: str = '1d',
    db: Session = Depends(get_db)
):
    """
    Calculate stop-loss and take-profit levels for a specific entry

    This is a more flexible endpoint that accepts POST data
    """
    # Get price data using TimeframeService
    df = TimeframeService.get_price_data_smart(
        db=db,
        stock_id=stock_id,
        timeframe=timeframe,
        lookback_days=200
    )

    if df.empty or len(df) < 14:
        raise HTTPException(
            status_code=400,
            detail="Insufficient price data for ATR calculation"
        )

    risk_manager = RiskManager(df)

    # Calculate stops and targets
    stops_targets = risk_manager.calculate_stop_loss_take_profit(
        entry_price=request.entry_price,
        direction=request.direction,
        atr_stop_multiplier=request.atr_stop_multiplier,
        atr_target_multiplier=request.atr_target_multiplier
    )

    # Calculate position sizing if capital provided
    if request.account_capital and request.risk_per_trade_percent:
        position_sizing = risk_manager.calculate_position_size(
            account_capital=request.account_capital,
            risk_per_trade_percent=request.risk_per_trade_percent,
            entry_price=request.entry_price,
            stop_loss=stops_targets['stop_loss']
        )
        stops_targets.update(position_sizing)

    return stops_targets


@router.post("/api/risk-management/position-sizing")
async def calculate_position_sizing(request: PositionSizingRequest):
    """
    Calculate position size based on risk parameters

    This endpoint doesn't require stock data, just risk parameters
    """
    if request.entry_price <= 0 or request.stop_loss <= 0:
        raise HTTPException(status_code=400, detail="Invalid entry price or stop-loss")

    risk_per_share = abs(request.entry_price - request.stop_loss)

    if risk_per_share == 0:
        raise HTTPException(status_code=400, detail="Stop-loss cannot equal entry price")

    max_risk_amount = request.account_capital * (request.risk_per_trade_percent / 100)
    position_size_by_risk = int(max_risk_amount / risk_per_share)

    max_position_value = request.account_capital * (request.max_position_value_percent / 100)
    max_position_size_by_value = int(max_position_value / request.entry_price)

    position_size = min(position_size_by_risk, max_position_size_by_value)
    position_value = position_size * request.entry_price
    actual_risk = position_size * risk_per_share
    actual_risk_percent = (actual_risk / request.account_capital) * 100

    warnings = []
    if position_size == 0:
        warnings.append('Position size is 0 - risk parameters too conservative')
    if position_value > max_position_value:
        warnings.append(f'Position capped at {request.max_position_value_percent}% of capital')

    return {
        'position_size': position_size,
        'position_value': round(position_value, 2),
        'risk_amount': round(actual_risk, 2),
        'capital_at_risk_percent': round(actual_risk_percent, 2),
        'position_as_percent_of_capital': round((position_value / request.account_capital) * 100, 2),
        'warnings': warnings if warnings else None
    }


@router.post("/api/risk-management/trailing-stop")
async def calculate_trailing_stop_level(
    stock_id: int,
    request: TrailingStopRequest,
    timeframe: str = '1d',
    db: Session = Depends(get_db)
):
    """
    Calculate trailing stop-loss for an open position
    """
    # Get price data using TimeframeService
    df = TimeframeService.get_price_data_smart(
        db=db,
        stock_id=stock_id,
        timeframe=timeframe,
        lookback_days=200
    )

    if df.empty or len(df) < 14:
        raise HTTPException(
            status_code=400,
            detail="Insufficient price data for ATR calculation"
        )

    risk_manager = RiskManager(df)

    trailing_stop_data = risk_manager.calculate_trailing_stop(
        entry_price=request.entry_price,
        current_price=request.current_price,
        direction=request.direction,
        trailing_atr_multiplier=request.trailing_atr_multiplier
    )

    return trailing_stop_data
