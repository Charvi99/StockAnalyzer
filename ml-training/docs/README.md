# ML Training Scripts

This directory contains data preparation and training scripts for the StockAnalyzer ML pipeline.

**IMPORTANT**: This is now a **UNIFIED PIPELINE** with single scripts for each task. No more duplicate or obsolete scripts in active use.

---

## 🎯 NEW: Dataset Folder Organization

Datasets are now organized in folders for easy comparison between classification types:

```
outputs/features/
├── dataset_20260204_185139/              ← One folder per dataset
│   ├── features.parquet                   ← The features (186 MB)
│   ├── labels_binary.parquet              ← Binary labels
│   ├── labels_3class.parquet              ← 3-class labels
│   ├── labels_5class.parquet              ← 5-class labels
│   └── metadata.json                      ← Dataset info
├── dataset_20260205_100000/
│   ├── features.parquet
│   └── labels_binary.parquet              ← Maybe only binary for this run
└── obsolete/                              ← Old datasets (legacy format)
    ├── features_swing_*.parquet
    └── labels_*.parquet
```

**Benefits:**
- All related files in one place
- Easy to compare binary vs 3class vs 5class on SAME features
- Train script auto-detects available label types
- Cleaner organization

---

## Core Scripts

### 1. Feature Engineering: `feature_engineering.py`

**Purpose**: THE SINGLE feature engineering script for the entire ML pipeline.

**Features Created** (~121 total):
- **Price & Returns** (15): OHLCV, returns, log returns, price momentum
- **Technical Indicators** (60+): RSI, MACD, Bollinger Bands, ATR, Stochastic, etc.
- **Swing Trading Features** (15): MA crossovers, price vs MA, consecutive up/down days, gaps
- **Market Context** (10): SPY moving averages, market regime, volatility regime
- **Insider Trading** (12): SEC Form 4 data (CEO/CTO/CFO buys, cluster buying, etc.)
- **Alternative Data** (9): Congressional trading, off-exchange volume, WSB activity

**Removed** (low importance):
- Harmonic indicators: mama, fama, tema, t3, trix
- Hilbert transforms: ht_trendline, ht_dcperiod, etc.
- Stochastic RSI: stochrsi_k, stochrsi_d
- **Frontend-only features**: All `*_signal` (BUY/SELL/HOLD strings) and `*_reason` columns
  - NOTE: `macd_signal` is KEPT - it's the numeric MACD signal line, not a categorical signal

**Usage**:
```bash
# Run inside Docker container
docker exec -it stockanalyzer-ml-1 python scripts/feature_engineering.py
```

**Output**: `/app/outputs/features/dataset_YYYYMMDD_HHMMSS/features.parquet`

**Notes**:
- Creates a new dataset folder with timestamp
- Saves `features.parquet` and `metadata.json` inside
- Processes all tracked stocks (skips ETFs)
- Automatically filters out frontend-only features
- No embedded labels (separation of concerns)
- ~185 MB file size

---

### 2. Label Creation: `create_labels.py`

**Purpose**: THE SINGLE label creation script supporting all classification types.

**Classification Types**:

#### Binary Classification
**Usage**:
```bash
python scripts/create_labels.py --type binary --dataset-folder dataset_20260204_185139
```

**Parameters** (optional):
- `--profit-target 0.03` - Profit target (default: +3%)
- `--stop-loss -0.02` - Stop loss (default: -2%)
- `--lookahead 20` - Days to look ahead (default: 20)
- `--dataset-folder <folder>` - Dataset folder name (auto-detects latest if not specified)

**Label Strategy**:
- Target: +3% profit within 20 days before hitting -2% stop loss
- Binary: BUY (1) or DON'T BUY (0)
- Based on max upside, not final return

**Example**:
```bash
# Use auto-detected dataset folder
python scripts/create_labels.py --type binary

# Use specific dataset folder
python scripts/create_labels.py --type binary --dataset-folder dataset_20260204_185139

# Custom parameters
python scripts/create_labels.py --type binary --profit-target 0.05 --stop-loss -0.03 --lookahead 30
```

