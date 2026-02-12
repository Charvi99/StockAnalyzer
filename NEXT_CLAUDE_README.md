# Instructions for Next Claude Session

## Current Status: TabNet Training Running

### What Just Happened

1. **Fixed Sharpe optimization bug** - Index alignment issue in `tuner.py`
2. **Implemented Hybrid AUC+Sharpe optimization** - Working but Sharpe signal too strong
3. **Tested on CatBoost (5 trials each)**:
   - AUC: Test Sharpe 1.605, Return 4493%, Win Rate 58.7% 🏆
   - Sharpe: Test Sharpe 1.186, Return 4358%, Win Rate 56.6%
   - Hybrid: Same as Sharpe (even with 10% weight)

4. **Started TabNet training (10 trials)** - Currently running in background

### Check Status Immediately

```bash
# See if TabNet training is still running or completed
docker exec stock_analyzer_ml_training tail -50 /tmp/tabnet_training.log
```

---

## When TabNet Training Completes

### 1. Review Results

```bash
# See all trial results
docker exec stock_analyzer_ml_training grep "Trial.*finished" /tmp/tabnet_training.log

# Get best trial
docker exec stock_analyzer_ml_training grep "Trial.*finished" /tmp/tabnet_training.log | sort -t: -k4 -n | tail -1

# Check final evaluation
docker exec stock_analyzer_ml_training grep -A10 "MODEL COMPARISON" /tmp/tabnet_training.log
```

### 2. Compare with CatBoost

TabNet results to compare against:
- **CatBoost AUC:** Sharpe 1.605, Return 4493%, Win Rate 58.7%
- **CatBoost Sharpe:** Sharpe 1.186, Return 4358%, Win Rate 56.6%

### 3. Run Backtest Comparison (if model saved)

First, update `scripts/compare_objectives.py` to include TabNet:

```python
# In compare_objectives.py, add to the models dict:
models = {
    'AUC': Path('/app/outputs/models/catboost/auc'),
    'Sharpe': Path('/app/outputs/models/catboost/sharpe'),
    'Hybrid': Path('/app/outputs/models/catboost/hybrid'),
    'TabNet': Path('/app/outputs/models/tabnet/latest'),  # Add this
}
```

Note: TabNet has different loading method - may need custom backtest script.

---

## Key Files to Know

### Modified This Session

1. **`ml_framework/tuner.py`** - Sharpe/Hybrid optimization logic
2. **`ml_framework/config.py`** - Added `sharpe_weight` parameter
3. **`train.py`** - Added `--objective hybrid` and `--sharpe-weight` args

### Documentation Created

1. **`TABNET_TRAINING_SESSION.md`** - Full session guide
2. **`docs/HYBRID_OPTIMIZATION_RESULTS.md`** - Hybrid implementation results
3. **`docs/SHARPE_OPTIMIZATION_BUGFIX_SUMMARY.md`** - Bug fix details
4. **`docs/OBJECTIVE_COMPARISON_RESULTS_2026-02-10.md`** - CatBoost comparison

---

## Next Steps (After TabNet Completes)

### Option 1: Compare All Models
- Run backtests on TabNet vs CatBoost
- Does TabNet avoid the Sharpe overfitting problem?

### Option 2: Test Different Approaches
- Lower Sharpe weight (3-5%) for hybrid
- Implement Sharpe capping (limit to 2-3)
- Test on different time periods

### Option 3: New Features
- Walk-forward validation
- Ensemble methods
- Different objectives (Sortino, Profit)

---

## Important Notes

### TabNet Characteristics
- **Slower** than CatBoost (3-5 min/trial vs 2-3 min)
- **Deep learning** based (PyTorch)
- May have **different overfitting behavior** than CatBoost
- Uses **attention mechanism** for feature selection

### Why Test TabNet?
CatBoost Sharpe optimization overfits because:
- Gradient boosting memorizes specific stock patterns
- Very low learning rate (0.0038) underfits generalizable patterns

TabNet might:
- Learn more robust features via attention
- Handle temporal patterns differently
- Be less prone to Sharpe overfitting

---

## Quick Commands

```bash
# ===== MONITORING =====
# Watch live
docker exec stock_analyzer_ml_training tail -f /tmp/tabnet_training.log

# Check trial count
docker exec stock_analyzer_ml_training grep -c "Trial.*finished" /tmp/tabnet_training.log

# ===== WHEN COMPLETE =====
# Get best AUC
docker exec stock_analyzer_ml_training grep "Best AUC" /tmp/tabnet_training.log

# Check test metrics
docker exec stock_analyzer_ml_training grep -A5 "TABNET:" /tmp/tabnet_training.log | tail -10

# ===== IF CRASHED =====
# Check error
docker exec stock_analyzer_ml_training tail -200 /tmp/tabnet_training.log | grep -A10 -B10 "Error\|Traceback"

# Restart with fewer trials
docker exec stock_analyzer_ml_training python train.py --models tabnet --trials 5 --dataset-folder dataset_for_autogluon
```

---

## Contact Info

**User:** Started TabNet training (10 trials) before ending session
**Time:** ~14:17 UTC, 2026-02-10
**Duration expected:** 30-50 minutes
**Next action:** Review results, compare with CatBoost, decide next steps

---

**Good luck! 🚀**
