# AutoGluon Implementation Guide

**Date**: 2026-02-10
**Status**: ✅ Complete

---

## What is AutoGluon?

AutoGluon is Amazon's **AutoML (Automated Machine Learning)** library that automatically:
- Trains multiple models (XGBoost, CatBoost, LightGBM, Random Forest, etc.)
- Tunes hyperparameters for each model
- Creates ensembles through stacking and bagging
- Selects the best model/ensemble automatically

**Key Advantage**: State-of-the-art performance on tabular data with minimal manual tuning.

---

## Implementation Summary

### Files Created/Modified

#### New Files:
1. **`ml_framework/models/autogluon_model.py`**
   - AutoGluonModel class that wraps AutoGluon's TabularPredictor
   - Supports both binary and multi-class classification
   - Automatic ensemble creation during training

#### Modified Files:
2. **`ml_framework/config.py`**
   - Added `AutoGluonConfig` dataclass with preset configurations
   - Added to master `Config` class

3. **`ml_framework/models/__init__.py`**
   - Added `AutoGluonModel` and `check_autogluon_available` to exports

4. **`ml_framework/trainer.py`**
   - Added AutoGluon to model_map
   - Imported AutoGluonModel

5. **`train.py`**
   - Added 'autogluon' to AVAILABLE_MODELS list

6. **`requirements.txt` & `requirements.gpu.txt`**
   - Added `autogluon==1.1.1`

---

## Configuration Options

### AutoGluonConfig Parameters

```python
@dataclass
class AutoGluonConfig:
    # Training parameters
    time_limit: int = 3600  # Total training time in seconds (default: 1 hour)

    # Preset quality levels:
    # 'best_quality' - Best predictions, ~200x longer than good_quality
    # 'high_quality' - Better predictions, ~20x longer
    # 'medium_quality' - Good predictions, ~4x longer
    # 'good_quality' - Fast predictions (default)
    presets: str = "medium_quality"

    # Ensemble settings
    num_bag_sets: int = 1  # Bagging folds (higher = better but slower)
    num_stack_levels: int = 0  # Stacking levels (higher = better but slower)

    # Hardware
    use_gpu: bool = True
    verbosity: int = 1
```

---

## Usage Examples

### Basic Training

```bash
# Train AutoGluon only (1 hour default)
python train.py --models autogluon

# Train with 3-hour time limit
python train.py --models autogluon --time-limit 10800

# Train with best quality preset (slower)
python train.py --models autogluon --presets best_quality

# Train with binary labels
python train.py --models autogluon --label-type binary

# Train with 3-class labels
python train.py --models autogluon --label-type 3class
```

### Advanced Configuration

Edit `ml_framework/config.py` or create a custom config:

```python
from ml_framework.config import AutoGluonConfig

# High quality ensemble
autogluon_config = AutoGluonConfig(
    time_limit=7200,  # 2 hours
    presets='high_quality',
    num_bag_sets=5,  # 5-fold bagging
    num_stack_levels=2,  # 2-level stacking
    use_gpu=True
)
```

---

## How AutoGluon Works

### Training Process

```
┌─────────────────────────────────────────────────┐
│  AutoGluon Training Pipeline                     │
├─────────────────────────────────────────────────┤
│                                                 │
│  1. Train Multiple Models                      │
│     ├── XGBoost (with various parameters)       │
│     ├── CatBoost (with various parameters)      │
│     ├── LightGBM (with various parameters)      │
│     ├── Random Forest                           │
│     ├── Extra Trees                             │
│     └── ... more models                         │
│                                                 │
│  2. Hyperparameter Tuning                       │
│     └── Bayesian optimization for each model    │
│                                                 │
│  3. Bagging (if num_bag_sets > 0)              │
│     └── Train multiple versions with resampling │
│                                                 │
│  4. Stacking (if num_stack_levels > 0)          │
│     └── Meta-learner on top of base models     │
│                                                 │
│  5. Select Best Model/Ensemble                  │
│     └── Automatic selection based on validation │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Model Weights Example

After training, AutoGluon might create an ensemble like:

```
WeightedEnsemble_L1:
  ├── XGBoost (weight: 0.35)
  ├── CatBoost (weight: 0.25)
  ├── LightGBM (weight: 0.20)
  ├── RandomForest (weight: 0.10)
  └── ExtraTrees (weight: 0.10)