#### 3-Class Classification
**Usage**:
```bash
python scripts/create_labels.py --type 3class --dataset-folder dataset_20260204_185139
```

**Parameters** (optional):
- `--sell-threshold -0.05` - Sell threshold (default: -5%)
- `--buy-threshold 0.05` - Buy threshold (default: +5%)
- `--lookaheads 20 30 40` - Multiple timeframes (default: all three)

**Label Strategy**:
- Uses final return approach
- SELL: return < -5%
- HOLD: -5% to +5%
- BUY: return > +5%
- Multi-timeframe: 20d, 30d, 40d

**Output**: Saves to `dataset_folder/labels_3class.parquet`

#### 5-Class Classification
**Usage**:
```bash
python scripts/create_labels.py --type 5class --dataset-folder dataset_20260204_185139
```

**Parameters** (optional):
- `--strong-sell-threshold -0.10` - Strong sell threshold (default: -10%)
- `--sell-threshold -0.05` - Sell threshold (default: -5%)
- `--buy-threshold 0.05` - Buy threshold (default: +5%)
- `--strong-buy-threshold 0.10` - Strong buy threshold (default: +10%)
- `--lookaheads 20 30 40` - Multiple timeframes (default: all three)

**Label Strategy**:
- Uses final return with risk penalty
- Score = Final Return (%) - 0.3 * |Max Drawdown| (if < -3%)
- STRONG SELL: score ≤ -10%
- SELL: -10% < score ≤ -5%
- HOLD: -5% < score ≤ +5%
- BUY: +5% < score ≤ +10%
- STRONG BUY: score > +10%

**Output**: Saves to `dataset_folder/labels_5class.parquet`

**Common Parameters**:
- `--days 1825` - Number of days of history (default: 5 years)

---

### 3. Model Training: `train.py`

**Purpose**: THE SINGLE training script for all models and classification types.

**Dataset Folder Mode (RECOMMENDED)**:
```bash
# Auto-detect latest dataset folder and label type
python train.py

# Use specific dataset folder
python train.py --dataset-folder dataset_20260204_185139

# Specify label type (if multiple available)
python train.py --dataset-folder dataset_20260204_185139 --label-type binary
python train.py --dataset-folder dataset_20260204_185139 --label-type 5class
```

**Model Selection**:
```bash
# Train all models with default settings
python train.py

# Train specific models
python train.py --models xgboost catboost

# Skip TCN (memory issues)
python train.py --skip-tcn

# Use Polars for faster loading
python train.py --use-polars

# Custom number of trials
python train.py --trials 50

# Skip hyperparameter tuning
python train.py --no-tune
```

**Legacy Mode (individual file paths)**:
```bash
# Use specific feature/label files
python train.py --data-path outputs/features/features_20260203.parquet
python train.py --labels-path outputs/features/labels_binary_20260203.parquet

# Use specific label column (for multi-class)
python train.py --label-column label_20d --num-classes 3

# Use 5-class labels
python train.py --labels-path labels_5class_*.parquet --label-column label_20d --num-classes 5
```

**Confidence Threshold Analysis**:
```bash
# Custom thresholds
python train.py --confidence-thresholds 0.5 0.6 0.7 0.8 0.9
```

**Full Example**:
```bash
# Train XGBoost and CatBoost with 5-class labels, 50 trials
python train.py \
  --dataset-folder dataset_20260204_185139 \
  --label-type 5class \
  --models xgboost catboost \
  --trials 50 \
  --confidence-thresholds 0.5 0.6 0.7 0.8
```

**Output Interpretation**:

The training script produces comprehensive output:

1. **Per-Model Performance**:
   - Accuracy, Precision, Recall, AUC
   - Confusion Matrix (for ALL classification types)
   - Error Severity Analysis

2. **Confidence Threshold Analysis**:
   - Shows performance at different confidence levels
   - Coverage: % of predictions above threshold
   - Precision: How many confident predictions are correct
   - Catastrophic Error Rate: How many bad predictions

