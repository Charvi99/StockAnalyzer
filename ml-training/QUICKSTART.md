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

## 📚 Full Documentation

See: [ML_FRAMEWORK_README.md](ML_FRAMEWORK_README.md)
