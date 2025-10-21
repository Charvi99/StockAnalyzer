
"""
API routes for technical analysis and predictions
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import pandas as pd
import logging

from app.db.database import get_db
from app.models.stock import Stock, StockPrice, Prediction, SentimentScore
from app.schemas.analysis import (
    TechnicalAnalysisResponse,
    AnalysisRequest,
    MLPredictionRequest,
    MLPredictionResponse,
    RecommendationResponse,
    PredictionResponse
)
from app.services.technical_indicators import TechnicalIndicators

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_recommendation_for_stock(stock: Stock, db: Session) -> RecommendationResponse:
    """
    Reusable function to get a comprehensive recommendation for a single stock.
    """
    # Get price data
    prices = db.query(StockPrice).filter(
        StockPrice.stock_id == stock.id
    ).order_by(StockPrice.timestamp.asc()).all()

    if not prices or len(prices) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient price data for analysis. Have {len(prices)}, need at least 50."
        )

    # Convert to DataFrame
    df = pd.DataFrame([{'timestamp': p.timestamp, 'open': float(p.open), 'high': float(p.high), 'low': float(p.low), 'close': float(p.close), 'volume': int(p.volume)} for p in prices])
    df.set_index('timestamp', inplace=True)

    # Calculate technical indicators
    df = TechnicalIndicators.calculate_all_indicators(df)
    tech_recommendation = TechnicalIndicators.generate_recommendation(df)

    # Get latest prediction (if any)
    latest_prediction = db.query(Prediction).filter(
        Prediction.stock_id == stock.id
    ).order_by(Prediction.created_at.desc()).first()

    # Get latest sentiment (if any)
    latest_sentiment = db.query(SentimentScore).filter(
        SentimentScore.stock_id == stock.id
    ).order_by(SentimentScore.timestamp.desc()).first()

    # Prepare response
    latest = df.iloc[-1]
    current_price = float(latest['close'])

    # Extract technical signals
    technical_signals = {indicator: details.get('signal', 'HOLD') for indicator, details in tech_recommendation['indicators'].items()}

    # Determine final recommendation
    reasoning = [f"Technical analysis ({tech_recommendation['confidence']:.0%} confidence): {tech_recommendation['reason']}"]
    ml_rec, ml_conf, predicted_price = (latest_prediction.recommendation, float(latest_prediction.confidence_score), float(latest_prediction.predicted_price)) if latest_prediction and latest_prediction.confidence_score else (None, None, None)
    if ml_conf:
        reasoning.append(f"ML prediction ({ml_conf:.0%} confidence): {ml_rec}")

    sentiment_rec, sentiment_conf, sentiment_index = (None, None, None)
    if latest_sentiment:
        sentiment_index = float(latest_sentiment.sentiment_index)
        if sentiment_index > 30:
            sentiment_rec, sentiment_conf = "BUY", min(abs(sentiment_index) / 100, 0.9)
        elif sentiment_index < -30:
            sentiment_rec, sentiment_conf = "SELL", min(abs(sentiment_index) / 100, 0.9)
        else:
            sentiment_rec, sentiment_conf = "HOLD", 0.5
        reasoning.append(f"Market sentiment (index: {sentiment_index:.1f}, {sentiment_conf:.0%} confidence): {sentiment_rec} ({latest_sentiment.positive_count} positive, {latest_sentiment.negative_count} negative news)")

    # Combine all recommendations
    recommendations = [(tech_recommendation['recommendation'], tech_recommendation['confidence'])]
    weights = [0.4]
    if ml_rec and ml_conf and ml_conf > 0.6:
        recommendations.append((ml_rec, ml_conf))
        weights.append(0.4)
    else:
        weights[0] += 0.4

    if sentiment_rec and sentiment_conf:
        recommendations.append((sentiment_rec, sentiment_conf))
        weights.append(0.2)
    else:
        extra_weight = 0.2 / len(weights)
        weights = [w + extra_weight for w in weights]

    rec_scores = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
    for (rec, conf), weight in zip(recommendations, weights):
        rec_scores[rec] += conf * weight

    final_rec = max(rec_scores, key=rec_scores.get)
    final_conf = rec_scores[final_rec]

    if len(recommendations) >= 2 and len(set([r[0] for r in recommendations])) == 1:
        reasoning.append("✓ All indicators agree")
        final_conf = min(final_conf * 1.1, 1.0)
    else:
        reasoning.append("⚠ Mixed signals - use caution")

    risk_level = "LOW" if final_conf >= 0.75 else "MEDIUM" if final_conf >= 0.50 else "HIGH"

    return RecommendationResponse(
        stock_id=stock.id,
        symbol=stock.symbol,
        current_price=current_price,
        timestamp=df.index[-1],
        technical_recommendation=tech_recommendation['recommendation'],
        technical_confidence=tech_recommendation['confidence'],
        technical_signals=technical_signals,
        ml_recommendation=ml_rec,
        ml_confidence=ml_conf,
        predicted_price=predicted_price,
        sentiment_index=sentiment_index,
        sentiment_positive=latest_sentiment.positive_count if latest_sentiment else None,
        sentiment_negative=latest_sentiment.negative_count if latest_sentiment else None,
        final_recommendation=final_rec,
        overall_confidence=final_conf,
        reasoning=reasoning,
        risk_level=risk_level
    )


@router.get("/analysis/dashboard", response_model=List[RecommendationResponse])
def get_dashboard_analysis(db: Session = Depends(get_db)):
    """
    Get comprehensive analysis for all tracked stocks for the dashboard.
    This is an efficient endpoint to avoid N+1 API calls from the frontend.
    """
    logger.info("Getting dashboard analysis for all tracked stocks")
    stocks = db.query(Stock).filter(Stock.is_tracked == True).all()
    dashboard_data = []
    for stock in stocks:
        try:
            recommendation = _get_recommendation_for_stock(stock, db)
            dashboard_data.append(recommendation)
        except HTTPException as e:
            logger.warning(f"Could not get recommendation for stock {stock.id} ('{stock.symbol}'): {e.detail}")
            dashboard_data.append(RecommendationResponse(stock_id=stock.id, symbol=stock.symbol, error=e.detail))
        except Exception as e:
            logger.error(f"An unexpected error occurred for stock {stock.id} ('{stock.symbol}'): {e}")
            dashboard_data.append(RecommendationResponse(stock_id=stock.id, symbol=stock.symbol, error="An unexpected error occurred during analysis."))
    return dashboard_data


@router.post("/stocks/{stock_id}/analyze-complete")
async def analyze_complete(
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

    new_prediction = Prediction(stock_id=stock_id, prediction_date=datetime.now(), target_date=datetime.now() + timedelta(days=request.forecast_days), predicted_price=predicted_price, predicted_change_percent=(predicted_change / current_price) * 100, confidence_score=confidence, model_version=f"technical_v1_{request.model_type}", recommendation=recommendation['recommendation'])
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

