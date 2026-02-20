# ML Model Performance Diagnosis & Brainstorming Session

**Date:** 2026-02-01
**Current Best AUC:** 56.8% (Ensemble)
**Target AUC:** 65%+
**Status:** Models performing at ~random levels (50% = coin flip)

---

## PART 1: WHAT WE HAVE - Current Setup

### Data Statistics

| Metric | Value | Expected | Status |
|--------|-------|----------|--------|
| **Stocks** | 252 | 250-650 | OK |
| **Historical Data** | 3 years (2023-2026) | 5+ years | INSUFFICIENT |
| **Training Samples** | ~130,000 | 250,000+ | LOW |
| **Features** | 76 | 40-60 | HIGH (may be overfitting) |
| **Positive Class** | 44.8% | 40-50% | BALANCED |
| **Target** | +3% before -2% (20 days) | Swing trading | OK |

### Current Feature Breakdown

```
Technical Indicators (~30 features):
├── RSI (14-day)
├── MACD (12, 26, 9)
├── Bollinger Bands (20-day, 2σ)
├── Moving Averages (50, 200) + crossovers
├── ADX, +DI, -DI
└── SMA/EMA signals

Log Returns & Momentum (~15 features):
├── log_return_1d, 5d, 10d, 20d
├── momentum_5d, 10d, 20d
└── Price position within range

Volatility (~10 features):
├── volatility_10d, 20d, 60d
├── volume_volatility_10d
└── daily_range features

Volume (~8 features):
├── log_volume
├── volume_change
└── gap up/down patterns

Price Action (~8 features):
├── daily_range
├── gap (overnight)
└── Price vs MA slopes

Market Context: 0 features ❌
Insider Trading: 0 features ❌
Sector Features: 0 features ❌
Regime Detection: 0 features ❌
```

### Current Model Performance

| Model | AUC | Accuracy | Precision | Recall | Weight |
|-------|-----|----------|-----------|--------|--------|
| XGBoost | 56.3% | 56.6% | 48.9% | 25.5% | 29% |
| CatBoost | 56.7% | 56.7% | 49.1% | 28.6% | 53% |
| TCN | 50.0% | 42.9% | 42.9% | 100.0% | 18% |
| Chronos | 49.0% | 43.0% | 42.9% | 99.5% | 0% |
| **Ensemble** | **56.8%** | **49.6%** | **45.3%** | **84.0%** | - |

---

## PART 2: WHY PERFORMANCE IS LOW - Root Cause Analysis

### Issue #1: NOT ENOUGH HISTORICAL DATA

```
Current: 3 years = ~750 trading days
Recommended: 5+ years = 1,250+ trading days

Impact:
├── Fewer training samples (130K vs 250K+)
├── Only saw bull market (2023-2024 was mostly up)
├── No bear market experience (missing 2022 crash)
├── No high-volatility regime (COVID era excluded)
└── Model overfits to recent market conditions
```

**Evidence:**
- 3 years covers only ONE market regime
- Model may fail when market changes
- Insufficient samples for 76 features (ratio: ~1,700 samples/feature - need 5,000+)

### Issue #2: MISSING "YOUR EDGE" - INSIDER TRADING FEATURES

```
From ML_CONVERSATION_KEYPOINTS.md:
"Insider trading data is YOUR COMPETITIVE EDGE"
"Expected to contribute 30% of feature importance"

Current Implementation: 0 insider features ❌
```

**Missing Insider Features (12 planned, 0 implemented):**
- `insider_buy_count_30d`
- `insider_sell_count_30d`
- `insider_net_ratio`
- `ceo_bought_30d` ← STRONG SIGNAL
- `cfo_bought_30d` ← STRONG SIGNAL
- `cluster_buying` (3+ insiders) ← +5.2% abnormal returns
- `insider_buy_at_52w_low` ← +8.3% abnormal returns (STRONGEST!)
- `insider_timing_score`
- `insider_sector_consensus`

**Impact:**
- Missing strongest predictive signals available
- Using only public technical data that everyone has
- No competitive edge vs other traders

### Issue #3: NO MARKET CONTEXT FEATURES

```
Current: Model treats each stock in isolation
Problem: Stocks don't move independently!

Missing Features:
├── VIX (volatility index)
├── SPY correlation (beta)
├── Sector performance
├── Market regime (bull/bear/range)
└── Cross-stock momentum
```

**Impact:**
- Model doesn't know if market is crashing or rallying
- Buys stocks in bear market (should be selling)
- Doesn't account for sector rotation
- Misses clear market-level signals

