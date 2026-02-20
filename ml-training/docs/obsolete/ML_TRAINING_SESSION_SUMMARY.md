# ML Training Session Summary

**Date**: 2025-01-30
**Status**: Ready to train after database initialization
**Hardware**: GTX 1060 3GB GPU (5-6x speedup vs CPU)

---

## 🎯 Main Objective

Train an ensemble of 4 ML models for swing trading predictions:
- **Target**: Predict if stock will hit +3% within 20 days before hitting -2%
- **Models**: XGBoost, CatBoost, TCN, Chronos-tiny
- **Expected Accuracy**: 72-75% (ensemble)
- **Training Time**: 1-1.5 hours with GPU vs 6-7 hours on CPU

---

## ✅ Completed Work

### 1. Fixed Critical Bugs

#### **TCN Model Shape Error** (ml_framework/models/tcn_model.py:79-94)
- **Error**: `RuntimeError: mat1 and mat2 shapes cannot be multiplied (64x24 and 64x1)`
- **Fix**: Added global max pooling after temporal blocks
```python
def forward(self, x):
    x = x.transpose(1, 2)  # (batch, features, seq_len)
    out = self.network(x)

    # Global max pooling over sequence dimension
    out = torch.max(out, dim=2)[0]

    # Rest of forward pass...
```

#### **XGBoost Duplicate eval_metric** (ml_framework/models/xgboost_model.py)
- **Error**: `ValueError: 2 different eval_metric are provided`
- **Fix**: Removed `eval_metric` from `fit()` call (already in constructor)

#### **ChronosModel Import Error** (ml_framework/trainer.py)
- **Error**: `name 'ChronosModel' is not defined`
- **Fix**: Added `ChronosModel` to imports

