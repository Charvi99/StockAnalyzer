# REVISED ROADMAP - After Critical Discovery

**Date:** 2026-02-05
**Discovery:** Model without SPY performs at RANDOM (48.8% AUC)
**Impact:** Complete strategy revision required

---

## CRITICAL FINDING 🚨

### What We Discovered

```
Original Assumption (WRONG):
├─ Model had 63.6% AUC without SPY
├─ Could predict alpha with some success
└─ Alpha labels would improve on 63.6%

Actual Reality (TRUE):
├─ Model WITHOUT SPY: 48.8% AUC (RANDOM!)
├─ Model WITH SPY: 63.6% AUC (market timing only)
└─ Model has ZERO alpha prediction capability
```

### What This Means

**Your model is a market-timing model, NOT a stock-picking model.**

- Without SPY features: Random guessing (48.8% AUC)
- With SPY features: Market direction prediction (63.6% AUC)
- Either way: No stock selection capability

---

## REVISED STRATEGY

### Core Problem Statement

**Your model learns:**
```
"If SPY is going up, predict BUY for all stocks"
"If SPY is going down, predict DON'T BUY for all stocks"
```

**It does NOT learn:**
```
"Will THIS stock beat SPY?"
"Which stocks have the best risk-reward?"
"Which stocks have insider accumulation?"
```

### The Fix

**We need to FORCE the model to learn stock-specific alpha:**

1. **Alpha labels** - Make the objective explicit (beat SPY by 2%)
2. **Remove/minimize SPY** - Force model to find stock-specific signals
3. **Enhanced features** - Raw insider data isn't enough
4. **Feature transformations** - Unusual activity, value context, etc.

---

## REVISED ROADMAP

### PHASE 0: Baseline Establishment ⚠️ (NEW)

**Status:** In Progress
**Duration:** 1-2 days
**Goal:** Establish TRUE baseline with alpha labels

| Step | Action | Expected Outcome |
|------|--------|------------------|
| 0.1 | ✅ Alpha labels created | `labels_alpha_binary.parquet` exists |
| 0.2 | Train with alpha labels + SPY | AUC: 50-54% (worse than 63.6%) |
| 0.3 | Train with alpha labels - SPY | AUC: 50-53% (slightly better than random) |
| 0.4 | Compare feature importance | Confirm insider features still ignored |

**Success Criteria:**
- AUC drops to 50-54% (expected, not bad!)
- Understand current baseline capability

**Files Created:**
- `labels_alpha_binary.parquet` ✅
- Diagnostic results ✅

---

### PHASE 1: Aggressive Feature Engineering 🔧 (PRIORITY)

**Status:** Not Started
**Duration:** 1 week
**Goal:** Create features that ACTUALLY predict stock performance

#### 1.1 Enhanced Insider Features (CRITICAL)

```python
# Current insider features (model ignores):
insider_buy_count_30d = 5     # Model: "So what?"
insider_sentiment_30d = 0.6    # Model: "Meaningless"

# Enhanced insider features (new):
insider_buy_unusual = 1         # Model: "This is top 20% historically!"
insider_buying_dip = 1         # Model: "Insiders buying + RSI<30!"
insider_at_52w_low = 1         # Model: "Insiders buying at 52-week low!"
exec_cluster = 1               # Model: "CEO AND CFO buying together!"
```

**Script:** `04_engineer_insider_features.py`

#### 1.2 Market-Relative Features

```python
# Stock performance vs sector peers
stock_vs_sector_20d = stock_return - sector_etf_return_20d

# Relative strength vs market
relative_strength = stock_return / spy_return_20d

# Beta-adjusted returns
expected_return = beta * spy_return
alpha = stock_return - expected_return
```

**Script:** `05_create_relative_features.py`

#### 1.3 Regime-Specific Features

```python
# Market regime
regime_bull = (adx > 25) & (spy_return_20d > 0)
regime_bear = (adx > 25) & (spy_return_20d < 0)
regime_ranging = (adx < 20)

# Volatility regime
vol_high = (atr / atr_50d_ma) > 1.2
vol_low = (atr / atr_50d_ma) < 0.8

# Regime-adjusted insider signals
insider_signal_strong = insider_sentiment_30d * (1 + regime_ranging * 0.5)
```

**Script:** `06_create_regime_features.py`

---

### PHASE 2: Feature Selection & Experimentation 🧪

**Status:** Not Started
**Duration:** 3-5 days
**Goal:** Find features that actually predict alpha