### Issue #4: TOO MANY CORRELATED FEATURES

```
Feature correlation analysis needed:
├── RSI, MACD, Bollinger Bands → HIGHLY correlated
├── 4 volatility measures → REDUNDANT
├── 4 momentum measures → REDUNDANT
├── Multiple moving averages → REDUNDANT

Result: Model confused, overfitting to noise
```

**Rule of thumb:**
- Start with 20-30 high-quality features
- Each feature should add UNIQUE information
- Feature importance > 1% is meaningful
- Features < 1% importance → DROP

### Issue #5: TARGET DEFINITION ISSUES

```
Current: +3% before -2% within 20 days

Problems:
├── 44.8% of samples hit target → Is this realistic?
├── 20-day window is LONG (many things happen in 20 days)
├── +3% target may be TOO ambitious for current features
├── Doesn't account for transaction costs
└── Binary (0/1) loses information (how close was it?)
```

**Alternative:**
- Try +5% before -3% (easier to predict)
- Try 10-day window (shorter = more signal)
- Try regression (predict expected return, not binary)

### Issue #6: NO REGIME AWARENESS

```
Different strategies work in different markets:

Bull Market (SPY 50d > 200d, VIX < 18):
├── Best: Momentum, trend-following
├── Expected win rate: 65-70%
└── Current model: Same for all conditions

Bear Market (SPY 50d < 200d, VIX > 25):
├── Best: Mean-reversion, short-selling
├── Expected win rate: 55-60% (harder)
└── Current model: Same for all conditions

Current: One model for all regimes ❌
```

### Issue #7: TEMPORAL VALIDATION WITH ONLY 3 YEARS

```
3-year split:
├── Train: 2023-01 to 2024-06 (~70%)
├── Val: 2024-06 to 2024-09 (~15%)
└── Test: 2024-09 to 2024-12 (~15%)

Problem:
├── Train/test are from SAME market regime
├── No out-of-sample regime testing
├── 56.8% AUC may be LUCK (overfit to recent conditions)
└── Real performance could be 50% when market changes
```

---

## PART 3: IS STOCK PREDICTION EVEN POSSIBLE?

### The Efficient Market Hypothesis

```
Strong Form: Prices reflect ALL information (public + private)
  → Stock prediction is IMPOSSIBLE
  → Current AUC: 56.8% (supports this)

Semi-Strong Form: Prices reflect all PUBLIC information
  → Insider trading gives edge
  → Public technical analysis: NO edge
  → Current: Only public features (consistent with 56.8% AUC)

Weak Form: Prices reflect all PAST price information
  → Technical analysis should NOT work
  → Current: Only technical features (consistent with poor results)
```

**Conclusion:**
- With ONLY technical indicators → 56-57% AUC is expected
- To get 65%+ AUC → Need INSIDER data or alternative data
- Stock market IS mostly efficient, but NOT perfectly efficient

### Why 56.8% Might Be "Good" (Given Current Features)

```
Current features: ONLY public technical indicators
Competition: Hedge funds, HFT, institutional traders
Reality: They ALL have the same technical indicators

Therefore:
├── Technical edge = ZERO
├── 56.8% AUC = Slightly better than random
├── May be due to: Overfitting, luck, or tiny signal
└── Real out-of-sample: Could be 50-52%
```

---

## PART 4: ACTION PLAN - How to Get 65%+ AUC

### Priority 1: ADD INSIDER TRADING FEATURES ⭐⭐⭐⭐⭐

**Expected Impact:** +8-12% AUC

```python
# Implement these features (in database):
insider_features = {
    # Basic counts (from insider_trades table)
    'insider_buy_count_30d': "COUNT(*) WHERE transaction_type='buy' AND date > NOW()-30",
    'insider_sell_count_30d': "COUNT(*) WHERE transaction_type='sell' AND date > NOW()-30",
    'insider_net_ratio': "(buys - sells) / (buys + sells)",

    # KEY INSIDERS (strongest signals)
    'ceo_bought_30d': "EXISTS(SELECT 1 WHERE insider_type='CEO' AND transaction_type='buy')",
    'cfo_bought_30d': "EXISTS(SELECT 1 WHERE insider_type='CFO' AND transaction_type='buy')",

    # Cluster detection (3+ insiders buying)
    'cluster_buying': "COUNT(DISTINCT insider_id) WHERE buy AND 30d >= 3",

    # Context features (CRITICAL)
    'insider_buy_at_52w_low': "buy AND price_within_5pct_of_52w_low",  # +8.3% returns!
    'insider_buy_at_52w_high': "buy AND price_within_5pct_of_52w_high",  # Weaker signal

    # Historical accuracy
    'insider_timing_score': "AVG(accuracy_of_past_trades_for_this_insider)",

    # Sector consensus
    'insider_sector_consensus': "pct_of_insiders_buying_in_same_sector_last_30d",

    # Leader detection
    'insider_pattern_leader': "This insider's historical beat_market_rate",
}

# Expected feature importance: 25-35%
```

