# Alpha Label Creation - Implementation Folder

**Purpose:** Fix ML model to predict stock-picking ability (alpha) instead of market direction (beta)

**Status:** Phase 1 - Diagnosis & Baseline Establishment

**Created:** 2026-02-05
**Target Win Rate:** 55-58% (realistic), 65% (stretch goal)
**Risk-Reward:** 1% loss / 2-3% gain (2:1 to 3:1 ratio)

---

## Problem Statement

**Current Issue:** Model achieves 76% AUC but this measures market timing (beta), not stock selection (alpha)

**Evidence:**
- Top 5 features = 42% importance, ALL SPY-related
- Insider trading features = 0.00-1.2% importance (ignored)
- Technical indicators (RSI, MFI) = <0.02% importance (ignored)

**Impact:**
- Model predicts: "Will market go up?" (useful for market timing)
- Should predict: "Will THIS stock beat the market?" (useful for stock picking)

---

## Solution Overview

### Core Strategy: Predict Alpha, Not Returns

**Before (Current):**
```python
# Predicts absolute return
label = 1 if stock_return > 0.03 else 0
```

**After (Proposed):**
```python
# Predicts outperformance vs market
alpha = stock_return - spy_return
label = 1 if alpha > 0.02 else 0
```

### Implementation Phases

```
Phase 1: Diagnosis (Week 1)
├── 01_diagnose_current_labels.py
│   ├── Feature importance analysis
│   ├── Label-SPY correlation test
│   └── Ablation study (with/without SPY)
│
├── 02_create_alpha_labels.py
│   ├── Binary alpha labels (2% outperformance)
│   ├── 5-class alpha labels
│   └── Beta-adjusted alpha labels
│
└── 03_train_comparison.py
    ├── Train on current labels (baseline)
    ├── Train on alpha labels + SPY
    └── Train on alpha labels - SPY

Phase 2: Feature Engineering (Week 2)
├── 04_engineer_insider_features.py
│   ├── Unusual activity indicators
│   ├── Technical + insider combinations
│   └── Executive conviction signals
│
├── 05_create_regime_features.py
│   ├── Market regime classification
│   ├── Volatility regime indicators
│   └── Regime-adjusted signals
│
└── 06_train_enhanced.py
    ├── Retrain with new features
    └── Compare feature importance

Phase 3: Advanced Models (Week 3-4)
├── 07_stacking_ensemble.py
├── 08_tabnet_implementation.py
└── 09_final_evaluation.py
```

---

## File Structure

```
create_labels/
├── README.md                              # This file
├── DIAGNOSIS_REPORT.md                    # Diagnostic results (generated)
├── IMPLEMENTATION_LOG.md                  # Track all changes
│
├── 01_diagnose_current_labels.py          # Phase 1: Diagnostic tests
├── 02_create_alpha_labels.py              # Phase 1: Alpha label generation
├── 03_train_comparison.py                 # Phase 1: A/B testing
│
├── 04_engineer_insider_features.py        # Phase 2: Enhanced features
├── 05_create_regime_features.py           # Phase 2: Regime features
├── 06_train_enhanced.py                   # Phase 2: Train with new features
│
├── 07_stacking_ensemble.py                # Phase 3: Ensemble methods
├── 08_tabnet_implementation.py            # Phase 3: TabNet model
├── 09_final_evaluation.py                 # Phase 3: Final evaluation
│
├── config/
│   ├── alpha_config.yaml                  # Alpha label parameters
│   └── feature_config.yaml                # Feature engineering config
│
├── outputs/
│   ├── diagnostic_plots/                  # Visualization of diagnostics
│   ├── feature_importance/                # Feature importance analysis
│   └── comparison_results/                # A/B test results
│
└── docs/
    ├── LABEL_STRATEGY.md                  # Detailed label strategy
    ├── FEATURE_ENGINEERING_GUIDE.md       # Feature engineering guide
    └── VALIDATION_CHECKLIST.md            # Pre-deployment checklist
```

---

## Quick Start

### Step 1: Run Diagnostics (1 hour)

```bash
cd /home/jakub/StockAnalyzer/ml-training

# Run diagnostic tests
docker-compose run --rm ml-training python create_labels/01_diagnose_current_labels.py
```

