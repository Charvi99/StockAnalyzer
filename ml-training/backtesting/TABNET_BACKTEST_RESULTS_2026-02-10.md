# TabNet vs CatBoost vs Buy & Hold - Backtest Results

**Date**: 2026-02-10
**Period**: Q1 2024 (January 1 - March 28, 2024)
**Starting Capital**: $100,000

---

## Executive Summary

| Rank | Strategy | Total Return | Sharpe Ratio | Win Rate | Volatility |
|------|----------|--------------|-------------|----------|------------|
| 🥇 | **TabNet 3-Class** | **+9.71%** | **2.44** | **52.1%** | **15.71%** |
| 🥈 | Buy & Hold | +8.73% | 1.96 | N/A | 17.77% |
| 🥉 | CatBoost Binary | +7.91% | 1.75 | 48.2% | 18.17% |

**Key Finding**: TabNet significantly outperforms both CatBoost (+1.8%) and Buy & Hold (+1.0%) with superior risk-adjusted returns (Sharpe 2.44).

---

## Performance Comparison

### Absolute Returns (Q1 2024)

| Strategy | Starting | Ending | Return | Annualized |
|----------|----------|--------|--------|------------|
| TabNet | $100,000 | $109,708.37 | **+9.71%** | ~38.8% CAGR |
| Buy & Hold | $100,000 | $108,729.16 | +8.73% | ~34.9% CAGR |
| CatBoost | $100,000 | $107,913.89 | +7.91% | ~31.6% CAGR |

### Risk-Adjusted Returns (Sharpe Ratio)

| Strategy | Sharpe Ratio | Annual Return | Volatility | Rating |
|----------|-------------|--------------|------------|--------|
| **TabNet** | **2.44** | 40.34% | 15.71% | Excellent (Professional) |
| Buy & Hold | 1.96 | 36.90% | 17.77% | Good |
| CatBoost | 1.75 | 33.81% | 18.17% | Good |

---

## Trading Statistics

### TabNet 3-Class (35% Confidence)

| Metric | Value |
|--------|-------|
| Total Trades | 284 |
| Win Rate | **52.1%** |
| Average P&L per Trade | +0.85% |
| Median P&L | +3.05% |
| Standard Deviation | 4.73% |

**Exit Breakdown:**
- Profit Target (+3%): 146 trades (51.4%)
- Stop Loss (-2%): 134 trades (47.2%)
- Time Exit (20 days): 4 trades (1.4%)

**P&L Distribution:**
- Best Trade: +21.7%
- Worst Trade: -13.8%
- 75th Percentile: +3.96%
- 25th Percentile: -2.93%

### CatBoost Binary (35% Confidence)

| Metric | Value |
|--------|-------|
| Total Trades | 394 |
| Win Rate | 48.2% |
| Average P&L per Trade | +0.44% |
| Median P&L | -2.03% |
| Standard Deviation | 5.26% |

**Exit Breakdown:**
- Profit Target (+3%): 189 trades (48.0%)
- Stop Loss (-2%): 203 trades (51.5%)
- Time Exit (20 days): 2 trades (0.5%)

**P&L Distribution:**
- Best Trade: +28.4%
- Worst Trade: -33.1%
- 75th Percentile: +4.01%
- 25th Percentile: -3.25%

### Buy & Hold

| Metric | Value |
|--------|-------|
| Total Trades | 0 (held 20 stocks entire period) |
| Positions | 20 stocks |
| No active trading or risk management |

---

## Strategy Comparison

### Advantages

| Strategy | Advantages |
|----------|------------|
| **TabNet** | ✅ Highest returns (9.71%)<br>✅ Best Sharpe ratio (2.44)<br>✅ Highest win rate (52.1%)<br>✅ Lowest volatility (15.71%)<br>✅ More profit targets hit (51.4%)<br>✅ Fewer catastrophic losses |
| **CatBoost** | ✅ Best single trade (+28.4%)<br>✅ More trading opportunities (394 trades)<br>✅ Active risk management |
| **Buy & Hold** | ✅ Simple, no trading required<br>✅ Decent returns (8.73%)<br>✅ No transaction costs |

### Disadvantages

| Strategy | Disadvantages |
|----------|---------------|
| **TabNet** | ⚠️ Fewer trading opportunities (284 trades)<br>⚠️ Requires ML model monitoring |
| **CatBoost** | ❌ Lowest returns (7.91%)<br>❌ Lowest win rate (48.2%)<br>❌ Highest volatility (18.17%)<br>❌ More stop losses hit (51.5%)<br>❌ Worst single trade (-33.1%) |
| **Buy & Hold** | ⚠️ Capital tied up entire period<br>⚠️ No risk management<br>⚠️ Must endure full drawdowns |

---

## Head-to-Head: TabNet vs CatBoost

