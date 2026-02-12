# Backtesting Framework - Brainstorming & Roadmap

**Goal**: Simulate real-life trading performance of ML models and compare against baseline strategies.

---

## 📋 USER REQUIREMENTS

### Strategies to Test

**1. Static Baseline Strategies:**
- Buy & Hold (buy at start, hold till end)
- SMA Crossover (buy when fast MA > slow MA)
- MACD Strategy (buy when MACD crosses above signal)
- Random Buy/Sell (null hypothesis test)

**2. ML Model Strategies:**
- Load models from path
- Use classification outputs for buy/sell signals
- Binary: Target-based exit (+3% profit, -2% loss, or 20 days)
- 3-Class/5-Class: Use SELL signals for exits

**3. Key Decisions:**
- **Position Sizing**: Equal weight across positions
- **Rebalancing**: Buy once at start (no rebalancing)
- **Universe**: Same stocks for all strategies
- **Time Period**: Validation period (out-of-sample, no model advantage)

**4. Output:**
- Side-by-side comparison of all strategies
- Interactive HTML plots (PNG fallback)
- Images to shared folder for easy access
- Focus metrics: Return, Win Rate, Trade Count
- Include advanced metrics: Sharpe, Max DD, Volatility, etc.

---

## 🧠 BRAINSTORMING: Key Questions & Considerations

### 1. Binary Classification Exit Strategy ✅ DECIDED

**Chosen: Option B - Target-Based Exit**
```
Entry: Model says BUY with confidence > threshold
Exit (whichever comes first):
  - Profit target: +3%
  - Stop loss: -2%
  - Time exit: 20 days
```

**Why This Works:**
- Matches label definition (labels created with 3% target, 2% stop, 20 days)
- Clear exit rules (no ambiguity)
- Model only needs to predict entry, not exit timing

---

### 2. What Makes Backtesting "Realistic"?

**Common Pitfalls to Avoid:**
- ❌ Look-ahead bias (using future data)
- ❌ Survivorship bias (only testing stocks that still exist)
- ❌ Ignoring transaction costs
- ❌ Assuming perfect fills at theoretical prices
- ❌ Ignoring market impact (our orders moving the price)
- ❌ Overfitting to historical data