**Expected Output:**
- Confirmation that SPY features dominate (42%+ importance)
- Label-SPY correlation > 0.60
- Ablation study: AUC drops 20+ points without SPY

### Step 2: Generate Alpha Labels (30 minutes)

```bash
# Generate alpha labels (binary, 2% target)
docker-compose run --rm ml-training python create_labels/02_create_alpha_labels.py \
    --type binary \
    --alpha-target 0.02 \
    --lookahead 20

# Also generate 5-class for comparison
docker-compose run --rm ml-training python create_labels/02_create_alpha_labels.py \
    --type 5class \
    --alpha-target 0.02 \
    --lookahead 20
```

### Step 3: Train Comparison Models (2-4 hours)

```bash
# Train 3 models in parallel
docker-compose run --rm ml-training python create_labels/03_train_comparison.py \
    --models current alpha_with_spy alpha_no_spy \
    --dataset-folder <your_dataset> \
    --trials 25
```

**Expected Results:**

| Model Type | Expected AUC | Insider Features Used? | Real Alpha? |
|------------|--------------|------------------------|-------------|
| Current (beta) | 76% | No (0.00-1.2%) | No |
| Alpha + SPY | 56-60% | Partial (5-15%) | Partial |
| Alpha - SPY | 52-56% | Yes (15-25%) | **Yes** |

### Step 4: Analyze Results (30 minutes)

```bash
# View comparison report
cat create_labels/outputs/comparison_results/comparison_summary.txt

# View feature importance
cat create_labels/outputs/feature_importance/alpha_no_spy_importance.csv
```

**Decision Point:**
- If Alpha - SPY shows insider features in top 20: **Proceed to Phase 2**
- If SPY still dominates: **Need stronger alpha labels or more feature engineering**

---

## Configuration

### Alpha Label Parameters

Edit `config/alpha_config.yaml`:

```yaml
alpha_labels:
  # Binary classification
  binary:
    alpha_target: 0.02      # 2% outperformance
    lookahead: 20           # 20 days
    min_samples: 100        # Minimum samples per stock

  # 5-class classification
  multiclass:
    strong_outperform: 0.03    # >3% alpha
    outperform: 0.01           # >1% alpha
    market_perform: -0.01      # -1% to +1%
    underperform: -0.03        # <-3% alpha

  # Beta-adjusted
  beta_adjusted:
    alpha_target: 0.02
    beta_window: 252          # 1 year rolling beta
    min_beta_stocks: 50       # Minimum stocks for beta calc
```

### Risk Parameters

Your risk tolerance:
```yaml
trading:
  stop_loss: -0.02           # 2% loss
  profit_target: 0.03        # 3% gain (conservative)
  profit_target_aggressive: 0.04  # 4% gain (aggressive)
  risk_reward_ratio: 1.5     # Minimum 1.5:1
  max_positions: 10          # Max concurrent positions
  position_size: 0.02        # 2% per position
```

---

## Success Criteria

### Phase 1 Success (Week 1)

✅ Diagnostics confirm SPY dominance
✅ Alpha labels generated successfully
✅ Alpha - SPY model shows insider features in top 20
✅ AUC drop is acceptable (52-56% vs 76%)

### Phase 2 Success (Week 2)

✅ Enhanced insider features increase importance to 10-20%
✅ Regime features add predictive power
✅ AUC improves to 56-60% with alpha labels
✅ Backtest shows positive alpha vs SPY

### Phase 3 Success (Week 3-4)

✅ Stacking ensemble improves AUC to 58-62%
✅ TabNet adds attention-based interpretability
✅ Win rate achieves 55-58% on test set
✅ Sharpe ratio > 1.5 on validation data

### Final Success Metrics

| Metric | Current | Target | Stretch |
|--------|---------|--------|---------|
| AUC | 76% (beta) | 54-58% (alpha) | 60-64% |
| Win Rate | Unknown | 55-58% | 60-65% |
| Annual Alpha | -1% | +4-7% | +10-13% |
| Sharpe Ratio | < 1.0 | 1.2-1.6 | 1.6-2.0 |
| Max Drawdown | > 25% | < 20% | < 15% |

