# TCN Fix Roadmap

**Date**: 2026-02-09
**Status**: Ready for Implementation
**Priority**: High (TCN: 49.8% AUC = random guessing)

---

## Executive Summary

The TCN model is currently performing at **49.8% AUC** (equivalent to random guessing at 50%). Investigation revealed **4 critical issues** that must be fixed:

1. **Feature Mismatch**: TCN uses 29 old features vs 261 current features
2. **Sequence Bug**: Sequences span multiple stocks (violates temporal structure)
3. **Temporal Split Bug**: Data split by row index instead of timestamp
4. **Data Type Mismatch**: TCN expects time-series, receives cross-sectional snapshots

**Expected Outcome**: After all fixes, TCN should reach **60-65% AUC** (competitive with XGBoost/CatBoost at 61-62%).

---

## Problem Analysis

### Issue #1: Feature Mismatch (CRITICAL)

**Current State:**
```
TCN Model (trained Feb 4):
  - 29 features from old feature engineering script
  - Features: log_return_1d, log_return_5d, price_position_20d, gap, etc.
  - These features DON'T EXIST in current dataset!

XGBoost/CatBoost (trained Feb 7):
  - 261 features from current feature engineering
  - Includes lag features, market context, insider trading
```

**Impact:** TCN receives NaN/zeros for 92% of features that tree models use.

**Root Cause Location:**
- Old hardcoded feature list in legacy code
- TCN was trained on stale `dataset_20260204_*` instead of `dataset_lags_20260206_*`

---

### Issue #2: Sequence Creation Bug (CRITICAL)

**Location:** `ml_framework/trainer.py:_create_sequences()` (lines 207-285)

**Current Code:**
```python
def _create_sequences(self, X: pd.DataFrame, y: pd.Series, sequence_length: int):
    X_values = X.values  # Loses stock_id information!

    for i in range(n_samples):
        X_seq[i] = X_values[i:i+sequence_length]  # Takes consecutive ROWS
        y_seq[i] = y_values[i+sequence_length]
```

**The Problem:**
```
Data is sorted by: [stock_id, timestamp]

Row 1000: Stock A, day 50
Row 1001: Stock A, day 51
Row 1002: Stock A, day 52
Row 1003: Stock B, day 1  ← Sequence continues with different stock!
Row 1004: Stock B, day 2

Sequence [1000:1025] contains:
  - Stock A days 50-52
  - Stock B days 1-22  ← WRONG! Different stock
```

**Impact:** TCN learns from mixed stock sequences → random noise.

---

### Issue #3: Temporal Split Bug (HIGH)

**Location:** `ml_framework/trainer.py:prepare_data()` (lines 320-332)

**Current Code:**
```python
# Temporal split (NOT random!)
n = len(X)
train_end = int(n * self.config.data.train_ratio)  # 70% by ROW count

X_train = X.iloc[:train_end]  # Takes first 70% of ROWS
```

**The Problem:**
- Data is sorted by `[stock_id, timestamp]`
- Split by row index means training set contains:
  - Stock A: days 1-1000
  - Stock B: days 1-800
  - Stock C: days 1-600
  - Stock Z: days 1-200 (partial)
- Test set might contain **older data** than training set!

**Impact:** Look-ahead bias, invalid temporal validation.

---

### Issue #4: Data Type Mismatch (MEDIUM)

**The Problem:**
- Your 261 features are **cross-sectional snapshots** (single-day calculations)
- RSI(today), MACD(today) already aggregated from historical data
- TCN expects **sequential patterns** across timesteps

**Impact:** TCN can't find temporal patterns because features are already flattened.

---

## Fix Roadmap

### Phase 1: Feature Unification (1-2 hours)

**Goal:** Make TCN use the same 261 features as XGBoost/CatBoost.

#### Step 1.1: Remove Hardcoded Feature List

**File:** Search for where TCN's 29 features are defined

**Action:**
```bash
# Find where TCN features are hardcoded
grep -r "log_return_1d\|price_position_20d" ml-framework/
```

**Expected locations:**
- Training pipeline that filters features for TCN
- Config file with TCN-specific feature list
- Old feature engineering script