**What We MUST Include:**
- ✅ Temporal validation (train on past, test on future)
- ✅ Transaction costs (commission + ECN fees)
- ✅ Slippage (price movement between signal and execution)
- ✅ Market hours timing (signals execute at next open, not instant)
- ✅ Position limits (max % of portfolio per stock)
- ✅ Cash constraints (can't invest more than available)
- ✅ Stop losses & profit targets (how labels were created)
- ✅ Holding period constraints (max days in position)

---

### 3. Trading Strategy Definition

**How Do We Trade Model Predictions?**

```
Model Output → Signal → Position Entry → Position Exit → P&L
```

**Decision Points:**

| Stage | Options | Considerations |
|-------|---------|----------------|
| **Signal Generation** | - Raw probability<br>- Confidence threshold<br>- Top-N stocks per day | Higher confidence = fewer trades but higher precision |
| **Entry Timing** | - Market open next day<br>- Limit orders<br>- Market orders | Market open = realistic, but gap risk |
| **Position Sizing** | - Fixed dollar amount<br>- Kelly criterion<br>- Volatility-weighted<br>- Equal weight | Equal weight simplest to implement |
| **Entry Criteria** | - All signals<br>- Top-N by confidence<br>- Filter by liquidity<br>- Filter by volatility | Need minimum volume/dollar volume |
| **Exit Rules** | - Label target reached (+3%, -2%)<br>- Time-based exit (20 days)<br>- Trailing stop<br>- Model prediction change | Labels define theoretical exit |
| **Risk Management** | - Max drawdown stop<br>- Daily loss limit<br>- Sector exposure limits | Critical for real trading |
| **Portfolio Constraints** | - Max concurrent positions<br>- Max new positions per day<br>- Cash buffer | Practical constraints |

---

### 4. Market Simulation Components

**A. Price Execution**
- Where do we enter? (Open, Close, Limit order fill?)
- What slippage to assume? (0.05% for liquid stocks, more for illiquid)
- How long do orders stay valid? (Day only, GTC?)

**B. Transaction Costs**
| Cost Type | Estimation | Notes |
|-----------|------------|-------|
| Commission | $0.65 per contract (IBKR) | Per share or per trade? |
| ECN Fees | ~$0.003/share | Removing liquidity adds cost |
| SEC Fee | $0.0000081/share | Selling only |
| FINRA TAF | $0.000119/share | Selling only |
| **Total** | ~0.1-0.2% round trip | Depends on trade size |

**C. Market Impact**
- Large orders move price against us
- Use % of average daily volume as proxy
- Example: If order > 1% ADV, add slippage penalty

**D. Short Selling Constraints**
- Short stock availability (hard to borrow list)
- Short costs (borrow fees 0.1% - 5%+ annually)
- Short sale rule (uptick rule - mostly gone but exists in some form)

---

### 5. Performance Metrics

**Return Metrics:**
- Total Return
- CAGR (Compound Annual Growth Rate)
- Monthly/Annual returns
- Return distribution (skew, kurtosis)

**Risk Metrics:**
- Volatility (std of returns)
- Max Drawdown
- Average Drawdown
- Downside Deviation

**Risk-Adjusted Returns:**
- Sharpe Ratio (return / volatility)
- Sortino Ratio (return / downside volatility)
- Calmar Ratio (return / max drawdown)
- Information Ratio (excess return / tracking error)

**Trading Metrics:**
- Win Rate (% of profitable trades)
- Profit Factor (gross profit / gross loss)
- Average Win / Average Loss
- Hold Time (average days in position)
- Trades Per Month
- Turnover

**Classification Metrics:**
- Precision by confidence bucket
- Recall by confidence bucket
- Actual label distribution vs predicted

**Benchmark Comparison:**
- vs SPY (S&P 500)
- vs Buy & Hold each stock
- vs Random strategy
- vs Simple technical strategy (e.g., MA crossover)

---

### 6. Data Requirements

**Historical Data Needed:**
```
For each stock and date:
- OHLCV prices (already have)
- Model predictions (need to generate)
- Actual future returns (for validation)
- Dividends & splits (total return calculation)
- Corporate actions (delistings, bankruptcies)
- Margin requirements (if shorting)
- Borrow rates (if shorting)
```

**Prediction Generation Strategy:**
- Walk-forward validation: Train on rolling window, predict next period
- Or: Use current trained model, predict on historical test set
- Need to save predictions with dates for backtesting

---

### 7. Classification Type Comparison

**Binary (BUY/DON'T BUY):**
- ✅ Simplest to implement
- ✅ Best ensemble performance (76.8% AUC, 0% cat. error)
- ✅ Clear action: buy or don't buy
- ❌ No SELL signals (only hold existing positions)

**3-Class (SELL/HOLD/BUY):**
- ✅ Full trading cycle (enter long, exit, enter short)
- ✅ More nuanced position management
- ⚠️ Moderate catastrophic error rate (11.79%)
- ⚠️ Ensemble hurts performance (use CatBoost alone)

**5-Class (STRONG SELL/SELL/HOLD/BUY/STRONG BUY):**
- ✅ Most granular signals
- ✅ Position sizing hints (strong = larger position?)
- ❌ Highest catastrophic error (18.42%)
- ❌ Ensemble collapses (use CatBoost alone)

**Recommendation for Backtesting:**
1. Start with **Binary** CatBoost (safest, best performance)
2. Test **3-Class** CatBoost (full trading cycle)
3. Compare both to understand trade-offs

---

## 🎯 STATIC BASELINE STRATEGIES

These serve as benchmarks to compare ML performance against.

### 1. Buy & Hold

**Logic:**
```python
# At start date:
for stock in universe:
    buy_equal_weight()
# Hold till end date
# No selling
```

**Parameters:**
- Entry: First day of test period
- Exit: Last day of test period
- Position sizing: Equal weight across all stocks
- Rebalancing: None (buy once)

**Why Include:**
- Simplest possible strategy
- Shows "market return" for the stock universe
- If ML can't beat this, something's wrong

---

### 2. SMA Crossover

**Logic:**
```python
if SMA(fast_period) > SMA(slow_period):
    if not in_position:
        buy()
else:
    if in_position:
        sell()
```

**Parameters:**
- Fast SMA: 20 days
- Slow SMA: 50 days
- Position sizing: Equal weight
- Max concurrent positions: Unlimited (or cap at 20)

**Why Include:**
- Classic trend-following strategy
- Widely used, easy to understand
- Tests if ML captures trend signals better

---

### 3. MACD Strategy

**Logic:**
```python
macd = EMA(12) - EMA(26)
signal = EMA(macd, 9)

if macd crosses above signal:
    buy()
elif macd crosses below signal:
    sell()
```

**Parameters:**
- Standard MACD (12, 26, 9)
- Position sizing: Equal weight
- Entry: Next day open after crossover

**Why Include:**
- Classic momentum strategy
- Tests if ML captures momentum better
- Another common baseline

---

### 4. Random Strategy

**Logic:**
```python
each_day:
    for stock in universe:
        if random() < 0.02:  # 2% chance to buy
            buy()
    # Exit after 20 days (like binary strategy)
```

**Parameters:**
- Buy probability: 2% per stock per day
- Position sizing: Equal weight
- Exit: After 20 days (matching binary)

**Why Include:**
- Null hypothesis test
- Shows if ML is better than random
- Expected return: ~0 (minus transaction costs)

---

### 5. ML Model Strategy

**Logic:**
```python
# Load model from path
model = CatBoost()
model.load(model_path)

each_day:
    for stock in universe:
        # Get model prediction
        features = calculate_features(stock, date)
        prediction = model.predict(features)

        # Convert prediction to signal
        if prediction == 'BUY' and confidence > threshold:
            buy(stock)
        elif prediction == 'SELL':
            sell(stock)

# Exit based on label targets
for position in portfolio:
    days_held += 1
    pnl = (current_price - entry_price) / entry_price

    if pnl >= 0.03:      # +3% profit target
        sell(position)
    elif pnl <= -0.02:   # -2% stop loss
        sell(position)
    elif days_held >= 20: # 20 day time exit
        sell(position)
```

**Parameters:**
- Model path: User-specified
- Confidence threshold: 0.6 (default, configurable)
- Position sizing: Equal weight
- Max concurrent positions: 20 (configurable)

**Binary vs Multi-Class:**
- **Binary**: Only enters on BUY, exits on targets/time
- **3-Class**: Can enter on BUY, exit on SELL or targets
- **5-Class**: More nuanced, uses STRONG signals

---

## 📊 COMPARISON OUTPUT

All strategies compared side-by-side:

```csv
Strategy          Return  WinRate  Trades  Sharpe  MaxDD  Volatility
----------------  ------  -------  ------  ------  -----  ----------
Buy & Hold        +12.5%  N/A      0      0.82    -25%   18%
SMA Cross         +8.3%   42%      156    0.61    -18%   15%
MACD              +5.1%   38%      203    0.42    -15%   14%
Random            -2.4%   34%      187   -0.12   -30%   22%
Binary CatBoost   +15.8%  68%      95     1.23    -12%   12%
3Class CatBoost   +18.2%  62%      124    1.41    -14%   13%
5Class CatBoost   +14.1%  58%      142    1.15    -16%   14%
```

---

## 📋 IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Week 1)

**Goal**: Build minimum viable backtester

**Tasks:**
1. ✅ Create folder structure
2. ⬜ `config.py` - Backtesting configuration (costs, limits, parameters)
3. ⬜ `data_loader.py` - Load predictions, prices, returns
4. ⬜ `portfolio.py` - Track positions, cash, P&L
5. ⬜ `executor.py` - Simulate order execution with slippage/costs
6. ⬜ `metrics.py` - Calculate all performance metrics
7. ⬜ `backtester.py` - Main backtesting engine
8. ⬜ `report.py` - Generate visual reports

**Deliverable:**
- Working backtester that can:
  - Load historical predictions
  - Execute trades with basic costs
  - Calculate basic metrics (returns, win rate, drawdown)

---

### Phase 2: Strategy Implementation (Week 2)

**Goal**: Implement trading strategies around model predictions

**Tasks:**
1. ⬜ `strategies/base.py` - Base strategy class
2. ⬜ `strategies/binary_strategy.py` - Binary classification strategy
3. ⬜ `strategies/multiclass_strategy.py` - 3-class/5-class strategy
4. ⬜ `signal_generator.py` - Convert predictions to trade signals
5. ⬜ `position_sizer.py` - Position sizing logic
6. ⬜ `risk_manager.py` - Risk rules (max drawdown, position limits)

**Strategy Features:**
- Confidence threshold filtering
- Top-N stock selection per day
- Position sizing (equal weight, volatility-weighted, Kelly)
- Entry/exit rules (label-based, time-based, stop-loss)
- Portfolio constraints (max positions, sector limits)

**Deliverable:**
- Complete strategy implementations
- Backtest results for different parameter combinations

---

### Phase 3: Validation & Analysis (Week 3)

**Goal**: Ensure backtesting is realistic and analyze results

**Tasks:**
1. ⬜ `validator.py` - Check for look-ahead bias, data leaks
2. ⬜ `walk_forward.py` - Walk-forward validation implementation
3. ⬜ `market_regime_analysis.py` - Performance by market regime
4. ⬜ `sensitivity_analysis.py` - Parameter sensitivity
5. ⬜ `attribution.py` - Performance attribution (what works?)
6. ⬜ `benchmark.py` - Benchmark comparisons

**Analysis Outputs:**
- Performance by market regime (bull/bear/sideways)
- Performance by stock characteristics (size, sector, volatility)
- Confidence threshold curve (precision vs coverage)
- Feature importance in practice vs theory
- Worst-case scenario analysis

**Deliverable:**
- Comprehensive analysis report
- Visualization of all metrics
- Recommendations for live trading

---

### Phase 4: Advanced Features (Week 4)

**Goal**: Add sophistication and edge cases

**Tasks:**
1. ⬜ `slippage_model.py` - Advanced slippage estimation
2. ⬜ `market_impact.py` - Large order impact
3. ⬜ `short_selling.py` - Short selling constraints & costs
4. ⬜ `multi_symbol.py` - Portfolio-level optimization
5. ⬜ `regime_detection.py` - Market regime-aware trading
6. ⬜ `ensemble_strategy.py` - Combine multiple models
7. ⬜ `adaptive_sizing.py` - Dynamic position sizing
8. ⬜ `monte_carlo.py` - Monte Carlo simulation of uncertainty

**Deliverable:**
- Production-ready backtesting framework
- Full suite of advanced strategies

---

## 🏗️ ARCHITECTURE DESIGN

```
ml-training/backtesting/
├── README.md                    # This file
├── BRAINSTORMING.md             # Detailed brainstorming
├── ROADMAP.md                   # Implementation roadmap
│
├── config/
│   ├── __init__.py
│   └── backtest_config.py       # All configuration parameters
│
├── data/
│   ├── __init__.py
│   ├── loader.py                # Load predictions, prices
│   ├── predictor.py             # Generate historical predictions
│   └── features.py              # Feature engineering for backtest
│
├── core/
│   ├── __init__.py
│   ├── backtester.py            # Main backtesting engine
│   ├── portfolio.py             # Portfolio tracking
│   ├── executor.py              # Order execution simulation
│   ├── events.py                # Event system (fills, etc)
│   └── clock.py                 # Time/calendar management
│
├── strategies/
│   ├── __init__.py
│   ├── base.py                  # Base strategy class
│   ├── binary_strategy.py       # Binary classification
│   ├── multiclass_strategy.py   # 3-class/5-class
│   ├── signal_generator.py      # Prediction → Signal
│   ├── position_sizer.py        # Position sizing
│   └── risk_manager.py          # Risk management
│
├── analysis/
│   ├── __init__.py
│   ├── metrics.py               # Performance metrics
│   ├── reports.py               # Report generation
│   ├── plots.py                 # Visualization
│   ├── validator.py             # Bias validation
│   ├── attribution.py           # Performance attribution
│   └── comparison.py            # Strategy comparison
│
├── simulation/
│   ├── __init__.py
│   ├── slippage.py              # Slippage models
│   ├── market_impact.py         # Market impact
│   ├── transaction_costs.py     # Cost models
│   └── short_selling.py         # Short constraints
│
├── scripts/
│   ├── 01_generate_predictions.py  # Generate historical predictions
│   ├── 02_run_backtest.py          # Run backtest
│   ├── 03_compare_strategies.py    # Compare different strategies
│   ├── 04_sensitivity_analysis.py  # Parameter sensitivity
│   ├── 05_market_regime_analysis.py# Performance by regime
│   └── 06_monte_carlo.py           # Monte Carlo simulation
│
├── outputs/
│   ├── predictions/             # Historical predictions
│   ├── backtests/               # Backtest results
│   ├── reports/                 # HTML/PDF reports
│   └── plots/                   # Visualization outputs
│
└── notebooks/
    ├── exploratory_analysis.ipynb
    ├── strategy_development.ipynb
    └── results_review.ipynb
```

---

## 📊 KEY DESIGN DECISIONS

### Decision 1: Prediction Generation

**Option A: Re-train model for each historical period**
- Pro: Most realistic (no look-ahead)
- Con: Very slow (need to train 100+ models)
- **Choice: Use for final validation only**

**Option B: Use current model on all historical data**
- Pro: Fast, simple
- Con: Look-ahead bias (model saw future data)
- **Choice: Use for development/debugging**

**Option C: Walk-forward with rolling window**
- Pro: Realistic, efficient
- Con: Moderate complexity
- **Choice: Use for production backtesting**

---

### Decision 2: Execution Timing

**Option A: Execute at next day's open**
- Pro: Realistic (can't trade instantly)
- Con: Gap risk (overnight news)
- **Choice: Standard approach**

**Option B: Execute same day at close**
- Pro: No gap risk
- Con: Unrealistic (need to predict during trading day)
- **Choice: Not recommended**

**Option C: Limit orders with fill probability**
- Pro: Most realistic
- Con: Complex to model
- **Choice: Advanced feature**

---

### Decision 3: Position Sizing

**Option A: Equal dollar per position**
- Pro: Simple, interpretable
- Con: Doesn't account for risk
- **Choice: Baseline approach**

**Option B: Volatility-weighted**
- Pro: Risk-balanced
- Con: More complex
- **Choice: Implement as option**

**Option C: Kelly criterion**
- Pro: Theoretically optimal
- Con: Assumes normal returns, unstable
- **Choice: Experimental**

---

### Decision 4: Short Selling

**Approach**: Implement as optional feature
- Default: Long-only (simpler, more robust)
- Optional: Enable short selling with:
  - Borrow cost assumption
  - Hard-to-borrow list
  - Short sale constraints

---

## 🎯 SUCCESS CRITERIA

**Minimum Viable Product:**
- ✅ Can run backtest on historical predictions
- ✅ Accounts for transaction costs
- ✅ Generates basic performance report
- ✅ Compares to buy-and-hold benchmark

**Production Ready:**
- ✅ Walk-forward validation implemented
- ✅ Multiple strategies tested
- ✅ Comprehensive metrics and reporting
- ✅ Validated against realistic constraints
- ✅ Documented findings and recommendations

**Live Trading Ready:**
- ✅ Paper trading validation
- ✅ Risk management tested
- ✅ Slippage models calibrated
- ✅ Execution strategy finalized
- ✅ Monitoring and alerting defined

---

## 📝 NEXT STEPS

1. **Review and refine** this roadmap
2. **Create config file** with all parameters
3. **Implement Phase 1** (Foundation)
4. **Test on simple case** (binary, equal weight)
5. **Iterate and expand**

---

**Last Updated**: 2026-02-05
**Status**: Brainstorming Complete, Ready for Implementation
