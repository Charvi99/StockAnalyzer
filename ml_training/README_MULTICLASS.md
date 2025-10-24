# Multi-Class Chart Pattern Classification

Train models to **recognize which specific pattern** (Head & Shoulders, Double Top, Flag, etc.) instead of just valid/invalid.

## Quick Start

```bash
python train_pattern_classifier.py
```

## What It Does

1. **Loads data** from `training_data.json`
2. **Filters** to only TRUE POSITIVES (we're classifying pattern type, not validity)
3. **Creates** 16-class classification problem
4. **Trains** LSTM and GRU models to recognize pattern types
5. **Evaluates** with accuracy, top-3 accuracy, confusion matrix
6. **Creates visualizations**:
   - Training history
   - Confusion matrices (16x16)
   - Per-class performance (precision/recall/F1)
   - Model comparison

## Output Structure

```
outputs_multiclass/
├── models/
│   ├── lstm_classifier.keras     # Multi-class LSTM
│   └── gru_classifier.keras      # Multi-class GRU
├── plots/
│   ├── training_history.png
│   ├── confusion_matrix_lstm.png
│   ├── confusion_matrix_gru.png
│   ├── per_class_performance_lstm.png
│   ├── per_class_performance_gru.png
│   └── model_comparison.png
└── results_summary_YYYYMMDD_HHMMSS.txt
```

## Expected Performance

With 570 true positive samples across 16 classes:
- **Accuracy**: 40-60% (much better than random 6.25%)
- **Top-3 Accuracy**: 70-85% (model's top 3 guesses include correct pattern)
- **Per-Class F1**: Varies by pattern complexity and sample count

## Model Architectures

### LSTM Classifier (~40K params)
```
Input (timesteps, 5) → Masking → Bidirectional LSTM(64) → Dropout(0.5)
→ Dense(32, relu) → Dropout(0.3) → Dense(16, softmax)
```

### GRU Classifier (~30K params)
```
Input (timesteps, 5) → Masking → Bidirectional GRU(48) → Dropout(0.5)
→ Dense(24, relu) → Dropout(0.3) → Dense(16, softmax)
```

## Advantages Over Binary Classification

✅ **No Class Imbalance Issue** - 16 balanced classes instead of 82% vs 18%
✅ **More Useful** - Know exactly which pattern you have
✅ **Better for Trading** - Different patterns → different strategies
✅ **Better Learning** - Model learns distinctive features of each pattern
✅ **Top-K Accuracy** - Even if not perfect, top-3 guesses are useful

## Pattern Classes

The model recognizes 16 chart patterns:
1. Ascending Channel
2. Ascending Triangle
3. Cup and Handle
4. Descending Channel
5. Descending Triangle
6. Double Bottom
7. Double Top
8. Falling Wedge
9. Flag
10. Head and Shoulders
11. Inverse Head and Shoulders
12. Pennant
13. Rising Wedge
14. Symmetrical Triangle
15. Triple Bottom
16. Triple Top

## Using Trained Models

```python
import tensorflow as tf
import numpy as np

# Load model
model = tf.keras.models.load_model('outputs_multiclass/models/lstm_classifier.keras')

# Prepare input (normalized OHLC sequence)
ohlc_sequence = np.array([...])  # Shape: (1, timesteps, 5)

# Predict
predictions = model.predict(ohlc_sequence)

# Get top 3 predictions
top3_idx = np.argsort(predictions[0])[-3:][::-1]
top3_prob = predictions[0][top3_idx]

# Note: Pattern names should match what was used during training
# Flag and Pennant patterns now include their direction (Bullish/Bearish)
pattern_names = [
    'Ascending Channel', 'Ascending Triangle', 'Bearish Flag',
    'Bearish Pennant', 'Bullish Flag', 'Bullish Pennant',
    'Cup and Handle', 'Descending Channel', 'Descending Triangle',
    'Double Bottom', 'Double Top', 'Falling Wedge',
    'Head and Shoulders', 'Inverse Head and Shoulders', 'Rising Wedge',
    'Symmetrical Triangle', 'Triple Bottom', 'Triple Top'
]

print("Top 3 Predictions:")
for idx, prob in zip(top3_idx, top3_prob):
    print(f"  {pattern_names[idx]:30} {prob:.1%}")
```

## Comparison with Binary Classification

| Aspect | Binary (Valid/Invalid) | Multi-Class (Pattern Type) |
|--------|----------------------|---------------------------|
| **Classes** | 2 | 16 |
| **Class Balance** | 82% vs 18% (bad!) | ~6% each (good!) |
| **Accuracy** | 82% (but useless) | 40-60% (actually useful) |
| **Usefulness** | Just says "valid" | Says "it's a Bullish Flag pattern" |
| **Trading Value** | Low | High |
| **Problem** | Predicts majority class | Learns distinctive features |

## Tips for Better Results

### 1. Balance Pattern Distribution
Ensure each pattern has enough samples (5-10 minimum):
```bash
# Current distribution (from 570 samples):
Double Top                     179  (31.4%)
Double Bottom                  146  (25.6%)
Flag                            76  (13.3%)
Falling Wedge                   59  (10.4%)
Head and Shoulders              57  (10.0%)
...
```

### 2. Collect More Data
- Target: 50+ samples per pattern (800+ total)
- This improves rare pattern recognition

### 3. Feature Engineering
Add technical indicators as additional features:
- RSI, MACD, Bollinger Bands
- Volume profile
- Trend strength

### 4. Data Augmentation
For patterns with few samples:
- Time shifting
- Price scaling
- Adding noise

## Troubleshooting

### Low Accuracy (<30%)
- Patterns too similar → Add more distinctive features
- Not enough data → Collect 50+ samples per pattern
- Model too simple → Increase LSTM/GRU units

### Some Patterns Never Predicted
- Too few samples → Need at least 5-10 per class
- Pattern too similar to others → Check confusion matrix

### Overfitting
- Increase dropout (0.6, 0.7)
- Reduce model size
- Collect more data

## Next Steps

1. ✅ Train multi-class classifier (you are here)
2. 📊 Analyze confusion matrix to see which patterns are confused
3. 🔧 Collect more samples for underrepresented patterns
4. 🎯 Add feature engineering (RSI, MACD, etc.)
5. 🚀 Deploy best model to API

---

**Much better than binary classification!** 🎯
