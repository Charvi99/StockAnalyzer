# ML Label Inconsistency - Quick Reference Guide

**Last Updated:** 2026-02-04
**Status:** CRITICAL INCONSISTENCIES IDENTIFIED

---

## 🚨 THE PROBLEM (1-Minute Summary)

You have **3 different label schemes** with **duplicate scripts** and **no tracking**. This makes it **impossible** to:
- Compare model performance fairly
- Track improvements over time
- Know which labeling strategy works best

---

## 📊 CURRENT LANDSCAPE

### Label Creation Scripts (4 files)

| Script | Status | Classes | When to Use |
|--------|--------|---------|-------------|
| `create_multiclass_labels.py` | ✅ **USE THIS** | 5-class | **STANDARD** |
| `convert_to_3class.py` | ⚠️ UTILITY | 3-class | If 5-class too complex |
| `create_labels.py` | ❌ DELETE | Binary | Never (duplicate) |
| `02_create_labels.py` | ⚠️ LEGACY | Binary | Only for simple screening |

### Feature Engineering Scripts (4 files)

| Script | Status | Embedded Labels? | When to Use |
|--------|--------|------------------|-------------|
| `feature_engineering_swing.py` | ✅ **USE THIS** | No | **STANDARD** |
| `feature_engineering_clean.py` | ❌ DELETE | Unknown | Never |
| `feature_engineering.py` | ❌ DELETE | Yes (binary) | Never |
| `01l_feature_engineering_*.py` | ❌ DELETE | Yes (binary) | Never |

---

## 🎯 RECOMMENDED STANDARD

### Use 5-Class Multi-Timeframe Labels

**Why:**
- ✅ Most granular (STRONG SELL / SELL / HOLD / BUY / STRONG BUY)
- ✅ Risk-aware (penalizes volatile stocks)
- ✅ Multi-timeframe (20d / 30d / 40d)
- ✅ Validated (70-75% quality score)
- ✅ Actionable trading signals

**Standard Pipeline:**
```bash
# 1. Create features (no embedded labels)
python scripts/feature_engineering_swing.py

# 2. Create 5-class labels
python scripts/create_multiclass_labels.py

# 3. Validate quality
python scripts/backtest_labels.py

# 4. Train on 20-day labels
python train.py --label-column label_20d --num-classes 5

# 5. Train on 30-day labels (for comparison)
python train.py --label-column label_30d --num-classes 5

# 6. Train on 40-day labels (for comparison)
python train.py --label-column label_40d --num-classes 5
```

---

## 🔥 IMMEDIATE CLEANUP (30 minutes)

### Delete These Files:

```bash
cd /home/jakub/StockAnalyzer

# Duplicate binary label script
rm ml-training/scripts/create_labels.py

# Feature engineering with embedded labels (OLD)
rm ml-training/scripts/feature_engineering.py
rm ml-training/scripts/feature_engineering_clean.py
rm ml-training/scripts/01l_feature_engineering_40features_simplified.py

# Obsolete directory (entire thing)
rm -rf ml-training/scripts/obsolete/
```

### After Cleanup, You Should Have:

**Label Scripts:**
- `create_multiclass_labels.py` ✅ (5-class - STANDARD)
- `convert_to_3class.py` ✅ (utility)
- `02_create_labels.py` ⚠️ (legacy - keep for reference)

**Feature Scripts:**
- `feature_engineering_swing.py` ✅ (STANDARD - no embedded labels)

**Analysis Scripts:**
- `backtest_labels.py` ✅
- `analyze_feature_importance.py` ✅
- `analyze_model_predictions.py` ✅
- `analyze_multi_timeframe_correlation.py` ✅

---

## 📋 LABEL SCHEMES COMPARISON

### Binary (2-Class) - DEPRECATED

```
Classes:
  0 = DON'T BUY
  1 = BUY

Logic:
  If price hits +3% before -2% within 20 days → BUY (1)
  Otherwise → DON'T BUY (0)

Distribution: ~40-45% BUY

Use Case: Simple screening only
Status: DEPRECATED - Use 5-class instead
```

### 3-Class - ALTERNATIVE

```
Classes:
  0 = SELL (merged STRONG SELL + SELL)
  1 = HOLD
  2 = BUY (merged BUY + STRONG BUY)

Distribution: ~25% SELL, ~35% HOLD, ~40% BUY

Use Case: When 5-class is too granular
Status: ALTERNATIVE - Use if sample size limited
```

