# StockAnalyzer ML Training - TODO

**Active development tasks and future improvements**

Hardware: RTX 3060 12GB, i7-7700K, 32GB RAM

---

## Priority 1 - High Priority

### ✅ MODEL CLASSIFICATION COMPARISON (2026-02-04)

**COMPLETED**: Comprehensive 10-trial comparison across binary, 3-class, and 5-class classification

**Results Summary**:
- **Binary (PRODUCTION READY)**: 76.8% AUC, 0% catastrophic error ✅
- **3-Class (RISKY)**: 78.0% AUC, 11.8% catastrophic error ⚠️
- **5-Class (NOT SAFE)**: 75.4% AUC, 18.4% catastrophic error ❌

**Critical Findings**:
1. **Stacking ensemble breaks multi-class**:
   - 3-class: Accuracy drops 60.2% → 49.5%
   - 5-class: Accuracy drops 52.4% → 36.6%
   - Meta-learner collapses to predicting HOLD for everything
   - **Solution**: Use `weighted_average` or CatBoost alone

2. **CatBoost > XGBoost consistently**:
   - Better AUC across all types
   - Better precision-recall tradeoff
   - More stable training

3. **Binary is only safe option**:
   - 0% catastrophic error at all thresholds
   - Confidence threshold 0.7 = 81.1% precision
   - Multi-class has 11-18% catastrophic error

**Documentation**: `docs/RESULTS_2026-02_04.md`

**Next Steps**:
- Try `weighted_average` ensemble instead of `stacking` for multi-class
- Increase trials to 50-100 for better hyperparameters
- Focus on binary for production use

---

### ✅ ML PIPELINE CLEANUP & STANDARDIZATION (2026-02-04)

**PROBLEM**: Multiple duplicate scripts, inconsistent label schemes, missing evaluation output
**SOLUTION**: Unify scripts, fix train.py output, create single source of truth

**Tasks**:

#### 1. Cleanup Obsolete Scripts
**Files to DELETE**:
- `scripts/create_labels.py` (duplicate of 02_create_labels.py)
- `scripts/feature_engineering.py` (has embedded labels, use swing version instead)
- `scripts/feature_engineering_clean.py` (unknown purpose)
- `scripts/01l_feature_engineering_40features_simplified.py` (old version)
- `scripts/obsolete/` (entire directory - 10+ obsolete scripts)

**Command**:
```bash
cd /home/jakub/StockAnalyzer/ml-training
rm scripts/create_labels.py
rm scripts/feature_engineering.py
rm scripts/feature_engineering_clean.py
rm scripts/01l_feature_engineering_40features_simplified.py
rm -rf scripts/obsolete/
```

#### 2. Create Unified Feature Engineering Script
**Current State**: `scripts/feature_engineering_swing.py` (has correct filtering)
**Goal**: Make this THE SINGLE feature engineering script

**Requirements**:
- No embedded labels (separate concerns)
- No string signal/reason columns (BUY/SELL/HOLD strings)
- Include all swing trading features
- Include insider trading features ("secret weapon")
- Include market context features (SPY data)
- Filter out frontend-only features automatically

**Output**: `features_swing_YYYYMMDD_HHMMSS.parquet`
**Features**: ~120 features (OHLCV + indicators + swing + insider + market context)

**File**: `scripts/feature_engineering.py` (replace existing)

#### 3. Create Unified Label Creator Script
**Current State**: Multiple label scripts (binary, 3-class, 5-class)
**Goal**: ONE script with `--type` argument

**Requirements**:
```bash
scripts/create_labels.py --type binary|3class|5class [options]

Binary:
  --type binary
  --profit-target 0.03    # +3%
  --stop-loss -0.02         # -2%
  --lookahead 20           # days

3-Class:
  --type 3class
  --sell-threshold -0.05   # -5%
  --buy-threshold 0.05      # +5%
  --lookaheads 20 30 40    # multi-timeframe

5-Class:
  --type 5class
  --strong-sell-threshold -0.10    # ≤ -10%
  --sell-threshold -0.05              # -10% to -5%
  --buy-threshold 0.05                # +5% to +10%
  --strong-buy-threshold 0.10        # > +10%
  --lookaheads 20 30 40              # multi-timeframe
```

**Output**: `labels_[type]_YYYYMMDD_HHMMSS.parquet`

**File**: `scripts/create_labels.py` (replace all existing)

#### 4. Fix train.py Evaluation Output
**Problem**: Missing confusion matrix and confidence threshold analysis for binary classification