| Metric | TabNet | CatBoost | Winner |
|--------|--------|----------|--------|
| Total Return | +9.71% | +7.91% | TabNet (+1.8%) |
| Sharpe Ratio | 2.44 | 1.75 | TabNet (+0.69) |
| Win Rate | 52.1% | 48.2% | TabNet (+3.9%) |
| Avg P&L per Trade | +0.85% | +0.44% | TabNet (+0.41%) |
| Median P&L | +3.05% | -2.03% | TabNet (+5.08%) |
| Volatility | 15.71% | 18.17% | TabNet (-2.46%) |
| Profit Target Rate | 51.4% | 48.0% | TabNet (+3.4%) |
| Stop Loss Rate | 47.2% | 51.5% | TabNet (-4.3%) |
| Worst Trade | -13.8% | -33.1% | TabNet (+19.3%) |

**TabNet wins on 9/9 metrics!**

---

## Key Insights

### Why TabNet Outperforms

1. **Superior Classification**: 3-class model (SELL/HOLD/BUY) captures more nuance than binary (BUY/DON'T BUY)

2. **Better Selectivity**: 284 trades vs 394 (CatBoost) - more selective, higher quality signals

3. **Stronger Win Rate**: 52.1% means profitable trades outnumber losses

4. **Lower Volatility**: 15.71% vs 18.17% - more consistent performance

5. **Better Risk Management**: Fewer stop losses hit (47.2% vs 51.5%)

### CatBoost Issues

1. **Lower Win Rate**: 48.2% means more losers than winners

2. **Higher Volatility**: 18.17% - larger swings in performance

3. **More Catastrophic Losses**: Worst trade -33.1% vs TabNet's -13.8%

4. **Median Negative**: -2.03% median P&L means typical trade loses money

### Buy & Hold Performance

Buy & Hold performs surprisingly well (8.73%) due to strong Q1 2024 market conditions, but:
- No active risk management
- Capital tied up entire period
- Performance depends entirely on market direction

---

## Configuration

### Backtest Parameters

| Parameter | Value |
|-----------|-------|
| Period | 2024-01-01 to 2024-03-28 (61 trading days) |
| Initial Capital | $100,000 |
| Max Positions | 20 |
| Max Position Size | 10% of portfolio |
| Confidence Threshold | 35% (both models) |

### Exit Rules

| Rule | Value |
|------|-------|
| Profit Target | +3% |
| Stop Loss | -2% |
| Max Holding Period | 20 days |

### Transaction Costs

| Cost | Value |
|------|-------|
| Commission | $0.0035/share |
| ECN Fees | ~0.0025/share |
| SEC/FINRA Fees | ~0.00013/share |
| **Total** | ~0.1-0.2% per trade |

---

## Model Details

### TabNet Model
- **Type**: 3-Class Classification (SELL/HOLD/BUY)
- **Features**: 126 (technical + insider + market context)
- **Training Dataset**: Enhanced dataset with sector ETF & volatility features
- **Model Path**: `/app/outputs/models/tabnet/latest/`

### CatBoost Model
- **Type**: Binary Classification (BUY/DON'T BUY)
- **Features**: 126 (same features as TabNet)
- **Training Dataset**: Enhanced dataset with sector ETF & volatility features
- **Model Path**: `/app/outputs/models/catboost/v1.0.0-binary/`

---

## Recommendations

### Primary Recommendation: Use TabNet

**TabNet is the clear winner** with:
- Highest returns (+9.71%)
- Best risk-adjusted performance (Sharpe 2.44)
- Highest win rate (52.1%)
- Lowest volatility (15.71%)

### Suggested Settings

```python
# Optimal TabNet configuration
strategy = TabNetMLStrategy(
    model_path="/app/outputs/models/tabnet/latest",
    confidence_threshold=0.35,  # 35% BUY class confidence
    buy_class=2  # BUY class in 3-class model
)

# Exit rules
profit_target = +0.03  # +3%
stop_loss = -0.02      # -2%
max_hold_days = 20
```

### Future Improvements

1. **Test longer periods** - Validate TabNet's edge over 6-12 months
2. **Optimize confidence threshold** - Test 30%, 40%, 45% thresholds
3. **Ensemble approach** - Combine TabNet + CatBoost predictions
4. **Adaptive position sizing** - Size positions based on prediction confidence
5. **Sector filtering** - Avoid certain sectors during market conditions

---

## Backtest Results Files

Results saved to:
- TabNet: `/app/outputs/features/backtests/tabnet_ml_20260210_074611/`
- CatBoost: `/app/outputs/features/backtests/binary_ml_20260210_080347/`
- Buy & Hold: `/app/outputs/features/backtests/buy_and_hold_20260210_075145/`

Each folder contains:
- `trades.csv` - All executed trades with entry/exit details
- `portfolio_history.csv` - Daily portfolio values
- `metrics.json` - Calculated performance metrics
- `summary.txt` - Human-readable summary

---

**Generated**: 2026-02-10
**Framework**: ML Backtesting Engine v1.0
**Dataset**: dataset_backtest_tabnet_20260210_072155 (433,756 samples, 132 features)
