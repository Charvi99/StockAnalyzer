# TabNet Training Session - 2026-02-10

## Status: 🚀 TRAINING IN PROGRESS

**Model:** TabNet
**Trials:** 10
**Started:** 2026-02-10 ~14:17 UTC
**Dataset:** 2018-2020, 3-class classification, 133 features, 485k samples

---

## Quick Commands

### Watch Live Output
```bash
# Real-time log monitoring (follows as it grows)
docker exec stock_analyzer_ml_training tail -f /tmp/tabnet_training.log

# Check last 50 lines
docker exec stock_analyzer_ml_training tail -50 /tmp/tabnet_training.log

# Search for trial results
docker exec stock_analyzer_ml_training grep -E "(Trial|Best|AUC)" /tmp/tabnet_training.log | tail -20
```

### Check Progress
```bash
# Count completed trials
docker exec stock_analyzer_ml_training grep -c "Trial.*finished" /tmp/tabnet_training.log

# See all trial results
docker exec stock_analyzer_ml_training grep "Trial.*finished" /tmp/tabnet_training.log

# Check if training completed
docker exec stock_analyzer_ml_training grep "TRAINING COMPLETE" /tmp/tabnet_training.log
```

### Find the Model
```bash
# Check if model was saved
docker exec stock_analyzer_ml_training ls -lah /app/outputs/models/tabnet/

# Model will be at:
# /app/outputs/models/tabnet/latest/
# or on host: /home/jakub/StockAnalyzer/ml-training/outputs/models/tabnet/latest/
```

---

## Expected Timeline

**TabNet training time:** ~3-5 minutes per trial × 10 trials = **30-50 minutes total**

Training started: ~14:17 UTC
Expected completion: ~14:50-15:10 UTC

---

## For Next Claude Instance

### Context Summary

We've been implementing and testing different optimization objectives for ML trading models:

1. **Fixed Sharpe optimization bug** - Was failing due to index misalignment
2. **Implemented Hybrid optimization** - Combines AUC + Sharpe (but Sharpe signal too strong)
3. **Compared CatBoost models** - AUC still wins (test Sharpe 1.605 vs 1.186)

**Current task:** Testing TabNet with 10 trials to see if it behaves differently from CatBoost

### Key Files Modified

1. **`ml_framework/tuner.py`**:
   - Fixed `_calculate_returns_from_signals()` - Added length mismatch handling
   - Modified `_create_sharpe_objective()` - Added hybrid objective support
   - Better error logging with trial numbers

2. **`ml_framework/config.py`**:
   - Added `sharpe_weight` parameter for hybrid optimization

3. **`train.py`**:
   - Added `--objective hybrid` option
   - Added `--sharpe-weight` parameter
   - Fixed price data loading for Sharpe/Hybrid objectives

4. **`scripts/compare_objectives.py`**:
   - Updated to compare AUC, Sharpe, and Hybrid models

### Documentation Created

- `docs/SHARPE_OPTIMIZATION_BUGFIX_SUMMARY.md` - Bug fix details and results
- `docs/HYBRID_OPTIMIZATION_RESULTS.md` - Hybrid implementation and findings
- `docs/OBJECTIVE_COMPARISON_RESULTS_2026-02-10.md` - Original CatBoost comparison

### What to Do When Training Completes

1. **Check the results:**
   ```bash
   docker exec stock_analyzer_ml_training tail -100 /tmp/tabnet_training.log | grep -E "(Trial|Best|AUC|Sharpe)"
   ```

2. **Find the best trial:**
   ```bash
   docker exec stock_analyzer_ml_training grep "Trial.*finished" /tmp/tabnet_training.log | sort -t: -k4 -n | tail -1
   ```

3. **Backtest the model:**
   ```bash
   # Update compare_objectives.py to include TabNet
   # Then run:
   docker exec stock_analyzer_ml_training python scripts/compare_objectives.py
   ```

4. **Compare with CatBoost:**
   - CatBoost AUC: Sharpe 1.605, Return 4493%, Win Rate 58.7%
   - Does TabNet beat this?

### Potential Issues

**If training crashed:**
- Check error: `docker exec stock_analyzer_ml_training tail -100 /tmp/tabnet_training.log`
- Common issue: CUDA OOM - try fewer trials or smaller batch size
- Restart: `docker exec stock_analyzer_ml_training python train.py --models tabnet --trials 5`

**If training is slow:**
- TabNet is slower than CatBoost (deep learning vs gradient boosting)
- Expected: 3-5 min per trial vs CatBoost's 2-3 min

---

## Previous Session Results

### CatBoost Comparison (5 trials each)

| Model | Test Sharpe | Return | Win Rate | Learning Rate |
|-------|-------------|--------|----------|---------------|
| AUC | **1.605** | **4493%** | **58.7%** | 0.037 |
| Sharpe | 1.186 | 4358% | 56.6% | 0.0038 (overfit) |
| Hybrid (10%) | 1.186 | 4358% | 56.6% | 0.0038 |

**Key finding:** Sharpe optimization overfits to validation period (Sharpe 6.5 → 1.186 on test)

---

## Commands to Quick-Start Next Session

```bash
# 1. Check TabNet training status
docker exec stock_analyzer_ml_training tail -50 /tmp/tabnet_training.log

# 2. If completed, compare models
docker exec stock_analyzer_ml_training python scripts/compare_objectives.py

# 3. Train additional models if needed
docker exec stock_analyzer_ml_training python train.py --models xgboost --trials 5 --dataset-folder dataset_for_autogluon

# 4. Test hybrid with lower Sharpe weight
docker exec stock_analyzer_ml_training python train.py --models catboost --objective hybrid --sharpe-weight 0.05 --trials 5 --dataset-folder dataset_for_autogluon
```

---

## Contact Point

**User request:** Run TabNet test (10 trials) and provide monitoring commands
**Status:** ✅ Training started, monitoring commands provided above

**When user returns:** Check `/tmp/tabnet_training.log` for results and proceed with comparison/backtesting

---

**Generated:** 2026-02-10 14:18 UTC
**Session:** StockAnalyzer ML Training - Sharpe/Hybrid Optimization Implementation
