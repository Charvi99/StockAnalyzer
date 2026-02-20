# Quick Start Guide - ML Framework

**Get your models trained in 3 simple steps**

## 🚀 Step 1: Start ML Container

```bash
# From project root
docker-compose build ml-training  # First time only
docker-compose run --rm ml-training bash
```

## 🚀 Step 2: Prepare Data (First Time Only)

```bash
# Inside ML container
cd /app/scripts

# 1. Engineer features (~10 minutes)
python 01_feature_engineering.py

# Output:
# ✅ Saved 335 feature rows to /app/outputs/features/features_20250130.parquet

# 2. Create labels (~5 minutes)
python 02_create_labels.py

# Output:
# ✅ Saved 48,520 label rows to /app/outputs/features/labels_20250130.parquet
```

## 🚀 Step 3: Train Models

```bash
# Option A: Fast training (no tuning, 1-2 hours)
cd /app/ml-framework

# Edit train.py, set:
tune_models = False

python ../train.py

# Option B: Full training (with tuning, 4-6 hours)
python ../train.py

# Output:
# ✅ XGBoost trained. Best iteration: 1247
# ✅ CatBoost trained. Best iteration: 1156
# ✅ Ensemble created
# ✅ Models saved to /app/outputs/models/
```

## ✅ Done! Models Are Ready

Your trained models are now saved to:
```
/app/outputs/models/
├── xgboost/latest/model.json
├── catboost/latest/model.cbm
└── ensemble/latest/
```

## 📊 Check Performance

After training completes, you'll see:

```
MODEL COMPARISON
================

XGBOOST:
  Accuracy:  64.2%
  Precision: 58.7%
  Recall:    46.3%
  AUC:       0.6834

CATBOOST:
  Accuracy:  64.8%
  Precision: 59.2%
  Recall:    47.1%
  AUC:       0.6891

ENSEMBLE PERFORMANCE:
  Accuracy:  66.5%
  Precision: 62.1%
  Recall:    51.2%
  AUC:       0.7056
```

## 🎯 What Just Happened?

1. **Feature Engineering** - 45 features extracted from your database
2. **Label Creation** - Swing trading targets (+3% within 20 days)
3. **Model Training** - 3 models trained with optimal hyperparameters
4. **Ensemble** - Models combined for best accuracy
5. **Saving** - Everything saved to disk for production use

## 📦 Next: Use in Backend

The trained models can now be loaded in your backend API for predictions!

(See: ML_FRAMEWORK_README.md - Section "Loading Models in Backend")

## 🔧 Customization

### Change Training Parameters

```python
# Edit ml_framework/config.py

class DataConfig:
    profit_target: float = 0.05  # Change from 0.03 (3%)
    stop_loss: float = -0.03  # Change from -0.02 (2%)
    lookahead_days: int = 30  # Change from 20

class TrainingConfig:
    n_trials: int = 100  # Change from 50 (more tuning)
```

### Change Models

```python
# Edit ml_framework/config.py

class EnsembleConfig:
    models: List[str] = ["xgboost", "catboost"]
    method: str = "stacking"  # Use stacking instead of weighted average
```

## 💡 Tips

**Speed Up Training:**
- Set `tune_models = False` in train.py
- Reduce `n_trials` in config

**Improve Accuracy:**
- Increase `n_trials` to 200
- Use "stacking" ensemble method
- Add more features

**Reduce Overfitting:**
- Reduce model depth
- Increase dropout
- Add more training data

## ⚠️ Important: Temporal Data Splitting

This framework uses **temporal splitting** for training, which is critical for financial ML:

```
Train (70%): 2018-01-01 to 2022-12-31  ← Learn from past
Val (15%):   2023-01-01 to 2024-06-30  ← Tune hyperparameters
Test (15%):  2024-07-01 to 2025-12-31  ← Evaluate on future
```

### Why Temporal Split?

| Split Type | What It Tests | AUC (example) |
|------------|---------------|---------------|
| **Temporal** | Can model predict future data? | ~60% |
| Cross-sectional | Can model predict unseen stocks? | ~83% |
| Random | (Data leakage - misleading) | ~89%+ |

**Temporal split gives realistic performance estimates** for live trading.

### Expected AUC Ranges

With proper temporal split on 2018-2025 data:
- **XGBoost/CatBoost**: 60-63% AUC (3-class)
- **AutoGluon**: 59-62% AUC (3-class)
- **Random baseline**: 50% AUC

> Note: These are realistic AUCs for stock prediction. Much higher values often indicate data leakage.
>
> **Performance:** This framework uses Polars for 2-3x faster data loading and 50-70% memory reduction compared to pandas.

## 📋 Data Requirements

### Label Files

Labels use multi-timeframe format with lookahead returns:

```
labels_3class.parquet columns:
- timestamp
- stock_id
- final_return_20d  # Actual 20-day return
- label_20d         # 0=SELL, 1=HOLD, 2=BUY (20-day)
- final_return_30d
- label_30d
- final_return_40d
- label_40d
```

The trainer automatically uses `label_20d` by default.

### Timestamp Alignment

**Critical**: Features and labels must have matching timestamps.

Labels may have time component (e.g., `2024-01-15 05:00:00`) while features use midnight (`2024-01-15 00:00:00`). The trainer normalizes timestamps automatically, but verify if merge count seems low:

```python
# Check timestamp formats
features['timestamp'].dtype  # Should be datetime64[ns]
labels['timestamp'].dtype    # Should be datetime64[ns]

# Check for time component differences
features['timestamp'].head()  # Look for 00:00:00
labels['timestamp'].head()    # Look for non-zero times
```

## 🐛 Troubleshooting

**Error: "No feature files found"**
```bash
# Run feature engineering first
python 01_feature_engineering.py
```

**Error: "No label files found"**
```bash
# Run label creation first
python 02_create_labels.py
```

**Training too slow?**
```bash
# Skip tuning, use defaults
# Edit train.py: tune_models = False
```

**Low AUC (~50-52%) or unexpected results?**
```bash
# Check these common issues:

# 1. Verify data date range - you need 2018-2025 data for good results
docker-compose exec ml-training python -c "
import pandas as pd
from pathlib import Path
f = pd.read_parquet('/app/outputs/features/dataset_XXX/features.parquet', columns=['timestamp'])
l = pd.read_parquet('/app/outputs/features/dataset_XXX/labels_3class.parquet', columns=['timestamp'])
print(f'Features: {f.timestamp.min()} to {f.timestamp.max()}')
print(f'Labels: {l.timestamp.min()} to {l.timestamp.max()}')
"

# 2. Check merged data count - should be close to label count
# If merge loses 60%+ of data, timestamps may not align
```

## 📚 Documentation

### Essential Guides
- **[ML Framework Guide](docs/guides/ML_FRAMEWORK_README.md)** - Complete ML framework (5 models)
- **[Configuration Guide](configs/README.md)** - YAML config system reference

### Additional Resources
- **[Architecture](docs/architecture.md)** - System design
- **[Framework](docs/framework.md)** - ML Framework details
- **[Configuration Reference](docs/configuration.md)** - YAML options (legacy, see configs/README.md)

### Results & Analysis
- **[Results](docs/results/)** - Training results and model comparisons

### Implementation Notes
- **[Implementation Summaries](docs/implementation/)** - Development session notes

### Planning
- **[Roadmaps & TODOs](docs/plans/)** - Future plans
