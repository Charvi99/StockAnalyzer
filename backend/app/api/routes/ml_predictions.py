"""
API routes for ML pattern predictions
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.database import get_db
from app.models.stock import ChartPattern
from app.schemas.ml_predictions import MLPredictionResponse, MLModelInfo
from app.services.ml_predictor import get_ml_predictor

router = APIRouter()


@router.get("/ml/models/info", response_model=MLModelInfo)
def get_ml_models_info():
    """
    Get information about loaded ML models
    
    Returns model status, availability, and details
    """
    predictor = get_ml_predictor()
    return predictor.get_model_info()


@router.post("/chart-patterns/{pattern_id}/ml-predict", response_model=MLPredictionResponse)
def predict_pattern_validity(
    pattern_id: int,
    db: Session = Depends(get_db)
):
    """
    Use ML models to predict if a chart pattern is valid
    
    Uses both LSTM and GRU models (if available) and provides:
    - Individual predictions from each model
    - Ensemble prediction (average)
    - Confidence scores
    
    Args:
        pattern_id: Chart pattern ID to validate
    """
    predictor = get_ml_predictor()
    
    if not predictor.is_available():
        return MLPredictionResponse(
            available=False,
            predictions={},
            message="ML models not available. Train models first using ml_training/train_pattern_models.py"
        )
    
    # Get pattern from database
    pattern = db.query(ChartPattern).filter(ChartPattern.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    
    # Get OHLC data for the pattern
    from app.models.stock import StockPrice
    
    all_prices = db.query(StockPrice).filter(
        StockPrice.stock_id == pattern.stock_id
    ).order_by(StockPrice.timestamp).all()
    
    if not all_prices:
        raise HTTPException(status_code=400, detail="No price data available for this pattern")
    
    # Find pattern indices
    pattern_start_idx = None
    pattern_end_idx = None
    
    for i, price in enumerate(all_prices):
        if price.timestamp >= pattern.start_date and pattern_start_idx is None:
            pattern_start_idx = i
        if price.timestamp >= pattern.end_date:
            pattern_end_idx = i
            break
    
    if pattern_start_idx is None or pattern_end_idx is None:
        raise HTTPException(status_code=400, detail="Pattern dates not found in price data")
    
    # Get pattern window with padding (5 candles before/after)
    padding = 5
    window_start_idx = max(0, pattern_start_idx - padding)
    window_end_idx = min(len(all_prices) - 1, pattern_end_idx + padding)
    
    window_prices = all_prices[window_start_idx:window_end_idx + 1]
    
    # Prepare pattern data
    ohlc_data = []
    all_prices_list = []
    all_volumes = []
    
    for price in window_prices:
        candle = {
            'open': float(price.open),
            'high': float(price.high),
            'low': float(price.low),
            'close': float(price.close),
            'volume': int(price.volume) if price.volume else 0
        }
        ohlc_data.append(candle)
        all_prices_list.extend([candle['high'], candle['low']])
        all_volumes.append(candle['volume'])
    
    pattern_data = {
        'ohlc_data': ohlc_data,
        'price_min': min(all_prices_list) if all_prices_list else 0.0,
        'price_max': max(all_prices_list) if all_prices_list else 0.0,
        'volume_max': max(all_volumes) if all_volumes else 0
    }
    
    # Get predictions
    results = predictor.predict_all(pattern_data)
    
    return MLPredictionResponse(**results)


@router.get("/ml/models/available")
def check_ml_availability():
    """
    Quick check if ML models are available
    
    Returns:
        Dict with availability status
    """
    predictor = get_ml_predictor()
    return {
        "available": predictor.is_available(),
        "models": list(predictor.models.keys()) if predictor.is_available() else []
    }
