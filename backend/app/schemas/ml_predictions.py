"""
Pydantic schemas for ML predictions
"""
from pydantic import BaseModel
from typing import Optional, Dict

class MLPredictionSingle(BaseModel):
    """Single model prediction result"""
    model: str
    score: float
    is_valid: bool
    confidence: float
    label: str

class MLPredictionEnsemble(BaseModel):
    """Ensemble prediction (average of all models)"""
    score: float
    is_valid: bool
    confidence: float
    label: str
    models_used: int

class MLPredictionResponse(BaseModel):
    """Response schema for ML predictions"""
    available: bool
    predictions: Dict[str, MLPredictionSingle]
    ensemble: Optional[MLPredictionEnsemble] = None
    message: Optional[str] = None

class MLModelInfo(BaseModel):
    """Information about loaded ML models"""
    tensorflow_available: bool
    models_loaded: list
    model_details: Dict
