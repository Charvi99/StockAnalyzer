# ML-Training Configuration Guide

**Version**: 3.0.0 - Unified Configuration System

---

## Overview

The ML-Training framework uses a hierarchical YAML configuration system with Python dataclasses for type safety. Configurations support inheritance via the `extends:` directive, allowing you to create specialized configs from a base template.

---

## Configuration Files

### 1. `default.yaml` (Base Configuration)

The master configuration file that defines all default values.

**Purpose**: Provides sensible defaults for all components

**Usage**:
```bash
python train.py --config configs/default.yaml
```

**Sections**:

#### Project Metadata
```yaml
project:
  name: "ml-training"           # Project identifier
  version: "3.0.0"              # Version number
  description: "Stock price prediction using machine learning"
```

#### Data Configuration
```yaml
data:
  base_path: "/home/jakub/StockAnalyzer"
  features_path: "ml-training/outputs/features"    # Where to load features from
  models_path: "ml-training/outputs/models"      # Where to save models
  cache_dir: "ml-training/.cache"              # Temporary cache location
```

#### Training Configuration
```yaml
training:
  default_model: "catboost"                  # Default model when none specified
  available_models:                           # Models available for training
    - xgboost
    - catboost
    - tabnet
    - autogluon
    - fttransformer
  test_size: 0.2                             # 20% for testing
  random_seed: 42                              # Reproducibility
  n_trials: 10                                 # Hyperparameter tuning trials
  gpu_enabled: true                            # Enable GPU acceleration
  early_stopping_rounds: 100                   # Stop if no improvement
```

#### Feature Toggles
```yaml
features:
  technical_indicators: true    # RSI, MACD, Bollinger Bands, etc.
  swing_features: true        # MA crossovers, consecutive moves, gaps
  insider_features: true       # SEC Form 4 data (CEO/CFO buys)
  market_features: true        # SPY indicators, market regime
  news_features: false       # News sentiment (requires API)
```

#### Label Configuration
```yaml
labels:
  type: "binary"                # Label type: binary | 3class | 5class
  lookahead_days: [5, 10, 20]  # Days to look ahead for returns
  quantiles: 5                         # Number of quantiles for classification
```

#### Backtesting Configuration
```yaml
backtesting:
  initial_capital: 10000      # Starting capital ($10,000)
  commission: 0.001             # 0.1% per trade
  strategies:
    - buy_and_hold            # Benchmark strategy
    - ml_signal               # Use ML predictions directly
    - ensemble                # Weighted ensemble of models
```

#### Logging Configuration
```yaml
logging:
  level: "INFO"                      # DEBUG | INFO | WARNING | ERROR
  mlflow_tracking: true               # Enable MLflow experiment tracking
  tensorboard: false                   # Enable TensorBoard logging
  log_dir: "ml-training/logs"         # Log file location
```

---

### 2. `binary_classification.yaml` (Binary Classification)

**Purpose**: Optimized configuration for binary buy/sell signal prediction

**Extends**: `default.yaml`

**Overrides**:
```yaml
labels:
  type: "binary"          # Binary: BUY (1) or SELL (0)

training:
  n_trials: 20                     # More trials for binary
  eval_metric: "auc"               # Optimize for AUC

models:
  xgboost:
    learning_rate: 0.01            # Lower learning rate
    max_depth: 6
    n_estimators: 500

  catboost:
    learning_rate: 0.01
    depth: 8
    iterations: 1000
```

**Best For**: Simple buy/sell signals with clear binary outcomes

**Expected Performance**:
- CatBoost: ~76% AUC
- XGBoost: ~75% AUC

---

### 3. `multiclass.yaml` (Multi-Class Classification)

**Purpose**: Configuration for 3-class or 5-class price prediction

**Extends**: `default.yaml`

**Overrides**:
```yaml
labels:
  type: "3class"         # Can be "3class" or "5class"
                              # 3class: STRONG_BUY, HOLD, STRONG_SELL
                              # 5class: VERY_WEAK, WEAK, HOLD, STRONG, VERY_STRONG

training:
  n_trials: 30                     # More trials for complexity
  eval_metric: "multiclass"         # Use multiclass metrics
```