#### 2.1 Ablation Studies

```bash
# Test different feature combinations:
1. Technical only (no insider, no SPY)
2. Technical + Insider (no SPY)
3. Technical + SPY (current)
4. Technical + Insider + SPY (all)
```

**Expected Results:**
| Feature Set | Expected AUC | Insider Used? | Trading Value |
|-------------|--------------|---------------|---------------|
| Technical only | 50-52% | N/A | Low |
| Tech + Insider | 52-55% | Maybe | Some |
| Tech + SPY | 63.6% | No | Market timing only |
| All features | 54-58% | Yes | **Stock picking!** |

#### 2.2 SPY Feature Strategy

**Three approaches to test:**

**Option A: Remove SPY entirely**
- Pros: Forces model to find stock-specific signals
- Cons: Hardest task, might fail completely

**Option B: Transform SPY to relative features**
- Replace: `spy_ma_200`, `spy_close`
- With: `stock_vs_spy_correlation`, `beta`, `relative_strength`
- Pros: Keeps market context without overfitting
- Cons: More complex

**Option C: Keep SPY but use alpha labels**
- Pros: Easiest, keeps useful information
- Cons: Model might still just predict market direction

**Recommendation:** Start with Option C, try B if C fails.

---

### PHASE 3: Model Training & Validation 🎯

**Status:** Not Started
**Duration:** 1 week
**Goal:** Achieve realistic alpha prediction

#### 3.1 Training Configuration

```yaml
Label: Alpha binary (beat SPY by 2%)
Features:
  - Technical indicators ✓
  - Enhanced insider features ✓
  - Market-relative features ✓
  - SPY (transformed) ✓

Train/Test Split:
  - Train: 2021-2023 (70%)
  - Val: 2024 (15%)
  - Test: 2025 (15%)

Class Balancing:
  - Scale_pos_weight: auto
  - Or: SMOTE for minority class
```

#### 3.2 Realistic Targets

| Metric | Current | Realistic Target | Stretch Goal |
|--------|---------|------------------|--------------|
| **AUC** | 48.8% (no SPY) | **52-55%** | 55-58% |
| **Accuracy** | 73.6% | 70-72% | 72-74% |
| **Precision** | 48.5% | 52-55% | 55-58% |
| **Recall** | 9.5% | **20-25%** | 25-30% |
| **Win Rate** | Unknown | **52-55%** | 55-58% |
| **Annual Alpha** | -1% | **+2-4%** | +4-6% |

**Key insight:** Improving RECALL from 9.5% to 20-25% is CRITICAL. This means finding more BUY signals.

---

### PHASE 4: Advanced Model Architecture 🤖

**Status:** Not Started
**Duration:** 1-2 weeks
**Goal:** Squeeze out extra performance

**ONLY PROCEED IF:** Phase 3 achieves 52%+ AUC

#### 4.1 Ensemble Methods

```python
models = [
    'XGBoost (conservative)',
    'CatBoost (balanced)',
    'LightGBM (fast)',
]

# Stacking ensemble
meta_learner = LogisticRegression()
```

**Expected gain:** +1-2% AUC

#### 4.2 TabNet (Attention-based)

```python
from pytorch_tabnet import TabNetClassifier

# Learns feature interactions automatically
# Attention mechanism shows which features matter
```

**Expected gain:** +2-3% AUC

#### 4.3 Temporal Models (if data supports it)

```python
# Use sequence of past prices to predict future
# More complex, might not help for 20-day horizon
```

**Expected gain:** +0-2% AUC

**Maximum realistic AUC: 58-60%** (with perfect feature engineering)

---

### PHASE 5: Production Deployment 🚀

**Status:** Not Started
**Duration:** 1 week
**Goal:** Deploy to trading with proper risk management

#### 5.1 Trading Strategy

```python
# Only trade when confidence is high
if prediction_probability > 0.65:
    position_size = 2%  # 2% of portfolio
    stop_loss = -2%
    target = +3%
elif prediction_probability > 0.55:
    position_size = 1%  # 1% of portfolio
    stop_loss = -2%
    target = +3%
else:
    # Don't trade
    pass
```

#### 5.2 Risk Management

```python
# Max positions
max_positions = 10
max_correlation = 0.7  # Don't over-expose to correlated stocks

# Sector diversification
max_per_sector = 30%

# Stop loss
max_drawdown_per_position = -2%
max_portfolio_drawdown = -10%
```

#### 5.3 Monitoring