---

## Key Decisions & Rationale

### Decision 1: Keep SPY Features Initially

**Rationale:**
- A/B testing needs baseline
- SPY provides market context (valuable information)
- Can remove later if confirmed harmful
- Better to have data than assumptions

**Reversible:** Yes - can drop SPY anytime

### Decision 2: Target 55-58% Win Rate (not 65%)

**Rationale:**
- 65% is extremely ambitious for 20-day stock picking
- Professionals target 55-60%
- Focus on risk-adjusted returns (Sharpe ratio)
- 55% with 2:1 risk-reward = profitable trading

**Adjustable:** Can aim higher if initial results strong

### Decision 3: Binary Labels First, 5-Class Later

**Rationale:**
- Binary is simpler and more interpretable
- Easier to validate (outperform vs not)
- 5-class adds complexity without clear benefit yet
- Can always expand to 5-class if binary works

**Extensible:** 5-class implementation ready when needed

### Decision 4: Long-Only Strategy

**Rationale:**
- Matches your trading approach
- Simpler risk management
- No short-selling costs/borrowing issues
- Focus on finding winners, not predicting losers

**Note:** Alpha labels still valuable (find stocks that beat market)

### Decision 5: 20-Day Lookahead

**Rationale:**
- Matches your swing trading timeframe
- Short enough for reasonable signal count
- Long enough to capture meaningful moves
- Aligns with 3-4 week holding periods

**Flexible:** Can test 10d/30d/40d if needed

---

## Validation Checklist

Before deploying any model to production:

- [ ] Diagnostics run and documented
- [ ] Alpha labels validated (check distribution)
- [ ] Feature importance shows insider features in top 20
- [ ] AUC measured on out-of-sample data (2024+)
- [ ] Backtest shows positive alpha vs SPY buy-and-hold
- [ ] Win rate > 52% on test set (minimum)
- [ ] Sharpe ratio > 1.0 on validation
- [ ] Maximum drawdown < 25%
- [ ] No data leakage confirmed
- [ ] Regime testing: works in bull, bear, ranging markets
- [ ] Predictions have low correlation with SPY direction (<0.4)
- [ ] Feature importance shows diverse feature usage

---

## Troubleshooting

### Issue: "AUC drops to 52% - this is worse!"

**Reality Check:**
- 52% AUC on alpha is BETTER than 76% on beta
- You're now solving the correct problem
- This is the genuine difficulty of stock picking
- 52-56% alpha AUC can generate real trading profits

### Issue: "Insider features still ignored after alpha labels"

**Solutions:**
1. Check feature engineering (raw counts may not be useful)
2. Transform to unusual activity indicators
3. Create interaction features (insider × technical)
4. Remove SPY features (force model to use insider)

### Issue: "Win rate only 52%, not 65%"

**Perspective:**
- 52% win rate with 2:1 risk-reward = profitable
- 65% win rate is extremely ambitious
- Focus on Sharpe ratio, not just win rate
- Many profitable traders run 53-55% win rates

### Issue: "Model fails in ranging markets"

**Solutions:**
1. Regime-specific models (train separate models)
2. Add regime features (ADX, volatility regime)
3. Reduce position sizes in low-conviction periods
4. Only trade when ADX > 20 (trending)

---

## Next Steps

1. **Review this README** and confirm strategy aligns with your goals
2. **Run diagnostic script** to confirm the problem
3. **Generate alpha labels** for your dataset
4. **Train comparison models** to validate approach
5. **Analyze results** and decide on Phase 2

---

## Questions or Concerns?

If anything in this plan doesn't align with your goals, we can adjust:

- Want higher win rate → Stricter thresholds, more features
- Want simpler approach → Skip advanced models, use XGBoost only
- Want faster implementation → Use existing labels, enhance features only
- Want different timeframe → Adjust lookahead period

**The key insight:** Better to solve the right problem (alpha) imperfectly, than the wrong problem (beta) perfectly.

---

**Last Updated:** 2026-02-05
**Status:** Ready for Phase 1 Implementation
**Owner:** ML Team
**Review Date:** After Phase 1 completion
