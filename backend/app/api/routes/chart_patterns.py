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
    ChartPatternTrainingDataExport,
    OHLCCandle
)
from app.services.chart_patterns import ChartPatternDetector
from app.services.multi_timeframe_patterns import MultiTimeframePatternDetector

router = APIRouter()


@router.post("/stocks/{stock_id}/detect-chart-patterns", response_model=ChartPatternDetectionResponse)
def detect_chart_patterns(
    stock_id: int,
    request: ChartPatternDetectionRequest = ChartPatternDetectionRequest(),
    db: Session = Depends(get_db)
):
    """
    Detect chart patterns using multi-timeframe analysis

    Analyzes OHLC data across 1h, 4h, and 1d timeframes for chart patterns.
    Patterns confirmed on multiple timeframes receive confidence boosts.

    Expected results:
    - 40-60% reduction in false positives
    - Patterns with higher reliability scores
    - Better entry/exit timing for swing trading
    """
    # Get stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Use multi-timeframe pattern detector
    detector = MultiTimeframePatternDetector(
        db=db,
        stock_id=stock_id,
        min_pattern_length=request.min_pattern_length,
        peak_order=request.peak_order,
        min_confidence=request.min_confidence,
        min_r_squared=request.min_r_squared
    )

    # Detect patterns across multiple timeframes
    result = detector.detect_all_patterns(
        days=request.days,
        exclude_patterns=request.exclude_patterns,
        remove_overlaps=request.remove_overlaps,
        overlap_threshold=request.overlap_threshold
    )

    detected_patterns = result['patterns']

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
                trendlines=pattern['trendlines'],
                # Multi-timeframe fields
                primary_timeframe=pattern.get('primary_timeframe', '1d'),
                detected_on_timeframes=pattern.get('detected_on_timeframes', ['1d']),
                confirmation_level=pattern.get('confirmation_level', 1),
                base_confidence=pattern.get('base_confidence'),
                alignment_score=pattern.get('alignment_score')
            )
            db.add(db_pattern)
            saved_count += 1

    db.commit()

    # Count patterns by type and signal
    reversal_count = sum(
        1 for p in detected_patterns if p['pattern_type'] == 'reversal')
    continuation_count = sum(
        1 for p in detected_patterns if p['pattern_type'] == 'continuation')
    bullish_count = sum(
        1 for p in detected_patterns if p['signal'] == 'bullish')
    bearish_count = sum(
        1 for p in detected_patterns if p['signal'] == 'bearish')
    neutral_count = sum(
        1 for p in detected_patterns if p['signal'] == 'neutral')

    # Calculate multi-timeframe statistics
    multi_tf_confirmed = sum(1 for p in detected_patterns if p.get('is_multi_timeframe_confirmed', False))
    three_tf_count = sum(1 for p in detected_patterns if p.get('confirmation_level', 1) == 3)
    two_tf_count = sum(1 for p in detected_patterns if p.get('confirmation_level', 1) == 2)

    timeframes_analyzed = ', '.join(result.get('statistics', {}).get('timeframes_analyzed', ['1h', '4h', '1d']))
    analysis_period = f"{request.days} days on {timeframes_analyzed}" if request.days else f"all available data on {timeframes_analyzed}"

    return ChartPatternDetectionResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        analysis_period=analysis_period,
        total_patterns=len(detected_patterns),
        reversal_patterns=reversal_count,
        continuation_patterns=continuation_count,
        bullish_count=bullish_count,
        bearish_count=bearish_count,
        neutral_count=neutral_count,
        patterns=[ChartPatternDetected(**p) for p in detected_patterns],
        message=f"Multi-timeframe analysis: {len(detected_patterns)} patterns ({three_tf_count} on 3TF, {two_tf_count} on 2TF) | Saved: {saved_count} new"
    )