**Required Output** (for ALL classification types):
```
======================================================================
CONFUSION MATRIX ANALYSIS
======================================================================

Analyzing prediction errors to determine model usability...

──────────────────────────────────────────────────────────────────────
XGBOOST - Error Analysis
──────────────────────────────────────────────────────────────────────

Confusion Matrix (Actual rows → Predicted columns):
               DON'T BUY   BUY
DON'T BUY      57000       20025
BUY            12000       27575

Error Severity Analysis:
Predicted    → Actual      =    Count        Cost        Severity
BUY          → DON'T BUY   =     12000     -3.00%     ✅ Acceptable
DON'T BUY    → BUY         =     20025     +3.00%     ✅ Acceptable

======================================================================
ERROR SUMMARY:
  Total Errors:     32,025
  ✅ Acceptable:     32,025 (100.0%)
  ⚠️  Moderate:      0 (0.0%)
  ❌ Catastrophic:   0 (0.0%)

Catastrophic Error Rate: 0.00%
  ✅ MODEL IS SAFE for trading

──────────────────────────────────────────────────────────────────────
XGBOOST - Confidence Threshold Analysis
──────────────────────────────────────────────────────────────────────

Threshold    Coverage     Precision    Recall       F1
────────────────────────────────────────────────────────────────────────
0.50         33.9%        65.1%        46.2%        54.3%
0.60         12.8%        72.3%        31.5%        43.7%
0.70         3.2%         81.5%        15.9%        26.4%

RECOMMENDATIONS:
✅ Best for Safety: Threshold 0.70 (Precision: 81.5%)
🎯 Best Balance: Threshold 0.50 (Coverage: 33.9%)
📊 Best for Precision: Threshold 0.70 (Precision: 81.5%)

──────────────────────────────────────────────────────────────────────
ENSEMBLE CREATION
======================================================================

ENSEMBLE PERFORMANCE:
  Accuracy:  73.6%
  Precision: 64.1%
  Recall:    24.3%
  AUC:       73.7%
```

**File**: `train.py` (add binary analysis section, fix CLASS_NAMES for all types)

#### 5. Document Everything in scripts/readme.md
**Sections to add**:
- Feature engineering script usage
- Label creation script usage (all types)
- Training script usage (with examples)
- Output interpretation guide
- Troubleshooting common issues

**File**: `scripts/readme.md`

**Estimated Effort**: 4-6 hours
**Priority**: HIGH - This blocks further development

---

### [ ] ATR-Adjusted Multi-Class Labels with Multiple Lookaheads
**PROBLEM**: Current binary labels have weak signal (55.7% samples never hit +3% target)
**SOLUTION**: Implement rich multi-timeframe, multi-class labeling system

**Architecture**:
```
5 Classes × 3 Timeframes = 15 label combinations
┌─────────────────────────────────────────────────────────────────┐
│                    Timeframes (lookahead)                    │
├──────────────┬──────────────┬──────────────┬──────────────┬──────────────┤
│ Classes      │ 20 days       │ 30 days       │ 40 days       │
├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ STRONG SELL  │ ≤ -2×ATR     │ ≤ -2.5×ATR    │ ≤ -3×ATR     │
│ SELL        │ -2×ATR to -1×ATR│ -2.5×ATR to   │ -3×ATR to     │
│              │               │ -1×ATR      │ -2×ATR       │
│ HOLD        │ Between -1×ATR │ Between -1×ATR │ Between -2×ATR │
│              │ and +1×ATR    │ and +1.25×ATR│ and +1.5×ATR │
│ BUY         │ +1×ATR to     │ +1.25×ATR to   │ +1.5×ATR to   │
│              │ +2×ATR        │ +2.5×ATR     │ +3×ATR       │
│ STRONG BUY   │ > +2×ATR      │ > +2.5×ATR    │ > +3×ATR     │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

**Implementation Options**:

**Option A: Separate Models per Timeframe (Recommended)**
- Train 3 independent models (20d, 30d, 40d)
- Each predicts 5 classes
- Ensemble voting across timeframes
- Pros: Simpler, faster training, interpretable
- Cons: More models to manage, no temporal learning

**Option B: Multi-Output Model (Advanced)**
- Single model with 15 outputs (5 classes × 3 timeframes)
- Shared feature extractor, separate heads
- Pros: Learns temporal relationships, single model
- Cons: Complex, harder to train, harder to interpret

**Option C: Hierarchical (Time → Class)**
- First predict "optimal timeframe"
- Then predict class for that timeframe
- Pros: Efficient, learns to choose best horizon
- Cons: More complex, error propagation

**Benefits**:
- ✅ Better class separation (5 classes vs 2)
- ✅ Volatility-aware (ATR-adjusted)
- ✅ Multiple trading horizons (swing to position)
- ✅ Learns "momentum building" (BUY → STRONG BUY over time)
- ✅ More realistic (most days = HOLD, not binary)

**Files to Create**:
- `scripts/create_multiclass_labels.py` - ATR-based multi-timeframe labels
- `ml_framework/models/multiclass_tcn.py` - TCN for 5-class output
- `ml_framework/ensemble.py` - Ensemble across timeframes
- `ml_framework/config.py` - Add MultiClassConfig section

**Estimated Distribution**:
- HOLD: 40-50% (most common - "do nothing")
- BUY: 15-20% (moderate signal)
- SELL: 15-20% (moderate weakness)
- STRONG BUY: 5-10% (strong momentum)
- STRONG SELL: 5-10% (strong breakdown)

**Status**: Design phase
**Priority**: High - This could dramatically improve model performance
**Estimated Effort**: 8-12 hours (implementation + testing)

### [ ] Integration Test Script
Create `scripts/test_integration.sh` that validates the entire ML pipeline:
- Run feature engineering on small subset
- Create labels
- Train XGBoost with 3 trials (smoke test)
- Verify model outputs
- Test ensemble creation
- Should complete in under 10 minutes

**Status**: Pending
**File**: `scripts/test_integration.sh`

### [ ] Test Training with New GPU Drivers
After installing new GPU drivers, test the training pipeline:

```bash
# Quick smoke test - XGBoost and CatBoost only (no TCN)
python train.py --models xgboost catboost --trials 5 --no-tune

