# ML Training 5-Year Expansion Guide

**Date:** 2026-02-02
**Goal:** Improve AUC from 56.8% → 63-68% (+6-11%)
**Approach:** Combine data expansion with feature reduction

---

## Overview

This expansion implements Priority 2 and Priority 3 from `ML_BRAINSTORMING_DIAGNOSIS_2026.md`:
- **Priority 2:** Reduce features (76 → 28, -63%) - +1-3% AUC
- **Priority 3:** Extend historical data (3 → 5 years, 252 → 500+ stocks) - +2-4% AUC

**Combined Expected Impact:** +6-11% AUC improvement

---

## What's Included

### 1. Stock Universe Expansion (`add_diverse_stocks_5years.py`)
- **S&P 500:** Top ~400-450 stocks by market cap
- **NASDAQ 100:** Top ~80-100 tech stocks
- **Popular ETFs:** Index + sector ETFs (SPY, QQQ, XLK, XLV, etc.)
- **Total:** 500-600 stocks with GICS sector information

**Sources:**
- Wikipedia for S&P 500 and NASDAQ 100 lists
- Each stock includes sector and sub-industry

### 2. Historical Data Fetching (`fetch_historical_data_5years.py`)
- **Time range:** 5 years (2019-2026)
- **Timeframe:** Daily (1d)
- **Data points:** ~250K-300K samples (vs current 130K)
- **Paid Polygon.io API:** Parallel fetching (10 workers)
- **Expected time:** 1-2 hours

**Market Regimes Covered:**
- 2019: Bull market
- 2020: COVID crash + recovery
- 2021: Bull market
- 2022: Bear market (inflation, rate hikes)
- 2023-2026: Mixed conditions

### 3. Reduced Feature Engineering (`01h_feature_engineering_28features.py`)
- **Features:** 28 high-quality (down from 76)
- **Data leakage fix:** All features shifted by 1 day
- **Categories:**
  - Core Momentum (4): RSI, log_return_1d, log_return_5d, price_position_20d
  - Core Trend (3): SMA 50, SMA 200, MA slope
  - Core Volatility (3): volatility_20d, ATR, daily_range
  - Core Volume (3): log_volume, OBV, VWAP
  - MACD (3): MACD, MACD histogram, MACD signal
  - ADX (2): ADX, +DI
  - Other (9): PSAR, CCI, ROC, Aroon, LinearReg, Gap, NATR, MFI, StochK
  - Derived (1): price_vs_sma50

### 4. Orchestration Script (`run_full_ml_pipeline_5years.sh`)
- Runs all steps in sequence
- Interactive prompts for safety
- Progress tracking
- Error handling

---

## Quick Start

### Option 1: Run Full Pipeline (Recommended)

```bash
# From ml-training container
docker-compose exec ml-training bash /app/run_full_ml_pipeline_5years.sh

# Or from backend container
docker-compose exec backend bash /app/scripts/run_full_ml_pipeline_5years.sh
```

**Expected time:** 2-4 hours total
- Step 1 (Add stocks): 5-10 minutes
- Step 2 (Fetch data): 1-2 hours (paid API)
- Step 3 (Feature engineering): 20-30 minutes
- Step 4 (Model training): 30-60 minutes (GPU-dependent)

### Option 2: Run Steps Individually

```bash
# Step 1: Add stocks
docker-compose exec backend python /app/scripts/add_diverse_stocks_5years.py

# Step 2: Fetch historical data
docker-compose exec backend python /app/scripts/fetch_historical_data_5years.py

# Step 3: Feature engineering
docker-compose exec ml-training python scripts/01h_feature_engineering_28features.py

# Step 4: Train models
docker-compose exec ml-training python train.py
```

---

## Prerequisites

### Environment Variables

```bash
# Required: Polygon.io API key (paid tier)
export POLYGON_API_KEY='your_paid_key_here'

# Database URL (usually set in docker-compose.yml)
export DATABASE_URL='postgresql://stockuser:stockpass123@database:5432/stock_analyzer'
```

### Database Schema

The scripts automatically add required columns:
- `stocks.sector` - GICS sector (11 sectors)
- `stocks.sub_industry` - GICS sub-industry

### Dependencies

```bash
# Already installed in docker-compose.yml
# - pandas, numpy, sqlalchemy
# - requests, tqdm
# - Polygon.io API access
```

---

## Expected Results

### Data Statistics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Stocks** | 252 | 500-600 | +98-138% |
| **Historical Data** | 3 years | 5 years | +67% |
| **Training Samples** | ~130K | ~250K-300K | +92-131% |
| **Features** | 76 | 28 | -63% |
| **Market Regimes** | 1 | 5 | +400% |
| **Sectors** | Unknown | 11 GICS + ETFs | Complete |

### Model Performance (Expected)

| Model | Current AUC | Expected AUC | Improvement |
|-------|------------|--------------|-------------|
| XGBoost | 56.3% | 62-65% | +6-9% |
| CatBoost | 56.7% | 63-66% | +6-9% |
| Ensemble | 56.8% | **63-68%** | **+6-11%** |

---

## Feature Reduction Rationale

### Dropped Features (48)

**Redundant Moving Averages (8):**
- `sma_20`, `ema_20`, `ema_50` → Keep `sma_50`, `sma_200` only
- `kama`, `tema`, `t3` → Too many MA types
- `ht_trendline` → Redundant with `sma_50`

**Redundant Momentum (7):**
- `log_return_10d`, `log_return_20d` → Keep 1d and 5d only
- `momentum_5d`, `momentum_10d`, `momentum_20d` → Same as log_return
- `stochrsi` → RSI of stochastic (overkill)