**Fix:**
- Remove any feature filtering for TCN
- Use the same `feature_cols` as XGBoost/CatBoost

---

#### Step 1.2: Update Feature Engineering (if needed)

**File:** `scripts/feature_engineering.py`

**Action:** Ensure all 261 features are properly created and include:
- OHLCV (6 features)
- Technical indicators (60+ features)
- Swing trading features (15+ features)
- Insider trading (12 features)
- Market context (10+ features)
- Lag features (150+ features)
- Interaction features (8 features)

**Validation:**
```python
# After feature engineering, verify
assert len(feature_cols) == 261, f"Expected 261 features, got {len(feature_cols)}"
```

---

### Phase 2: Fix Sequence Creation (2-3 hours)

**Goal:** Create proper stock-wise sequences that respect temporal boundaries.

#### Step 2.1: Rewrite `_create_sequences()` Method

**File:** `ml_framework/trainer.py`

**Current Implementation (BROKEN):**
```python
def _create_sequences(self, X: pd.DataFrame, y: pd.Series, sequence_length: int):
    X_values = X.values  # Loses stock_id!
    for i in range(n_samples):
        X_seq[i] = X_values[i:i+sequence_length]  # Wrong!
```

**New Implementation:**
```python
def _create_sequences(self, X: pd.DataFrame, y: pd.Series, sequence_length: int):
    """
    Create stock-wise sequences for TCN.

    CRITICAL: Sequences must NOT cross stock boundaries.

    Args:
        X: Features DataFrame with MultiIndex (stock_id, timestamp) or stock_id column
        y: Labels Series
        sequence_length: Number of timesteps per sequence

    Returns:
        X_seq: 3D array (samples, sequence_length, features)
        y_seq: Labels aligned to sequences
    """
    import gc

    # Check if X has stock_id information
    if 'stock_id' in X.columns:
        # Method 1: stock_id is a column
        stock_groups = X.groupby('stock_id')
    elif isinstance(X.index, pd.MultiIndex) and 'stock_id' in X.index.names:
        # Method 2: MultiIndex with stock_id
        stock_groups = X.groupby(level='stock_id')
    else:
        raise ValueError("Cannot determine stock boundaries! "
                        "X must have stock_id column or MultiIndex.")

    sequences = []
    labels = []

    for stock_id, stock_data in stock_groups:
        # Sort by timestamp within stock
        stock_data = stock_data.sort_values('timestamp')

        # Extract features (drop non-feature columns)
        feature_cols = [c for c in stock_data.columns
                       if c not in ['stock_id', 'timestamp', 'label',
                                    'max_upside', 'max_drawdown']]
        X_stock = stock_data[feature_cols].values
        y_stock = y.loc[stock_data.index].values

        # Create sequences within THIS stock only
        n_samples = len(X_stock) - sequence_length

        if n_samples <= 0:
            continue  # Skip stocks with too few days

        for i in range(n_samples):
            sequences.append(X_stock[i:i+sequence_length])
            labels.append(y_stock[i+sequence_length])

    # Convert to arrays
    X_seq = np.array(sequences, dtype=np.float32)
    y_seq = np.array(labels, dtype=np.float32)

    logger.info(f"✅ Created {len(sequences)} stock-wise sequences")
    logger.info(f"   Shape: {X_seq.shape} (samples, timesteps, features)")

    return X_seq, y_seq
```

**Key Changes:**
1. Groups data by `stock_id` before creating sequences
2. Each sequence comes from a SINGLE stock
3. No crossing stock boundaries

---

#### Step 2.2: Update Data Preparation

**File:** `ml_framework/trainer.py:prepare_data()`

**Action:** Pass stock_id information to sequence creation

```python
# Before creating sequences, ensure stock_id is available
# Merge stock_id back into X if needed

# Current (BROKEN):
# X = df[feature_cols].fillna(0)  # stock_id lost!

# Fix:
feature_cols = [c for c in df.columns
                if c not in ['stock_id', 'timestamp', 'label',
                             'max_upside', 'max_drawdown']]
X = df[feature_cols + ['stock_id', 'timestamp']].fillna(0)  # Keep stock_id!

# Pass to sequence creation
X_train_seq, y_train_seq = self._create_sequences(
    X_train.merge(df[['stock_id', 'timestamp']],
                  left_index=True,
                  right_index=True),
    y_train,
    sequence_length
)
```

