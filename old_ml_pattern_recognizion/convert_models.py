"""
Convert trained models to TensorFlow 2.15 compatible format
Run this script locally (not in Docker) to re-save models in H5 format
"""
import tensorflow as tf
from pathlib import Path

def convert_model(keras_path, h5_path):
    """Convert .keras model to .h5 format"""
    print(f"Loading {keras_path}...")
    try:
        # Load the model
        model = tf.keras.models.load_model(keras_path)
        print(f"Model loaded successfully!")
        print(f"Saving to {h5_path}...")

        # Save in H5 format (more compatible)
        model.save(h5_path, save_format='h5')
        print(f"[OK] Converted {keras_path.name} -> {h5_path.name}")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to convert {keras_path.name}: {e}")
        return False

def main():
    models_dir = Path("outputs/models")

    if not models_dir.exists():
        print(f"Error: {models_dir} does not exist!")
        return

    # Convert LSTM model
    lstm_keras = models_dir / "lstm.keras"
    lstm_h5 = models_dir / "lstm.h5"
    if lstm_keras.exists():
        convert_model(lstm_keras, lstm_h5)
    else:
        print(f"Warning: {lstm_keras} not found")

    # Convert GRU model
    gru_keras = models_dir / "gru.keras"
    gru_h5 = models_dir / "gru.h5"
    if gru_keras.exists():
        convert_model(gru_keras, gru_h5)
    else:
        print(f"Warning: {gru_keras} not found")

    print("\nConversion complete!")
    print("Now update ml_predictor.py to load .h5 files instead of .keras files")

if __name__ == "__main__":
    main()
