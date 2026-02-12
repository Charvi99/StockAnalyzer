# Configuration Reference

The ML-Training project uses YAML configuration files for all settings.

## Configuration Files

Location: `configs/`

- `default.yaml` - Base configuration
- `binary_classification.yaml` - Binary buy/sell prediction
- `multiclass.yaml` - Multi-class prediction

## Usage

### Loading Configuration

```python
from ml_framework.config import load_config

# Load default config
config = load_config()

# Load specific config
config = load_config('configs/binary_classification.yaml')

# Access values
model = config['training']['default_model']
gpu_enabled = config['training']['gpu_enabled']
```

### Command Line Override

```bash
# Use specific config file
python scripts/train.py --config configs/binary_classification.yaml

# Override specific values
python scripts/train.py --model xgboost --n-trials 5
```

### Environment Variable Override

```bash
# Format: ML_TRAINING_<SECTION>__<KEY>
export ML_TRAINING_GPU_ENABLED=false
export ML_TRAINING_N_TRIALS=20
export ML_TRAINING_LABELS__TYPE=binary

python scripts/train.py
```

## Configuration Schema

### Project

```yaml
project:
  name: "ml-training"           # Project name
  version: "3.0.0"              # Version
  description: "..."            # Description
```

### Data Paths

```yaml
data:
  base_path: "/path/to/project"     # Base project directory
  features_path: "outputs/features"  # Relative to base_path
  models_path: "outputs/models"
  cache_dir: ".cache"
```

### Training

```yaml
training:
  default_model: "catboost"          # Default model to use
  available_models:                   # Available model types
    - "xgboost"
    - "catboost"
    - "tabnet"
    - "autogluon"
  test_size: 0.2                     # Validation set ratio
  random_seed: 42                    # Random seed for reproducibility
  n_trials: 10                       # Hyperparameter tuning trials
  gpu_enabled: true                  # Use GPU if available
  early_stopping_rounds: 100         # Early stopping patience
```

### Features

```yaml
features:
  technical_indicators: true    # 50+ RSI, MACD, etc.
  swing_features: true          # 30+ pivot points, S/R
  insider_features: true        # 20+ SEC Form 4 data
  market_features: true         # 20+ SPY, sector ETFs
  news_features: false          # Optional, requires API
```

### Labels

```yaml
labels:
  type: "binary"               # binary | 3class | 5class
  lookahead_days: [5, 10, 20]   # Prediction horizons
  quantiles: 5                 # For quantile-based labels
```

### Backtesting

```yaml
backtesting:
  initial_capital: 10000        # Starting capital
  commission: 0.001            # Trading commission (0.1%)
  strategies:                  # Available strategies
    - "buy_and_hold"
    - "ml_signal"
    - "ensemble"
```

### Logging

```yaml
logging:
  level: "INFO"                # DEBUG | INFO | WARNING | ERROR
  mlflow_tracking: true        # Enable MLflow logging
  tensorboard: false           # Enable TensorBoard
  log_dir: "logs"              # Log directory
```

## Configuration Inheritance

Configs can extend other configs using `extends` field:

```yaml
# binary_classification.yaml
extends: default

labels:
  type: "binary"

training:
  n_trials: 20
```

This loads `default.yaml` and overrides specific values.

## Model-Specific Configuration

Each model can have specific hyperparameters:

```yaml
models:
  xgboost:
    learning_rate: 0.01
    max_depth: 6
    n_estimators: 500

  catboost:
    learning_rate: 0.01
    depth: 8
    iterations: 1000
```

## Priority Order

Configuration values are applied in this order (later overrides earlier):

1. Base YAML config (e.g., `default.yaml`)
2. Extended YAML config (if using `extends`)
3. Environment variables (`ML_TRAINING_*`)
4. Command-line arguments

## Examples

### Quick Development Iteration

```yaml
# configs/dev.yaml
extends: default

training:
  n_trials: 3              # Fast iteration
  gpu_enabled: false       # Use CPU

logging:
  level: "DEBUG"           # Verbose logging
```

Usage: `python scripts/train.py --config configs/dev.yaml`

### Production Training

```yaml
# configs/production.yaml
extends: binary_classification

training:
  n_trials: 50             # Thorough search
  gpu_enabled: true        # Use GPU

logging:
  level: "INFO"
  mlflow_tracking: true    # Track experiments
```

Usage: `python scripts/train.py --config configs/production.yaml`

### CPU-Only Environment

```bash
export ML_TRAINING_GPU_ENABLED=false
python scripts/train.py
```
