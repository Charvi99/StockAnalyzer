"""
API routes for candlestick pattern detection
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import List
from datetime import datetime, timedelta
import pandas as pd

from app.db.database import get_db
from app.models.stock import Stock, StockPrice, CandlestickPattern
from app.schemas.patterns import (
    PatternDetectionRequest,
    PatternDetectionResponse,
    PatternDetected,
    PatternInDB,
    PatternListResponse,
    PatternConfirmRequest,
    PatternStatsResponse,
    TrainingDataExport
)
from app.services.candlestick_patterns import CandlestickPatternDetector

router = APIRouter()


@router.post("/stocks/{stock_id}/detect-patterns", response_model=PatternDetectionResponse)
def detect_patterns(
    stock_id: int,
    request: PatternDetectionRequest = PatternDetectionRequest(),
    db: Session = Depends(get_db)
):
    """
    Detect candlestick patterns in stock price data

    Analyzes OHLC data for 40 different candlestick patterns (20 bullish, 20 bearish)
    """
    # Get stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Get price data for analysis
    start_date = datetime.now() - timedelta(days=request.days)
    prices = db.query(StockPrice).filter(
        and_(
            StockPrice.stock_id == stock_id,
            StockPrice.timestamp >= start_date
        )
    ).order_by(StockPrice.timestamp).all()

    if len(prices) < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient data for pattern detection. Need at least 10 candles, got {len(prices)}"
        )

    # Convert to DataFrame
    df = pd.DataFrame([{
        'timestamp': p.timestamp,
        'open': float(p.open),
        'high': float(p.high),
        'low': float(p.low),
        'close': float(p.close),
        'volume': int(p.volume) if p.volume else 0
    } for p in prices])

    # Detect patterns
    detector = CandlestickPatternDetector(df)
    detected_patterns = detector.detect_all_patterns()

    # Save patterns to database
    saved_count = 0
    for pattern in detected_patterns:
        # Check if pattern already exists
        existing = db.query(CandlestickPattern).filter(
            and_(
                CandlestickPattern.stock_id == stock_id,
                CandlestickPattern.pattern_name == pattern['pattern_name'],
                CandlestickPattern.timestamp == pattern['timestamp']
            )
        ).first()

        if not existing:
            db_pattern = CandlestickPattern(
                stock_id=stock_id,
                pattern_name=pattern['pattern_name'],
                pattern_type=pattern['pattern_type'],
                timestamp=pattern['timestamp'],
                confidence_score=pattern['confidence_score'],
                candle_data=pattern['candle_data']
            )
            db.add(db_pattern)
            saved_count += 1

    db.commit()

    # Count patterns by type
    bullish_count = sum(1 for p in detected_patterns if p['pattern_type'] == 'bullish')
    bearish_count = sum(1 for p in detected_patterns if p['pattern_type'] == 'bearish')

    return PatternDetectionResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        analysis_period=f"{request.days} days",
        total_patterns=len(detected_patterns),
        bullish_patterns=bullish_count,
        bearish_patterns=bearish_count,
        patterns=[PatternDetected(**p) for p in detected_patterns],
        message=f"Detected {len(detected_patterns)} patterns ({saved_count} new, {len(detected_patterns) - saved_count} existing)"
    )


@router.get("/stocks/{stock_id}/patterns", response_model=PatternListResponse)
def get_patterns(
    stock_id: int,
    days: int = Query(default=30, ge=1, le=365),
    confirmed_only: bool = Query(default=False),
    pattern_type: str = Query(default=None, regex="^(bullish|bearish|neutral)$"),
    db: Session = Depends(get_db)
):
    """
    Get detected patterns for a stock

    Args:
        stock_id: Stock ID
        days: Number of days to retrieve
        confirmed_only: Only return user-confirmed patterns
        pattern_type: Filter by pattern type (bullish, bearish, neutral)
    """
    # Get stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Build query
    start_date = datetime.now() - timedelta(days=days)
    query = db.query(CandlestickPattern).filter(
        and_(
            CandlestickPattern.stock_id == stock_id,
            CandlestickPattern.timestamp >= start_date
        )
    )

    if confirmed_only:
        query = query.filter(CandlestickPattern.user_confirmed == True)

    if pattern_type:
        query = query.filter(CandlestickPattern.pattern_type == pattern_type)

    patterns = query.order_by(CandlestickPattern.timestamp.desc()).all()

    # Count confirmations
    confirmed_count = sum(1 for p in patterns if p.user_confirmed == True)
    rejected_count = sum(1 for p in patterns if p.user_confirmed == False)
    pending_count = sum(1 for p in patterns if p.user_confirmed is None)

    return PatternListResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        total_patterns=len(patterns),
        confirmed_count=confirmed_count,
        rejected_count=rejected_count,
        pending_count=pending_count,
        patterns=[PatternInDB.from_orm(p) for p in patterns]
    )


@router.patch("/patterns/{pattern_id}/confirm", response_model=PatternInDB)
def confirm_pattern(
    pattern_id: int,
    request: PatternConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Confirm or reject a detected pattern (for ML training data collection)

    Args:
        pattern_id: Pattern ID
        request: Confirmation details
    """
    pattern = db.query(CandlestickPattern).filter(CandlestickPattern.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    # Update pattern
    pattern.user_confirmed = request.confirmed
    pattern.confirmed_at = datetime.now()
    pattern.confirmed_by = request.confirmed_by
    pattern.notes = request.notes

    db.commit()
    db.refresh(pattern)

    return PatternInDB.from_orm(pattern)


@router.delete("/patterns/{pattern_id}")
def delete_pattern(
    pattern_id: int,
    db: Session = Depends(get_db)
):
    """Delete a detected pattern"""
    pattern = db.query(CandlestickPattern).filter(CandlestickPattern.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    db.delete(pattern)
    db.commit()

    return {"message": "Pattern deleted successfully", "pattern_id": pattern_id}


@router.delete("/stocks/{stock_id}/patterns")
def delete_all_patterns(
    stock_id: int,
    confirmed_only: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    """Delete all patterns for a stock"""
    query = db.query(CandlestickPattern).filter(CandlestickPattern.stock_id == stock_id)

    if confirmed_only:
        query = query.filter(CandlestickPattern.user_confirmed == True)

    count = query.delete()
    db.commit()

    return {"message": f"Deleted {count} patterns", "stock_id": stock_id}


@router.get("/patterns/stats", response_model=PatternStatsResponse)
def get_pattern_stats(
    stock_id: int = Query(default=None),
    db: Session = Depends(get_db)
):
    """
    Get pattern statistics for ML training

    Returns counts of confirmed/rejected patterns and breakdown by pattern type
    """
    query = db.query(CandlestickPattern)

    if stock_id:
        query = query.filter(CandlestickPattern.stock_id == stock_id)

    all_patterns = query.all()

    confirmed = [p for p in all_patterns if p.user_confirmed == True]
    rejected = [p for p in all_patterns if p.user_confirmed == False]
    pending = [p for p in all_patterns if p.user_confirmed is None]

    # Pattern breakdown
    pattern_breakdown = {}
    for pattern in all_patterns:
        name = pattern.pattern_name
        pattern_breakdown[name] = pattern_breakdown.get(name, 0) + 1

    # Count by type
    bullish_count = sum(1 for p in all_patterns if p.pattern_type == 'bullish')
    bearish_count = sum(1 for p in all_patterns if p.pattern_type == 'bearish')

    # Average confidence
    avg_confidence = sum(float(p.confidence_score) for p in all_patterns) / len(all_patterns) if all_patterns else 0

    return PatternStatsResponse(
        total_patterns=len(all_patterns),
        confirmed_patterns=len(confirmed),
        rejected_patterns=len(rejected),
        pending_patterns=len(pending),
        pattern_breakdown=pattern_breakdown,
        bullish_count=bullish_count,
        bearish_count=bearish_count,
        avg_confidence=round(avg_confidence, 4)
    )


@router.get("/patterns/export/training-data", response_model=List[TrainingDataExport])
def export_training_data(
    confirmed_only: bool = Query(default=True),
    stock_id: int = Query(default=None),
    db: Session = Depends(get_db)
):
    """
    Export confirmed patterns as training data for ML

    Returns patterns with labels for supervised learning
    """
    query = db.query(CandlestickPattern).join(Stock)

    if confirmed_only:
        query = query.filter(CandlestickPattern.user_confirmed != None)

    if stock_id:
        query = query.filter(CandlestickPattern.stock_id == stock_id)

    patterns = query.all()

    training_data = []
    for pattern in patterns:
        # Determine label
        if pattern.user_confirmed == True:
            label = 'true_positive'
        elif pattern.user_confirmed == False:
            label = 'false_positive'
        else:
            label = 'unknown'

        training_data.append(TrainingDataExport(
            pattern_id=pattern.id,
            stock_symbol=pattern.stock.symbol,
            pattern_name=pattern.pattern_name,
            pattern_type=pattern.pattern_type,
            timestamp=pattern.timestamp,
            confidence_score=float(pattern.confidence_score),
            candle_data=pattern.candle_data,
            user_confirmed=pattern.user_confirmed if pattern.user_confirmed is not None else False,
            label=label
        ))

    return training_data
