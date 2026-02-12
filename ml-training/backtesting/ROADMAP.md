# Backtesting Implementation Roadmap

**Goal**: Build production-ready backtesting framework for ML trading models.

---

# Backtesting Implementation Roadmap

**Goal**: Build production-ready backtesting framework comparing ML models against baseline strategies.

---

## 📅 Phase 1: Foundation (Days 1-3)

### Core Components

**1. Configuration (`config/backtest_config.py`)**
```python
# Transaction costs
COMMISSION_PER_SHARE = 0.0035
ECN_FEE_REMOVE = 0.0025
SEC_FEE = 0.0000081
FINRA_TAF = 0.000119

# Slippage
SLIPPAGE_BASE = 0.05%  # for liquid stocks
SLIPPAGE_ILLIQUID = 0.20%  # for illiquid stocks

# Portfolio constraints
MAX_POSITIONS = 20
MAX_POSITION_PCT = 0.10  # 10% max per position
MIN_STOCK_PRICE = 5.0
MIN_DOLLAR_VOLUME = 1_000_000

# Strategy parameters
CONFIDENCE_THRESHOLD = 0.6
TOP_N_SIGNALS = 5  # max new positions per day
HOLDING_PERIOD_MAX = 30  # days
```

**2. Data Loader (`data/loader.py`)**
- Load historical predictions
- Load OHLCV data
- Merge predictions with prices
- Calculate actual forward returns

**3. Portfolio (`core/portfolio.py`)**
```python
class Portfolio:
    - cash: float
    - positions: Dict[symbol, Position]
    - total_value: float
    - add_position(symbol, shares, entry_price)
    - remove_position(symbol, shares, exit_price)
    - update_prices(current_prices)
    - get_pnl()
```

**4. Order Executor (`core/executor.py`)**
```python
def execute_order(order, bar):
    # Apply slippage
    # Calculate commission
    # Check margin requirements (if shorting)
    # Return fill with actual execution price
```

**5. Backtester (`core/backtester.py`)**
```python
def run_backtest(predictions, strategy, config):
    for date, bars in data:
        # 1. Update portfolio prices
        # 2. Check exit conditions
        # 3. Generate signals from model
        # 4. Execute entries
        # 5. Record metrics
```

**6. Metrics (`analysis/metrics.py`)**
- Returns, CAGR, volatility
- Sharpe, Sortino, Calmar
- Max drawdown, win rate
- Profit factor, avg win/loss

**7. Report Generator (`analysis/reports.py`)**
- Text summary
- Equity curve plot
- Drawdown plot
- Monthly returns heatmap
- Trade distribution

---

## 📅 Phase 2: Strategy Implementation (Days 4-6)

### Static Baseline Strategies

**1. Buy & Hold (`strategies/buy_and_hold.py`)**
```python
class BuyAndHoldStrategy:
    def __init__(self, universe, start_date, end_date):
        # Buy all stocks at start_date
        # Hold until end_date
        # Equal weight positioning
```

**2. SMA Crossover (`strategies/sma_crossover.py`)**
```python
class SMACrossoverStrategy:
    def __init__(self, fast_period=20, slow_period=50):
        # Buy when fast SMA crosses above slow SMA
        # Sell when fast SMA crosses below slow SMA
        # Equal weight positioning
```

**3. MACD Strategy (`strategies/macd_strategy.py`)**
```python
class MACDStrategy:
    def __init__(self, fast=12, slow=26, signal=9):
        # Buy when MACD crosses above signal line
        # Sell when MACD crosses below signal line
        # Equal weight positioning
```

**4. Random Strategy (`strategies/random_strategy.py`)**
```python
class RandomStrategy:
    def __init__(self, buy_probability=0.02, hold_days=20):
        # Random buy each day with P%
        # Exit after hold_days (matches binary exit)
        # Equal weight positioning
```

### ML Model Strategies

**Binary Strategy (`strategies/binary_ml_strategy.py`)**
```python
class BinaryMLStrategy:
    def __init__(self, model_path, confidence_threshold=0.6):
        self.model = load_model(model_path)  # CatBoost/XGBoost
        self.threshold = confidence_threshold

    def generate_signals(self, date, features):
        predictions = self.model.predict_proba(features)
        # Return BUY signals where confidence > threshold
```

**Entry Rules:**
- Model predicts BUY with confidence > threshold
- Stock passes filters (price > $5, volume > 1M)
- Portfolio has room (under max positions)

**Exit Rules (Target-Based - Option B):**
- Profit target: +3% from entry
- Stop loss: -2% from entry
- Time exit: 20 days (whichever first)

**Position Sizing:**
- Equal weight: investable_cash / n_signals

### Multi-Class Strategy (`strategies/multiclass_ml_strategy.py`)

**Entry Rules:**
- BUY signal: enter long
- STRONG BUY: enter long (could be larger position?)
- SELL signal: exit long positions
- STRONG SELL: exit immediately (or enter short)

**Exit Rules:**
- Same target-based as binary (+3%/-2%/20 days)
- OR: When prediction changes to HOLD/neutral

---

## 📅 Phase 3: Validation & Analysis (Days 7-9)

### Walk-Forward Validation

```
Train: [2020-01-01 → 2022-01-01] → Test: [2022-01-01 → 2022-04-01]
Train: [2020-04-01 → 2022-04-01] → Test: [2022-04-01 → 2022-07-01]
...
```

### Market Regime Analysis

- Bull market performance
- Bear market performance
- Sideways/choppy performance
- High volatility period performance

### Sensitivity Analysis

Vary parameters and plot results:
- Confidence threshold (0.5 → 0.9)
- Max positions (5 → 50)
- Position sizing method
- Stop loss / profit target

### Benchmark Comparison