3. **Ensemble Performance**:
   - Combines all trained models
   - Uses stacking with XGBoost meta-learner (default)
   - Shows combined performance metrics

**Example Output** (3-Class):
```
======================================================================
CONFUSION MATRIX ANALYSIS
======================================================================

──────────────────────────────────────────────────────────────────────
XGBOOST - Error Analysis
──────────────────────────────────────────────────────────────────────

Confusion Matrix (Actual rows → Predicted columns):
               SELL        HOLD       BUY
SELL            8500       1200        300
HOLD            1500      45000       2500
BUY              300       1800      7200

Error Severity Analysis:
Predicted    → Actual      =    Count        Cost        Severity
SELL         → HOLD       =     1500       6.02%     ✅ Acceptable
SELL         → BUY        =       300      16.56%     ⚠️  Moderate
BUY          → HOLD       =     1800       6.50%     ✅ Acceptable
BUY          → SELL       =       300      22.28%     ❌ Catastrophic
...
```

---

## Pipeline Execution Order

The standard ML pipeline follows this order:

### 1. Feature Engineering
```bash
python scripts/feature_engineering.py
```
**Output**: `dataset_YYYYMMDD_HHMMSS/` folder containing:
- `features.parquet` (~121 features, 186 MB)
- `metadata.json` (dataset info)

### 2. Label Creation (one or more types)
```bash
# Binary (for simple buy/don't buy decisions)
python scripts/create_labels.py --type binary --dataset-folder dataset_20260204_185139

# 3-Class (simplified multi-class)
python scripts/create_labels.py --type 3class --dataset-folder dataset_20260204_185139

# 5-Class (full granularity with risk penalty)
python scripts/create_labels.py --type 5class --dataset-folder dataset_20260204_185139
```
**Output**: Saves to `dataset_folder/labels_*.parquet`

### 3. Model Training
```bash
# Auto-detect latest dataset and label type
python train.py

# Or specify explicitly
python train.py --dataset-folder dataset_20260204_185139 --label-type binary

# Compare different label types on SAME dataset:
python train.py --dataset-folder dataset_20260204_185139 --label-type binary --models xgboost --trials 25
python train.py --dataset-folder dataset_20260204_185139 --label-type 3class --models xgboost --trials 25
python train.py --dataset-folder dataset_20260204_185139 --label-type 5class --models xgboost --trials 25
```

---

## Troubleshooting

### "No feature files found"
**Solution**: Run feature engineering first
```bash
python scripts/feature_engineering.py
```

### "No label files found"
**Solution**: Run label creation after feature engineering
```bash
python scripts/create_labels.py --type binary  # or 3class or 5class
```

### "Database connection error"
**Solution**: Ensure database is running
```bash
docker-compose up -d database
```

### "Out of memory" (TCN issues)
**Solution**: Skip TCN or use chunked sequences
```bash
python train.py --skip-tcn
```

### "ModuleNotFoundError: No module named 'pandas'"
**Solution**: Run inside Docker container, not on host
```bash
docker exec -it stockanalyzer-ml-1 python scripts/feature_engineering.py
```

### Low Model Performance
**Possible causes**:
1. **Label quality**: Binary labels have weak signal (55% never hit +3% target)
   - **Solution**: Use 5-class labels for better granularity

2. **Feature leakage**: Features contain future information
   - **Solution**: Ensure all features use only historical data

3. **Overfitting**: Model memorizing training data
   - **Solution**: Increase trials, use more regularization

4. **Class imbalance**: One class dominates
   - **Solution**: Use 5-class labels, adjust class weights

---

## Obsolete Scripts

The `scripts/obsolete/` directory contains older scripts that have been superseded. **Do not use these**.

### Moved to Obsolete (2026-02-04):
**Feature Engineering** (14 scripts):
- `01_feature_engineering.py` - Original version
- `01b_*, 01c_*, 01d_*` - Early iterations
- `01e_*` - Log returns version
- `01f_*` - No data leakage version
- `01h_*` - 28-feature version
- `01i_*` - With insider features
- `01j_*` - With congressional features
- `01k_*` - 40-feature with Form 4
- `01l_feature_engineering_40features_simplified.py` - 40-feature simplified
- `feature_engineering.py` - Old version with embedded labels
- `feature_engineering_clean.py` - Unknown purpose
- `feature_engineering_swing.py` - Source script (copied to new unified version)