---

### Phase 3: Fix Temporal Split (1-2 hours)

**Goal:** Split data by timestamp, not row index.

#### Step 3.1: Implement Timestamp-Based Split

**File:** `ml_framework/trainer.py:prepare_data()`

**Current (BROKEN):**
```python
n = len(X)
train_end = int(n * self.config.data.train_ratio)  # 70% by ROW count
X_train = X.iloc[:train_end]
```

**New Implementation:**
```python
def prepare_data(self, features: pd.DataFrame, labels: pd.DataFrame, skip_sequences: bool = False):
    """Prepare data with proper temporal split"""

    # Merge features and labels
    df = pd.merge(
        features,
        labels[['stock_id', 'timestamp', 'label']],
        on=['stock_id', 'timestamp'],
        how='inner'
    )

    # Get unique timestamps and sort
    unique_timestamps = df['timestamp'].unique()
    unique_timestamps.sort()

    # Split by TIMESTAMP (not row index)
    n_timestamps = len(unique_timestamps)
    train_end_idx = int(n_timestamps * self.config.data.train_ratio)
    val_end_idx = int(n_timestamps * (self.config.data.train_ratio + self.config.data.val_ratio))

    train_timestamps = unique_timestamps[:train_end_idx]
    val_timestamps = unique_timestamps[train_end_idx:val_end_idx]
    test_timestamps = unique_timestamps[val_end_idx:]

    logger.info(f"✅ Temporal split by timestamp:")
    logger.info(f"  Train: {train_timestamps[0]} to {train_timestamps[-1]} ({len(train_timestamps)} days)")
    logger.info(f"  Val:   {val_timestamps[0]} to {val_timestamps[-1]} ({len(val_timestamps)} days)")
    logger.info(f"  Test:  {test_timestamps[0]} to {test_timestamps[-1]} ({len(test_timestamps)} days)")

    # Split data
    train_mask = df['timestamp'].isin(train_timestamps)
    val_mask = df['timestamp'].isin(val_timestamps)
    test_mask = df['timestamp'].isin(test_timestamps)

    X_train = df[train_mask][feature_cols]
    y_train = df[train_mask]['label']

    X_val = df[val_mask][feature_cols]
    y_val = df[val_mask]['label']

    X_test = df[test_mask][feature_cols]
    y_test = df[test_mask]['label']

    # Verify no overlap
    assert len(set(train_timestamps) & set(val_timestamps)) == 0
    assert len(set(val_timestamps) & set(test_timestamps)) == 0

    # Continue with sequence creation...
```

**Key Changes:**
1. Find all unique timestamps
2. Split timestamps (not rows)
3. Filter data by timestamp ranges
4. Ensures proper temporal ordering

---

### Phase 4: Retrain TCN (3-4 hours runtime)

**Goal:** Train TCN with fixed code on correct features.

#### Step 4.1: Backup Current Models

```bash
cd /home/jakub/StockAnalyzer/ml-training
cp -r outputs/models outputs/models_backup_BEFORE_TCN_FIX
```

#### Step 4.2: Clear Old TCN Models

```bash
rm -rf outputs/models/tcn/latest/*
rm -rf outputs/models/ensemble/latest/*
```

#### Step 4.3: Retrain TCN

```bash
# Quick test (10 trials, ~30 min)
docker exec stock_analyzer_ml_training python train.py \
  --models tcn \
  --trials 10 \
  --dataset-folder dataset_lags_20260206_111644 \
  --label-type binary

# Full training (50 trials, ~2 hours)
docker exec stock_analyzer_ml_training python train.py \
  --models xgboost catboost tcn \
  --trials 50 \
  --dataset-folder dataset_lags_20260206_111644 \
  --label-type binary
```

