"""
Use trained models to predict if a pattern is valid

Usage:
    python predict.py --model lstm --pattern-id 123
    python predict.py --model gru --json pattern_data.json
"""

import argparse
import json
import numpy as np
import tensorflow as tf
from pathlib import Path


class PatternPredictor:
    """Load model and predict pattern validity"""

    def __init__(self, model_path):
        self.model_path = Path(model_path)
        self.model = None
        self.load_model()

    def load_model(self):
        """Load trained model"""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        print(f"Loading model from: {self.model_path}")
        self.model = tf.keras.models.load_model(self.model_path)
        print(f"✓ Model loaded successfully")
        print(f"  Input shape: {self.model.input_shape}")

    def preprocess_pattern(self, pattern_data):
        """
        Preprocess pattern data for prediction

        Args:
            pattern_data: Dict with 'ohlc_data', 'price_min', 'price_max', 'volume_max'

        Returns:
            Preprocessed numpy array (1, timesteps, 5)
        """
        ohlc_sequence = []

        for candle in pattern_data['ohlc_data']:
            ohlc_sequence.append([
                candle['open'],
                candle['high'],
                candle['low'],
                candle['close'],
                candle['volume']
            ])

        ohlc_array = np.array(ohlc_sequence, dtype=np.float32)

        # Normalize using pattern's metadata
        price_range = pattern_data['price_max'] - pattern_data['price_min']
        if price_range > 0:
            ohlc_array[:, :4] = (ohlc_array[:, :4] - pattern_data['price_min']) / price_range

        if pattern_data['volume_max'] > 0:
            ohlc_array[:, 4] = ohlc_array[:, 4] / pattern_data['volume_max']

        # Add batch dimension
        return ohlc_array.reshape(1, *ohlc_array.shape)

    def predict(self, pattern_data):
        """
        Predict if pattern is valid

        Returns:
            Dict with prediction score and classification
        """
        # Preprocess
        X = self.preprocess_pattern(pattern_data)

        # Predict
        prediction = self.model.predict(X, verbose=0)
        score = float(prediction[0][0])
        is_valid = score > 0.5

        return {
            'score': score,
            'is_valid': is_valid,
            'confidence': score if is_valid else (1 - score),
            'label': 'True Pattern' if is_valid else 'False Pattern'
        }


def fetch_pattern_from_api(pattern_id, padding_candles=5):
    """Fetch single pattern from API for prediction"""
    import requests

    url = f"http://localhost:8000/api/v1/chart-patterns/export/training-data"
    params = {
        'padding_candles': padding_candles,
        'confirmed_only': False  # Get all patterns
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    patterns = response.json()

    # Find pattern by ID
    for pattern in patterns:
        if pattern['pattern_id'] == pattern_id:
            return pattern

    raise ValueError(f"Pattern {pattern_id} not found")


def main():
    parser = argparse.ArgumentParser(description='Predict pattern validity using trained model')
    parser.add_argument('--model', choices=['lstm', 'gru'], default='lstm',
                       help='Model to use for prediction')
    parser.add_argument('--pattern-id', type=int,
                       help='Pattern ID to fetch from API')
    parser.add_argument('--json', type=str,
                       help='JSON file with pattern data')
    parser.add_argument('--padding', type=int, default=5,
                       help='Padding candles (for API fetch)')

    args = parser.parse_args()

    # Load model
    model_path = Path('outputs') / 'models' / f'{args.model}.keras'
    predictor = PatternPredictor(model_path)

    # Get pattern data
    if args.pattern_id is not None:
        print(f"\nFetching pattern {args.pattern_id} from API...")
        pattern_data = fetch_pattern_from_api(args.pattern_id, args.padding)
    elif args.json:
        print(f"\nLoading pattern from {args.json}...")
        with open(args.json, 'r') as f:
            pattern_data = json.load(f)
    else:
        parser.error("Must provide --pattern-id or --json")

    # Display pattern info
    print(f"\nPattern Information:")
    print(f"  Pattern ID:   {pattern_data.get('pattern_id', 'N/A')}")
    print(f"  Stock:        {pattern_data.get('stock_symbol', 'N/A')}")
    print(f"  Pattern Name: {pattern_data.get('pattern_name', 'N/A')}")
    print(f"  Signal:       {pattern_data.get('signal', 'N/A')}")
    print(f"  Candles:      {pattern_data.get('total_candles', len(pattern_data.get('ohlc_data', [])))}")

    if 'user_confirmed' in pattern_data and pattern_data['user_confirmed'] is not None:
        actual_label = 'True Pattern' if pattern_data['user_confirmed'] else 'False Pattern'
        print(f"  Actual Label: {actual_label}")

    # Predict
    print(f"\nPredicting with {args.model.upper()} model...")
    result = predictor.predict(pattern_data)

    # Display results
    print(f"\n{'='*50}")
    print(f"PREDICTION RESULTS")
    print(f"{'='*50}")
    print(f"  Score:      {result['score']:.4f}")
    print(f"  Prediction: {result['label']}")
    print(f"  Confidence: {result['confidence']:.1%}")
    print(f"{'='*50}")

    # Check if correct
    if 'user_confirmed' in pattern_data and pattern_data['user_confirmed'] is not None:
        actual = pattern_data['user_confirmed']
        predicted = result['is_valid']
        correct = (actual == predicted)

        print(f"\n✓ Correct!" if correct else "\n✗ Incorrect")

    return result


if __name__ == '__main__':
    main()