```python
# Track metrics daily
- Win rate (rolling 30 trades)
- Sharpe ratio
- Maximum drawdown
- Correlation with SPY (should be low for alpha!)
```

---

## IMMEDIATE NEXT STEPS (This Week)

### Step 1: Train Baseline with Alpha Labels (Today)

```bash
docker-compose run --rm ml-training python train.py \
  --dataset-folder dataset_20260204_204134 \
  --label-type alpha_binary \
  --models xgboost catboost \
  --trials 25 \
  --skip-tcn
```

**Expected:**
- AUC: 50-54% (with SPY)
- Confirms baseline with alpha labels
- Provides comparison point

### Step 2: Engineer Enhanced Features (Week 1)

```bash
# Create enhanced insider features
python create_labels/04_engineer_insider_features.py

# Create market-relative features
python create_labels/05_create_relative_features.py
```

### Step 3: Retrain with Enhanced Features (Week 2)

```bash
docker-compose run --rm ml-training python train.py \
  --dataset-folder dataset_20260204_204134 \
  --label-type alpha_binary \
  --features-file enhanced_features.parquet \
  --models xgboost catboost \
  --trials 50
```

**Expected:**
- AUC: 52-55%
- Insider features in top 20 importance
- Better recall (20-25%)

### Step 4: Evaluate & Decide (Week 2-3)

**If AUC ≥ 52%:**
- ✅ Proceed to Phase 3 (Model tuning)
- ✅ Consider advanced architectures
- ✅ Plan production deployment

**If AUC < 52%:**
- ⚠️ More feature engineering needed
- ⚠️ Consider different label strategy
- ⚠️ May need more data sources

---

## REALISTIC TIMELINE

```
Week 1 (Feb 5-11):   Baseline + Feature Engineering
Week 2 (Feb 12-18):  Training & Evaluation
Week 3 (Feb 19-25):  Iteration & Improvement
Week 4 (Feb 26-Mar 4): Advanced Models (if needed)
Month 2 (Mar 5-30):   Production Preparation
```

**Total time to viable model:** 4-6 weeks

---

## REVISED SUCCESS CRITERIA

### Minimum Viable Model (MVP)

**Must achieve:**
- ✅ AUC: 52% on temporal test set
- ✅ Win rate: 52% on predictions with p > 0.6
- ✅ Annual alpha: +2% vs SPY buy-and-hold
- ✅ Sharpe ratio: > 1.0
- ✅ Max drawdown: < 20%
- ✅ Insider features: Top 30 importance

**Trading performance:**
- 100 trades over 6 months
- 52% win rate with 2:1 risk-reward
- Average hold: 20 days
- Expected return: +12-15% annually

### Production Model

**Stretch goals:**
- AUC: 55% on temporal test set
- Win rate: 55% on predictions with p > 0.6
- Annual alpha: +4-6% vs SPY
- Sharpe ratio: > 1.5
- Max drawdown: < 15%

---

## KEY STRATEGIC SHIFTS

### FROM (Original Plan):

```
Assumption: Model has 63.6% AUC without SPY
Strategy: Improve to 54-56% with alpha labels
Focus: Model architecture (TabNet, TFT, etc.)
```

### TO (Revised Plan):

```
Reality: Model has 48.8% AUC without SPY (random!)
Strategy: Build alpha capability from scratch
Focus: FEATURE ENGINEERING (not models)
Approach: Incremental, data-driven, validated at each step
```

---

## DECISION POINTS

### Decision 1: SPY Feature Strategy (Choose One)

**Option A: Remove SPY** ⚠️ Aggressive
- Pros: Forces pure alpha learning
- Cons: Hardest path, might fail

**Option B: Transform SPY** ✅ Recommended
- Pros: Keeps market context, avoids overfitting
- Cons: More complex

**Option C: Keep SPY + Alpha Labels** 🎯 Start here
- Pros: Easiest, good baseline
- Cons: Risk of still predicting beta

**Decision:** Start with C, try B if C doesn't improve enough

### Decision 2: Feature Engineering Priority

**Priority 1 (CRITICAL):** Enhanced insider features
- Unusual activity indicators
- Value context features
- Executive conviction signals

**Priority 2 (HIGH):** Market-relative features
- Stock vs sector performance
- Beta-adjusted returns
- Relative strength metrics

**Priority 3 (MEDIUM):** Regime features
- Market regime classification
- Volatility regime indicators
- Regime-adjusted signals

### Decision 3: Label Strategy

