# EXTEND DATASET TO 2018-2020 - COMPLETE GUIDE

**Goal:** Create continuous 2018-2025 dataset with diverse market regimes

**Why This Matters:**
- **2018-2020 provides critical market regimes:** Trade war, COVID crash, bear markets
- **Current data (2021-2025):** Mostly bull market recovery, missing volatility
- **Result:** Model learns to handle different market conditions

---

## 📋 EXECUTION PLAN

### Phase 1: Fetch Historical Data (1-2 days)

**Script:** `backend/scripts/fetch_historical_2018_2020.py`

**What it does:**
- Fetches OHLCV data for all 249 stocks from 2018-2020
- Uses Polygon API (requires API key)
- Saves to `stock_prices` table

**Command:**
```bash
cd backend
python scripts/fetch_historical_2018_2020.py
```

**Time Estimates:**
- 249 stocks × 12 seconds between requests = **~50 minutes**
- Plus API rate limiting = **1-2 hours total**

**API Costs:**
- Polygon free tier: 5 requests/minute
- Cost: **$0** (free tier)
- No additional costs

**Prerequisites:**
- ✅ `POLYGON_API_KEY` set in `.env`
- ✅ Database connection working

**Expected Output:**
```
Successfully fetched: 249/249 stocks
Records by year:
  2018: ~60,000 records
  2019: ~60,000 records
  2020: ~60,000 records
Total: ~180,000 new records
```

---

### Phase 2: Regenerate Features (30-60 minutes)

**Script:** `ml-training/regenerate_features_extended.py`

**What it does:**
- Runs feature engineering pipeline for 2018-2025
- Calculates technical indicators (RSI, MACD, moving averages)
- Fetches insider trading data (already available from 2001)
- Creates features.parquet file

**Command:**
```bash
docker-compose run --rm ml-training python regenerate_features_extended.py
```

**Time Estimate:**
- 249 stocks × 8 years = **30-60 minutes**
- Depends on CPU speed

**Expected Output:**
```
Dataset: dataset_extended_TIMESTAMP/
├── features.parquet (480k samples, 121 features)
└── labels_alpha_binary.parquet (generated next)
```

---

### Phase 3: Generate Alpha Labels (5-10 minutes)

**Script:** Same alpha label creation process

**Command:**
```bash
docker-compose run --rm ml-training python create_labels/validate_alpha_labels.py --dataset-folder dataset_extended_TIMESTAMP
```

**Expected Output:**
```
Total samples: ~480,000 (vs 300k currently)
Date range: 2018-01-01 to 2025-12-31
BUY rate: ~35% (similar to current)
```

---

### Phase 4: Train with Extended Dataset (2-3 hours)

**Command:**
```bash
docker-compose run --rm ml-training python train.py \
  --data-path /app/outputs/features/dataset_extended_TIMESTAMP/features.parquet \
  --labels-path /app/outputs/features/dataset_extended_TIMESTAMP/labels_alpha_binary.parquet \
  --models xgboost catboost \
  --trials 50 \
  --skip-tcn
```

**Expected Improvements:**
| Aspect | Current (2021-2025) | Extended (2018-2025) |
|--------|---------------------|---------------------|
| **Samples** | 300k | **480k** (+60%) |
| **Market Regimes** | Bull market | **All regimes** ✅ |
| **AUC** | 58% | **58-60%** (+2%) |
| **Robustness** | Medium | **High** ✅ |
| **Bear Market Performance** | Unknown | **Validated** ✅ |

---

## 🕐 TIMELINE

| Phase | Duration | Effort |
|-------|----------|--------|
| **1. Fetch 2018-2020 data** | 1-2 days | Low (automated) |
| **2. Regenerate features** | 30-60 min | Low (automated) |
| **3. Create alpha labels** | 5-10 min | Low (automated) |
| **4. Train models** | 2-3 hours | Low (automated) |
| **5. Validate & compare** | 30 min | Low (analysis) |

**Total Time: 2-3 days** (mostly automated waiting time)

---

## 💰 COST ANALYSIS

### Polygon API (Free Tier)
- **Cost:** $0
- **Rate limit:** 5 requests/minute
- **Total requests:** ~250 (249 stocks + 1 verification)
- **Time:** ~50 minutes of actual fetching, 1-2 hours with rate limiting

### Computing
- **Current:** Docker containers (already running)
- **Cost:** $0 (using existing infrastructure)

### Database Storage
- **Current:** 306k records (2021-2026)
- **After:** ~486k records (2018-2026)
- **Increase:** ~180k records
- **Storage cost:** Minimal (<1GB additional)

**Total Cost: $0** ✅

---

## ✅ BENEFITS OF EXTENDED DATASET

### 1. **Market Regime Diversity**

**Current (2021-2025):**
- COVID recovery
- Low interest rates
- Bull market dominance
- Single market regime

**Extended (2018-2025):**
- ✅ 2018: Trade war volatility
- ✅ 2019: Market corrections
- ✅ 2020: **COVID crash and recovery** (critical!)
- ✅ 2021-2025: Bull market

### 2. **Improved Model Robustness**

**Testing Scenarios Now Available:**
- Bull market performance (2021-2025) ✅
- Bear market performance (2020 crash) ✅
- High volatility (2018 trade war) ✅
- Market corrections (2019) ✅

**Expected Impact:**
- Model learns to handle different market conditions
- More reliable predictions across regimes
- Better generalization

### 3. **Better Validation**

**Current Problem:**
- Test set (2025) might be bull market only
- Can't validate bear market performance

**After Extension:**
- Test set includes multiple regimes
- Can validate bear market performance
- More confidence in model robustness

---

