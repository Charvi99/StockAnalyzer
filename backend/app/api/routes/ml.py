"""
ML routes for model training and advanced predictions
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
import pandas as pd

from app.db.database import get_db
from app.models.stock import Stock, StockPrice, Prediction
from app.schemas.ml_sentiment import (
    MLTrainingRequest, MLTrainingResponse,
    MLPredictionRequest, MLPredictionResponse
)
from app.services.ml_predictor import MLPredictorService

router = APIRouter(prefix="/api/v1/ml", tags=["Machine Learning"])

# Global ML service instance
ml_service = MLPredictorService(model_dir="/app/models")


@router.post("/stocks/{stock_id}/train", response_model=MLTrainingResponse)
async def train_model(
    stock_id: int,
    request: MLTrainingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Train a machine learning model on stock data

    - **stock_id**: ID of the stock to train on
    - **model_type**: LSTM, Transformer, CNN, or CNNLSTM
    - **seq_length**: Sequence length for time series (default: 30)
    - **epochs**: Number of training epochs (default: 50)
    - **batch_size**: Batch size for training (default: 32)
    - **learning_rate**: Learning rate (default: 0.001)
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Fetch historical prices
    prices = db.query(StockPrice).filter(
        StockPrice.stock_id == stock_id
    ).order_by(StockPrice.timestamp).all()

    if len(prices) < 100:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient data for training. Need at least 100 records, have {len(prices)}"
        )

    # Convert to DataFrame
    df = pd.DataFrame([
        {
            'Open': float(p.open),
            'High': float(p.high),
            'Low': float(p.low),
            'Close': float(p.close),
            'Volume': int(p.volume)
        }
        for p in prices
    ])

    try:
        # Train the model
        result = ml_service.train_model(
            df=df,
            model_type=request.model_type,
            seq_length=request.seq_length,
            epochs=request.epochs,
            batch_size=request.batch_size,
            learning_rate=request.learning_rate
        )

        return MLTrainingResponse(
            model_type=result['model_type'],
            best_val_loss=result['best_val_loss'],
            final_val_accuracy=result['final_val_accuracy'],
            epochs=result['epochs'],
            message=f"Model {request.model_type} trained successfully for {stock.symbol}"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.post("/stocks/{stock_id}/predict", response_model=MLPredictionResponse)
async def predict_with_ml(
    stock_id: int,
    request: MLPredictionRequest,
    db: Session = Depends(get_db)
):
    """
    Make predictions using a trained ML model

    - **stock_id**: ID of the stock to predict
    - **model_type**: Model to use (LSTM, Transformer, CNN, CNNLSTM)
    - **seq_length**: Sequence length (default: 30)
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Fetch historical prices
    prices = db.query(StockPrice).filter(
        StockPrice.stock_id == stock_id
    ).order_by(StockPrice.timestamp).all()

    if len(prices) < request.seq_length:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient data for prediction. Need at least {request.seq_length} records"
        )

    # Convert to DataFrame
    df = pd.DataFrame([
        {
            'Open': float(p.open),
            'High': float(p.high),
            'Low': float(p.low),
            'Close': float(p.close),
            'Volume': int(p.volume)
        }
        for p in prices
    ])

    try:
        # Make prediction
        result = ml_service.predict(
            df=df,
            model_type=request.model_type,
            seq_length=request.seq_length
        )

        # Get current price
        latest_price = prices[-1]
        current_price = float(latest_price.close)

        # Save prediction to database
        prediction = Prediction(
            stock_id=stock_id,
            prediction_date=datetime.utcnow(),
            target_date=datetime.utcnow(),
            predicted_price=current_price,
            predicted_change_percent=0.0,
            confidence_score=result['confidence'],
            model_version=f"ML_{request.model_type}",
            recommendation=result['signal']
        )
        db.add(prediction)
        db.commit()

        return MLPredictionResponse(
            signal=result['signal'],
            confidence=result['confidence'],
            probabilities=result['probabilities'],
            model_type=result['model_type'],
            current_price=current_price,
            timestamp=datetime.utcnow()
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/models")
async def list_available_models():
    """
    List all available trained models
    """
    import os

    model_dir = "/app/models"
    if not os.path.exists(model_dir):
        return {"models": [], "message": "No models have been trained yet"}

    model_files = [f for f in os.listdir(model_dir) if f.endswith('_best.pth')]
    models = [f.replace('_best.pth', '') for f in model_files]

    return {
        "models": models,
        "count": len(models),
        "model_dir": model_dir
    }


@router.delete("/models/{model_type}")
async def delete_model(model_type: str):
    """
    Delete a trained model

    - **model_type**: Type of model to delete (LSTM, Transformer, CNN, CNNLSTM)
    """
    import os

    model_dir = "/app/models"
    model_path = os.path.join(model_dir, f"{model_type}_best.pth")
    scaler_path = os.path.join(model_dir, f"{model_type}_scaler.pkl")

    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail=f"Model {model_type} not found")

    try:
        os.remove(model_path)
        if os.path.exists(scaler_path):
            os.remove(scaler_path)

        # Remove from memory if loaded
        if model_type in ml_service.models:
            del ml_service.models[model_type]
        if model_type in ml_service.scalers:
            del ml_service.scalers[model_type]

        return {
            "message": f"Model {model_type} deleted successfully",
            "model_type": model_type
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {str(e)}")
