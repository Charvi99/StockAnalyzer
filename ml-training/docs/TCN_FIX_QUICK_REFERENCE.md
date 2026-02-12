# TCN Fix Quick Reference

**Created:** 2026-02-09
**Full Roadmap:** [TCN_FIX_ROADMAP.md](./TCN_FIX_ROADMAP.md)

---

## TL;DR

TCN gets **49.8% AUC** because:
1. ❌ Uses **29 features** instead of **261** (feature mismatch)
2. ❌ Sequences **cross stock boundaries** (mixed stocks in same sequence)
3. ❌ Data split by **row index** instead of **timestamp** (look-ahead bias)

**Fix:** All 3 issues → TCN should reach **60-65% AUC**

---

## Files to Modify

### 1. `ml_framework/trainer.py`

**Location:** Lines 207-285, 287-364

**Changes:**
```python
# BEFORE (BROKEN)
def _create_sequences(self, X: pd.DataFrame, y: pd.Series, sequence_length: int):
    X_values = X.values  # Loses stock_id
    for i in range(n_samples):
        X_seq[i] = X_values[i:i+sequence_length]  # Crosses stocks

# AFTER (FIXED)
def _create_sequences(self, X: pd.DataFrame, y: pd.Series, sequence_length: int):
    # Group by stock_id first
    for stock_id, stock_data in X.groupby('stock_id'):
        stock_data = stock_data.sort_values('timestamp')
        # Create sequences WITHIN stock only
        for i in range(len(stock_data) - sequence_length):
            sequences.append(stock_data.iloc[i:i+sequence_length][features])
```

```python
# BEFORE (BROKEN)
train_end = int(n * self.config.data.train_ratio)
X_train = X.iloc[:train_end]  # Splits by row index

# AFTER (FIXED)
unique_timestamps = df['timestamp'].unique()
train_end_idx = int(len(unique_timestamps) * 0.7)
train_timestamps = unique_timestamps[:train_end_idx]
X_train = df[df['timestamp'].isin(train_timestamps)]
```

---

## Implementation Steps

### Phase 1: Feature Fix (1-2 hours)

```bash
# 1. Find hardcoded TCN features
grep -r "log_return_1d\|price_position_20d" ml-framework/

# 2. Remove feature filtering for TCN

# 3. Verify feature count
python -c "import json; meta = json.load(open('outputs/models/catboost/latest/metadata.json')); print(f'Features: {len(meta[\"feature_cols\"])}')"
# Should output: Features: 261

# 4. Quick retrain test
docker exec stock_analyzer_ml_training python train.py \
  --models tcn \
  --trials 5 \
  --skip-tune
```

**Expected:** TCN metadata shows 261 features, AUC ~55-58%

---

### Phase 2: Sequence Fix (2-3 hours)

**Edit:** `ml_framework/trainer.py:_create_sequences()`

Copy implementation from `TCN_FIX_ROADMAP.md` Phase 2, Step 2.1

**Key points:**
- Keep `stock_id` column when creating sequences
- Group by `stock_id` before creating sequences
- Each sequence from ONE stock only

---

### Phase 3: Temporal Split Fix (1-2 hours)

**Edit:** `ml_framework/trainer.py:prepare_data()`

Copy implementation from `TCN_FIX_ROADMAP.md` Phase 3, Step 3.1

**Key points:**
- Get unique timestamps
- Split timestamps (not rows)
- Filter data by timestamp ranges

---

### Phase 4: Full Retrain (3-4 hours)

```bash
# Backup
cd /home/jakub/StockAnalyzer/ml-training
cp -r outputs/models outputs/models_backup_BEFORE_TCN_FIX

# Retrain all models
docker exec stock_analyzer_ml_training python train.py \
  --models xgboost catboost tcn \
  --trials 50 \
  --label-type binary

# Check results
cat outputs/models/tcn/latest/metadata.json | grep feature_cols | wc -l
# Should be: 261
```

**Expected Results:**
```
TCN AUC: 60-65% (up from 49.8%)
Ensemble AUC: 63-66% (up from 61.9%)
```

---

## Quick Validation Commands

```bash
# Check TCN feature count
docker exec stock_analyzer_ml_training python -c "
import json
with open('outputs/models/tcn/latest/metadata.json') as f:
    meta = json.load(f)
print(f'TCN Features: {len(meta[\"feature_cols\"])}')
print(f'First 5: {meta[\"feature_cols\"][:5]}')
"

# Run feature importance
docker exec stock_analyzer_ml_training python scripts/analyze_feature_importance.py \
  --top-n 30

# Verify model performance
docker exec stock_analyzer_ml_training python -c "
import json
for model in ['xgboost', 'catboost', 'tcn']:
    try:
        with open(f'outputs/models/{model}/latest/metadata.json') as f:
            meta = json.load(f)
            print(f'{model.upper()}: {len(meta[\"feature_cols\"])} features')
    except:
        print(f'{model.upper()}: No metadata')
"
```

---

## Rollback (If Needed)

```bash
# Quick rollback
cd /home/jakub/StockAnalyzer/ml-training
rm -rf outputs/models/tcn/latest/*
rm -rf outputs/models/ensemble/latest/*
cp -r outputs/models_backup_BEFORE_TCN_FIX/tcn/* outputs/models/tcn/latest/
cp -r outputs_models_backup_BEFORE_TCN_FIX/ensemble/* outputs/models/ensemble/latest/

# Continue without TCN
docker exec stock_analyzer_ml_training python train.py --skip-tcn
```

---

## Common Issues

| Issue | Symptom | Fix |
|-------|---------|-----|
| Feature count mismatch | TCN has 29 features | Remove hardcoded feature list |
| "Cannot determine stock boundaries" | Error in sequence creation | Ensure stock_id column exists |
| Memory error | OOM during sequence creation | Reduce `sequence_length` in config |
| TCN AUC still <55% | No improvement | Check if features contain NaN |

---

## Timeline Estimate

| Phase | Time | AUC Improvement |
|-------|------|-----------------|
| Phase 1 (Feature fix) | 1-2h | 49.8% → 55-58% |
| Phase 2 (Sequence fix) | 2-3h | 55-58% → 58-62% |
| Phase 3 (Temporal fix) | 1-2h | Prevents look-ahead bias |
| Phase 4 (Retrain) | 3-4h | Final model ready |
| **Total** | **7-11h** | **49.8% → 60-65%** |

---

## Success Criteria

- [ ] TCN metadata shows 261 features
- [ ] All sequences are stock-wise (validated)
- [ ] Temporal split uses timestamps
- [ ] TCN AUC > 55% (minimum)
- [ ] TCN AUC > 60% (target)
- [ ] Ensemble AUC improves >1%

---

## Contact

For questions or issues, refer to the full roadmap:
`/home/jakub/StockAnalyzer/ml-training/docs/TCN_FIX_ROADMAP.md`