**Implementation:**
1. Check if `insider_trades` table exists in DB
2. If yes → Write feature extraction script
3. If no → Sign up for insider trading API (OpenInsider, Quiver, etc.)

### Priority 2: ADD MARKET CONTEXT FEATURES ⭐⭐⭐⭐

**Expected Impact:** +3-5% AUC

```python
market_context_features = {
    # Market regime indicators
    'vix_value': "Current VIX value",
    'vix_change_5d': "VIX change over 5 days",
    'spy_above_ma200': "SPY close > SPY 200-day MA",
    'spy_50d_above_200d': "SPY 50d MA > SPY 200d MA (bull/bear market)",

    # Correlation features
    'stock_beta': "Correlation with SPY (60-day)",
    'stock_relative_strength': "stock_return_20d / spy_return_20d",

    # Sector features
    'sector_return_5d': "Average return of sector (5-day)",
    'sector_relative_strength': "sector_return / market_return",

    # Market-wide signals
    'advance_decline_ratio': "advancing_stocks / declining_stocks (NYSE)",
    'new_highs_lows': "(new_52w_highs - new_52w_lows) / total_stocks",
}

# Expected feature importance: 10-15%
```

**Implementation:**
1. Add VIX data to DB (free from Polygon.io or Alpha Vantage)
2. Add SPY data (benchmark ETF)
3. Calculate sector returns
4. Add market regime detection

### Priority 3: EXTEND HISTORICAL DATA ⭐⭐⭐⭐

**Expected Impact:** +2-4% AUC

```
Current: 3 years (2023-2026)
Target: 5+ years (2019-2026)

Benefits:
├── More training samples (130K → 200K+)
├── Multiple market regimes:
│   ├── 2019: Bull market
│   ├── 2020: COVID crash + recovery
│   ├── 2021: Bull market
│   ├── 2022: Bear market (inflation, rate hikes)
│   ├── 2023: Recovery
│   └── 2024-2026: Mixed conditions
├── Model learns regime-specific patterns
└── Better generalization

Implementation:
├── Extend Polygon.io data download
├── Backfill to 2019-01-01
└── Use exponential weighting (recent = more important)
```

### Priority 4: FEATURE REDUCTION ⭐⭐⭐

**Expected Impact:** +1-3% AUC (via better generalization)

```python
# Current: 76 features (too many correlated)
# Target: 25-35 features (high quality)

KEEP (high signal):
├── RSI (14) - momentum indicator
├── Volatility (20d) - risk measure
├── log_return_5d - recent momentum
├── volume_change_5d - volume breakout
├── price_vs_ma50 - trend
├── beta - market correlation
├── vix_value - market fear
├── insider_buy_count_30d - YOUR EDGE
├── ceo_bought_30d - YOUR EDGE
├── cluster_buying - YOUR EDGE
└── insider_buy_at_52w_low - YOUR EDGE

DROP (redundant):
├── log_return_10d, log_return_20d (keep 5d only)
├── volatility_10d, volatility_60d (keep 20d only)
├── Multiple MAs (keep 50d and 200d only)
├── Bollinger Bands (redundant with volatility)
├── ADX/+DI/-DI (redundant with RSI)
└── gap_up_5d_sum, gap_down_5d_sum (weak signal)
```

### Priority 5: REGIME-AWARE MODEL ⭐⭐⭐

**Expected Impact:** +2-4% AUC

```python
class RegimeAwareModel:
    """
    Train separate models for different market regimes
    """
    def __init__(self):
        self.bull_market_model = None  # VIX < 18, SPY 50d > 200d
        self.bear_market_model = None  # VIX > 25, SPY 50d < 200d
        self.range_bound_model = None  # VIX < 15

    def predict(self, features, market_data):
        # Detect regime
        vix = market_data['vix']
        spy_trend = market_data['spy_50d_above_200d']

        if vix < 18 and spy_trend:
            return self.bull_market_model.predict(features)
        elif vix > 25 and not spy_trend:
            return self.bear_market_model.predict(features)
        else:
            return self.range_bound_model.predict(features)

# Expected:
# - Bull market: 65-70% accuracy
# - Bear market: 55-60% accuracy (harder)
# - Overall: 62-65% accuracy
```

