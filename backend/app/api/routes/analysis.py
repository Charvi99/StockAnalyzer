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


@router.post("/stocks/{stock_id}/analyze-complete")
async def analyze_complete(
    stock_id: int,
    db: Session = Depends(get_db)
):
    """
    Comprehensive analysis - fetches data and runs all analyses

    Returns progress updates and final recommendation
    """
    from app.services.polygon_fetcher import PolygonFetcher

    logger.info(f"Starting comprehensive analysis for stock {stock_id}")

    # Get stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    result = {
        "stock_id": stock_id,
        "symbol": stock.symbol,
        "progress": 0,
        "status": "starting",
        "steps": []
    }

    try:
        # Step 1: Fetch latest price data (25%)
        result["status"] = "fetching_data"
        result["progress"] = 25
        result["steps"].append("Fetching latest price data...")

        fetcher = PolygonFetcher()
        try:
            # Fetch historical data from Polygon
            historical_data = fetcher.fetch_historical_data(stock.symbol, "1mo", "1d")

            if historical_data:
                # Save to database
                records_saved = 0
                for price_data in historical_data:
                    # Check if record already exists
                    existing = db.query(StockPrice).filter(
                        StockPrice.stock_id == stock_id,
                        StockPrice.timestamp == price_data['timestamp']
                    ).first()

                    if not existing:
                        new_price = StockPrice(
                            stock_id=stock_id,
                            **price_data
                        )
                        db.add(new_price)
                        records_saved += 1

                if records_saved > 0:
                    db.commit()
                    result["steps"].append(f"Fetched {len(historical_data)} records, saved {records_saved} new")
                else:
                    result["steps"].append(f"Data already up to date ({len(historical_data)} records checked)")
            else:
                result["steps"].append("Using existing price data")
        except Exception as e:
            logger.warning(f"Failed to fetch new data: {e}")
            result["steps"].append("Using existing price data")

        # Step 2: Technical Analysis (50%)
        result["status"] = "technical_analysis"
        result["progress"] = 50
        result["steps"].append("Running technical analysis...")

        prices = db.query(StockPrice).filter(
            StockPrice.stock_id == stock_id
        ).order_by(StockPrice.timestamp.asc()).all()

        if len(prices) < 50:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient price data for analysis. Have {len(prices)}, need at least 50."
            )

        df = pd.DataFrame([{
            'timestamp': p.timestamp,
            'open': float(p.open) if p.open else None,
            'high': float(p.high) if p.high else None,
            'low': float(p.low) if p.low else None,
            'close': float(p.close) if p.close else None,
            'volume': int(p.volume) if p.volume else 0
        } for p in prices])
        df.set_index('timestamp', inplace=True)

        df = TechnicalIndicators.calculate_all_indicators(df)
        tech_recommendation = TechnicalIndicators.generate_recommendation(df)

        # Step 3: ML Prediction (75%)
        result["status"] = "ml_prediction"
        result["progress"] = 75
        result["steps"].append("Running ML predictions...")

        latest_prediction = db.query(Prediction).filter(
            Prediction.stock_id == stock_id
        ).order_by(Prediction.created_at.desc()).first()

        ml_rec = None
        ml_conf = None
        if latest_prediction:
            ml_rec = latest_prediction.recommendation
            ml_conf = float(latest_prediction.confidence_score) if latest_prediction.confidence_score else None

        # Step 4: Sentiment Analysis (90%)
        result["status"] = "sentiment_analysis"
        result["progress"] = 90
        result["steps"].append("Analyzing market sentiment...")

        latest_sentiment = db.query(SentimentScore).filter(
            SentimentScore.stock_id == stock_id
        ).order_by(SentimentScore.timestamp.desc()).first()

        sentiment_index = None
        if latest_sentiment:
            sentiment_index = float(latest_sentiment.sentiment_index)

        # Step 5: Final Recommendation (100%)
        result["status"] = "completed"
        result["progress"] = 100
        result["steps"].append("Generating final recommendation...")

        # Get comprehensive recommendation
        recommendation_data = {
            "stock_id": stock_id,
            "symbol": stock.symbol,
            "current_price": float(df['close'].iloc[-1]),
            "timestamp": df.index[-1],
            "technical_recommendation": tech_recommendation['recommendation'],
            "technical_confidence": tech_recommendation['confidence'],
            "ml_recommendation": ml_rec,
            "ml_confidence": ml_conf,
            "sentiment_index": sentiment_index,
        }

        # Calculate final recommendation
        recommendations = []
        weights = []

        recommendations.append((tech_recommendation['recommendation'], tech_recommendation['confidence']))
        weights.append(0.4)

        if ml_rec and ml_conf and ml_conf > 0.6:
            recommendations.append((ml_rec, ml_conf))
            weights.append(0.4)
        else:
            weights[0] += 0.4

        if sentiment_index is not None:
            if sentiment_index > 30:
                sentiment_rec = "BUY"
                sentiment_conf = min(abs(sentiment_index) / 100, 0.9)
            elif sentiment_index < -30:
                sentiment_rec = "SELL"
                sentiment_conf = min(abs(sentiment_index) / 100, 0.9)
            else:
                sentiment_rec = "HOLD"
                sentiment_conf = 0.5
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

        recommendation_data["final_recommendation"] = final_rec
        recommendation_data["overall_confidence"] = final_conf

        result["recommendation"] = recommendation_data
        result["steps"].append("Analysis complete!")

        return result

    except Exception as e:
        logger.error(f"Error in comprehensive analysis: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result


@router.post("/stocks/{stock_id}/analyze", response_model=TechnicalAnalysisResponse)
def analyze_stock(
    stock_id: int,
    request: AnalysisRequest = AnalysisRequest(),
    db: Session = Depends(get_db)
):
    """
    Perform technical analysis on a stock

    Returns technical indicators (RSI, MACD, Bollinger Bands, Moving Averages)
    and an overall recommendation (BUY/SELL/HOLD).
    """
    logger.info(f"Analyzing stock {stock_id}")

    # Get stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Get price data
    prices = db.query(StockPrice).filter(
        StockPrice.stock_id == stock_id
    ).order_by(StockPrice.timestamp.asc()).all()

    if not prices or len(prices) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient price data. Need at least 50 data points, have {len(prices)}"
        )

    # Convert to DataFrame
    df = pd.DataFrame([{
        'timestamp': p.timestamp,
        'open': float(p.open) if p.open else None,
        'high': float(p.high) if p.high else None,
        'low': float(p.low) if p.low else None,
        'close': float(p.close) if p.close else None,
        'volume': int(p.volume) if p.volume else 0
    } for p in prices])

    df.set_index('timestamp', inplace=True)

    # Calculate indicators
    df = TechnicalIndicators.calculate_all_indicators(
        df,
        rsi_period=request.rsi_period,
        macd_fast=request.macd_fast,
        macd_slow=request.macd_slow,
        macd_signal=request.macd_signal,
        bb_window=request.bb_window,
        bb_std=request.bb_std,
        ma_short=request.ma_short,
        ma_long=request.ma_long
    )

    # Generate recommendation
    recommendation = TechnicalIndicators.generate_recommendation(df)

    # Get latest values
    latest = df.iloc[-1]
    latest_timestamp = df.index[-1]

    return TechnicalAnalysisResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        timestamp=latest_timestamp,
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

    Combines technical analysis with recent predictions to provide
    a final recommendation.
    """
    logger.info(f"Getting recommendation for stock {stock_id}")

    # Get stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Get price data
    prices = db.query(StockPrice).filter(
        StockPrice.stock_id == stock_id
    ).order_by(StockPrice.timestamp.asc()).all()

    if not prices or len(prices) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient price data for analysis"
        )

    # Convert to DataFrame
    df = pd.DataFrame([{
        'timestamp': p.timestamp,
        'open': float(p.open) if p.open else None,
        'high': float(p.high) if p.high else None,
        'low': float(p.low) if p.low else None,
        'close': float(p.close) if p.close else None,
        'volume': int(p.volume) if p.volume else 0
    } for p in prices])

    df.set_index('timestamp', inplace=True)

    # Calculate technical indicators
    df = TechnicalIndicators.calculate_all_indicators(df)
    tech_recommendation = TechnicalIndicators.generate_recommendation(df)

    # Get latest prediction (if any)
    latest_prediction = db.query(Prediction).filter(
        Prediction.stock_id == stock_id
    ).order_by(Prediction.created_at.desc()).first()

    # Get latest sentiment (if any)
    latest_sentiment = db.query(SentimentScore).filter(
        SentimentScore.stock_id == stock_id
    ).order_by(SentimentScore.timestamp.desc()).first()

    # Prepare response
    latest = df.iloc[-1]
    current_price = float(latest['close'])

    # Extract technical signals
    technical_signals = {}
    for indicator, details in tech_recommendation['indicators'].items():
        technical_signals[indicator] = details.get('signal', 'HOLD')

    # Determine final recommendation
    reasoning = []

    # Technical analysis reasoning
    tech_rec = tech_recommendation['recommendation']
    tech_conf = tech_recommendation['confidence']
    reasoning.append(f"Technical analysis ({tech_conf:.0%} confidence): {tech_recommendation['reason']}")

    # ML prediction reasoning (if available)
    ml_rec = None
    ml_conf = None
    predicted_price = None

    if latest_prediction:
        ml_rec = latest_prediction.recommendation
        ml_conf = float(latest_prediction.confidence_score) if latest_prediction.confidence_score else None
        predicted_price = float(latest_prediction.predicted_price) if latest_prediction.predicted_price else None

        if ml_conf:
            reasoning.append(f"ML prediction ({ml_conf:.0%} confidence): {ml_rec}")

    # Sentiment analysis reasoning (if available)
    sentiment_rec = None
    sentiment_conf = None
    sentiment_index = None

    if latest_sentiment:
        sentiment_index = float(latest_sentiment.sentiment_index)

        # Convert sentiment index to recommendation
        if sentiment_index > 30:
            sentiment_rec = "BUY"
            sentiment_conf = min(abs(sentiment_index) / 100, 0.9)
        elif sentiment_index < -30:
            sentiment_rec = "SELL"
            sentiment_conf = min(abs(sentiment_index) / 100, 0.9)
        else:
            sentiment_rec = "HOLD"
            sentiment_conf = 0.5

        reasoning.append(
            f"Market sentiment (index: {sentiment_index:.1f}, {sentiment_conf:.0%} confidence): {sentiment_rec} "
            f"({latest_sentiment.positive_count} positive, {latest_sentiment.negative_count} negative news)"
        )

    # Combine all recommendations (technical, ML, sentiment)
    recommendations = []
    weights = []

    # Always include technical analysis
    recommendations.append((tech_rec, tech_conf))
    weights.append(0.4)  # Base weight for technical

    # Add ML if available and confident
    if ml_rec and ml_conf and ml_conf > 0.6:
        recommendations.append((ml_rec, ml_conf))
        weights.append(0.4)  # Weight for ML
    else:
        weights[0] += 0.4  # Give extra weight to technical if no ML

    # Add sentiment if available
    if sentiment_rec and sentiment_conf:
        recommendations.append((sentiment_rec, sentiment_conf))
        weights.append(0.2)  # Weight for sentiment
    else:
        # Distribute sentiment weight to existing recommendations
        extra_weight = 0.2 / len(weights)
        weights = [w + extra_weight for w in weights]

    # Calculate weighted recommendation
    rec_scores = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
    for (rec, conf), weight in zip(recommendations, weights):
        rec_scores[rec] += conf * weight

    # Final recommendation is the highest scored
    final_rec = max(rec_scores, key=rec_scores.get)
    final_conf = rec_scores[final_rec]

    # Check for agreement
    if len(recommendations) >= 2:
        recs = [r[0] for r in recommendations]
        if len(set(recs)) == 1:
            reasoning.append("✓ All indicators agree")
            final_conf = min(final_conf * 1.1, 1.0)  # Boost confidence if all agree
        else:
            reasoning.append("⚠ Mixed signals - use caution")

    # Determine risk level
    if final_conf >= 0.75:
        risk_level = "LOW"
    elif final_conf >= 0.50:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    return RecommendationResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        current_price=current_price,
        timestamp=df.index[-1],
        technical_recommendation=tech_rec,
        technical_confidence=tech_conf,
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

    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Get predictions
    predictions = db.query(Prediction).filter(
        Prediction.stock_id == stock_id
    ).order_by(Prediction.created_at.desc()).limit(limit).all()

    return predictions


@router.post("/stocks/{stock_id}/predict", response_model=MLPredictionResponse)
def create_ml_prediction(
    stock_id: int,
    request: MLPredictionRequest = MLPredictionRequest(),
    db: Session = Depends(get_db)
):
    """
    Create a new ML-based prediction

    This is a placeholder for future ML model integration.
    Currently uses technical indicators to make predictions.
    """
    logger.info(f"Creating ML prediction for stock {stock_id}")

    # Get stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Get price data
    prices = db.query(StockPrice).filter(
        StockPrice.stock_id == stock_id
    ).order_by(StockPrice.timestamp.asc()).all()

    if not prices or len(prices) < 50:
        raise HTTPException(
            status_code=400,
            detail="Insufficient price data for prediction"
        )

    # Convert to DataFrame
    df = pd.DataFrame([{
        'timestamp': p.timestamp,
        'close': float(p.close) if p.close else None,
        'open': float(p.open) if p.open else None,
        'high': float(p.high) if p.high else None,
        'low': float(p.low) if p.low else None,
        'volume': int(p.volume) if p.volume else 0
    } for p in prices])

    df.set_index('timestamp', inplace=True)

    # Calculate indicators
    df = TechnicalIndicators.calculate_all_indicators(df)
    recommendation = TechnicalIndicators.generate_recommendation(df)

    # Simple prediction based on trend
    current_price = float(df['close'].iloc[-1])

    # Use moving average slope for prediction
    ma_slope = df['ma_short_slope'].iloc[-5:].mean()  # Average slope over last 5 days
    predicted_change = ma_slope * request.forecast_days
    predicted_price = current_price + predicted_change

    # Calculate confidence based on indicator agreement
    confidence = recommendation['confidence']

    # Save prediction to database
    new_prediction = Prediction(
        stock_id=stock_id,
        prediction_date=datetime.now(),
        target_date=datetime.now() + timedelta(days=request.forecast_days),
        predicted_price=predicted_price,
        predicted_change_percent=(predicted_change / current_price) * 100,
        confidence_score=confidence,
        model_version=f"technical_v1_{request.model_type}",
        recommendation=recommendation['recommendation']
    )

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
