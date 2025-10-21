"""
API routes for chart pattern detection
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import List
from datetime import datetime, timedelta
import pandas as pd

from app.db.database import get_db
from app.models.stock import Stock, StockPrice, ChartPattern
from app.schemas.chart_patterns import (
    ChartPatternDetectionRequest,
    ChartPatternDetectionResponse,
    ChartPatternDetected,
    ChartPatternInDB,
    ChartPatternListResponse,
    ChartPatternConfirmRequest,
    ChartPatternStatsResponse,
    ChartPatternTrainingDataExport
)
from app.services.chart_patterns import ChartPatternDetector

router = APIRouter()


@router.post("/stocks/{stock_id}/detect-chart-patterns", response_model=ChartPatternDetectionResponse)
def detect_chart_patterns(
    stock_id: int,
    request: ChartPatternDetectionRequest = ChartPatternDetectionRequest(),
    db: Session = Depends(get_db)
):
    """
    Detect chart patterns in stock price data

    Analyzes OHLC data for chart patterns like Head & Shoulders, Triangles,
    Cup & Handle, Flags, Wedges, etc.
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

    if len(prices) < request.min_pattern_length:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient data for pattern detection. Need at least {request.min_pattern_length} candles, got {len(prices)}"
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
    detector = ChartPatternDetector(df, min_pattern_length=request.min_pattern_length)
    detected_patterns = detector.detect_all_patterns()

    # Save patterns to database
    saved_count = 0
    for pattern in detected_patterns:
        # Check if pattern already exists
        existing = db.query(ChartPattern).filter(
            and_(
                ChartPattern.stock_id == stock_id,
                ChartPattern.pattern_name == pattern['pattern_name'],
                ChartPattern.end_date == pattern['end_date']
            )
        ).first()

        if not existing:
            db_pattern = ChartPattern(
                stock_id=stock_id,
                pattern_name=pattern['pattern_name'],
                pattern_type=pattern['pattern_type'],
                signal=pattern['signal'],
                start_date=pattern['start_date'],
                end_date=pattern['end_date'],
                breakout_price=pattern.get('breakout_price'),
                target_price=pattern.get('target_price'),
                stop_loss=pattern.get('stop_loss'),
                confidence_score=pattern['confidence_score'],
                key_points=pattern['key_points'],
                trendlines=pattern['trendlines']
            )
            db.add(db_pattern)
            saved_count += 1

    db.commit()

    # Count patterns by type and signal
    reversal_count = sum(1 for p in detected_patterns if p['pattern_type'] == 'reversal')
    continuation_count = sum(1 for p in detected_patterns if p['pattern_type'] == 'continuation')
    bullish_count = sum(1 for p in detected_patterns if p['signal'] == 'bullish')
    bearish_count = sum(1 for p in detected_patterns if p['signal'] == 'bearish')
    neutral_count = sum(1 for p in detected_patterns if p['signal'] == 'neutral')

    return ChartPatternDetectionResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        analysis_period=f"{request.days} days",
        total_patterns=len(detected_patterns),
        reversal_patterns=reversal_count,
        continuation_patterns=continuation_count,
        bullish_count=bullish_count,
        bearish_count=bearish_count,
        neutral_count=neutral_count,
        patterns=[ChartPatternDetected(**p) for p in detected_patterns],
        message=f"Detected {len(detected_patterns)} patterns ({saved_count} new, {len(detected_patterns) - saved_count} existing)"
    )


@router.get("/stocks/{stock_id}/chart-patterns", response_model=ChartPatternListResponse)
def get_chart_patterns(
    stock_id: int,
    days: int = Query(default=90, ge=1, le=730),
    confirmed_only: bool = Query(default=False),
    pattern_type: str = Query(default=None, regex="^(reversal|continuation)$"),
    signal: str = Query(default=None, regex="^(bullish|bearish|neutral)$"),
    db: Session = Depends(get_db)
):
    """
    Get detected chart patterns for a stock

    Args:
        stock_id: Stock ID
        days: Number of days to retrieve
        confirmed_only: Only return user-confirmed patterns
        pattern_type: Filter by pattern type (reversal, continuation)
        signal: Filter by signal (bullish, bearish, neutral)
    """
    # Get stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Build query
    start_date = datetime.now() - timedelta(days=days)
    query = db.query(ChartPattern).filter(
        and_(
            ChartPattern.stock_id == stock_id,
            ChartPattern.end_date >= start_date
        )
    )

    if confirmed_only:
        query = query.filter(ChartPattern.user_confirmed == True)

    if pattern_type:
        query = query.filter(ChartPattern.pattern_type == pattern_type)

    if signal:
        query = query.filter(ChartPattern.signal == signal)

    patterns = query.order_by(ChartPattern.end_date.desc()).all()

    # Count confirmations
    confirmed_count = sum(1 for p in patterns if p.user_confirmed == True)
    rejected_count = sum(1 for p in patterns if p.user_confirmed == False)
    pending_count = sum(1 for p in patterns if p.user_confirmed is None)

    return ChartPatternListResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        total_patterns=len(patterns),
        confirmed_count=confirmed_count,
        rejected_count=rejected_count,
        pending_count=pending_count,
        patterns=[ChartPatternInDB.from_orm(p) for p in patterns]
    )