## ⚠️ RISKS & MITIGATION

### Risk 1: Fetch Failure
**Risk:** Polygon API might not have data for some stocks (especially smaller ones)
**Mitigation:**
- Skip stocks with no 2018-2020 data
- Model can still train on available stocks
- 249 stocks → expect 230-245 complete

### Risk 2: Sparse Insider Data (2018-2020)
**Current:** 2018-2020 has sparse insider data (36-140 records/year vs 38k+ in 2021)
**Mitigation:**
- Sparse data is better than no data
- Model can still learn some patterns
- Focus on price-based features for this period

### Risk 3: Feature Drift
**Risk:** Features calculated differently in 2018 vs 2025
**Mitigation:**
- Same feature engineering pipeline
- Consistent calculations
- Just different time periods

---

## 🎯 SUCCESS CRITERIA

**Extended Dataset Success Metrics:**

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Data Coverage** | ≥95% stocks have 2018-2020 data | Check database |
| **Sample Count** | ≥450k samples | features.parquet row count |
| **Regime Coverage** | All 4 regimes represented | Year distribution |
| **Model AUC** | 58-60% | Training output |
| **Bear Market AUC** | ≥55% | Test on 2020 data specifically |
| **Overfitting** | <3% gap train/test | Compare metrics |

---

## 📝 POST-EXTENSION VALIDATION

### After Training, Validate:

1. **Regime-Specific Performance**
   ```python
   # Test on 2020 (COVID crash) specifically
   # Test on 2018 (trade war)
   # Compare to 2021-2025 (bull market)
   ```

2. **Feature Importance Stability**
   ```python
   # Check if relative features still important
   # Check if insider features used in all regimes
   # Verify SPY features stay minimal
   ```

3. **Prediction Consistency**
   ```python
   # Compare predictions for same stock in different regimes
   # Model should adapt to market conditions
   ```

---

## 🚀 GETTING STARTED

### Step 1: Fetch Data (Run from backend directory)

```bash
cd backend
python scripts/fetch_historical_2018_2020.py
```

**Watch for:**
- ✅ Successfully fetched: 230-245/249 stocks
- ⚠️ Failed: <10 stocks (acceptable)

### Step 2: Regenerate Features

```bash
cd ml-training
docker-compose run --rm ml-training python regenerate_features_extended.py
```

**Watch for:**
- ✅ Generated ~480k samples
- ✅ Features saved correctly

### Step 3: Train Models

```bash
# Use the actual dataset folder name from output
docker-compose run --rm ml-training python train.py \
  --data-path /app/outputs/features/dataset_extended_TIMESTAMP/features.parquet \
  --labels-path /app/outputs/features/dataset_extended_TIMESTAMP/labels_alpha_binary.parquet \
  --models xgboost catboost \
  --trials 50 \
  --skip-tcn
```

### Step 4: Compare Results

```python
# Compare models trained on:
# 1. 2021-2025 data (current)
# 2. 2018-2025 data (extended)

# Metrics to compare:
# - Overall AUC
# - Year-by-year AUC (especially 2020!)
# - Feature importance stability
```

---

## 🔧 TROUBLESHOOTING

### Issue: Polygon API Errors

**Symptoms:**
- "404 Not Found" for some stocks
- "429 Too Many Requests"

**Solutions:**
- 404: Stock wasn't public in 2018-2019, skip it
- 429: Increase delay between requests (edit script: `time.sleep(15)`)
- API quota exceeded: Wait for next day

### Issue: Database Slow

**Symptoms:**
- Inserts taking too long

**Solutions:**
- Batch inserts (already implemented)
- Increase database connection pool
- Add indexes after data loaded

### Issue: Feature Generation Too Slow

**Symptoms:**
- Taking >2 hours for feature generation

**Solutions:**
- Reduce number of stocks for testing
- Use GPU for feature calculations (if available)
- Optimize SQL queries

---

## 📊 EXPECTED OUTCOMES

### Optimistic Scenario ✅

**Extended Dataset Performance:**
- AUC: 60% (+2% over current)
- Recall: 22% → 25% (+3%)
- Precision: 43% → 45% (+2%)
- **Bear Market AUC (2020): 55%** (new capability!)

**Feature Importance:**
- Relative features: 11% → 12%
- Insider features: 12% → 15%
- SPY features: 3.2% → 2%

### Realistic Scenario ✅

**Extended Dataset Performance:**
- AUC: 58-59% (similar to current)
- Recall: 18% → 20% (+2%)
- Precision: 43% (similar)
- **Bear Market AUC (2020): 54-56%** (validated!)

**Key Benefit:** **Robustness across regimes**

---

## 💡 FINAL RECOMMENDATION

**Do the extension because:**

1. ✅ **Low cost:** $0, 2-3 days, mostly automated
2. ✅ **High value:** Bear market validation, regime diversity
3. ✅ **Strategic:** Future-proofing for different market conditions
4. ✅ **Low risk:** Can still use current model if it fails

**Expected outcome:**
- Slight AUC improvement (0-2%)
- **Huge robustness improvement** (validated across regimes)
- Better confidence in model's real-world performance

---

## 📚 FILES CREATED

1. **`backend/scripts/fetch_historical_2018_2020.py`**
   - Fetches 2018-2020 stock prices from Polygon API

2. **`ml-training/regenerate_features_extended.py`**
   - Regenerates features for extended period

3. **`EXTEND_DATASET_2018_2020_GUIDE.md`** (this file)
   - Complete guide for the extension process

---

**Ready to proceed?** Start with Phase 1 (fetch data) and I'll monitor progress!

**Questions before starting?**
- API key configured?
- Database connection working?
- Time available (2-3 days)?