**Label Creation** (3 scripts):
- `create_labels.py` - Old binary-only version
- `02_create_labels.py` - Binary labels (old)
- `create_multiclass_labels.py` - 5-class labels (old)
- `convert_to_3class.py` - 3-class converter (utility)

**Training** (2 scripts):
- `03_train_xgboost.py` - Use `train.py` instead
- `train_40features.py` - Use `train.py` instead

**Analysis** (1 script):
- `analyze_multi_timeframe_correlation.py` - Timeframe correlation analysis

### Active Scripts (Only 5 core scripts + 1 init):
**Core Pipeline** (3 scripts):
- `feature_engineering.py` - **NEW unified version** (121 features)
- `create_labels.py` - **NEW unified version** (binary/3class/5class)
- `backtest_labels.py` - Label backtesting utility

**Analysis** (2 scripts):
- `analyze_feature_importance.py` - Feature importance analysis
- `analyze_model_predictions.py` - Model prediction analysis

**Other**:
- `__init__.py` - Python package init file

---

## Feature Importance

Based on recent training runs with 121 features:

### Top Features (Most Important):
1. **Market Context** (dominates):
   - SPY MA 50/200/20 day crossovers
   - Market regime indicators
   - SPY trend strength

2. **Basic Technical Indicators**:
   - RSI
   - MACD
   - ATR (volatility)

3. **Price Momentum**:
   - Returns (1d, 5d, 20d)
   - Price vs MA distance

### Low Importance Features (<0.5%):
- 77 features have minimal predictive power
- Could be removed for faster training
- Consider feature selection for production

### Insider Trading Features:
- **Mixed results**:
  - Sell-side features: Predictive (insiders selling = bearish)
  - Buy-side features: Zero importance (possible data quality issue)
  - Cluster buying: Some predictive power

---

## Model Performance Baselines

### Binary Classification (121 features, 25 trials):
- **XGBoost**: 74.0% AUC
- **CatBoost**: 72.6% AUC
- **Ensemble**: 73.7% AUC
- **Precision**: ~64%
- **Recall**: ~24%

### 3-Class Classification (Expected):
- Target: ~70% accuracy
- Better class separation than binary

### 5-Class Classification (Expected):
- Target: ~70-75% validation accuracy
- Best granularity for swing trading
- Handles edge cases better

---

## Related Documentation

- [Main README](../README.md)
- [TODO.md](../TODO.md) - Active development tasks
- [CHANGELOG.md](../CHANGELOG.md) - Recent changes
- [Architecture Documentation](../docs/architecture.md)

---

## Quick Reference

### File Locations:
- **Datasets**: `/app/outputs/features/dataset_*/` (folder-based organization)
  - `features.parquet` - Feature data
  - `labels_binary.parquet` - Binary labels
  - `labels_3class.parquet` - 3-class labels
  - `labels_5class.parquet` - 5-class labels
  - `metadata.json` - Dataset metadata
- **Models**: `/app/outputs/models/` (trained models)
- **Logs**: `/app/training-logs/`

### Host Filesystem Access (via shared folder):
- **Datasets**: `/home/jakub/StockAnalyzer/ml-training/outputs/features/dataset_*/`
- **Models**: `/home/jakub/StockAnalyzer/ml-training/outputs/models/`

### Environment Variables:
- `DATABASE_URL` - PostgreSQL connection string
- `GPU_MEMORY_LIMIT` - Max GPU memory (GB)
- `USE_GPU` - Enable GPU training (true/false)

### Docker Commands:
```bash
# Start ML container
docker-compose up -d ml

# Run script in container
docker exec -it stockanalyzer-ml-1 python train.py

# View logs
docker logs -f stockanalyzer-ml-1

# Stop container
docker-compose stop ml
```