- Buy & hold SPY
- Buy & hold equal-weight portfolio
- Random stock selection
- Simple MA crossover strategy

---

## 📅 Phase 4: Advanced Features (Days 10-14)

### Slippage Modeling

```python
def calculate_slippage(order, bar):
    base_slippage = 0.05%
    # Adjust for order size vs ADV
    size_impact = (order.shares / bar.avg_daily_volume) * 0.1%
    # Adjust for volatility
    vol_impact = bar.volatility * 0.5%
    return base_slippage + size_impact + vol_impact
```

### Market Impact

For large orders:
- Impact increases with order size
- Temporary impact (recovers)
- Permanent impact (shifts price)

### Short Selling

- Hard-to-borrow list check
- Borrow fee estimation (0.1% - 5% annually)
- Dividend responsibility (short pays dividends)

### Monte Carlo Simulation

- Resample trade returns
- Generate 1000 equity curves
- Calculate confidence intervals
- Estimate probability of ruin

---

## 🎯 Implementation Priority

### High Priority (Must Have)
1. ✅ Basic backtester engine
2. ✅ Transaction costs & slippage
3. ✅ Binary strategy implementation
4. ✅ Core performance metrics
5. ✅ Basic report generation

### Medium Priority (Should Have)
1. ⬜ Multi-class strategies
2. ⬜ Walk-forward validation
3. ⬜ Market regime analysis
4. ⬜ Parameter sensitivity
5. ⬜ Benchmark comparisons

### Low Priority (Nice to Have)
1. ⬜ Advanced slippage models
2. ⬜ Market impact simulation
3. ⬜ Short selling constraints
4. ⬜ Monte Carlo simulation
5. ⬜ Portfolio optimization

---

## 📊 Expected Outputs

### For Each Backtest Run

**Data Files:**
```
outputs/backtests/{run_id}/
├── trades.csv              # All trades with entry/exit
├── portfolio.csv           # Daily portfolio values
├── positions.csv           # Daily positions
├── returns.csv             # Daily returns
├── metrics.json            # All calculated metrics
└── config.json             # Config used for run
```

**Reports:**
```
outputs/reports/{run_id}/
├── summary.html            # Interactive HTML report (primary)
├── summary.txt             # Text summary (fallback)
├── equity_curve.png        # Static plot (fallback)
├── comparison.html         # Strategy comparison (interactive)
└── metrics.json            # Raw metrics data
```

**Shared Output (for easy access):**
```
# Via Docker volume mount
./ml-training/outputs/plots/
├── backtest_comparison_20260205.html
├── equity_curves_20260205.html
├── drawdowns_20260205.html
└── metrics_comparison_20260205.html
```

---

## 🚀 Quick Start Commands

```bash
# 1. Generate historical predictions
python scripts/01_generate_predictions.py \
    --model-type binary \
    --start-date 2022-01-01 \
    --end-date 2024-01-01

# 2. Run single strategy backtest
python scripts/02_run_backtest.py \
    --strategy binary \
    --model-path /app/outputs/models/catboost/v1.0.0-binary/model.cbm \
    --confidence-threshold 0.6

# 3. Compare all strategies (baselines + ML)
python scripts/03_compare_strategies.py \
    --strategies buy_and_hold sma_crossover macd random binary_ml \
    --models /app/outputs/models/catboost/v1.0.0-binary/model.cbm

# 4. Generate comparison report
python scripts/04_generate_report.py \
    --backtest-dir /app/outputs/backtests/comparison_20260205 \
    --format html \
    --output /app/outputs/plots/comparison.html

# 5. Parameter sensitivity
python scripts/05_sensitivity_analysis.py \
    --strategy binary_ml \
    --parameter confidence_threshold \
    --range 0.5 0.9 0.05

# 6. Market regime analysis
python scripts/06_market_regime_analysis.py \
    --backtest-dir /app/outputs/backtests/comparison_20260205
```
    --confidence-threshold 0.6 \
    --max-positions 10

# 3. Compare strategies
python scripts/03_compare_strategies.py \
    --strategies binary 3class 5class

# 4. Sensitivity analysis
python scripts/04_sensitivity_analysis.py \
    --parameter confidence_threshold \
    --range 0.5 0.9 0.05

# 5. Market regime analysis
python scripts/05_market_regime_analysis.py \
    --strategy binary

# 6. Monte Carlo simulation
python scripts/06_monte_carlo.py \
    --backtest-id <run_id> \
    --simulations 1000
```

---

## 📋 Checklist

### Before Starting Implementation
- [ ] Review and approve brainstorming document
- [ ] Decide on final architecture
- [ ] Set up development environment
- [ ] Create test data sample

### Phase 1 Complete
- [ ] Config file created
- [ ] Data loader working
- [ ] Portfolio tracking works
- [ ] Order execution simulated
- [ ] Basic backtester runs end-to-end
- [ ] Metrics calculated correctly
- [ ] Simple report generated

### Phase 2 Complete
- [ ] Binary strategy implemented
- [ ] Multi-class strategies implemented
- [ ] Signal generator working
- [ ] Position sizer working
- [ ] Risk manager working
- [ ] All strategies produce results

### Phase 3 Complete
- [ ] Walk-forward validation runs
- [ ] Market regime analysis complete
- [ ] Sensitivity analysis complete
- [ ] Benchmark comparisons done
- [ ] Comprehensive report generated

### Phase 4 Complete
- [ ] Advanced slippage modeled
- [ ] Market impact simulated
- [ ] Short selling implemented
- [ ] Monte Carlo simulation working
- [ ] Production-ready framework

---

**Last Updated**: 2026-02-05
**Status**: Ready for Implementation
**Next Action**: Start Phase 1 - Create config file
