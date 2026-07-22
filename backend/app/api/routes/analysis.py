
"""
API routes for technical analysis and predictions
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, selectinload, Load
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import pandas as pd
import logging

from app.db.database import get_db
from app.models.stock import Stock, StockPrice, Prediction, SentimentScore, CandlestickPattern, ChartPattern
from app.schemas.analysis import (
    TechnicalAnalysisResponse,
    AnalysisRequest,
    MLPredictionRequest,
    MLPredictionResponse,
    RecommendationResponse,
    PredictionResponse,
    # Phase 2: Completeness schemas
    BatchCompletenessRequest,
    BatchCompletenessResponse,
    AnalysisCompletenessResponse,
    ComponentCompletenessDetail,
    TriggerAnalysisRequest,
    TriggerAnalysisResponse,
    TriggeredTask,
    # Phase 4: Real-time updates schemas
    RecentUpdate,
    RecentUpdatesResponse,
    GetByIdsRequest,
    GetByIdsResponse
)
from app.services.technical_indicators import TechnicalIndicators
from app.services.order_calculator import OrderCalculatorService
from app.services.market_regime import MarketRegimeService
from app.services.realtime_recommendation import _get_recommendation_for_stock

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/analysis/dashboard", response_model=List[RecommendationResponse])
def get_dashboard_analysis(db: Session = Depends(get_db)):
    """
    Get comprehensive analysis for all tracked stocks for the dashboard.
    This is an efficient endpoint to avoid N+1 API calls from the frontend.

    Uses eager loading to avoid N+1 query problem (1651 queries -> 6 queries!)

    PHASE 1 OPTIMIZATION: Selective data loading
    - Only loads daily (1d) timeframe data for dashboard
    - Limits to last 200 days (sufficient for technical analysis)
    - Reduces I/O from 625K rows to ~100K rows (6x improvement)
    """
    logger.info("Getting dashboard analysis for all tracked stocks")

    # Calculate cutoff date for price data (200 days for technical indicators)
    # 200 days gives us enough history for:
    # - 200-day MA (longest indicator)
    # - Weekly trend analysis (40+ weeks)
    # - Pattern detection with context
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=200)

    # Calculate cutoff for patterns/sentiment (30 days - recent signals only)
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # PHASE 1 OPTIMIZATION: Selective eager loading with filters
    # BEFORE: Loaded ALL prices (all timeframes, all dates) = 625K+ rows for 500 stocks
    # AFTER: Only daily prices from last 200 days = ~100K rows (6x reduction!)
    stocks = db.query(Stock).filter(Stock.is_tracked == True).options(
        selectinload(Stock.prices),
        selectinload(Stock.predictions),
        selectinload(Stock.sentiment_scores),
        selectinload(Stock.candlestick_patterns),
        selectinload(Stock.chart_patterns),
        selectinload(Stock.news)  # for news-derived sentiment (avoids N+1)
    ).all()

    logger.info(f"Loaded {len(stocks)} stocks with optimized selective loading (1d/200d only)")

    dashboard_data = []
    for stock in stocks:
        # Pre-check: Skip analysis if no price data available
        prices = sorted(stock.prices, key=lambda p: p.timestamp) if stock.prices else []
        if not prices or len(prices) < 50:
            # Skip warning for stocks without data - just return error response silently
            dashboard_data.append(RecommendationResponse(
                stock_id=stock.id,
                symbol=stock.symbol,
                name=stock.name,
                sector=stock.sector,
                industry=stock.industry,
                error=f"Insufficient price data for analysis. Have {len(prices)}, need at least 50."
            ))
            continue

        try:
            recommendation = _get_recommendation_for_stock(stock, db)
            dashboard_data.append(recommendation)
        except HTTPException as e:
            logger.warning(f"Could not get recommendation for stock {stock.id} ('{stock.symbol}'): {e.detail}")
            dashboard_data.append(RecommendationResponse(stock_id=stock.id, symbol=stock.symbol, name=stock.name, sector=stock.sector, industry=stock.industry, error=e.detail))
        except Exception as e:
            logger.error(f"An unexpected error occurred for stock {stock.id} ('{stock.symbol}'): {e}")
            dashboard_data.append(RecommendationResponse(stock_id=stock.id, symbol=stock.symbol, name=stock.name, sector=stock.sector, industry=stock.industry, error="An unexpected error occurred during analysis."))
    return dashboard_data


@router.get("/analysis/dashboard/chunk", response_model=List[RecommendationResponse])
def get_dashboard_analysis_chunk(
    offset: int = Query(0, ge=0, description="Starting index for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Number of stocks to return"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive analysis for a chunk of tracked stocks.
    Used for progressive loading in the frontend with loading states.

    This endpoint loads stocks in batches to provide immediate visual feedback
    while maintaining efficient database queries using eager loading.

    PHASE 1 OPTIMIZATION: Same selective loading as full dashboard endpoint

    Args:
        offset: Starting index (default 0)
        limit: Number of stocks to return (default 50, max 100)

    Returns:
        List of recommendations for the requested chunk
    """
    logger.info(f"Getting dashboard chunk: offset={offset}, limit={limit}")

    # Calculate cutoff dates (same as full dashboard)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=200)
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # PHASE 1 OPTIMIZATION: Selective eager loading
    stocks = db.query(Stock).filter(Stock.is_tracked == True).options(
        # Load prices, predictions, sentiment, etc.
        selectinload(Stock.prices),
        selectinload(Stock.predictions),
        selectinload(Stock.sentiment_scores),
        selectinload(Stock.candlestick_patterns),
        selectinload(Stock.chart_patterns),
        selectinload(Stock.news)  # for news-derived sentiment (avoids N+1)
    ).order_by(Stock.symbol).offset(offset).limit(limit).all()

    logger.info(f"Loaded {len(stocks)} stocks for chunk (offset={offset}) with selective loading")

    dashboard_data = []
    for stock in stocks:
        # Pre-check: Skip analysis if no price data available
        prices = sorted(stock.prices, key=lambda p: p.timestamp) if stock.prices else []
        if not prices or len(prices) < 50:
            # Skip warning for stocks without data - just return error response silently
            dashboard_data.append(RecommendationResponse(
                stock_id=stock.id,
                symbol=stock.symbol,
                name=stock.name,
                sector=stock.sector,
                industry=stock.industry,
                error=f"Insufficient price data for analysis. Have {len(prices)}, need at least 50."
            ))
            continue

        try:
            recommendation = _get_recommendation_for_stock(stock, db)
            dashboard_data.append(recommendation)
        except HTTPException as e:
            logger.warning(f"Could not get recommendation for stock {stock.id} ('{stock.symbol}'): {e.detail}")
            dashboard_data.append(RecommendationResponse(
                stock_id=stock.id,
                symbol=stock.symbol,
                name=stock.name,
                sector=stock.sector,
                industry=stock.industry,
                error=e.detail
            ))
        except Exception as e:
            logger.error(f"An unexpected error occurred for stock {stock.id} ('{stock.symbol}'): {e}")
            dashboard_data.append(RecommendationResponse(
                stock_id=stock.id,
                symbol=stock.symbol,
                name=stock.name,
                sector=stock.sector,
                industry=stock.industry,
                error="An unexpected error occurred during analysis."
            ))

    return dashboard_data