**Stick with 2% alpha target for now**
- If too few BUY signals → lower to 1%
- If too many false positives → raise to 3%

**Binary labels for now**
- 5-class can come later if binary works

---

## RISK MITIGATION

### Risk 1: Feature Engineering Takes Longer Than Expected

**Mitigation:**
- Start with MOST IMPORTANT features first (insider)
- Test incrementally (don't wait for perfect features)
- Can use current features while engineering new ones

### Risk 2: Can't Achieve 52% AUC

**Mitigation:**
- Accept 50-51% AUC if Sharpe ratio is good
- Focus on risk-adjusted returns, not just AUC
- Consider longer holding periods (30-40 days instead of 20)

### Risk 3: Model Works in Bull Market, Fails in Bear

**Mitigation:**
- Validate on different market regimes
- Use regime-specific features
- Reduce position sizes in low-confidence periods

### Risk 4: Overfitting to Training Period

**Mitigation:**
- Use purged cross-validation (gap between train/test)
- Test on out-of-sample period (2025 data)
- Regular model retraining (monthly)

---

## WEEKLY CHECKPOINTS

### Week 1 (Feb 5-11): Baseline Established

**Deliverables:**
- ✅ Alpha labels created
- ⏳ Baseline model trained (alpha + SPY)
- ⏳ Enhanced insider features created

**Success Criteria:**
- Model trains without errors
- Alpha labels work (35.5% BUY rate)
- Features file created

### Week 2 (Feb 12-18): Features Engineered

**Deliverables:**
- ⏳ Enhanced features created
- ⏳ Model retrained with new features
- ⏳ Feature importance analyzed

**Success Criteria:**
- AUC ≥ 52% with new features
- Insider features in top 30 importance
- Recall > 15%

### Week 3 (Feb 19-25): Model Validated

**Deliverables:**
- ⏳ Model tested on different regimes
- ⏳ Backtest results available
- ⏳ Trading strategy defined

**Success Criteria:**
- AUC consistent across test periods
- Sharpe ratio > 1.0
- Ready for paper trading

### Week 4 (Feb 26-Mar 4): Production Ready

**Deliverables:**
- ⏳ Model deployed to paper trading
- ⏳ Monitoring dashboard active
- ⏳ Risk management rules implemented

---

## SUCCESS METRICS TRACKING

### Primary Metrics (Must Hit)

| Metric | Baseline | Target | Current | Status |
|--------|----------|--------|---------|--------|
| AUC (test) | 48.8% | 52-55% | - | ⏳ |
| Win Rate | Unknown | 52-55% | - | ⏳ |
| Sharpe Ratio | <1.0 | >1.0 | - | ⏳ |
| Annual Alpha | -1% | +2-4% | - | ⏳ |
| Max Drawdown | >25% | <20% | - | ⏳ |

### Secondary Metrics (Nice to Have)

| Metric | Target | Notes |
|--------|--------|-------|
| Insider Feature Importance | Top 30 | Stock-specific signals |
| Correlation with SPY | <0.3 | Not predicting beta |
| Recall | >20% | Finding opportunities |
| Precision | >50% | When predicting BUY |

---

## CONCLUSION

### What Changed

**Old understanding:**
- Model had 63.6% AUC without SPY
- Could improve to 54-56% with alpha labels
- Needed "tweaks" to be great

**New reality:**
- Model has 48.8% AUC without SPY (random!)
- Starting from scratch for alpha prediction
- Needs AGGRESSIVE feature engineering
- Target is 52-55% AUC (harder than thought!)

### What This Means

**The challenge is HARDER but the goal is CLEARER:**

1. Build alpha prediction from scratch (48.8% → 52%)
2. Force model to find stock-specific signals
3. Don't rely on market timing (SPY)
4. Focus on FEATURE ENGINEERING, not model architecture

### The Good News

**This is actually liberating:**

✅ You now know the TRUE baseline (48.8%, not 63.6%)
✅ Clear path forward: feature engineering
✅ Realistic targets: 52-55% AUC
✅ No false expectations about beating professionals

### Next Immediate Action

```bash
# Train baseline with alpha labels THIS WEEK
docker-compose run --rm ml-training python train.py \
  --dataset-folder dataset_20260204_204134 \
  --label-type alpha_binary \
  --trials 25 \
  --skip-tcn
```

This will tell us where we really stand and what feature engineering is most needed.

---

**Last Updated:** 2026-02-05
**Status:** Roadmap revised based on critical discovery
**Next Action:** Train baseline with alpha labels