**Redundant Volatility (7):**
- `volatility_10d`, `volatility_60d` → Keep `volatility_20d` only
- `stddev` → Same as volatility
- `volume_volatility_10d` → Weak signal

**Redundant Oscillators (8):**
- `willr` → Same as Stochastic
- `stoch_d` → Stochastic %D is redundant
- `cmo` → Similar to RSI
- `ultosc`, `trix`, `bop` → Rarely used, weak signal

**Redundant Channels (6):**
- `bb_upper`, `bb_middle`, `bb_lower` → Use ATR instead
- `kc_upper`, `kc_middle`, `kc_lower` → Redundant with BB
- `bb_signal`, `kc_signal` → Use ADX instead

**Redundant Volume (5):**
- `volume_change` → Use OBV instead
- `ad_line`, `ad_signal` → Use OBV instead
- `adosc`, `adosc_signal` → Use OBV instead

**Redundant Signals (7):**
- All `*_signal` columns → Model learns these patterns automatically

**Weak Gap Features (2):**
- `gap_up_5d_sum`, `gap_down_5d_sum` → Use `gap` only

---

## Troubleshooting

### Issue: "POLYGON_API_KEY not found"
**Solution:**
```bash
export POLYGON_API_KEY='your_key_here'
docker-compose exec backend bash /app/scripts/run_full_ml_pipeline_5years.sh
```

### Issue: "No tracked stocks found"
**Solution:** Run Step 1 (add_diverse_stocks_5years.py) first

### Issue: "Not enough data for feature engineering"
**Solution:** Run Step 2 (fetch_historical_data_5years.py) first

### Issue: Out of memory during training
**Solution:** The scripts already handle this via `resource_manager.py`. If issues persist:
```bash
# Train with fewer models
docker-compose exec ml-training python train.py --models xgboost catboost

# Or skip tuning
docker-compose exec ml-training python train.py --no-tune
```

### Issue: Slow data fetching
**Solution:** With paid Polygon.io, fetching should be fast. If slow:
- Check API key is valid (paid tier, not free)
- Check internet connection
- Reduce parallel workers in `fetch_historical_data_5years.py`

---

## Files Created

| File | Purpose | Location |
|------|---------|----------|
| `add_diverse_stocks_5years.py` | Add 500-600 stocks | `backend/scripts/` |
| `fetch_historical_data_5years.py` | Fetch 5 years data | `backend/scripts/` |
| `01h_feature_engineering_28features.py` | 28-feature engineering | `ml-training/scripts/` |
| `run_full_ml_pipeline_5years.sh` | Orchestration script | `ml-training/` |

---

## Next Steps (After This Expansion)

### Immediate (Priority 1 from Diagnosis)
1. **Add Insider Trading Features** (+8-12% AUC)
   - `insider_buy_count_30d`
   - `ceo_bought_30d`
   - `cluster_buying`
   - `insider_buy_at_52w_low`

2. **Add Market Context Features** (+3-5% AUC)
   - VIX data
   - SPY correlation (beta)
   - Market regime detection

### Advanced (Priority 5-7 from Diagnosis)
3. **Regime-Aware Models** (+2-4% AUC)
   - Separate models for bull/bear/range markets
   - Regime detection based on VIX + SPY trend

4. **Sector-Specific Models** (+1-3% AUC)
   - Train separate models per sector
   - Ensemble: 70% sector + 30% universal

---

## Expected Final Results

**With All Improvements (This Expansion + Priorities 1, 2, 5, 6):**
- **Current:** 56.8% AUC
- **This expansion:** 63-68% AUC (+6-11%)
- **+ Insider features:** 71-76% AUC
- **+ Market context:** 74-78% AUC
- **+ Regime-aware:** 76-80% AUC
- **+ Sector-specific:** 77-81% AUC

**Realistic Final AUC:** 70-75% (aligns with diagnosis document)

---

## Database Impact

### Storage Requirements

**Per stock:**
- 5 years × ~252 trading days = ~1,260 rows
- ~500 stocks × 1,260 rows = ~630,000 rows total
- Row size: ~100 bytes (OHLCV + indexes)
- **Total:** ~63 MB for stock_prices table

**Features:**
- ~250K samples × 28 features × 8 bytes (float64) = ~56 MB
- Labels: ~250K samples × 4 columns × 8 bytes = ~8 MB
- **Total:** ~64 MB for features

**Overall:** <200 MB additional storage

### Performance Impact

- **Queries:** Similar performance (indexes on stock_id, timestamp)
- **Training:** 63% faster (28 vs 76 features)
- **Inference:** 63% faster (fewer features to compute)

---

## Monitoring Progress

### During Data Fetching
```bash
# Check number of stocks
docker-compose exec backend python -c "
from app.models.stock import Stock
print(f'Stocks: {Stock.query.filter_by(is_tracked=True).count()}')
"

# Check price data count
docker-compose exec backend python -c "
from app.models.stock_price import StockPrice
print(f'Price records: {StockPrice.count()}')
"
```

### During Feature Engineering
Check feature file sizes:
```bash
docker-compose exec ml-training ls -lh /app/outputs/features/
```

### During Training
Check GPU utilization:
```bash
docker-compose exec ml-training nvidia-smi
```

---

## References

- `ML_BRAINSTORMING_DIAGNOSIS_2026.md` - Full diagnosis and roadmap
- `ML_IMPROVEMENT_ROADMAP.md` - Step-by-step implementation plan
- `ml_framework/config.py` - ML training configuration
- `backend/app/services/technical_indicators.py` - Indicator calculations

---

**End of Guide**
