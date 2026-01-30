# ML Training Module

This directory contains the ML training pipeline for StockAnalyzer.

## 🚀 Quick Start

### 1. Start ML Container

```bash
# From project root
docker-compose run --rm ml-training bash
```

### 2. Run Feature Engineering

```bash
# Inside ML container
cd /app/scripts
python 01_feature_engineering.py
```

This will:
- Connect to the database
- Fetch price data for all tracked stocks
- Engineer 45+ features
- Save to `/app/outputs/features/features_YYYYMMDD.parquet`

### 3. Create Labels

```bash
python 02_create_labels.py
```

This will:
- Create swing trading labels (+3% within 20 days before -2%)
- Save to `/app/outputs/features/labels_YYYYMMDD.parquet`

### 4. Train XGBoost Model

```bash
python 03_train_xgboost.py
```

This will:
- Train XGBoost on the features
- Use temporal train/val/test split (NOT random!)
- Evaluate performance
- Save model to `/app/outputs/models/xgboost/latest/`

### 5. Start Jupyter Lab (for experimentation)

```bash
cd /app
jupyter lab
```

Then open browser to: `http://localhost:8888`

## 📂 Directory Structure

```
ml-training/
├── Dockerfile           # CPU version
├── Dockerfile.gpu       # GPU version (use when you have GPU)
├── requirements.txt     # CPU dependencies
├── requirements.gpu.txt # GPU dependencies
├── scripts/             # Training scripts
│   ├── 01_feature_engineering.py
│   ├── 02_create_labels.py
│   ├── 03_train_xgboost.py
│   ├── 04_train_chronos.py      # TODO
│   ├── 05_train_ensemble.py      # TODO
│   └── 06_validate.py            # TODO
├── notebooks/           # Jupyter notebooks
│   └── 01_exploration.ipynb      # TODO
└── outputs/             # Generated data
    ├── features/         # Engineered features (parquet)
    ├── models/           # Trained models
    ├── logs/             # Training logs
    └── validation/       # Validation results
```

## 🔧 Scripts Overview

### 01_feature_engineering.py

Generates features from database:
- Technical indicators (15 features)
- Chart patterns (8 features)
- Candlestick patterns (6 features)
- Market regime (4 features)
- Price history (10 features)
- **Total: 45 features**

### 02_create_labels.py

Creates swing trading labels:
- Target: +3% within 20 days before -2%
- Binary classification: BUY (1) or DON'T BUY (0)
- Uses only historical data (no look-ahead bias)

### 03_train_xgboost.py

Trains XGBoost model:
- Temporal train/val/test split
- Handles class imbalance
- Early stopping
- MLflow tracking
- Saves model with versioning

## 📊 Model Storage

Trained models are saved in two locations:

```
/app/outputs/models/xgboost/
├── v1.0.0_20250130_120000/  # Versioned (timestamped)
│   ├── model.json
│   └── feature_cols.txt
└── latest/                   # Always latest model
    ├── model.json
    └── feature_cols.txt
```

The backend API can load from `latest/` for predictions.

## 🐳 Docker Commands

### Run ML Container Interactively

```bash
docker-compose run --rm ml-training bash
```

### Run Specific Script

```bash
docker-compose run --rm ml-training python /app/scripts/01_feature_engineering.py
```

### Start Jupyter Lab

```bash
docker-compose run --service-ports --rm ml-training
```

Then open: `http://localhost:8888`

## 📈 Current Status

- ✅ Feature engineering pipeline (45 features)
- ✅ Label creation (swing trading targets)
- ✅ XGBoost training (temporal split)
- ⏳ Chronos integration (TODO)
- ⏳ Ensemble training (TODO)
- ⏳ Walk-forward validation (TODO)

## 🔗 Database Access

The ML container connects to the same database as backend:

```python
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://stockuser:stockpass@db:5432/stockanalyzer'
)
```

No additional setup needed - Docker networking handles it!

## ⚠️ Important Notes

1. **CPU vs GPU**: Uses CPU by default. Will be slower but works.
2. **No Breaking Changes**: Backend is 100% unaffected.
3. **Optional**: You can ignore ML completely if you want.
4. **Shared Models**: Trained models saved to `./ml-models/` (shared with backend)

## 📝 Next Steps

1. ✅ Run feature engineering
2. ✅ Create labels
3. ✅ Train XGBoost model
4. ⏳ Integrate with backend API for predictions
5. ⏳ Add Chronos model
6. ⏳ Build ensemble

## 🆘 Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs ml-training

# Rebuild container
docker-compose build ml-training
```

### Database connection error

```bash
# Make sure database is running
docker-compose ps db

# Start database
docker-compose up -d db
```

### Out of memory

```bash
# Reduce batch size in training scripts
# Or run fewer stocks at once
```

## 📚 Resources

- XGBoost Docs: https://xgboost.readthedocs.io/
- MLflow Docs: https://mlflow.org/docs/
- Chronos Paper: https://arxiv.org/abs/2403.07815