**Expected Results:**
```
TCN AUC: 60-65% (up from 49.8%)
Ensemble AUC: 62-66% (small improvement)
```

---

### Phase 5: Validation & Testing (1 hour)

**Goal:** Verify fixes work correctly.

#### Step 5.1: Validate Sequences

Create a test script to verify sequences are stock-wise:

```python
# File: scripts/validate_sequences.py
import pandas as pd
import numpy as np

def validate_stock_wise_sequences(X_seq, stock_ids, timestamps):
    """Verify no sequence crosses stock boundaries"""

    for i in range(len(X_seq)):
        # All timesteps in sequence should have same stock_id
        stock_ids_in_seq = stock_ids.iloc[i:i+sequence_length]
        assert len(stock_ids_in_seq.unique()) == 1, \
            f"Sequence {i} spans multiple stocks!"

    print("✅ All sequences are stock-wise")
```

#### Step 5.2: Compare Model Performance

```bash
# Run feature importance on new models
docker exec stock_analyzer_ml_training python scripts/analyze_feature_importance.py \
  --top-n 50 \
  --strategy conservative
```

**Expected Improvement:**
```
Before Fix:
  TCN AUC: 49.8% (random)
  XGBoost AUC: 61.4%
  CatBoost AUC: 61.6%
  Ensemble AUC: 61.9%

After Fix:
  TCN AUC: 60-65% (competitive)
  XGBoost AUC: 61-62%
  CatBoost AUC: 61-62%
  Ensemble AUC: 63-66%
```

---

## Implementation Order

### Step 1: Quick Win (Same Day)
1. Fix feature mismatch (Phase 1)
2. Retrain TCN with correct features (Phase 4)

**Expected AUC improvement:** 49.8% → 55-58%

### Step 2: Critical Fixes (Day 2)
3. Fix sequence creation (Phase 2)
4. Fix temporal split (Phase 3)
5. Retrain TCN (Phase 4)

**Expected AUC improvement:** 55-58% → 60-65%

### Step 3: Validation (Day 2)
6. Run validation tests (Phase 5)
7. Feature importance analysis
8. Update documentation

---

## Testing Checklist

After each phase, verify:

- [ ] TCN metadata shows 261 features (not 29)
- [ ] All sequences are stock-wise (no cross-stock sequences)
- [ ] Temporal split uses timestamps, not row indices
- [ ] TCN AUC > 55% (minimum acceptable)
- [ ] TCN AUC > 60% (target)
- [ ] Ensemble AUC improves by at least 1%
- [ ] No look-ahead bias in data split
- [ ] Training logs show correct sequence counts

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Sequence creation breaks existing code | Medium | High | Thorough testing, keep backup |
| Temporal split reduces training data | Low | Medium | Verify data distribution |
| TCN still underperforms | Low | Low | TCN is optional, tree models work |
| Memory issues with stock-wise sequences | Medium | Medium | Adaptive sequence length already implemented |

---

## Rollback Plan

If fixes don't work:

```bash
# Restore original models
cd /home/jakub/StockAnalyzer/ml-training
rm -rf outputs/models/tcn/latest/*
cp -r outputs/models_backup_BEFORE_TCN_FIX/tcn/* outputs/models/tcn/latest/

# Continue with --skip-tcn
docker exec stock_analyzer_ml_training python train.py --skip-tcn
```

---

## Success Criteria

**Minimum Viable Product:**
- TCN uses same 261 features as tree models
- TCN AUC > 55% (up from 49.8%)
- No sequence or temporal bugs

**Target State:**
- TCN AUC > 60% (competitive with tree models)
- Ensemble AUC > 63% (measurable improvement)
- All validation tests pass
- Documentation updated

---

## Next Steps

1. **Review this roadmap** and confirm approach
2. **Implement Phase 1** (feature unification)
3. **Test TCN retrain** with 10 trials
4. **If AUC > 55%, proceed to Phase 2-3**
5. **Full retrain** with 50 trials
6. **Validate results**

**Estimated Total Time:** 6-10 hours (including training time)

**Owner:** ML Engineer
**Review Date:** 2026-02-09
**Target Completion:** 2026-02-11