@router.get("/stocks/{stock_id}/chart-patterns", response_model=ChartPatternListResponse)
def get_chart_patterns(
    stock_id: int,
    days: int = Query(default=None, ge=1, le=3650),
    confirmed_only: bool = Query(default=False),
    pattern_type: str = Query(default=None, regex="^(reversal|continuation)$"),
    signal: str = Query(default=None, regex="^(bullish|bearish|neutral)$"),
    db: Session = Depends(get_db)
):
    """
    Get detected chart patterns for a stock

    Args:
        stock_id: Stock ID
        days: Number of days to retrieve (None = all patterns)
        confirmed_only: Only return user-confirmed patterns
        pattern_type: Filter by pattern type (reversal, continuation)
        signal: Filter by signal (bullish, bearish, neutral)
    """
    # Get stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Build query
    query = db.query(ChartPattern).filter(ChartPattern.stock_id == stock_id)

    # Apply date filter only if days is specified
    if days is not None:
        start_date = datetime.now() - timedelta(days=days)
        query = query.filter(ChartPattern.end_date >= start_date)

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
    pattern = db.query(ChartPattern).filter(
        ChartPattern.id == pattern_id).first()
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
    pattern = db.query(ChartPattern).filter(
        ChartPattern.id == pattern_id).first()
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
    reversal_count = sum(
        1 for p in all_patterns if p.pattern_type == 'reversal')
    continuation_count = sum(
        1 for p in all_patterns if p.pattern_type == 'continuation')
    bullish_count = sum(1 for p in all_patterns if p.signal == 'bullish')
    bearish_count = sum(1 for p in all_patterns if p.signal == 'bearish')
    neutral_count = sum(1 for p in all_patterns if p.signal == 'neutral')

    # Average confidence
    avg_confidence = sum(float(p.confidence_score)
                         for p in all_patterns) / len(all_patterns) if all_patterns else 0

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
    padding_candles: int = Query(
        default=5, ge=0, le=100, description="Number of candles to include before/after pattern"),
    db: Session = Depends(get_db)
):
    """
    Export confirmed chart patterns as training data for ML with OHLC data

    Returns patterns with labels and complete OHLC data including padding for CNN training

    Args:
        confirmed_only: Only export patterns with user confirmation
        stock_id: Filter by specific stock
        padding_candles: Number of candles to include before/after pattern for context
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

        # Get OHLC data for the pattern with padding
        # Query stock prices ordered by timestamp
        all_prices = db.query(StockPrice).filter(
            StockPrice.stock_id == pattern.stock_id
        ).order_by(StockPrice.timestamp).all()

        if not all_prices:
            continue  # Skip patterns without price data

        # Find indices of pattern start and end in the price data
        pattern_start_idx = None
        pattern_end_idx = None

        for i, price in enumerate(all_prices):
            if price.timestamp >= pattern.start_date and pattern_start_idx is None:
                pattern_start_idx = i
            if price.timestamp >= pattern.end_date:
                pattern_end_idx = i
                break

        if pattern_start_idx is None or pattern_end_idx is None:
            continue  # Skip if pattern dates not found in price data

        # Calculate window with padding
        window_start_idx = max(0, pattern_start_idx - padding_candles)
        window_end_idx = min(len(all_prices) - 1,
                             pattern_end_idx + padding_candles)

        # Get actual padding amounts
        actual_padding_before = pattern_start_idx - window_start_idx
        actual_padding_after = window_end_idx - pattern_end_idx

        # Extract OHLC data for the window
        window_prices = all_prices[window_start_idx:window_end_idx + 1]

        ohlc_data = []
        all_prices_list = []
        all_volumes = []

        for price in window_prices:
            candle = {
                'timestamp': price.timestamp,
                'open': float(price.open),
                'high': float(price.high),
                'low': float(price.low),
                'close': float(price.close),
                'volume': int(price.volume) if price.volume else 0
            }
            ohlc_data.append(candle)
            all_prices_list.extend([candle['high'], candle['low']])
            all_volumes.append(candle['volume'])

        # Calculate normalization metadata
        price_min = min(all_prices_list) if all_prices_list else 0.0
        price_max = max(all_prices_list) if all_prices_list else 0.0
        volume_max = max(all_volumes) if all_volumes else 0

        # Pattern indices in the window (0-indexed)
        pattern_start_in_window = actual_padding_before
        pattern_end_in_window = pattern_start_in_window + \
            (pattern_end_idx - pattern_start_idx)

        training_data.append(ChartPatternTrainingDataExport(
            # Pattern metadata
            pattern_id=pattern.id,
            stock_symbol=pattern.stock.symbol,
            pattern_name=pattern.pattern_name,
            pattern_type=pattern.pattern_type,
            signal=pattern.signal,
            confidence_score=float(pattern.confidence_score),
            key_points=pattern.key_points or {},
            trendlines=pattern.trendlines or {},
            user_confirmed=pattern.user_confirmed if pattern.user_confirmed is not None else False,
            label=label,

            # Date ranges
            pattern_start_date=pattern.start_date,
            pattern_end_date=pattern.end_date,
            window_start_date=window_prices[0].timestamp,
            window_end_date=window_prices[-1].timestamp,

            # OHLC data with padding
            ohlc_data=ohlc_data,
            total_candles=len(ohlc_data),
            pattern_start_index=pattern_start_in_window,
            pattern_end_index=pattern_end_in_window,
            padding_before=actual_padding_before,
            padding_after=actual_padding_after,

            # Normalization metadata
            price_min=price_min,
            price_max=price_max,
            volume_max=volume_max
        ))

    return training_data