```

---

## Expected Performance

Based on AutoGluon's typical results on tabular data:

| Metric | Expected Value |
|--------|---------------|
| **vs Single Models** | +1-3% AUC improvement |
| **vs Manual Ensembling** | Similar or better |
| **Training Time** | 1-4 hours (depending on presets) |
| **Prediction Speed** | Fast (uses best single model) |

### Comparison with Existing Models

| Model | AUC | Training Time | Auto-Tuning |
|-------|-----|---------------|-------------|
| XGBoost | ~55-57% | 30-60 min | Manual (Optuna) |
| CatBoost | ~55-57% | 30-60 min | Manual (Optuna) |
| TabNet | ~55-57% | 45-90 min | Manual (Optuna) |
| **AutoGluon** | **~57-60%** | 1-4 hours | ✅ Automatic |

---

## Features

### 1. Automatic Feature Engineering

AutoGluon automatically handles:
- Missing values
- Categorical features
- Feature scaling
- Feature selection

### 2. Automatic Hyperparameter Tuning

Each model gets optimized with Bayesian optimization.

### 3. Automatic Ensembling

Multiple ensemble strategies:
- **Bagging**: Train multiple versions with different data samples
- **Stacking**: Use predictions as features for meta-learner
- **Weighted Ensemble**: Combine predictions with learned weights

### 4. Model Diversity

Trains many model types:
- Tree-based: XGBoost, CatBoost, LightGBM
- Linear: Linear models, GLM
- Tree ensembles: Random Forest, Extra Trees
- KNN: K-Nearest Neighbors
- And more...

---

## Installation

### In Docker

```bash
# Rebuild the ML training container
cd /home/jakub/StockAnalyzer
docker-compose build ml-training

# Or install manually in running container
docker exec -it stockanalyzer_ml-training pip install autogluon==1.1.1
```

### Locally

```bash
cd /home/jakub/StockAnalyzer/ml-training
pip install autogluon==1.1.1
```

---

## API Usage

### Training

```python
from ml_framework.models import AutoGluonModel
from ml_framework.config import AutoGluonConfig

# Create config
config = AutoGluonConfig(
    time_limit=3600,
    presets='medium_quality',
    use_gpu=True
)

# Create model
model = AutoGluonModel(config)

# Train
model.train(X_train, y_train, X_val, y_val, num_classes=3)
```

### Prediction

```python
# Predict classes
predictions = model.predict(X_test)

# Predict probabilities
probabilities = model.predict_proba(X_test)

# Get feature importance
importance = model.get_feature_importance()

# Get leaderboard (shows all models trained)
leaderboard = model.get_leaderboard()
print(leaderboard)
```

---

## Troubleshooting

### Memory Issues

AutoGluon can use significant memory during training. If you encounter OOM errors:

```python
# Reduce time limit (trains fewer models)
config = AutoGluonConfig(time_limit=1800)  # 30 minutes

# Use lower quality preset
config = AutoGluonConfig(presets='good_quality')

# Disable bagging/stacking
config = AutoGluonConfig(
    num_bag_sets=0,
    num_stack_levels=0
)
```

### GPU Issues

If AutoGluon doesn't detect your GPU:

```python
config = AutoGluonConfig(
    use_gpu=False,  # Force CPU
    verbosity=2  # Enable detailed logging
)
```

### Slow Training

If training is taking too long:

```python
# Use faster preset
config = AutoGluonConfig(
    presets='good_quality',  # Fastest
    time_limit=1800  # 30 minutes
)
```

---

## Preset Comparison

| Preset | Quality | Time | Use Case |
|--------|---------|------|----------|
| `good_quality` | Medium | Fast (10-30 min) | Quick experimentation |
| `medium_quality` | High | Medium (30-60 min) | **Default** |
| `high_quality` | Very High | Slow (1-2 hours) | Production models |
| `best_quality` | Maximum | Very Slow (3-6 hours) | Competitions/best results |

---

## Next Steps

1. **Install AutoGluon**:
   ```bash
   docker-compose build ml-training
   ```

2. **Train a model**:
   ```bash
   python train.py --models autogluon --label-type 3class
   ```

3. **Compare results**:
   - Check AutoGluon's leaderboard
   - Compare AUC vs XGBoost/CatBoost/TabNet
   - Backtest the best model

4. **Optimize**:
   - Try different presets
   - Adjust time_limit based on results
   - Experiment with bagging/stacking

---

**Generated**: 2026-02-10
**Framework**: ML Training Framework v1.0
**AutoGluon Version**: 1.1.1