### Priority 6: ALTERNATIVE TARGET DEFINITIONS ⭐⭐

**Expected Impact:** Unknown (experiment)

```python
# Option A: More conservative target
def create_labels_conservative(df, stock_id):
    """+5% before -3% within 20 days (easier to predict)"""
    target_profit = 0.05  # 5%
    stop_loss = 0.03      # 3%

# Option B: Shorter window
def create_labels_short_window(df, stock_id):
    """+3% before -2% within 10 days (more signal, less noise)"""
    lookahead_days = 10

# Option C: Regression instead of classification
def create_labels_regression(df, stock_id):
    """Predict expected return (not binary)"""
    return {
        'target': max_20d_return,  # Actual max return in 20 days
        'hit_target': 1 if max_return >= 0.03 else 0
    }

# Option D: Multi-class
def create_labels_multiclass(df, stock_id):
    """
    0: Strong Buy (hit +5% within 20d)
    1: Buy (hit +3% within 20d)
    2: Hold (neither)
    3: Sell (hit -3% within 20d)
    """
```

### Priority 7: SECTOR-SPECIFIC MODELS ⭐⭐

**Expected Impact:** +1-3% AUC

```python
# Different sectors behave differently
sector_models = {
    'Technology': "Growth-focused, high beta",
    'Healthcare': "Defensive, news-driven",
    'Financial': "Rate-sensitive, cyclical",
    'Energy': "Commodity-linked, cyclical",
    'Consumer': "Stable, earnings-driven",
}

# Approach:
# 1. Train universal model on all stocks
# 2. Train sector-specific models (11 sectors)
# 3. Ensemble: 70% sector + 30% universal
```

---

## PART 5: IMPLEMENTATION ROADMAP

### Phase 1: Quick Wins (1-2 weeks) - Target: 60-62% AUC

```yaml
Week 1: Insider Trading Features
  - [ ] Check if insider_trades table exists
  - [ ] If yes: Extract features
  - [ ] If no: Sign up for OpenInsider API (free)
  - [ ] Implement insider_buy_count_30d, ceo_bought_30d, cluster_buying
  - [ ] Add insider_buy_at_52w_low (strongest signal!)
  - [ ] Retrain models with new features
  - Expected: +5-8% AUC (62-64%)

Week 2: Market Context Features
  - [ ] Add VIX data to database (Polygon.io)
  - [ ] Add SPY data (benchmark)
  - [ ] Calculate beta, correlation
  - [ ] Add market regime detection
  - [ ] Retrain models
  - Expected: +2-3% AUC (64-67%)
```

### Phase 2: Data Expansion (2-3 weeks) - Target: 63-65% AUC

```yaml
Week 3-4: Extend Historical Data
  - [ ] Backfill data to 2019-01-01
  - [ ] Download historical data for all 252 stocks
  - [ ] Update feature engineering with exponential weighting
  - [ ] Retrain on 5+ years of data
  - Expected: +2-3% AUC (65-68%)

Week 5: Feature Reduction
  - [ ] Run feature importance analysis
  - [ ] Remove features < 1% importance
  - [ ] Remove highly correlated features (rho > 0.9)
  - [ ] Final feature set: 25-30 features
  - Expected: +1-2% AUC (66-70%)
```

### Phase 3: Advanced Models (2-3 weeks) - Target: 65-70% AUC

```yaml
Week 6: Regime-Aware Models
  - [ ] Split data by market regime (bull/bear/range)
  - [ ] Train separate models for each regime
  - [ ] Implement regime detector
  - [ ] Ensemble with regime selection
  - Expected: +2-4% AUC (68-74%)

Week 7: Sector-Specific Models
  - [ ] Group stocks by sector (11 sectors)
  - [ ] Train sector-specific models
  - [ ] Hybrid: 70% sector + 30% universal
  - Expected: +1-2% AUC (69-76%)

Week 8: Target Optimization
  - [ ] Experiment with alternative targets
  - [ ] Try regression instead of classification
  - [ ] Try multi-class classification
  - [ ] Select best performing target
  - Expected: +0-2% AUC (69-78%)
```

---

## PART 6: REALISTIC EXPECTATIONS

### What's Actually Achievable?