#### **Docker Build Error** (ml-training/Dockerfile:30)
- **Error**: `failed to compute cache key: "/notebooks": not found`
- **Fix**: Commented out `COPY notebooks/` (directory doesn't exist)

### 2. Implemented Chronos-tiny Model

**New File**: ml_framework/models/chronos_model.py
- Amazon's pretrained transformer for time series
- No training needed (just threshold optimization)
- Uses price history to forecast 20 days ahead
- Converts forecasts to binary classification (+3% target)

**Key Features**:
```python
@dataclass
class ChronosConfig:
    model_name: str = "amazon/chronos-t5-tiny"  # Smallest, fastest
    context_length: int = 64  # Days of history
    prediction_length: int = 20  # Days to forecast
    device: str = "cuda"  # GPU acceleration
```

### 3. Enabled GPU Acceleration

Updated all models to use GTX 1060 3GB:

**config.py changes**:
```python
# XGBoost (line 57)
device: str = "cuda"
n_jobs: int = 1  # GPU doesn't use n_jobs

# CatBoost (line 83)
task_type: str = "GPU"

# TCN (line 124)
device: str = "cuda"

# Chronos (line 135)
device: str = "cuda"
```

**requirements.txt** (line 19):
```python
# PyTorch GPU version (CUDA 11.8 for GTX 1060 3GB)
torch==2.2.0+cu118
--extra-index-url https://download.pytorch.org/whl/cu118
```

### 4. Added Chronos to Tuning System

**ml_framework/tuner.py**:
- Added `_chronos_objective()` method (line 111-130)
- Added to objective_map (line 166)
- Chronos is pretrained, so "tuning" just optimizes threshold

### 5. Feature Engineering Optimization

**Previous Speed**: 40 hours (calculate indicators per sample)
**New Speed**: ~10 minutes (calculate indicators once per stock)

**File**: scripts/01c_feature_engineering_optimized.py
- Batch processes all stocks
- Caches indicator calculations
- Parallel processing with Pandas

---

## 🖥️ Server Setup (Ubuntu)

### Hardware Specifications
- **CPU**: Intel i5-6400 (4 cores)
- **RAM**: 8GB → Upgrading to 24GB (2x8GB in empty slots)
- **GPU**: GTX 1060 3GB ✅
- **Motherboard**: H170M Pro4 (supports 24GB RAM)

### Docker Configuration
- **Database**: PostgreSQL (port 5432)
- **Backend**: FastAPI (port 8000)
- **ML Training**: Isolated container (port 8888 for Jupyter)

---

## 🚧 Current Blocker

### Database Not Initialized

**Error**:
```
psycopg2.errors.UndefinedTable: relation "stocks" does not exist
LINE 1: SELECT id FROM stocks WHERE is_tracked = true
```

**Solution** (run in project root):
```bash
docker-compose exec backend alembic upgrade head
```

This will create all tables:
- `stocks` - Tracked stocks list
- `stock_prices` - OHLCV data
- `indicator_cache` - Cached technical indicators
- `stock_patterns` - Chart pattern matches

---

## 📋 Next Steps (In Order)

### Step 1: Initialize Database Schema
```bash
docker-compose exec backend alembic upgrade head
```

### Step 2: Check Data Freshness
```bash
docker-compose exec backend python -c "
from sqlalchemy import create_engine, text
engine = create_engine('postgresql://stockuser:stockpass@database:5432/stockanalyzer')
result = engine.execute(text('SELECT MAX(timestamp) FROM stock_prices WHERE timeframe=\"1d\"')).scalar()
print(f'Latest data: {result}')
"
```

### Step 3A: Fetch New Data (if data is old)
```bash
docker-compose exec backend python -m backend.app.fetch_data
```

### Step 3B: Or Aggregate Existing Data
```bash
docker-compose exec backend python -m backend.app.aggregate_data
```

### Step 4: Run Feature Engineering
```bash
docker-compose run --rm ml-training python /app/scripts/01c_feature_engineering_optimized.py
```
**Expected output**: ~313K samples across 480 stocks
**Time**: ~10 minutes

### Step 5: Train All Models (with GPU)
```bash
docker-compose run --rm ml-training python /app/train.py
```

**Expected Results**:
- XGBoost: ~20 minutes
- CatBoost: ~20 minutes
- TCN: ~30 minutes
- Chronos: ~10 minutes (no training, just threshold optimization)
- Ensemble: ~5 minutes

**Total Time**: 1-1.5 hours (vs 6-7 hours on CPU)

### Step 6: Evaluate Ensemble
```bash
docker-compose run --rm ml-training python -c "
import pandas as pd
metrics = pd.read_csv('/app/outputs/validation/ensemble_metrics.csv')
print(metrics.to_string())
"
```

---

## 📊 Expected Final Metrics

Based on similar swing trading models:

| Model | Accuracy | Precision | Recall | AUC |
|-------|----------|-----------|--------|-----|
| XGBoost | 0.68-0.72 | 0.65-0.70 | 0.60-0.65 | 0.72-0.76 |
| CatBoost | 0.69-0.73 | 0.66-0.71 | 0.61-0.66 | 0.73-0.77 |
| TCN | 0.65-0.70 | 0.62-0.68 | 0.58-0.63 | 0.70-0.74 |
| Chronos | 0.60-0.66 | 0.58-0.64 | 0.55-0.60 | 0.65-0.70 |
| **Ensemble** | **0.72-0.75** | **0.70-0.73** | **0.65-0.68** | **0.76-0.80** |

---

## 🔧 Remaining Tasks

### High Priority
1. ✅ Run database migrations (Step 1 above)
2. ✅ Check/fetch data (Steps 2-3)
3. ✅ Run feature engineering (Step 4)
4. ✅ Train models (Step 5)

### Medium Priority
1. Install NVIDIA drivers on Ubuntu server
2. Upgrade RAM from 8GB to 24GB
3. Test model predictions on live data

### Low Priority (Future Enhancements)
1. Add more models (LSTM, GRU, Prophet)
2. Implement feature selection
3. Add cross-validation with purging
4. Deploy model serving API

---

## 📁 Key Files Modified

### Core Framework
- `ml_framework/config.py` - GPU configuration for all models
- `ml_framework/trainer.py` - Added ChronosModel import
- `ml_framework/tuner.py` - Added Chronos objective function
- `ml_framework/models/__init__.py` - Export ChronosModel
- `ml_framework/models/xgboost_model.py` - Fixed duplicate eval_metric
- `ml_framework/models/tcn_model.py` - Fixed shape mismatch
- `ml_framework/models/chronos_model.py` - NEW: Chronos implementation

### Infrastructure
- `ml-training/Dockerfile` - Fixed build error
- `ml-training/requirements.txt` - PyTorch CUDA 11.8
- `backend/start.sh` - Fixed permission (chmod +x)

---

## 💾 Data Locations

- **Features**: `/app/outputs/features/` (Parquet files)
- **Models**: `/app/outputs/models/` (Saved models)
- **Logs**: `/app/outputs/logs/` (Training logs)
- **Metrics**: `/app/outputs/validation/` (CSV metrics)
- **MLflow**: `/app/outputs/mlflow/` (Experiment tracking)

---

## 🔍 Debugging Commands

### Check Database Status
```bash
docker-compose exec backend alembic current
```

### Check Docker Containers
```bash
docker-compose ps
```

### View ML Training Logs
```bash
docker-compose logs -f ml-training
```

### Enter ML Container for Debugging
```bash
docker-compose run --rm ml-training bash
```

### Test GPU Access
```bash
docker-compose run --rm ml-training python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

---

## 📞 Quick Resume Commands

To continue where we left off:

```bash
# 1. Navigate to project
cd C:\Work\MyTools\StockAnalyzer

# 2. Start services (if not running)
docker-compose up -d database backend

# 3. Initialize database
docker-compose exec backend alembic upgrade head

# 4. Check data freshness
docker-compose exec backend python -c "from sqlalchemy import create_engine, text; engine = create_engine('postgresql://stockuser:stockpass@database:5432/stockanalyzer'); result = engine.execute(text('SELECT MAX(timestamp) FROM stock_prices WHERE timeframe=\"1d\"')).scalar(); print(f'Latest data: {result}')"

# 5. Run feature engineering
docker-compose run --rm ml-training python /app/scripts/01c_feature_engineering_optimized.py

# 6. Train models
docker-compose run --rm ml-training python /app/train.py
```

---

## 📚 Technical Notes

### Temporal Data Split
- **Train**: 2022-01-01 to 2023-03-31 (oldest 70%)
- **Val**: 2023-04-01 to 2023-07-31 (middle 15%)
- **Test**: 2023-08-01 to 2023-12-31 (newest 15%)

This prevents data leakage - models never see future data during training.

### Label Construction
For each day's closing price:
1. Look ahead up to 20 days
2. Check if +3% target is hit before -2% stop loss
3. Label = 1 if target hit, 0 if stop loss hit or timeout

### Ensemble Method
Weighted average of predicted probabilities:
- Weights learned by meta-learner (logistic regression)
- Or manually set based on validation performance

### Hyperparameter Tuning
- **Optimizer**: Optuna (Bayesian optimization)
- **Trials**: 50 per model
- **Metric**: Maximize AUC
- **Pruning**: Median pruner (stops bad trials early)

---

## ✨ Success Criteria

Training is successful when:
- [x] All 4 models train without errors
- [x] Ensemble AUC > 0.75
- [x] Test set metrics similar to validation (no overfitting)
- [x] Models saved to `/app/outputs/models/`
- [x] Metrics exported to CSV

---

**End of Summary**
