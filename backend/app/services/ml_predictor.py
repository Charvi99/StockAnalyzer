"""
ML Pattern Prediction Service
Loads trained LSTM and GRU models for real-time pattern validation
"""
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import logging

# TensorFlow imports
try:
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logging.warning("TensorFlow not available. ML predictions will be disabled.")


class MLPatternPredictor:
    """
    Service for loading and using trained ML models to predict pattern validity
    """

    def __init__(self, models_dir: str = "ml_training/outputs/models"):
        self.models_dir = Path(models_dir)
        self.models = {}
        self.model_info = {}

        if TENSORFLOW_AVAILABLE:
            self._load_models()
        else:
            logging.warning("Skipping model loading - TensorFlow not available")

    def _load_models(self):
        """Load all available trained models"""
        logging.info(f"Loading ML models from {self.models_dir}")

        # Custom object scope for backward compatibility
        custom_objects = {
            'Masking': tf.keras.layers.Masking
        }

        # Try to load LSTM model (H5 format for compatibility)
        lstm_path = self.models_dir / "lstm.h5"
        if lstm_path.exists():
            try:
                # Load without compiling to avoid compatibility issues
                model = tf.keras.models.load_model(str(lstm_path), compile=False)

                # Manually compile with the same settings as training
                model.compile(
                    optimizer=tf.keras.optimizers.Adam(learning_rate=0.00025),
                    loss='binary_crossentropy',
                    metrics=['accuracy']
                )

                self.models['LSTM'] = model
                self.model_info['LSTM'] = {
                    'path': str(lstm_path),
                    'size_kb': lstm_path.stat().st_size / 1024,
                    'loaded': True
                }
                logging.info(f"Loaded LSTM model from {lstm_path}")
            except Exception as e:
                logging.error(f"Failed to load LSTM model: {e}")
                self.model_info['LSTM'] = {'loaded': False, 'error': str(e)}

        # Try to load GRU model (H5 format for compatibility)
        gru_path = self.models_dir / "gru.h5"
        if gru_path.exists():
            try:
                # Load without compiling to avoid compatibility issues
                model = tf.keras.models.load_model(str(gru_path), compile=False)

                # Manually compile with the same settings as training
                model.compile(
                    optimizer=tf.keras.optimizers.Adam(learning_rate=0.00025),
                    loss='binary_crossentropy',
                    metrics=['accuracy']
                )

                self.models['GRU'] = model
                self.model_info['GRU'] = {
                    'path': str(gru_path),
                    'size_kb': gru_path.stat().st_size / 1024,
                    'loaded': True
                }
                logging.info(f"Loaded GRU model from {gru_path}")
            except Exception as e:
                logging.error(f"Failed to load GRU model: {e}")
                self.model_info['GRU'] = {'loaded': False, 'error': str(e)}

        if not self.models:
            logging.warning("No ML models loaded. Train models first using ml_training/train_pattern_models.py")

    def is_available(self) -> bool:
        """Check if ML prediction is available"""
        return TENSORFLOW_AVAILABLE and len(self.models) > 0

    def get_model_info(self) -> Dict:
        """Get information about loaded models"""
        return {
            'tensorflow_available': TENSORFLOW_AVAILABLE,
            'models_loaded': list(self.models.keys()),
            'model_details': self.model_info
        }

    def preprocess_pattern(self, ohlc_data: List[Dict], price_min: float,
                          price_max: float, volume_max: int,
                          max_length: int = 58) -> np.ndarray:
        """
        Preprocess pattern data for prediction
        """
        # Extract OHLC sequence
        ohlc_sequence = []
        for candle in ohlc_data:
            ohlc_sequence.append([
                float(candle['open']),
                float(candle['high']),
                float(candle['low']),
                float(candle['close']),
                int(candle['volume']) if candle['volume'] else 0
            ])

        ohlc_array = np.array(ohlc_sequence, dtype=np.float32)

        # Normalize
        price_range = price_max - price_min
        if price_range > 0:
            ohlc_array[:, :4] = (ohlc_array[:, :4] - price_min) / price_range

        if volume_max > 0:
            ohlc_array[:, 4] = ohlc_array[:, 4] / volume_max

        # Pad to max_length
        if len(ohlc_array) < max_length:
            padding = np.zeros((max_length - len(ohlc_array), 5), dtype=np.float32)
            ohlc_array = np.vstack([ohlc_array, padding])
        elif len(ohlc_array) > max_length:
            ohlc_array = ohlc_array[:max_length]

        return ohlc_array.reshape(1, max_length, 5)

    def predict_single(self, model_name: str, pattern_data: Dict) -> Optional[Dict]:
        """Predict pattern validity using a specific model"""
        if not self.is_available() or model_name not in self.models:
            return None

        try:
            X = self.preprocess_pattern(
                pattern_data['ohlc_data'],
                pattern_data['price_min'],
                pattern_data['price_max'],
                pattern_data['volume_max']
            )

            model = self.models[model_name]
            prediction = model.predict(X, verbose=0)
            score = float(prediction[0][0])
            is_valid = score > 0.5

            return {
                'model': model_name,
                'score': score,
                'is_valid': is_valid,
                'confidence': score if is_valid else (1 - score),
                'label': 'Valid Pattern' if is_valid else 'Invalid Pattern'
            }
        except Exception as e:
            logging.error(f"Prediction failed for {model_name}: {e}")
            return None

    def predict_all(self, pattern_data: Dict) -> Dict:
        """Predict pattern validity using all available models"""
        if not self.is_available():
            return {'available': False, 'message': 'ML models not available'}

        results = {'available': True, 'predictions': {}, 'ensemble': None}

        scores = []
        for model_name in self.models.keys():
            pred = self.predict_single(model_name, pattern_data)
            if pred:
                results['predictions'][model_name] = pred
                scores.append(pred['score'])

        if scores:
            avg_score = np.mean(scores)
            results['ensemble'] = {
                'score': float(avg_score),
                'is_valid': avg_score > 0.5,
                'confidence': float(avg_score) if avg_score > 0.5 else float(1 - avg_score),
                'label': 'Valid Pattern' if avg_score > 0.5 else 'Invalid Pattern',
                'models_used': len(scores)
            }

        return results


# Global singleton
_predictor_instance = None

def get_ml_predictor() -> MLPatternPredictor:
    """Get or create global ML predictor instance"""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = MLPatternPredictor()
    return _predictor_instance
