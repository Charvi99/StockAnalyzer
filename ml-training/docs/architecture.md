# ML-Training Architecture

## System Overview

The ML-Training system is organized into four main components:

1. **Feature Engineering** - Generate 121 technical and fundamental features
2. **Label Creation** - Create prediction targets (binary/multi-class)
3. **Model Training** - Train and evaluate ML models
4. **Backtesting** - Validate strategies on historical data

```
Raw Data → Features → Labels → Training → Models → Backtesting → Results
```

## Directory Structure

```
ml-training/
├── ml_framework/          # Core ML framework
│   ├── config.py          # Configuration management
│   ├── base.py           # BaseModel interface
│   ├── trainer.py        # Training orchestration
│   ├── tuner.py          # Hyperparameter tuning
│   ├── ensemble.py       # Ensemble methods
│   └── models/           # Model implementations
│       ├── xgboost_model.py
│       ├── catboost_model.py
│       ├── tabnet_model.py
│       ├── autogluon_model.py
│       └── fttransformer_model.py
├── scripts/              # Orchestration scripts
│   ├── create_features.py
│   ├── create_labels.py
│   ├── train.py
│   ├── backtest.py
│   └── utils/
├── configs/              # YAML configurations
├── outputs/              # Generated data and models
│   ├── features/
│   ├── models/
│   └── backtests/
└── archive/              # Archived code and data
```

## Component Relationships

### Feature Engineering Pipeline

`scripts/create_features.py` generates:
- **Technical Indicators** (50+): RSI, MACD, Bollinger Bands, etc.
- **Swing Features** (30+): Pivot points, support/resistance
- **Insider Features** (20+): SEC Form 4 trading data
- **Market Features** (20+): SPY correlations, sector ETFs

Output: `outputs/features/{timestamp}/features.csv`

### Label Creation

`scripts/create_labels.py` supports:
- **Binary**: Price up/down (threshold-based)
- **3-Class**: Strong up / neutral / strong down
- **5-Class**: Quintile-based classification
- **Multiple lookaheads**: 5, 10, 20 days

Output: `outputs/features/{timestamp}/labels.csv`

### Model Training

`scripts/train.py` orchestrates:
1. Data loading and preprocessing
2. Train/validation split (time-based)
3. Hyperparameter tuning (Optuna)
4. Model training with early stopping
5. Evaluation and metrics calculation
6. Model serialization

Output: `outputs/models/{timestamp}/model.pkl` + metrics

### Backtesting

`scripts/backtest.py` implements:
1. **Buy and Hold** - Baseline
2. **ML Signal** - Pure model predictions
3. **Ensemble** - Multiple strategies combined
4. Performance metrics (Sharpe, win rate, max drawdown)

Output: `outputs/backtests/{timestamp}/`

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     Raw Stock Data                            │
│              (PostgreSQL database / CSV)                      │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              Feature Engineering Pipeline                     │
│  Technical │ Swing │ Insider │ Market │ News (optional)      │
│    (50)   │  (30)  │  (20)   │  (20)   │    (0-50)          │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Features CSV (121 columns)                 │
│              outputs/features/{timestamp}/features.csv        │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   Label Creation                              │
│           Binary / 3-Class / 5-Class Labels                  │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Training Pipeline                          │
│    Preprocessing → Split → Tune → Train → Evaluate           │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                 Trained Model + Metrics                       │
│            outputs/models/{timestamp}/model.pkl               │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Backtesting                               │
│   Strategy Simulation → Performance Analysis → Reports       │
└─────────────────────────────────────────────────────────────┘
```

## Design Decisions

### Why CatBoost as Default?
- Best performance (76.7% AUC)
- Native categorical feature handling
- GPU support
- Fast training

### Why Binary Classification Only?
- Binary: 0% catastrophic error (production safe)
- 3-Class: 11.8% catastrophic error (risky)
- 5-Class: 18.4% catastrophic error (not safe)

### Why Archive Instead of Delete?
- Safe reference for historical context
- Can restore if needed
- Zero risk cleanup

### Why YAML Configuration?
- Human-readable
- Supports inheritance
- Environment variable overrides
- Single source of truth

## Performance Characteristics

| Operation | Time | Resources |
|-----------|------|-----------|
| Feature engineering | 10-30 min | CPU, 4GB RAM |
| Label creation | 1-5 min | CPU, 2GB RAM |
| Training (CatBoost) | 5-15 min | GPU (optional), 8GB RAM |
| Hyperparameter tuning | 30-60 min | GPU, 16GB RAM |
| Backtesting | 5-10 min | CPU, 4GB RAM |

## Scaling Considerations

- **Feature caching**: Reuse features across multiple runs
- **Incremental updates**: Only fetch new data
- **GPU acceleration**: CatBoost, XGBoost, TabNet support GPU
- **Parallel processing**: Multi-stock processing
