# Chart Pattern Recognition - ML Training

Proof-of-concept training pipeline for LSTM and GRU models to recognize chart patterns.

## Quick Start

### 1. Export Training Data

```bash
curl "http://localhost:8000/api/v1/chart-patterns/export/training-data?padding_candles=5" > training_data.json
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Train Models

```bash
python train_pattern_models.py
```

## What It Does

1. **Loads data** from `training_data.json` (exported from API)
2. **Preprocesses** OHLC sequences with normalization
3. **Trains** two models:
   - **Tiny LSTM** (~15K parameters)
   - **Tiny GRU** (~10K parameters)
4. **Evaluates** both models on test set
5. **Creates visualizations**:
   - Training history (loss, accuracy, precision, recall)
   - Confusion matrices
   - ROC curves
   - Precision-Recall curves
   - Model comparison bar chart
6. **Saves**:
   - Trained models (`.keras` format)
   - Plots (PNG)
   - Results summary (TXT)

## Output Structure

```
outputs/
├── models/
│   ├── lstm.keras          # Trained LSTM model
│   └── gru.keras           # Trained GRU model
├── plots/
│   ├── training_history.png
│   ├── confusion_matrices.png
│   ├── roc_curves.png
│   ├── precision_recall_curves.png
│   └── model_comparison.png
└── results_summary_YYYYMMDD_HHMMSS.txt
```

## Expected Performance

With ~319 confirmed samples:
- **Accuracy**: 65-75%
- **F1-Score**: 0.65-0.75
- **Training time**: 5-10 minutes (CPU)

## Model Architectures

### Tiny LSTM (~15K params)
```
Input (timesteps, 5) → Bidirectional LSTM(32) → Dropout(0.4)
→ Dense(16, relu) → Dropout(0.3) → Dense(1, sigmoid)
```

### Tiny GRU (~10K params)
```
Input (timesteps, 5) → Bidirectional GRU(24) → Dropout(0.4)
→ Dense(12, relu) → Dropout(0.3) → Dense(1, sigmoid)
```

## Training Configuration

- **Train/Val/Test Split**: 70% / 15% / 15%
- **Batch Size**: 16
- **Max Epochs**: 100
- **Early Stopping**: patience=20 (monitors val_loss)
- **Learning Rate**: 0.001 with ReduceLROnPlateau
- **Optimizer**: Adam
- **Loss**: Binary Crossentropy

## Using Trained Models

```python
import tensorflow as tf
import numpy as np

# Load model
model = tf.keras.models.load_model('outputs/models/lstm.keras')

# Prepare input (normalized OHLC sequence)
# Shape: (1, timesteps, 5)
ohlc_sequence = np.array([...])  # Your normalized data

# Predict
prediction = model.predict(ohlc_sequence)
is_valid_pattern = prediction[0][0] > 0.5

print(f"Pattern validity: {prediction[0][0]:.3f}")
print(f"Valid: {is_valid_pattern}")
```

## Tips for Better Results

### 1. Collect More Data
- Target: 1000+ confirmed patterns
- Add more stocks (MSFT, GOOGL, TSLA, etc.)
- Use different timeframes

### 2. Balance Dataset
- Aim for 50/50 true/false positives
- Use data augmentation if needed

### 3. Feature Engineering
- Add technical indicators (RSI, MACD, etc.)
- Include volume profile
- Add relative strength

### 4. Hyperparameter Tuning
- Try different LSTM/GRU units (16, 32, 64)
- Adjust dropout rates
- Experiment with learning rates

## Troubleshooting

### Out of Memory
- Reduce batch_size to 8
- Use smaller models

### Overfitting
- Increase dropout rates (0.5, 0.6)
- Reduce model size
- Collect more data

### Low Accuracy
- Check data quality (confirm more patterns)
- Balance dataset
- Try feature engineering
- Collect more samples

## Next Steps

1. ✅ **Train initial models** (you are here)
2. 📊 **Collect 1000+ patterns**
3. 🔧 **Add feature engineering**
4. 🎯 **Multi-class classification** (recognize specific patterns)
5. 🚀 **Deploy model** in production API
