# ML-Training Refactoring Design

**Date:** 2026-02-12
**Status:** Approved
**Author:** Claude (with user input)

## Overview

Comprehensive cleanup, restructuring, refactoring, and optimization of the ml-training project to improve maintainability, reduce technical debt, and prepare for production deployment.

## Current State

### Strengths
- Solid ML framework with 6 model implementations (CatBoost: 76.7% AUC)
- Complete backtesting framework with 91.9% win rate
- Comprehensive documentation and guides
- Production-ready binary classification pipeline

### Issues Found
- 50+ duplicate files (`scripts_host/` duplicates `scripts/`)
- 24+ obsolete scripts cluttering codebase
- 40+ test datasets wasting disk space
- Outdated documentation (TCN model references)
- Multiple conflicting configuration approaches
- Hard-coded parameters scattered across scripts

## Design

### 1. New Directory Structure

```
ml-training/
├── README.md - Main project overview (streamlined)
├── QUICKSTART.md - 4-step getting started guide
├── CHANGELOG.md - Version history
├── docs/
│   ├── architecture.md - System architecture design
│   ├── training.md - Training guide (consolidated)
│   ├── backtesting.md - Backtesting framework docs
│   ├── configuration.md - Configuration reference
│   └── api.md - API reference
├── ml_framework/ - Core framework (unchanged structure)
├── scripts/ - Core scripts (consolidated)
│   ├── create_features.py - Feature engineering pipeline
│   ├── create_labels.py - Label generation pipeline
│   ├── train.py - Model training orchestration
│   ├── backtest.py - Backtesting pipeline
│   └── utils/ - Shared utilities
├── archive/ - Archived code and data
│   ├── obsolete_scripts/ - All obsolete code
│   ├── old_datasets/ - Old test datasets
│   ├── scripts_host/ - Duplicate directory
│   └── deprecated_docs/ - Old documentation versions
├── configs/ - YAML configuration profiles
│   ├── default.yaml
│   ├── binary_classification.yaml
│   ├── multiclass.yaml
│   └── backtest.yaml
└── outputs/
    ├── models/ - Trained models (by date)
    ├── features/ - Generated features (by date)
    └── backtests/ - Backtesting results
```

### 2. Unified Configuration System

**Default Configuration:**
```yaml
# configs/default.yaml
project:
  name: "ml-training"
  version: "3.0.0"

data:
  base_path: "/home/jakub/StockAnalyzer"
  features_path: "outputs/features"
  models_path: "outputs/models"
  cache_dir: ".cache"

training:
  default_model: "catboost"
  available_models: ["xgboost", "catboost", "tabnet", "autogluon", "fttransformer"]
  test_size: 0.2
  random_seed: 42
  n_trials: 10
  gpu_enabled: true

features:
  technical_indicators: true
  swing_features: true
  insider_features: true
  market_features: true
  news_features: false

labels:
  type: "binary"
  lookahead_days: [5, 10, 20]
  quantiles: 5

backtesting:
  initial_capital: 10000
  commission: 0.001
  strategies: ["buy_and_hold", "ml_signal", "ensemble"]

logging:
  level: "INFO"
  mlflow_tracking: true
  tensorboard: false
```

**Configuration Loading:**
```python
from ml_framework.config import load_config

config = load_config()  # Loads default.yaml or specified profile
# Override with CLI: --config configs/binary_classification.yaml
# Override with env: ML_TRAINING_GPU_ENABLED=false
```

### 3. Modular Scripts Architecture

**Core Scripts:**
- `create_features.py` - Generate 121 features from raw data
- `create_labels.py` - Create binary/3-class/5-class labels
- `train.py` - Train models with hyperparameter tuning
- `backtest.py` - Backtest trained models

**Pipeline:**
```
create_features → create_labels → train → backtest
```

**Shared Utilities (scripts/utils/):**
- `data_loader.py` - Unified data loading
- `feature_cache.py` - Feature caching and versioning
- `model_registry.py` - Model versioning and metadata
- `plotting.py` - Visualization utilities
- `validation.py` - Input validation helpers

### 4. Documentation Consolidation

**Streamlined Root Docs:**
- `README.md` - Reduce from 746 to ~300 lines
- `QUICKSTART.md` - Keep unchanged (working well)
- `CHANGELOG.md` - Keep unchanged (working well)

**Consolidated docs/:**
- `architecture.md` (NEW) - System diagrams and design
- `training.md` (consolidated) - Feature engineering, labels, models, tuning
- `backtesting.md` (existing, updated) - Framework overview
- `configuration.md` (NEW) - YAML and CLI reference
- `api.md` (NEW) - Framework API reference

**Remove from docs:**
- TCN model references (3 locations)
- Duplicate ML guides
- Outdated performance metrics

### 5. Cleanup and Optimization Strategy

**Phase 1: Archive Creation (Safe)**
```bash
mkdir -p archive/{obsolete_scripts,old_datasets,scripts_host,deprecated_docs}

# Move obsolete scripts (24 files)
mv scripts/obsolete/* archive/obsolete_scripts/
mv scripts_host/obsolete/* archive/obsolete_scripts/

# Move duplicate scripts_host
mv scripts_host archive/scripts_host

# Archive old datasets (keep latest 5)
cd outputs/features
ls -t | tail -n +6 | xargs -I {} mv {} ../../../archive/old_datasets/

# Archive old models (keep latest 3)
cd ../models
ls -t | tail -n +4 | xargs -I {} mv {} ../../../archive/old_datasets/
```

**Phase 2: Script Consolidation**
- Remove `scripts_host/` from active codebase
- Archive all `obsolete/` subdirectories
- Standardize shebang lines
- Add type hints and docstrings

**Phase 3: Configuration Migration**
- Create YAML profiles
- Migrate hard-coded parameters
- Update scripts to use `load_config()`

**Phase 4: Documentation Updates**
- Remove TCN references
- Consolidate guides
- Update metrics
- Add diagrams

**Phase 5: Code Quality**
- Add type hints
- Reduce function sizes
- Improve error messages
- Standardize logging

**Expected Disk Recovery: 3-7 GB**

## Implementation Plan

Ready to create detailed implementation plan with git worktree for isolated development.