**Best For**: More nuanced predictions with multiple signal strengths

**Expected Performance**:
- 3-Class: ~78% AUC, ~60% accuracy
- 5-Class: ~75% AUC, ~52% accuracy

---

## Model-Specific Configuration

Each model can have its own hyperparameters defined in the YAML:

### XGBoost
```yaml
models:
  xgboost:
    # Fixed parameters (not tuned)
    objective: "binary:logistic"
    eval_metric: "auc"
    tree_method: "hist"              # Fast histogram-based
    device: "cuda"                  # GPU enabled

    # Tunable hyperparameters (search ranges)
    max_depth: (4, 8)                # Tree depth
    learning_rate: (0.001, 0.1)     # Step size shrinkage
    n_estimators: 2000                 # Number of trees
    subsample: (0.6, 0.9)           # Row sampling
    colsample_bytree: (0.6, 0.9)     # Column sampling
    reg_lambda: (0.0, 2.0)           # L2 regularization
    reg_alpha: (0.0, 1.0)            # L1 regularization
    min_child_weight: (1, 10)          # Minimum child weight
    gamma: (0.0, 5.0)                 # Minimum loss reduction
```

### CatBoost
```yaml
models:
  catboost:
    # Fixed parameters
    loss_function: "Logloss"
    eval_metric: "AUC"
    task_type: "GPU"                 # GPU enabled

    # Tunable hyperparameters
    depth: (4, 10)                   # Tree depth
    learning_rate: (0.001, 0.1)      # Step size
    iterations: 2000                   # Number of trees
    l2_leaf_reg: (1.0, 10.0)        # L2 regularization
    bagging_temperature: (0.0, 1.0)    # Bagging randomness
    border_count: (32, 255)             # Number of splits
    random_strength: (0.0, 2.0)        # Feature randomness
```

### TabNet
```yaml
models:
  tabnet:
    # Architecture
    n_d: 8                             # Decision step width
    n_a: 8                             # Attention step width
    n_steps: 3                          # Number of decision steps

    # Tunable
    n_d_range: (4, 16)
    n_a_range: (4, 16)
    n_steps_range: (1, 5)
    gamma: 1.5                           # Sparsity loss
    lambda_sparse: 1e-4                 # Sparsity regularization
```

### AutoGluon
```yaml
models:
  autogluon:
    # AutoML settings
    time_limit: 3600                    # 1 hour training
    presets: "high_quality"              # Quality vs speed tradeoff

    # Model inclusion
    included_models:
      - XGBoost
      - CatBoost
      - LightGBM
      - RandomForest
```

### FT-Transformer
```yaml
models:
  fttransformer:
    # Architecture
    d_model: 32                         # Embedding dimension
    n_heads: 2                          # Attention heads
    n_layers: 2                         # Transformer layers

    # Tunable
    d_model_range: (16, 64)
    n_heads_range: (1, 4)
    n_layers_range: (1, 4)
```

---

## Configuration Inheritance

The system supports YAML inheritance using the `extends:` directive:

```yaml
# my_config.yaml
extends: configs/default          # Inherit all defaults

training:
  n_trials: 50                    # Override just n_trials

models:
  xgboost:
    learning_rate: 0.005           # Override XGBoost LR
```

This creates a new config that:
1. Loads all defaults from `default.yaml`
2. Overrides specific sections
3. Keeps all other defaults unchanged

---

## CLI Overrides

Command-line arguments override YAML config:

```bash
# Override model selection
python train.py --config configs/default.yaml --models xgboost,catboost

# Override tuning trials
python train.py --config configs/default.yaml --tuning-trials 50

# Skip tuning
python train.py --config configs/default.yaml --no-tuning

# Override ensemble method
python train.py --config configs/default.yaml --ensemble-method stacking
```

---

## Environment Variable Overrides

Configuration can be overridden via environment variables:

```bash
# Disable GPU
export ML_TRAINING_GPU_ENABLED=false

# Increase trials
export ML_TRAINING_N_TRIALS=100

# Change log level
export ML_TRAINING_LOG_LEVEL=DEBUG

# Run with overrides
python train.py --config configs/default.yaml
```

---

## Label Types Explained