@router.patch("/chart-patterns/{pattern_id}/confirm", response_model=ChartPatternInDB)
def confirm_chart_pattern(
    pattern_id: int,
    request: ChartPatternConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Confirm or reject a detected chart pattern (for ML training data collection)

    Args:
        pattern_id: Pattern ID
        request: Confirmation details
    """
    pattern = db.query(ChartPattern).filter(ChartPattern.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    # Update pattern
    pattern.user_confirmed = request.confirmed
    pattern.confirmed_at = datetime.now()
    pattern.confirmed_by = request.confirmed_by
    pattern.notes = request.notes

    db.commit()
    db.refresh(pattern)

    return ChartPatternInDB.from_orm(pattern)


@router.delete("/chart-patterns/{pattern_id}")
def delete_chart_pattern(
    pattern_id: int,
    db: Session = Depends(get_db)
):
    """Delete a detected chart pattern"""
    pattern = db.query(ChartPattern).filter(ChartPattern.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    db.delete(pattern)
    db.commit()

    return {"message": "Pattern deleted successfully", "pattern_id": pattern_id}


@router.delete("/stocks/{stock_id}/chart-patterns")
def delete_all_chart_patterns(
    stock_id: int,
    confirmed_only: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    """Delete all chart patterns for a stock"""
    query = db.query(ChartPattern).filter(ChartPattern.stock_id == stock_id)

    if confirmed_only:
        query = query.filter(ChartPattern.user_confirmed == True)

    count = query.delete()
    db.commit()

    return {"message": f"Deleted {count} patterns", "stock_id": stock_id}


@router.get("/chart-patterns/stats", response_model=ChartPatternStatsResponse)
def get_chart_pattern_stats(
    stock_id: int = Query(default=None),
    db: Session = Depends(get_db)
):
    """
    Get chart pattern statistics for ML training

    Returns counts of confirmed/rejected patterns and breakdown by pattern type
    """
    query = db.query(ChartPattern)

    if stock_id:
        query = query.filter(ChartPattern.stock_id == stock_id)

    all_patterns = query.all()

    confirmed = [p for p in all_patterns if p.user_confirmed == True]
    rejected = [p for p in all_patterns if p.user_confirmed == False]
    pending = [p for p in all_patterns if p.user_confirmed is None]

    # Pattern breakdown
    pattern_breakdown = {}
    for pattern in all_patterns:
        name = pattern.pattern_name
        pattern_breakdown[name] = pattern_breakdown.get(name, 0) + 1

    # Count by type and signal
    reversal_count = sum(1 for p in all_patterns if p.pattern_type == 'reversal')
    continuation_count = sum(1 for p in all_patterns if p.pattern_type == 'continuation')
    bullish_count = sum(1 for p in all_patterns if p.signal == 'bullish')
    bearish_count = sum(1 for p in all_patterns if p.signal == 'bearish')
    neutral_count = sum(1 for p in all_patterns if p.signal == 'neutral')

    # Average confidence
    avg_confidence = sum(float(p.confidence_score) for p in all_patterns) / len(all_patterns) if all_patterns else 0

    return ChartPatternStatsResponse(
        total_patterns=len(all_patterns),
        confirmed_patterns=len(confirmed),
        rejected_patterns=len(rejected),
        pending_patterns=len(pending),
        pattern_breakdown=pattern_breakdown,
        reversal_count=reversal_count,
        continuation_count=continuation_count,
        bullish_count=bullish_count,
        bearish_count=bearish_count,
        neutral_count=neutral_count,
        avg_confidence=round(avg_confidence, 4)
    )


@router.get("/chart-patterns/export/training-data", response_model=List[ChartPatternTrainingDataExport])
def export_chart_pattern_training_data(
    confirmed_only: bool = Query(default=True),
    stock_id: int = Query(default=None),
    db: Session = Depends(get_db)
):
    """
    Export confirmed chart patterns as training data for ML

    Returns patterns with labels for supervised learning
    """
    query = db.query(ChartPattern).join(Stock)

    if confirmed_only:
        query = query.filter(ChartPattern.user_confirmed != None)

    if stock_id:
        query = query.filter(ChartPattern.stock_id == stock_id)

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

        training_data.append(ChartPatternTrainingDataExport(
            pattern_id=pattern.id,
            stock_symbol=pattern.stock.symbol,
            pattern_name=pattern.pattern_name,
            pattern_type=pattern.pattern_type,
            signal=pattern.signal,
            start_date=pattern.start_date,
            end_date=pattern.end_date,
            confidence_score=float(pattern.confidence_score),
            key_points=pattern.key_points or {},
            trendlines=pattern.trendlines or {},
            user_confirmed=pattern.user_confirmed if pattern.user_confirmed is not None else False,
            label=label
        ))

    return training_data