### 5-Class - RECOMMENDED ⭐

```
Classes:
  0 = STRONG SELL (score ≤ -10%)
  1 = SELL (-10% < score ≤ -5%)
  2 = HOLD (-5% < score ≤ +5%)
  3 = BUY (+5% < score ≤ +10%)
  4 = STRONG BUY (score > +10%)

Scoring:
  score = final_return (%) - risk_penalty
  risk_penalty = 0.3 × |max_drawdown| (if drawdown < -3%)

Distribution: ~10% STRONG SELL, ~20% SELL, ~35% HOLD, ~25% BUY, ~10% STRONG BUY

Validation Results (20-day labels):
  STRONG BUY → +19.49% mean return ✅
  BUY → +7.51% mean return ✅
  HOLD → +1.02% mean return ✅
  SELL → -4.97% mean return ✅
  STRONG SELL → -13.67% mean return ✅

Quality Score: 70-75% (trustworthy)

Use Case: Professional swing trading
Status: RECOMMENDED - Use this as standard
```

---

## 🚀 STANDARD WORKFLOW

### Step 1: Create Features

```bash
cd /home/jakub/StockAnalyzer/ml-training
python scripts/feature_engineering_swing.py
```

**Output:**
- `features_swing_YYYYMMDD_HHMMSS.parquet`
- 60+ features (technical + insider + swing-specific)
- NO embedded labels

### Step 2: Create Labels

```bash
python scripts/create_multiclass_labels.py
```

**Output:**
- `labels_multiclass_5class_YYYYMMDD_HHMMSS.parquet`
- Columns: `label_20d`, `label_30d`, `label_40d`
- Additional: `final_return_*`, `max_upside_*`, `max_drawdown_*`, `score_*`

### Step 3: Validate Quality

```bash
python scripts/backtest_labels.py
```

**Expected Output:**
```
20-Day Label Quality:
  STRONG BUY positivity rate: 75.2% ✅
  STRONG SELL negativity rate: 73.1% ✅
  HOLD small move rate: 65.8% ✅
  Overall quality score: 72.5/100 ✅

LABELS ARE TRUSTWORTHY (quality: 72.5/100)
```

### Step 4: Train Models

```bash
# Train on 20-day labels (default)
python train.py --label-column label_20d --num-classes 5

# Train on 30-day labels (for comparison)
python train.py --label-column label_30d --num-classes 5

# Train on 40-day labels (for comparison)
python train.py --label-column label_40d --num-classes 5
```

### Step 5: Compare Results

**Check `experiments.log`:**
```
Experiment ID | Date       | Scheme | Lookahead | Model | AUC   | Accuracy
EXPERIMENT-001| 2026-02-04 | 5-class | 20d       | XGB   | 0.568 | 56.6%
EXPERIMENT-002| 2026-02-04 | 5-class | 20d       | CAT   | 0.567 | 56.7%
EXPERIMENT-003| 2026-02-04 | 5-class | 30d       | XGB   | 0.572 | 57.1%
```

---

## ⚠️ COMMON PITFALLS

### ❌ WRONG: Using Wrong Label Column

```bash
# Labels file has: label_20d, label_30d, label_40d
# Default: uses 'label' (doesn't exist!)

python train.py  # FAILS with "Column 'label' not found"
```

### ✅ CORRECT: Specify Label Column

```bash
python train.py --label-column label_20d --num-classes 5
```

---

### ❌ WRONG: Training Binary Model on 5-Class Labels

```bash
# Labels have values [0, 1, 2, 3, 4]
# Using binary config

python train.py --num-classes 2  # Treats 2,3,4 as class 1 (WRONG!)
```

### ✅ CORRECT: Match num_classes to Labels

```bash
python train.py --label-column label_20d --num-classes 5
```

---

### ❌ WRONG: Using Old Feature Engineering

```bash
# Old script embeds binary labels
python scripts/feature_engineering.py

# Output: features_*.parquet with embedded 'label' column
# Problem: Can't change labels without re-engineering features!
```

### ✅ CORRECT: Use Decoupled Scripts

```bash
# Features only (no labels)
python scripts/feature_engineering_swing.py

# Labels separately
python scripts/create_multiclass_labels.py

# Benefit: Can mix and match features with different label schemes!
```

---

## 📈 CLASS DISTRIBUTION REFERENCE

### 5-Class Labels (Typical)