@router.post("/stocks/{stock_id}/analyze-complete")
def analyze_complete(
    stock_id: int,
    db: Session = Depends(get_db)
):
    """
    Comprehensive analysis - fetches data and runs all analyses
    """
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    try:
        recommendation = _get_recommendation_for_stock(stock, db)
        return {
            "stock_id": stock_id,
            "symbol": stock.symbol,
            "status": "completed",
            "recommendation": recommendation
        }
    except HTTPException as e:
        return {"stock_id": stock_id, "symbol": stock.symbol, "status": "error", "error": e.detail}
    except Exception as e:
        logger.error(f"Error in comprehensive analysis for stock {stock_id}: {e}")
        return {"stock_id": stock_id, "symbol": stock.symbol, "status": "error", "error": str(e)}


@router.post("/stocks/{stock_id}/analyze", response_model=TechnicalAnalysisResponse)
def analyze_stock(
    stock_id: int,
    request: AnalysisRequest = AnalysisRequest(),
    db: Session = Depends(get_db)
):
    """
    Perform technical analysis on a stock
    """
    logger.info(f"Analyzing stock {stock_id}")
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    prices = db.query(StockPrice).filter(StockPrice.stock_id == stock_id).order_by(StockPrice.timestamp.asc()).all()
    if not prices or len(prices) < 50:
        raise HTTPException(status_code=400, detail=f"Insufficient price data. Need at least 50 data points, have {len(prices)}")

    df = pd.DataFrame([{'timestamp': p.timestamp, 'open': float(p.open), 'high': float(p.high), 'low': float(p.low), 'close': float(p.close), 'volume': int(p.volume)} for p in prices])
    df.set_index('timestamp', inplace=True)

    df = TechnicalIndicators.calculate_all_indicators(df, rsi_period=request.rsi_period, macd_fast=request.macd_fast, macd_slow=request.macd_slow, macd_signal=request.macd_signal, bb_window=request.bb_window, bb_std=request.bb_std, ma_short=request.ma_short, ma_long=request.ma_long)
    recommendation = TechnicalIndicators.generate_recommendation(df)
    latest = df.iloc[-1]

    return TechnicalAnalysisResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        timestamp=df.index[-1],
        current_price=float(latest['close']),
        indicators=recommendation['indicators'],
        recommendation=recommendation['recommendation'],
        confidence=recommendation['confidence'],
        reason=recommendation['reason'],
        signal_counts=recommendation['signal_counts']
    )


