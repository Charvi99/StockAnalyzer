# Chart Pattern Recognition - Complete Usage Guide

## Table of Contents
1. [Quick Start](#quick-start)
2. [Manual Step-by-Step](#manual-step-by-step)
3. [Understanding the Output](#understanding-the-output)
4. [Making Predictions](#making-predictions)
5. [Tips for Better Results](#tips-for-better-results)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Windows
```batch
quick_start.bat
```

### Linux/Mac
```bash
chmod +x quick_start.sh
./quick_start.sh
```

That's it! The script will:
1. Export training data from API
2. Install dependencies
3. Train both LSTM and GRU models
4. Generate visualizations
5. Save results

---

## Manual Step-by-Step

### Step 1: Export Training Data

```bash
# Export with 5 candles padding (default)
curl "http://localhost:8000/api/v1/chart-patterns/export/training-data?padding_candles=5" > training_data.json

# Or with more padding for more context
curl "http://localhost:8000/api/v1/chart-patterns/export/training-data?padding_candles=10" > training_data.json
```

**What you get:**
```json
[
  {
    "pattern_id": 11,
    "stock_symbol": "AAPL",
    "pattern_name": "Rounding Top",
    "signal": "bearish",
    "label": "false_positive",
    "ohlc_data": [...],  // Array of 52 candles
    "total_candles": 52,
    "pattern_start_index": 10,
    "pattern_end_index": 49,
    "padding_before": 5,
    "padding_after": 2,
    "price_min": 216.58,
    "price_max": 264.38,
    "volume_max": 163741314
  }
]
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

**Dependencies:**
- TensorFlow 2.13+
- NumPy, Pandas
- Scikit-learn
- Matplotlib, Seaborn

### Step 3: Train Models

```bash
python train_pattern_models.py
```

**Training process:**
1. Loads and analyzes dataset
2. Preprocesses OHLC data (normalization)
3. Splits into train/val/test (70/15/15)
4. Trains LSTM model (~5 min)
5. Trains GRU model (~5 min)
6. Evaluates both on test set
7. Creates visualizations
8. Saves models and results

**Console output:**
```
==============================================================
LOADING TRAINING DATA
==============================================================
✓ Loaded 319 samples from training_data.json

Dataset Statistics:
  Total samples:     319
  True positives:    178 (55.8%)
  False positives:   141 (44.2%)
  Pattern types:     13

==============================================================
TRAINING LSTM
==============================================================
Model: "TinyLSTM"
_________________________________________________________________
Layer (type)                Output Shape              Param #
=================================================================
bidirectional_lstm         (None, 64)                9728
dropout_lstm               (None, 64)                0
dense_hidden               (None, 16)                1040
dropout_dense              (None, 16)                0
output                     (None, 1)                 17
=================================================================
Total params: 10,785
Trainable params: 10,785

Epoch 50/100
14/14 - 1s - loss: 0.5234 - accuracy: 0.7354 - val_loss: 0.5891
...

✓ Training completed for LSTM
  Best epoch: 48
  Best val_loss: 0.5823

==============================================================
EVALUATING LSTM
==============================================================

Test Set Results:
  Loss:      0.5891
  Accuracy:  0.7292
  Precision: 0.7407
  Recall:    0.7407
  F1-Score:  0.7407
  AUC:       0.7954

Classification Report:
              precision    recall  f1-score   support

False Pattern    0.7222    0.7222    0.7222        21
 True Pattern    0.7407    0.7407    0.7407        27

    accuracy                         0.7292        48
   macro avg    0.7315    0.7315    0.7315        48
weighted avg    0.7330    0.7292    0.7311        48

🏆 Best Model: LSTM (F1-Score: 0.7407)
```

---

## Understanding the Output

### Folder Structure
```
ml_training/
├── training_data.json          # Exported from API
├── outputs/
│   ├── models/
│   │   ├── lstm.keras          # Trained LSTM (~200KB)
│   │   └── gru.keras           # Trained GRU (~180KB)
│   ├── plots/
│   │   ├── training_history.png
│   │   ├── confusion_matrices.png
│   │   ├── roc_curves.png
│   │   ├── precision_recall_curves.png
│   │   └── model_comparison.png
│   └── results_summary_20251021_152345.txt
```

### Visualization Interpretation

#### 1. Training History
Shows how models learned over time:
- **Loss curves**: Should decrease and converge
- **Accuracy**: Should increase
- **Val vs Train**: Gap indicates overfitting

**Good signs:**
- ✓ Val curves follow train curves closely
- ✓ Both converge to stable values
- ✓ No divergence after certain epoch

**Bad signs:**
- ✗ Val loss increases while train loss decreases (overfitting)
- ✗ Large gap between train and val accuracy
- ✗ Erratic validation curves (unstable)

#### 2. Confusion Matrix
```
          Predicted
          False  True
Actual ┌──────────────┐
False  │  15  │   6  │  TN=15, FP=6
       ├──────┼──────┤
True   │   7  │  20  │  FN=7,  TP=20
       └──────────────┘
```

**Interpretation:**
- **True Negative (TN)**: Correctly rejected false patterns
- **False Positive (FP)**: Incorrectly accepted false patterns
- **False Negative (FN)**: Incorrectly rejected true patterns
- **True Positive (TP)**: Correctly accepted true patterns

**For trading:**
- High FN = Miss good trades
- High FP = Take bad trades

#### 3. ROC Curve
- **X-axis**: False Positive Rate (bad)
- **Y-axis**: True Positive Rate (good)
- **AUC**: Area Under Curve (higher = better)

**Interpretation:**
- AUC = 0.50: Random guessing
- AUC = 0.70-0.80: Good (expected for 319 samples)
- AUC = 0.80-0.90: Excellent
- AUC > 0.90: Outstanding

#### 4. Precision-Recall
- **Precision**: Of predicted positives, how many are correct?
- **Recall**: Of actual positives, how many did we find?
- **F1-Score**: Harmonic mean of precision and recall

**For pattern recognition:**
- High precision = Few false alarms
- High recall = Catch most patterns
- F1 balances both

---

## Making Predictions

### Using Trained Model

```bash
# Predict using LSTM model
python predict.py --model lstm --pattern-id 128

# Predict using GRU model
python predict.py --model gru --pattern-id 128

# Predict from JSON file
python predict.py --model lstm --json my_pattern.json
```

**Example output:**
```
Loading model from: outputs/models/lstm.keras
✓ Model loaded successfully

Pattern Information:
  Pattern ID:   128
  Stock:        AAPL
  Pattern Name: Rounding Bottom
  Signal:       bullish
  Candles:      55
  Actual Label: True Pattern

Predicting with LSTM model...

==================================================
PREDICTION RESULTS
==================================================
  Score:      0.8234
  Prediction: True Pattern
  Confidence: 82.3%
==================================================

✓ Correct!
```

### In Python Script

```python
import tensorflow as tf
import numpy as np
from predict import PatternPredictor

# Load model
predictor = PatternPredictor('outputs/models/lstm.keras')

# Your pattern data
pattern_data = {
    'ohlc_data': [...],  # List of candles
    'price_min': 200.0,
    'price_max': 250.0,
    'volume_max': 100000000
}

# Predict
result = predictor.predict(pattern_data)

print(f"Valid pattern: {result['is_valid']}")
print(f"Confidence: {result['confidence']:.1%}")
```

---

## Tips for Better Results

### 1. Collect More Data (Most Important!)

**Current:** 319 samples → 65-75% accuracy

**Target progression:**
- 500 samples → 70-78% accuracy
- 1000 samples → 75-82% accuracy
- 2000+ samples → 80-85%+ accuracy

**How to collect:**
```bash
# Detect patterns on multiple stocks
stocks=("AAPL" "MSFT" "GOOGL" "TSLA" "AMZN")

for stock in "${stocks[@]}"; do
  # Create stock and fetch data
  curl -X POST "http://localhost:8000/api/v1/stocks" \
    -d "{\"symbol\": \"$stock\", \"name\": \"$stock Inc.\"}"

  # Fetch historical data
  curl -X POST "http://localhost:8000/api/v1/stocks/$id/fetch" \
    -d "{\"period\": \"2y\", \"interval\": \"1d\"}"

  # Detect patterns (exclude recent 90 days for training)
  curl -X POST "http://localhost:8000/api/v1/stocks/$id/detect-chart-patterns" \
    -d "{\"exclude_recent_days\": 90}"
done
```

### 2. Balance Your Dataset

**Check class balance:**
```python
true_pos = 178  # 55.8%
false_pos = 141  # 44.2%
# ✓ Good balance (40-60% range)
```

**If imbalanced (e.g., 80% true, 20% false):**
- Confirm more false positives
- Use class weights in training
- Apply SMOTE for minority class

### 3. Tune Hyperparameters

Edit `train_pattern_models.py`:

```python
# Try different LSTM sizes
layers.LSTM(16)   # Smaller (less overfitting)
layers.LSTM(32)   # Default
layers.LSTM(64)   # Larger (needs more data)

# Adjust dropout
layers.Dropout(0.3)  # Less regularization
layers.Dropout(0.5)  # More regularization

# Try different learning rates
optimizer=Adam(learning_rate=0.0001)  # Slower
optimizer=Adam(learning_rate=0.001)   # Default
optimizer=Adam(learning_rate=0.01)    # Faster
```

### 4. Add Features

Enhance OHLC with technical indicators:

```python
def add_features(df):
    # Add to preprocessing
    features = []
    for i in range(len(df)):
        features.append([
            df[i]['open'],
            df[i]['high'],
            df[i]['low'],
            df[i]['close'],
            df[i]['volume'],
            calculate_rsi(df, i),      # RSI
            calculate_macd(df, i),     # MACD
            calculate_bb(df, i)        # Bollinger Bands
        ])
    return np.array(features)
```

### 5. Use Cross-Validation

For more robust evaluation:

```python
from sklearn.model_selection import KFold

kfold = KFold(n_splits=5, shuffle=True, random_state=42)
scores = []

for train_idx, val_idx in kfold.split(X):
    X_train, X_val = X[train_idx], X[val_idx]
    y_train, y_val = y[train_idx], y[val_idx]

    model = create_tiny_lstm(...)
    model.fit(X_train, y_train, validation_data=(X_val, y_val))
    score = model.evaluate(X_val, y_val)[1]  # Accuracy
    scores.append(score)

print(f"Cross-val accuracy: {np.mean(scores):.3f} ± {np.std(scores):.3f}")
```

---

## Troubleshooting

### Low Accuracy (<60%)

**Possible causes:**
1. Not enough data → Collect more (target 1000+)
2. Imbalanced classes → Balance dataset
3. Poor quality labels → Review confirmations
4. Model too simple → Try CNN-LSTM hybrid

**Solutions:**
```python
# 1. Check data quality
print(f"Samples: {len(data)}")  # Should be 500+
print(f"Balance: {np.mean(y)}")  # Should be 0.4-0.6

# 2. Add class weights
class_weight = {0: 1.5, 1: 1.0}  # Give more weight to minority
model.fit(..., class_weight=class_weight)

# 3. Try larger model
layers.LSTM(64)  # Instead of 32
```

### Overfitting (Train >> Val)

**Symptoms:**
- Train accuracy: 90%
- Val accuracy: 60%

**Solutions:**
```python
# 1. Increase dropout
layers.Dropout(0.5)  # From 0.3

# 2. Reduce model size
layers.LSTM(16)  # From 32

# 3. Early stopping
EarlyStopping(patience=10)  # From 20

# 4. L2 regularization
layers.LSTM(32, kernel_regularizer=l2(0.01))
```

### Out of Memory

**Solutions:**
```python
# Reduce batch size
batch_size=8  # From 16

# Or use generator
def data_generator(X, y, batch_size):
    while True:
        for i in range(0, len(X), batch_size):
            yield X[i:i+batch_size], y[i:i+batch_size]
```

### Predictions Always Same Class

**Cause:** Model collapsed to majority class

**Solutions:**
```python
# 1. Check class balance
print(f"True: {sum(y)}, False: {len(y) - sum(y)}")

# 2. Use class weights
from sklearn.utils.class_weight import compute_class_weight

weights = compute_class_weight('balanced',
                               classes=np.unique(y),
                               y=y)
class_weight = {0: weights[0], 1: weights[1]}
```

---

## Next Steps

1. ✅ **Run POC** - Train initial models
2. 📊 **Collect 1000+ patterns** - Add more stocks
3. 🎯 **Improve accuracy** - Feature engineering
4. 🔧 **Multi-class** - Recognize specific patterns
5. 🚀 **Deploy** - Integrate into API

**Good luck with your ML journey!** 🚀