```
With ONLY technical indicators:
├── Current: 56.8% AUC
└── Realistic Max: 58-60% AUC

With +Insider trading data:
├── Expected: 65-70% AUC
└── Best Case: 72-75% AUC

With +Market context:
├── Expected: 68-73% AUC
└── Best Case: 75-78% AUC

With +5 years data:
├── Expected: +2-3% AUC
└── Better generalization

With ALL improvements:
├── Realistic: 70-75% AUC
├── Optimistic: 75-78% AUC
└── Dream: 80%+ AUC (unlikely)
```

### The Hard Truth

```
Stock market prediction is HARD because:

1. Efficient Market Hypothesis (mostly true)
   ├── Public info → Already priced in
   ├── Technical analysis → Everyone has it
   └── Edge → Requires private data (insider, alt data)

2. Signal-to-Noise Ratio
   ├── Signal: Maybe 5-10% of price movement
   ├── Noise: 90-95% of price movement
   └── ML models: Hard to extract signal from noise

3. Non-Stationarity
   ├── Market patterns change over time
   ├── What worked in 2020 may not work in 2024
   └── Models need constant retraining

4. Competition
   ├── Hedge funds spend billions on this
   ├── HFT firms have microsecond advantages
   └── Retail traders: Always at disadvantage
```

### What 65% Accuracy Means in Practice

```
If you achieve 65% accuracy:

100 trades at $1,000 each:
├── 65 winners: +$3,000 (assuming 3% profit)
├── 35 losers: -$700 (assuming 2% loss)
├── Net profit: $2,300 (2.3% per trade)
└── Annual ROI: ~30-50% (compounding)

But watch out for:
├── Transaction costs (commissions, slippage)
├── Market impact (large orders move price)
├── Overfitting (paper trading ≠ real trading)
└── Regime changes (model fails in bear market)
```

---

## PART 7: IMMEDIATE NEXT STEPS

### Today: Check Insider Data Availability

```sql
-- Check if insider data exists
SELECT COUNT(*) FROM insider_trades;

-- If table exists, check date range
SELECT
    MIN(transaction_date) as first_trade,
    MAX(transaction_date) as last_trade,
    COUNT(DISTINCT stock_id) as stocks_covered
FROM insider_trades;
```

### This Week: Add Top 3 Features

```python
# Feature 1: VIX (market fear)
vix_data = fetch_vix_from_polygon()

# Feature 2: SPY correlation
beta = calculate_beta(stock_returns, spy_returns)

# Feature 3: Market regime
regime = detect_regime(vix, spy_ma50, spy_ma200)
```

### Next Week: Retrain with New Features

```bash
# 1. Run feature engineering with new features
docker-compose run --rm ml-training python \
    /app/scripts/feature_engineering_with_market_context.py

# 2. Retrain models
docker-compose run --rm ml-training python /app/train.py --trials 100

# 3. Check if AUC improved
# Expected: 60-65% AUC
```

---

## SUMMARY: The Path to 65%+ AUC

### Root Cause (Why 56.8% AUC)

1. ❌ No insider trading features (your biggest edge)
2. ❌ No market context features (VIX, SPY, regime)
3. ❌ Only 3 years of data (one market regime)
4. ❌ Too many correlated features (76 → overfitting)
5. ❌ No regime awareness (one model for all conditions)
6. ✅ Technical indicators alone = NOT enough (efficient market)

### Solution (How to Get 65%+)

| Priority | Feature | Effort | Expected Gain |
|----------|---------|--------|---------------|
| 1 | Insider trading features | Medium | +8-12% AUC |
| 2 | Market context (VIX, SPY) | Low | +3-5% AUC |
| 3 | Extend to 5+ years data | Medium | +2-4% AUC |
| 4 | Feature reduction (76→30) | Low | +1-3% AUC |
| 5 | Regime-aware models | Medium | +2-4% AUC |
| 6 | Sector-specific models | Medium | +1-3% AUC |
| 7 | Target optimization | Low | +0-2% AUC |

**Total Expected Improvement:** +17-33% AUC
**Realistic Final AUC:** 70-75%

### Bottom Line

> **Your current models are performing poorly because you're trying to predict the stock market using only public technical indicators that everyone else has.**
>
> **To get 65%+ accuracy, you MUST add:**
> 1. **Insider trading data** (your competitive edge)
> 2. **Market context** (VIX, SPY, regime detection)
> 3. **More historical data** (5+ years for regime diversity)
>
> **Stock market IS mostly efficient, but NOT perfectly efficient.** With the right features, 65-75% AUC is achievable. Without them, 55-58% AUC is expected.

---

**End of Brainstorming Session**

Next step: Check if insider_trades table exists, then implement Priority 1 features.