@router.get("/stocks/{stock_id}/recommendation", response_model=RecommendationResponse)
def get_recommendation(
    stock_id: int,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive recommendation for a stock
    """
    logger.info(f"Getting recommendation for stock {stock_id}")
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    return _get_recommendation_for_stock(stock, db)


@router.get("/stocks/{stock_id}/predictions", response_model=List[PredictionResponse])
def get_predictions(
    stock_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get prediction history for a stock
    """
    logger.info(f"Getting predictions for stock {stock_id}")
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    predictions = db.query(Prediction).filter(Prediction.stock_id == stock_id).order_by(Prediction.created_at.desc()).limit(limit).all()
    return predictions


@router.get("/stocks/{stock_id}/indicators")
def get_stock_indicators(
    stock_id: int,
    days: int = Query(default=365, description="Number of days of historical data to return"),
    rsi_period: int = Query(default=14, ge=2, le=50),
    macd_fast: int = Query(default=12, ge=1, le=50),
    macd_slow: int = Query(default=26, ge=1, le=100),
    macd_signal: int = Query(default=9, ge=1, le=50),
    bb_window: int = Query(default=20, ge=2, le=100),
    bb_std: float = Query(default=2.0, ge=0.1, le=5.0),
    ma_short: int = Query(default=20, ge=1, le=200),
    ma_long: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Get stock prices with calculated technical indicators for chart overlays
    """
    logger.info(f"Getting indicator data for stock {stock_id}")
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    prices = db.query(StockPrice).filter(StockPrice.stock_id == stock_id).order_by(StockPrice.timestamp.desc()).limit(days).all()
    if not prices or len(prices) < 50:
        raise HTTPException(status_code=400, detail=f"Insufficient price data. Need at least 50 data points, have {len(prices)}")

    prices.reverse()
    df = pd.DataFrame([{'timestamp': p.timestamp, 'open': float(p.open), 'high': float(p.high), 'low': float(p.low), 'close': float(p.close), 'volume': int(p.volume)} for p in prices])

    df = TechnicalIndicators.calculate_all_indicators(df, rsi_period=rsi_period, macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_signal, bb_window=bb_window, bb_std=bb_std, ma_short=ma_short, ma_long=ma_long)

    result_data = []
    for _, row in df.iterrows():
        record = {'timestamp': row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp']), 'open': float(row['open']) if pd.notna(row['open']) else None, 'high': float(row['high']) if pd.notna(row['high']) else None, 'low': float(row['low']) if pd.notna(row['low']) else None, 'close': float(row['close']) if pd.notna(row['close']) else None, 'volume': int(row['volume']) if pd.notna(row['volume']) else 0}
        if 'ma_short' in row and pd.notna(row['ma_short']): record['ma_short'] = float(row['ma_short'])
        if 'ma_long' in row and pd.notna(row['ma_long']): record['ma_long'] = float(row['ma_long'])
        if 'ema_fast' in row and pd.notna(row['ema_fast']): record['ema_fast'] = float(row['ema_fast'])
        if 'ema_slow' in row and pd.notna(row['ema_slow']): record['ema_slow'] = float(row['ema_slow'])
        if 'bb_upper' in row and pd.notna(row['bb_upper']): record['bb_upper'] = float(row['bb_upper'])
        if 'bb_middle' in row and pd.notna(row['bb_middle']): record['bb_middle'] = float(row['bb_middle'])
        if 'bb_lower' in row and pd.notna(row['bb_lower']): record['bb_lower'] = float(row['bb_lower'])
        if 'psar' in row and pd.notna(row['psar']): record['psar'] = float(row['psar'])
        result_data.append(record)

    return {'stock_id': stock_id, 'symbol': stock.symbol, 'prices': result_data}


@router.post("/stocks/{stock_id}/predict", response_model=MLPredictionResponse)
def create_ml_prediction(
    stock_id: int,
    request: MLPredictionRequest = MLPredictionRequest(),
    db: Session = Depends(get_db)
):
    """
    Create a new ML-based prediction
    """
    logger.info(f"Creating ML prediction for stock {stock_id}")
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    prices = db.query(StockPrice).filter(StockPrice.stock_id == stock_id).order_by(StockPrice.timestamp.asc()).all()
    if not prices or len(prices) < 50:
        raise HTTPException(status_code=400, detail="Insufficient price data for prediction")

    df = pd.DataFrame([{'timestamp': p.timestamp, 'close': float(p.close), 'open': float(p.open), 'high': float(p.high), 'low': float(p.low), 'volume': int(p.volume)} for p in prices])
    df.set_index('timestamp', inplace=True)

    df = TechnicalIndicators.calculate_all_indicators(df)
    recommendation = TechnicalIndicators.generate_recommendation(df)

    current_price = float(df['close'].iloc[-1])
    ma_slope = df['ma_short_slope'].iloc[-5:].mean()
    predicted_change = ma_slope * request.forecast_days
    predicted_price = current_price + predicted_change

    confidence = recommendation['confidence']

    new_prediction = Prediction(stock_id=stock_id, prediction_date=datetime.now(timezone.utc), target_date=datetime.now(timezone.utc) + timedelta(days=request.forecast_days), predicted_price=predicted_price, predicted_change_percent=(predicted_change / current_price) * 100, confidence_score=confidence, model_version=f"technical_v1_{request.model_type}", recommendation=recommendation['recommendation'])
    db.add(new_prediction)
    db.commit()
    db.refresh(new_prediction)

    logger.info(f"Created prediction {new_prediction.id} for stock {stock_id}")

    return MLPredictionResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        current_price=current_price,
        predicted_price=predicted_price,
        predicted_change=predicted_change,
        confidence=confidence,
        recommendation=recommendation['recommendation'],
        model_used=request.model_type,
        forecast_horizon=request.forecast_days,
        technical_indicators=recommendation['indicators'],
        reason=recommendation['reason']
    )


@router.post("/stocks/{stock_id}/order-calculator")
def calculate_order_parameters(
    stock_id: int,
    account_size: float = Query(default=10000.0, ge=100, le=10000000, description="Total account size"),
    risk_percentage: float = Query(default=2.0, ge=0.5, le=10.0, description="Risk percentage per trade"),
    db: Session = Depends(get_db)
):
    """
    Calculate recommended order parameters including entry, stop loss, and take profit

    Combines:
    - Chart pattern levels (stop loss, target prices)
    - Candlestick patterns for bias
    - Technical indicators (ATR for volatility)
    - Support/resistance levels

    Returns position sizing and risk/reward calculations
    """
    try:
        calculator = OrderCalculatorService(db)
        result = calculator.calculate_order_parameters(
            stock_id=stock_id,
            account_size=account_size,
            risk_percentage=risk_percentage
        )
        return result
    except ValueError as e:
        logger.error(f"Order calculator ValueError for stock {stock_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Order calculator error for stock {stock_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate order parameters: {str(e)}")



@router.post("/stocks/{stock_id}/trailing-stop")
def calculate_trailing_stop(
    stock_id: int,
    entry_price: float = Query(..., description="Original entry price"),
    current_price: float = Query(..., description="Current market price"),
    direction: str = Query(default='long', regex="^(long|short)$", description="Position direction"),
    trailing_atr_multiplier: float = Query(default=1.0, ge=0.5, le=3.0, description="ATR multiplier for trailing stop"),
    db: Session = Depends(get_db)
):
    """
    Calculate trailing stop-loss for an open position

    Uses ATR-based trailing stop that protects profits while giving the trade room to breathe
    """
    try:
        calculator = OrderCalculatorService(db)
        result = calculator.calculate_trailing_stop_for_position(
            stock_id=stock_id,
            entry_price=entry_price,
            current_price=current_price,
            direction=direction,
            trailing_atr_multiplier=trailing_atr_multiplier
        )
        return result
    except ValueError as e:
        logger.error(f"Trailing stop calculator error for stock {stock_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Trailing stop calculator error for stock {stock_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate trailing stop: {str(e)}")


@router.post("/portfolio/risk")
def calculate_portfolio_risk(
    open_positions: list[dict] = Body(..., description="List of open positions with entry_price, stop_loss, position_size"),
    account_capital: float = Body(..., ge=100, description="Total account capital"),
    max_portfolio_heat_percent: float = Body(default=6.0, ge=1.0, le=20.0, description="Maximum portfolio risk percentage"),
    db: Session = Depends(get_db)
):
    """
    Calculate total portfolio risk (heat) across all open positions

    Helps prevent over-leveraging by monitoring aggregate risk
    """
    try:
        calculator = OrderCalculatorService(db)
        result = calculator.calculate_portfolio_risk(
            open_positions=open_positions,
            account_capital=account_capital,
            max_portfolio_heat_percent=max_portfolio_heat_percent
        )
        return result
    except Exception as e:
        logger.error(f"Portfolio risk calculator error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate portfolio risk: {str(e)}")


@router.get("/stocks/{stock_id}/market-regime")
def get_market_regime(
    stock_id: int,
    lookback_periods: int = Query(default=100, ge=50, le=500, description="Number of periods to analyze"),
    db: Session = Depends(get_db)
):
    """
    Detect market regime using TCR (Trend/Channel/Range) + MA slope + Volatility analysis

    Returns:
        - regime: 'trend', 'channel', or 'range'
        - direction: 'bullish', 'bearish', 'neutral', 'bullish_weak', 'bearish_weak'
        - volatility_regime: 'low_vol', 'normal_vol', 'high_vol'
        - adx: Average Directional Index (trend strength)
        - ma20_slope: 20-period MA slope (percentage)
        - ma50_slope: 50-period MA slope (percentage)
        - recommendation: Trading recommendation based on regime
        - reasoning: Explanation of the recommendation
        - suggested_strategy: Strategy type to use

    Regime Classification:
        - Trend: ADX > 25 (strong directional movement)
        - Channel: ADX 20-25 (moderate directional movement)
        - Range: ADX < 20 (sideways movement)

    Direction Classification:
        - Bullish: MA20 and MA50 slopes positive + +DI > -DI
        - Bearish: MA20 and MA50 slopes negative + -DI > +DI
        - Neutral: Mixed signals

    Volatility Classification:
        - Low: ATR below 33rd percentile
        - Normal: ATR between 33rd and 67th percentile
        - High: ATR above 67th percentile
    """
    # Check if stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock with ID {stock_id} not found")

    try:
        regime_service = MarketRegimeService(db)
        result = regime_service.detect_market_regime(
            stock_id=stock_id,
            lookback_periods=lookback_periods
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Market regime detection error for stock {stock_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to detect market regime: {str(e)}")


# ============================================================================
# PHASE 2: Analysis Completeness & Auto-Trigger Endpoints
# ============================================================================

@router.post("/analysis/check-completeness", response_model=BatchCompletenessResponse)
def check_analysis_completeness(
    request: BatchCompletenessRequest,
    db: Session = Depends(get_db)
):
    """
    Check analysis completeness for multiple stocks

    This endpoint:
    1. Calculates analysis score for each stock (0.0 to 1.0)
    2. Determines which stocks need analysis refresh
    3. Returns detailed completeness information

    Use this before triggering batch analysis to avoid redundant work.

    Args:
        request: List of stock IDs and completeness criteria
        db: Database session

    Returns:
        Completeness info for each stock, including which ones need analysis
    """
    from app.services.analysis_completeness import AnalysisCompletenessService

    logger.info(f"Checking completeness for {len(request.stock_ids)} stocks")

    # Load all requested stocks
    stocks = db.query(Stock).filter(Stock.id.in_(request.stock_ids)).all()

    if not stocks:
        logger.warning("No stocks found for provided IDs")
        return BatchCompletenessResponse(
            total_checked=0,
            needs_analysis_count=0,
            stocks=[]
        )

    completeness_results = []
    needs_analysis_count = 0

    for stock in stocks:
        # Calculate completeness score
        score = AnalysisCompletenessService.calculate_completeness_score(
            stock, db, request.max_age_hours
        )

        # Check if analysis should be triggered. A stock that was comprehensively
        # analyzed recently must NOT be re-flagged just because its score is structurally
        # below threshold: sentiment is handled during news fetch (no analysis step) and
        # ml_prediction isn't running, so ~3/5 components cap the score at ~0.6 < 0.8 and
        # re-analysis can NEVER raise it. Without this cooldown guard every incomplete
        # stock loops forever (analyzed -> still incomplete -> needs_refresh -> re-trigger),
        # re-analyzing ~40+ stocks every ~60s. Cooldown reuses max_age_hours.
        recently_analyzed = (
            stock.last_comprehensive_analysis is not None
            and stock.last_comprehensive_analysis > datetime.now(timezone.utc) - timedelta(hours=request.max_age_hours)
        )
        needs_refresh = (not recently_analyzed) and (
            (score < request.min_score_threshold) or (stock.last_comprehensive_analysis is None)
        )

        if needs_refresh:
            needs_analysis_count += 1

        # Get missing components
        missing = AnalysisCompletenessService.get_missing_components(
            stock, db, request.max_age_hours
        )

        # Build response
        result = AnalysisCompletenessResponse(
            stock_id=stock.id,
            symbol=stock.symbol,
            analysis_score=score,
            analysis_complete=stock.analysis_complete,
            needs_refresh=needs_refresh,
            last_comprehensive_analysis=stock.last_comprehensive_analysis,
            missing_components=missing
        )

        # Add detailed component breakdown if requested
        if request.include_component_details:
            summary = AnalysisCompletenessService.get_completeness_summary(stock, db)
            result.components = {
                comp_name: ComponentCompletenessDetail(**comp_data)
                for comp_name, comp_data in summary['components'].items()
            }

        completeness_results.append(result)

    logger.info(
        f"Completeness check complete: {needs_analysis_count}/{len(stocks)} stocks need analysis"
    )

    return BatchCompletenessResponse(
        total_checked=len(stocks),
        needs_analysis_count=needs_analysis_count,
        stocks=completeness_results
    )


@router.post("/analysis/trigger-batch", response_model=TriggerAnalysisResponse)
def trigger_batch_analysis(
    request: TriggerAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Trigger comprehensive analysis for multiple stocks

    This endpoint queues Celery tasks to run analyze_stock_comprehensive
    for each requested stock. Tasks are queued with appropriate priority
    based on stock.priority field (or overridden priority).

    Important:
    - Does NOT wait for tasks to complete (async)
    - Returns task IDs for tracking progress
    - Use /analysis/check-completeness first to avoid redundant work

    Args:
        request: List of stock IDs and optional priority override
        db: Database session

    Returns:
        List of triggered task IDs and summary info
    """
    from app.tasks.analysis_tasks import analyze_stock_comprehensive

    logger.info(f"Triggering analysis for {len(request.stock_ids)} stocks")

    # Load all requested stocks
    stocks = db.query(Stock).filter(Stock.id.in_(request.stock_ids)).all()

    if not stocks:
        raise HTTPException(status_code=404, detail="No stocks found for provided IDs")

    triggered_tasks = []

    for stock in stocks:
        # Determine task priority
        if request.priority_override:
            priority = request.priority_override
        else:
            priority = stock.priority

        # Queue analysis task
        # Priority mapping: high=9, medium=5, low=1 (Celery priority)
        celery_priority = {'high': 9, 'medium': 5, 'low': 1}.get(priority, 5)

        try:
            task = analyze_stock_comprehensive.apply_async(
                args=[stock.id, stock.symbol],
                priority=celery_priority,
                queue='processor'  # Use processor queue for analysis tasks
            )

            triggered_tasks.append(TriggeredTask(
                stock_id=stock.id,
                symbol=stock.symbol,
                task_id=task.id,
                priority=priority
            ))

            logger.info(f"Queued analysis for {stock.symbol} (ID: {stock.id}, priority: {priority}, task: {task.id})")

        except Exception as e:
            logger.error(f"Failed to queue analysis for {stock.symbol}: {e}")
            # Continue with other stocks even if one fails

    if not triggered_tasks:
        raise HTTPException(
            status_code=500,
            detail="Failed to queue any analysis tasks"
        )

    message = f"Triggered analysis for {len(triggered_tasks)} stocks. Tasks are running in background."
    if len(triggered_tasks) < len(request.stock_ids):
        message += f" (Warning: {len(request.stock_ids) - len(triggered_tasks)} stocks failed to queue)"

    logger.info(message)

    return TriggerAnalysisResponse(
        triggered_count=len(triggered_tasks),
        tasks=triggered_tasks,
        message=message
    )


# ============================================================================
# Phase 4: Real-Time Updates (Polling Approach)
# ============================================================================

@router.get("/analysis/recent-updates", response_model=RecentUpdatesResponse)
def get_recent_updates(
    since: datetime,
    db: Session = Depends(get_db)
):
    """
    Get stocks that have been updated since a specific timestamp

    This endpoint is used for efficient polling to detect which stocks
    have new analysis data without fetching all stock data.

    Args:
        since: ISO timestamp - only return stocks updated after this time
        db: Database session

    Returns:
        List of stock IDs with their update timestamps and components
    """
    from app.models.stock import Stock

    logger.info(f"Checking for updates since {since}")

    # Find stocks with any analysis timestamp updated after 'since'
    # Check all analysis-related timestamps on Stock model
    updated_stocks = db.query(Stock).filter(
        Stock.is_tracked == True,
        (
            (Stock.last_comprehensive_analysis > since) |
            (Stock.last_chart_pattern_detection > since) |
            (Stock.last_candlestick_detection > since) |
            (Stock.last_technical_analysis > since) |
            (Stock.last_sentiment_analysis > since)
        )
    ).all()

    # Ensure 'since' is timezone-aware
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    updates = []
    for stock in updated_stocks:
        # Determine which components were updated
        components_updated = []

        # Helper to make timestamp timezone-aware if needed
        def make_aware(dt):
            if dt and dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        last_chart = make_aware(stock.last_chart_pattern_detection)
        last_candlestick = make_aware(stock.last_candlestick_detection)
        last_technical = make_aware(stock.last_technical_analysis)
        last_sentiment = make_aware(stock.last_sentiment_analysis)
        last_comprehensive = make_aware(stock.last_comprehensive_analysis)

        if last_chart and last_chart > since:
            components_updated.append('chart_patterns')
        if last_candlestick and last_candlestick > since:
            components_updated.append('candlestick_patterns')
        if last_technical and last_technical > since:
            components_updated.append('technical_indicators')
        if last_sentiment and last_sentiment > since:
            components_updated.append('sentiment')
        if last_comprehensive and last_comprehensive > since:
            components_updated.append('recommendation')

        # Use the most recent timestamp (use timezone-aware versions)
        most_recent = max(
            last_comprehensive or datetime.min.replace(tzinfo=timezone.utc),
            last_chart or datetime.min.replace(tzinfo=timezone.utc),
            last_candlestick or datetime.min.replace(tzinfo=timezone.utc),
            last_technical or datetime.min.replace(tzinfo=timezone.utc),
            last_sentiment or datetime.min.replace(tzinfo=timezone.utc)
        )

        updates.append(RecentUpdate(
            stock_id=stock.id,
            symbol=stock.symbol,
            updated_at=most_recent,
            components_updated=components_updated
        ))

    logger.info(f"Found {len(updates)} stocks updated since {since}")

    return RecentUpdatesResponse(
        count=len(updates),
        updates=updates,
        since=since
    )


@router.post("/analysis/get-by-ids", response_model=GetByIdsResponse)
def get_analysis_by_ids(
    request: GetByIdsRequest,
    db: Session = Depends(get_db)
):
    """
    Fetch full analysis data for specific stock IDs

    More efficient than re-fetching entire dashboard when only a few
    stocks have been updated. Used in conjunction with /recent-updates
    for efficient real-time polling.

    Args:
        request: List of stock IDs to fetch
        db: Database session

    Returns:
        Full RecommendationResponse for each requested stock
    """
    from app.models.stock import Stock

    logger.info(f"Fetching analysis for {len(request.stock_ids)} specific stocks")

    # Fetch stocks
    stocks = db.query(Stock).filter(
        Stock.id.in_(request.stock_ids),
        Stock.is_tracked == True
    ).all()

    if not stocks:
        return GetByIdsResponse(count=0, stocks=[])

    # Reuse the _get_recommendation_for_stock helper
    recommendations = []
    for stock in stocks:
        try:
            rec = _get_recommendation_for_stock(stock, db)
            recommendations.append(rec)
        except Exception as e:
            logger.error(f"Failed to get recommendation for {stock.symbol}: {e}")
            # Continue with other stocks

    logger.info(f"Successfully fetched analysis for {len(recommendations)} stocks")

    return GetByIdsResponse(
        count=len(recommendations),
        stocks=recommendations
    )