| Class | Name | Count | % | Mean Return | Expected Action |
|-------|------|-------|---|-------------|-----------------|
| 0 | STRONG SELL | 58K | 10% | -13.67% | Exit or Short |
| 1 | SELL | 117K | 20% | -4.97% | Take Profits |
| 2 | HOLD | 204K | 35% | +1.02% | Wait |
| 3 | BUY | 146K | 25% | +7.51% | Standard Entry |
| 4 | STRONG BUY | 58K | 10% | +19.49% | Large Position |

**Trading Strategy:**
- **STRONG BUY (4):** 2.5% portfolio, stop -2%, target +5%
- **BUY (3):** 1.5% portfolio, stop -2%, target +3%
- **HOLD (2):** No trade, wait for better entry
- **SELL (1):** Take profits or avoid
- **STRONG SELL (0):** Exit existing or short

---

## 🔧 TROUBLESHOOTING

### Error: "Column 'label' not found"

**Cause:** Labels file has `label_20d`, `label_30d`, `label_40d` but no `label` column

**Fix:**
```bash
python train.py --label-column label_20d --num-classes 5
```

---

### Error: "num_classes=2 but detected 5 classes"

**Cause:** Using `--num-classes 2` with 5-class labels

**Fix:**
```bash
python train.py --label-column label_20d --num-classes 5
```

---

### Warning: "Class distribution highly imbalanced"

**Cause:** Some classes have <100 samples

**Solutions:**
- Use 3-class labels instead: `python scripts/convert_to_3class.py`
- Collect more data (5+ years instead of 3)
- Use class weights in training

---

### Issue: "Low quality score (<60%)"

**Cause:** Labels not predictive (random distribution)

**Solutions:**
- Adjust thresholds (make classes wider)
- Change lookahead period (try 30d instead of 20d)
- Check data quality (missing prices, outliers)

---

## 📚 DOCUMENTATION

### Full Report
- `ML_LABEL_INCONSISTENCY_REPORT.md` - Comprehensive investigation

### Code
- `scripts/create_multiclass_labels.py` - 5-class label creation
- `scripts/feature_engineering_swing.py` - Feature engineering
- `train.py` - Training script
- `scripts/backtest_labels.py` - Validation

### Configuration
- `ml_framework/config.py` - Training parameters
- `ml_framework/trainer.py` - Data preparation

---

## ✅ CHECKLIST

### Before Training:

- [ ] Cleaned up obsolete scripts
- [ ] Created features with `feature_engineering_swing.py`
- [ ] Created labels with `create_multiclass_labels.py`
- [ ] Validated quality with `backtest_labels.py` (score >70%)
- [ ] Checked label column name (label_20d, label_30d, or label_40d)
- [ ] Matched `--num-classes` to label scheme (5 for 5-class)
- [ ] Created `experiments.log` entry

### During Training:

- [ ] Specified correct `--label-column`
- [ ] Specified correct `--num-classes`
- [ ] Monitoring class distribution
- [ ] Logging AUC, accuracy, precision, recall

### After Training:

- [ ] Logged results to `experiments.log`
- [ ] Compared to previous experiments
- [ ] Analyzed confusion matrix
- [ ] Checked catastrophic error rate (<3%)

---

## 🎯 KEY TAKEAWAYS

1. **Standardize on 5-class labels** - most expressive and validated
2. **Decouple features from labels** - mix and match flexibility
3. **Specify label column explicitly** - avoid confusion
4. **Validate before training** - catch errors early
5. **Log all experiments** - track progress over time
6. **Delete obsolete files** - eliminate confusion

---

## 📞 NEED HELP?

### Common Commands

```bash
# Check label columns
python -c "import pandas as pd; df=pd.read_parquet('labels_multiclass_5class_*.parquet'); print(df.columns)"

# Check label distribution
python -c "import pandas as pd; df=pd.read_parquet('labels_multiclass_5class_*.parquet'); print(df['label_20d'].value_counts())"

# Validate quality
python scripts/backtest_labels.py

# Train with correct parameters
python train.py --label-column label_20d --num-classes 5 --models xgboost catboost
```

### Files to Check

- `ML_LABEL_INCONSISTENCY_REPORT.md` - Full investigation
- `experiments.log` - Experiment tracking
- `scripts/backtest_labels.py` - Validation results

---

**End of Quick Reference**

**Last Updated:** 2026-02-04
**Status:** READY FOR IMPLEMENTATION