# Full test with TCN to verify memory fix
python train.py --models xgboost catboost tcn --trials 5
```

**Verify**:
- GPU is properly detected (RTX 3060 12GB)
- XGBoost and CatBoost train without errors
- TCN doesn't freeze system (chunked sequences fix)
- Models save correctly
- Expected time: 15-30 minutes

**Status**: Pending - waiting for system reboot after driver installation


---

## Priority 2 - Medium Priority

### [ ] Full Polars Migration
Migrate entire ML pipeline from Pandas to Polars for better performance.

**Current State**:
- Data loading supports Polars (`--use-polars` flag)
- Converts to pandas immediately for compatibility
- Only about 10% of Polars performance benefit realized

**Migration Plan**:

#### Phase 1: Core Data Processing
- [ ] Migrate `trainer.prepare_data()` to Polars
- [ ] Migrate `clean_features()` to Polars
- [ ] Migrate `trainer._create_sequences()` to Polars
- [ ] Remove pandas conversion step

#### Phase 2: Model Compatibility
- [ ] Update XGBoost model to accept Polars DataFrames
- [ ] Update CatBoost model to accept Polars DataFrames
- [ ] Convert TCN sequence creation to work with Polars arrays
- [ ] Handle numpy/pytorch array conversions from Polars

#### Phase 3: Feature Engineering
- [ ] Migrate `scripts/feature_engineering.py` to Polars
- [ ] Migrate `scripts/create_labels.py` to Polars
- [ ] Update all feature calculations to Polars expressions
- [ ] Benchmark performance improvements

#### Phase 4: Testing & Validation
- [ ] Compare output parity between Pandas and Polars
- [ ] Performance benchmarking (load time, memory usage)
- [ ] Update documentation with Polars examples

**Expected Benefits**:
- 2-5x faster data loading
- 30-50% lower memory usage
- Lazy evaluation for large datasets
- Better multi-threading

**Estimated Effort**: 4-6 hours
**File**: All data processing files

---

### [ ] Chronos Model Implementation
Implement full Chronos-mini model (currently just placeholder).

**Current State**:
- Config updated to use `amazon/chronos-t5-mini`
- Model implementation exists but not tested
- No integration with training pipeline

**Tasks**:
- [ ] Test Chronos-mini model loads correctly on RTX 3060 12GB
- [ ] Verify memory usage fits in 12GB VRAM
- [ ] Run training with Chronos (threshold optimization only)
- [ ] Add Chronos to ensemble if performance is good
- [ ] Document Chronos usage and expected accuracy

**Expected Performance**: 62-65% accuracy (pretrained, less trainable)

---

### [ ] Regression-Based Approach (Label as Continuous Target)
**PROBLEM**: Binary classification loses information - treats +3% and +20% the same way
**SOLUTION**: Predict continuous upside/ATR ratio, use thresholds for trading decisions

**Implementation**:
- Target: `max_upside / ATR` (normalized upside by volatility)
- Model predicts continuous value (e.g., 0.5 = 0.5×ATR upside potential)
- Post-processing: Apply thresholds for trading decisions
  - < -1.0×ATR: STRONG SELL
  - -1.0 to -0.5×ATR: SELL
  - -0.5 to +0.5×ATR: HOLD
  - +0.5 to +1.0×ATR: BUY
  - > +1.0×ATR: STRONG BUY

**Benefits**:
- ✅ Preserves full information about upside potential
- ✅ Single model instead of multiple binary models
- ✅ Flexible thresholds (adjustable without retraining)
- ✅ Better regression loss (MSE) vs sparse classification loss

**Challenges**:
- Need to calibrate ATR scaling factor
- Threshold optimization required
- Metrics: Use RMSE, MAE, R² instead of accuracy/AUC
- May need different ensemble strategy

**Status**: Design phase
**Priority**: High - Could improve prediction quality significantly
**Estimated Effort**: 4-6 hours

---

## Priority 3 - Low Priority / Nice to Have

### [ ] Configuration Profiles
Create multiple configuration profiles for different use cases:

- [ ] `config_fast.yaml` - Quick development iteration (3 trials, no TCN)
- [ ] `config_production.yaml` - Production training (100 trials, all models)
- [ ] `config_gpu_12gb.yaml` - Optimized for RTX 3060 12GB
- [ ] `config_test.yaml` - Minimal config for testing (1 trial, XGBoost only)

**File**: `config/` directory with YAML configs

---

### [ ] Model Versioning System
Improve model versioning and metadata:

- [ ] Git hash tracking in model metadata
- [ ] Automatic feature set versioning
- [ ] Model performance history tracking
- [ ] A/B testing framework for model comparison
- [ ] Rollback capability for production models

**File**: New `ml_framework/versioning.py`

---

### [ ] Data Quality Checks
Add comprehensive data quality validation:

- [ ] Check for missing values percentage
- [ ] Detect outliers in features
- [ ] Validate label distribution balance
- [ ] Check for data leakage between train/test
- [ ] Temporal continuity validation

**File**: `ml_framework/data_validator.py`

---

### [ ] Advanced Ensemble Methods
Add more sophisticated ensemble techniques:

- [ ] Blending ensemble (weighted average of predictions)
- [ ] Stacking with XGBoost as meta-learner
- [ ] Dynamic ensemble weights based on market regime
- [ ] Cross-validation ensemble

**File**: `ml_framework/ensemble.py`

---

### [ ] Feature Importance Analysis
Add tools for analyzing feature importance:

- [ ] SHAP values for model interpretability
- [ ] Permutation importance
- [ ] Feature correlation matrix
- [ ] Feature stability over time
- [ ] Automatic feature selection based on importance

**File**: `scripts/analyze_features.py`

---

## Completed (Moved from TODO)

### ✅ Dataset Folder Organization (2026-02-04)
Implemented folder-based dataset organization for easy comparison between classification types:

**Folder Structure**:
```
outputs/features/
├── dataset_20260204_185139/
│   ├── features.parquet
│   ├── labels_binary.parquet
│   ├── labels_3class.parquet
│   ├── labels_5class.parquet
│   └── metadata.json
```

**Changes Made**:
- **Feature Engineering**: Creates `dataset_*/` folder with `features.parquet` + `metadata.json`
- **Label Creation**: `--dataset-folder` argument, auto-detects latest, saves as `labels_{type}.parquet`
- **Training**: `--dataset-folder` and `--label-type` arguments, auto-detects available labels
- **Shared Folders**: Changed Docker volumes to bind mounts for host filesystem access
  - Datasets: `/home/jakub/StockAnalyzer/ml-training/outputs/features/`
  - Models: `/home/jakub/StockAnalyzer/ml-training/outputs/models/`

**Benefits**:
- All related files in one place (features + all label types)
- Easy to compare binary vs 3class vs 5class on SAME features
- Train script auto-detects available label types
- Direct filesystem access - no more hidden Docker volumes

### ✅ ML Pipeline Cleanup & Standardization (2026-02-04)
Cleaned up and unified the entire ML training pipeline to eliminate confusion and inconsistency:

**1. Script Cleanup**:
- Moved 21 obsolete scripts to `scripts/obsolete/`: all old feature engineering, label creation, training scripts

**2. Unified Feature Engineering**:
- Created `scripts/feature_engineering.py` as THE SINGLE feature engineering script
- Copied from `feature_engineering_swing.py` (already correct)
- Includes all swing trading features, insider trading ("secret weapon"), market context
- Automatically filters out frontend-only features (string signals/reasons)
- ~121 features (down from 202 after removing low-importance features)
- **NOW**: Creates dataset folders with metadata

**3. Unified Label Creator**:
- Created new `scripts/create_labels.py` supporting ALL classification types via `--type` argument
- Binary: `--type binary` (BUY/DON'T BUY with profit target/stop loss)
- 3-Class: `--type 3class` (SELL/HOLD/BUY with multi-timeframe)
- 5-Class: `--type 5class` (STRONG SELL/SELL/HOLD/BUY/STRONG BUY with risk penalty)
- Single script replaces all previous label scripts
- **NOW**: Saves labels into dataset folders

**4. Fixed train.py Evaluation Output**:
- Added confidence threshold analysis for binary classification (was missing)
- Added safety check for 1D probability arrays in `analyze_confidence_thresholds()`
- Confusion matrix now ALWAYS shows for ALL classification types
- Changed default ensemble method from `weighted_average` to `stacking` with XGBoost meta-learner
- **NOW**: Supports dataset folder mode with auto-detection

**5. Updated Documentation**:
- Completely rewrote `scripts/README.md` with current pipeline information
- Added usage examples for all three classification types
- Added troubleshooting guide
- Added feature importance analysis results
- Added model performance baselines
- **NOW**: Updated for folder-based organization

**Benefits**:
- No more confusion about which script to use
- Single source of truth for features and labels
- Consistent evaluation output across all classification types
- Better ensemble with stacking meta-learner
- Easy comparison between classification types

### ✅ TCN Sequence Optimization (2026-02-04)
Moved sequence creation from tuner to trainer for 10-20x faster tuning:
- Added `_create_sequences()` method to `trainer.py`
- `prepare_data()` now returns dictionary with 'regular' and 'tcn' data
- Sequences created once after temporal split, not on every trial
- `train_model()` accepts `tcn_sequences` parameter
- `train_all_models()` and `evaluate_all_models()` use data dictionary
- `tuner._tcn_objective()` accepts pre-created sequences as optional parameter
- Ensemble updated to handle TCN sequences in predictions

### ✅ Repository Reorganization (2026-02-03)
- Created `docs/`, `docs/obsolete/`, `scripts/obsolete/`, `scripts/utils/`, `pipelines/`
- Moved obsolete scripts and documentation
- Cleaned generated artifacts

### ✅ Documentation Overhaul (2026-02-03)
- Created comprehensive README.md with hardware specs
- Added Claude AI context section
- Created docs/architecture.md
- Created pipelines/README.md
- Created scripts/README.md

### ✅ Unified Training Script (2026-02-03)
- Merged train.py + train_40features.py
- Added --use-polars flag
- Added --skip-tcn flag
- Added --data-path and --labels-path
- Fixed string column handling

### ✅ TCN Memory Freeze Fix (2026-02-03)
- Replaced list-based sequence creation with pre-allocated arrays
- Added chunked processing (10K sequences per chunk)
- Added progress logging
- Fixed critical system freeze issue

### ✅ Chronos Upgrade (2026-02-03)
- Upgraded from chronos-t5-tiny to chronos-t5-mini
- Updated config for RTX 3060 12GB
- Updated requirements.gpu.txt for CUDA 12.1

### ✅ .gitignore (2026-02-03)
- Created comprehensive .gitignore
- Excludes outputs/, catboost_info/, mlruns/, training-logs/

---

## On Hold / Deprecated

### 🔄 MLFlow Integration
Current MLflow integration exists but may not be essential.

**Decision**: Keep as-is, not actively developing

---

## Ideas / Backlog

### Potential Future Enhancements

- **Real-time Training**: Add incremental learning for new data
- **Multi-GPU Training**: Distribute training across multiple GPUs
- **Model Compression**: Quantize models for faster inference
- **Feature Store**: Centralized feature management
- **Automated Retraining**: Schedule periodic model retraining
- **Explainability Dashboard**: UI for exploring model decisions
- **Alternative Data Sources**: News sentiment, social media, earnings calls
- **Multi-Timeframe**: Combine daily, weekly, monthly predictions
- **Sector Models**: Train separate models per sector
- **Market Regime Detection**: Adapt ensemble based on market conditions

---

## Task Template

When adding new tasks, use this format:

```markdown
### [ ] Task Name
Brief description of the task.

**Current State**: What exists now
**Proposed Solution**: What needs to be done
**Files to modify**: List of files
**Expected Benefits**: Why do this
**Estimated Effort**: Time/complexity
**Priority**: High/Medium/Low
```

---

## Notes

- Always update CHANGELOG.md after completing significant tasks
- Test with `--trials 5` before full training runs
- Use `--skip-tcn` if experiencing memory issues
- Backup working models before major changes
- Document breaking changes in README.md