### Binary Classification
```yaml
labels:
  type: "binary"
```
- **Classes**: 2 (BUY=1, SELL=0)
- **Use Case**: Simple directional predictions
- **Threshold**: Positive return = BUY
- **Best For**: Trading strategies needing clear signals

### 3-Class Classification
```yaml
labels:
  type: "3class"
```
- **Classes**: 3 (STRONG_BUY=2, HOLD=1, STRONG_SELL=0)
- **Use Case**: Moderate predictions with neutral zone
- **Thresholds**:
  - Top 20% = STRONG_BUY
  - Bottom 20% = STRONG_SELL
  - Middle 60% = HOLD
- **Best For**: Filtering weak signals

### 5-Class Classification
```yaml
labels:
  type: "5class"
```
- **Classes**: 5 (VERY_STRONG=4, STRONG=3, MODERATE=2, WEAK=1, VERY_WEAK=0)
- **Use Case**: Fine-grained predictions
- **Quantiles**: 5 quintiles (20% each)
- **Best For**: Position sizing based on signal strength

---

## Feature Toggles

Control which feature groups are used:

```yaml
features:
  technical_indicators: true    # ~60 features (RSI, MACD, BB, ATR, Stochastic, etc.)
  swing_features: true        # ~15 features (MA crosses, consecutive moves, gaps)
  insider_features: true       # ~12 features (Form 4 cluster buying)
  market_features: true        # ~10 features (SPY MAs, market regime)
  news_features: false       # ~9 features (sentiment analysis)
```

**Total Features** (with all enabled): ~106 features

**Benefits**:
- Disable features for faster experimentation
- Test feature group importance
- Reduce memory footprint

---

## Common Configurations

### Quick Test (Fast)
```yaml
training:
  n_trials: 3
  gpu_enabled: false

features:
  news_features: false
  insider_features: false
```

### Production (High Quality)
```yaml
training:
  n_trials: 50
  gpu_enabled: true

features:
  technical_indicators: true
  swing_features: true
  insider_features: true
  market_features: true
```

### Research (Maximum)
```yaml
training:
  n_trials: 100
  early_stopping_rounds: 200

features:
  news_features: true
```

---

## Troubleshooting

### Out of Memory (GPU)
```yaml
training:
  gpu_enabled: false          # Switch to CPU
  n_trials: 5                 # Reduce trials

models:
  xgboost:
    n_estimators: 500         # Fewer trees
```

### Training Too Slow
```yaml
training:
  n_trials: 10                # Fewer trials
  timeout: 1800               # 30 min timeout

models:
  catboost:
    task_type: "CPU"        # Switch to CPU
```

### Overfitting
```yaml
training:
  early_stopping_rounds: 50    # Stop earlier
  test_size: 0.3                 # More validation data

models:
  xgboost:
    max_depth: (3, 5)           # Simpler trees
    reg_lambda: (1.0, 5.0)       # More regularization
```

---

## Config Validation

The framework automatically validates configs on load:

- ✅ Checks data types (int, float, bool, etc.)
- ✅ Validates file paths exist
- ✅ Ensures label type is valid
- ✅ Verifies model names are recognized
- ✅ Detects Docker environment

If config is invalid, training will fail with a clear error message.

---

## Best Practices

1. **Start with defaults**: Use `default.yaml` as baseline
2. **Create task-specific configs**: Extend defaults, don't modify
3. **Version control configs**: Track changes in git
4. **Document experiments**: Save configs that work well
5. **Use inheritance**: Avoid duplication via `extends:`
6. **Test small first**: Low `n_trials` for quick feedback
7. **Scale up gradually**: Increase trials when promising

---

## Example: Creating Custom Config

```yaml
# configs/my_experiment.yaml
extends: configs/default

# My experiment: High-depth XGBoost
training:
  n_trials: 25
  gpu_enabled: true

labels:
  type: "binary"

models:
  xgboost:
    max_depth: (8, 12)           # Deeper trees
    learning_rate: (0.005, 0.05)  # Lower LR

features:
  news_features: false          # Disable news (slow)
```

Run with:
```bash
python train.py --config configs/my_experiment.yaml --models xgboost
```

---

**Last Updated**: 2026-02-12
**Config Version**: 3.0.0
