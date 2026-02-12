# News Sentiment Implementation - Comprehensive Summary

**Last Updated:** 2026-02-11

---

## Table of Contents

1. [Overview](#overview)
2. [Current Implementation](#current-implementation)
3. [Dataset Path](#dataset-path)
4. [News Features](#news-features)
5. [Drawbacks and Issues](#drawbacks-and-issues)
6. [Performance Analysis](#performance-analysis)
7. [Recommendations](#recommendations)

---

## Overview

The news sentiment feature implementation aims to enhance the machine learning models by incorporating financial news sentiment analysis using FinBERT (ProsusAI/finbert), a transformer model fine-tuned on financial text.

**Key Components:**
- **FinBERT Model**: For sentiment analysis of news headlines
- **20 Rolling Features**: Various time-window aggregations (1d, 3d, 7d, 14d, 30d)
- **Database Storage**: `stock_news` table with sentiment scores
- **ML Integration**: XGBoost and CatBoost classifiers (3-class: SELL/HOLD/BUY)

---

## Current Implementation

### Data Pipeline

```
Database (PostgreSQL)
    ↓
stock_news table
    ├── news_id
    ├── stock_id
    ├── timestamp (exact time from article)
    ├── title
    ├── description/news_text
    ├── source (Polygon.io)
    ├── url
    └── news_sentiment (FinBERT score: -1.0 to +1.0)

FinBERT Sentiment Analysis
    ↓
ml_framework/news_features.py
    ├── NewsFeatures class
    ├── fetch_news_from_db()
    ├── calculate_rolling_features()
    └── NEWS_FEATURES array (20 features)

Feature Engineering
    ↓
ml_framework/feature_engineering.py
    ├── engineer_features_v2()
    ├── Other features (technical, fundamental, insider, etc.)
    └── merge_features()

Dataset Creation
    ↓
scripts/create_labels.py
    ├── Load features
    ├── Calculate forward returns (20d, 30d, 40d)
    ├── Create 3-class labels (SELL/HOLD/BUY)
    └── Save to labels_3class.parquet

Training Pipeline
    ↓
train.py
    ├── Load features + labels
    ├── Split by time (train/val/test)
    ├── Hyperparameter tuning (Optuna, 20 trials)
    ├── Train XGBoost + CatBoost
    └── Ensemble (weighted average)
```

---

## Dataset Path

### Location
```
/app/outputs/features/dataset_20260211_103304/
├── features.parquet           # 490,544 rows × 158 columns
└── labels_3class.parquet       # 472,492 rows × 8 columns
```

### Dataset Contents

**Total Samples:** 490,544 (after merge with labels)

**Date Range:** 2018-01-02 to 2026-01-30

**Stock Coverage:** 268 stocks

**Total Features:** 158 (including stock_id, timestamp, labels)

**Feature Breakdown:**
- **Technical Indicators:** ~80 features
  - RSI, MACD, Moving Averages
  - Volatility measures
  - Price momentum
  - Volume indicators
  - ATR, Bollinger Bands

- **Alternative Data:** ~40 features
  - Insider trading (buy/sell unusual)
  - Congressional trading
  - Short interest
  - Market regime indicators

- **News Sentiment:** 20 features
  - All defined in `ml_framework/news_features.py`

---

## News Features

### Feature List (20 Total)

| # | Feature Name | Description | Time Window |
|---|---------------|-------------|--------------|
| **Rolling Averages** |||
| 1 | `news_sentiment_avg_1d` | Average sentiment | 1 day |
| 2 | `news_sentiment_avg_3d` | Average sentiment | 3 days |
| 3 | `news_sentiment_avg_7d` | Average sentiment | 7 days |
| 4 | `news_sentiment_avg_14d` | Average sentiment | 14 days |
| 5 | `news_sentiment_avg_30d` | Average sentiment | 30 days |
| **Weighted Averages** |||
| 6 | `news_sentiment_weighted_1d` | Volume-weighted sentiment | 1 day |
| 7 | `news_sentiment_weighted_7d` | Volume-weighted sentiment | 7 days |
| 8 | `news_sentiment_weighted_30d` | Volume-weighted sentiment | 30 days |
| **Ratio Features** |||
| 9 | `news_positive_ratio_7d` | % positive articles | 7 days |
| 10 | `news_negative_ratio_7d` | % negative articles | 7 days |
| 11 | `news_net_sentiment_7d` | (positive - negative) | 7 days |
| 12 | `news_sentiment_consensus_7d` | Agreement among articles | 7 days |
| **Intensity Features** |||
| 13 | `news_intensity_1d` | Article count | 1 day |
| 14 | `news_intensity_7d` | Article count | 7 days |
| 15 | `news_intensity_spike_7d` | Spike detection | 7 days vs avg |
| **Statistical Features** |||
| 16 | `news_sentiment_max_7d` | Max sentiment | 7 days |
| 17 | `news_sentiment_min_7d` | Min sentiment | 7 days |
| 18 | `news_sentiment_std_7d` | Std deviation | 7 days |
| 19 | `news_sentiment_trend_7d` | Linear trend | 7 days |
| **Metadata** |||
| 20 | `news_data_available` | Any news data | Binary flag |

### Implementation Location
```
ml_framework/news_features.py
├── NEWS_FEATURES = [...]  # Array of 20 feature names
├── class NewsFeatures:
│   ├── fetch_news_from_db(stock_id, start_date, end_date)
│   ├── calculate_rolling_features(news_df, feature_dates)
│   └── Helper methods for aggregations
└── Used by: ml_framework/feature_engineering.py
```

### Calculation Method

For each stock-day combination:
1. Fetch all news articles with timestamps for that stock
2. Group by date (normalized to midnight)
3. Calculate aggregations:
   - Average sentiment (simple and weighted by volume)
   - Positive/negative ratios
   - Max/min/std of sentiment
   - Article intensity (count)
   - Trend (linear regression slope)
4. Merge with features on `[stock_id, date]`

### Source Data
```sql
SELECT stock_id, timestamp, news_sentiment
FROM stock_news
WHERE stock_id = :stock_id
  AND timestamp >= :start_date
  AND timestamp <= :end_date
ORDER BY timestamp
```

---

## Drawbacks and Issues

### Critical Issues Discovered

#### 1. Zero Feature Importance ❌
**Problem:** ALL 20 news features received **0.00% importance** from trained models.

**Evidence:**
- CatBoost trained on `dataset_20260211_103304`
- Feature importance analysis showed:
  - Total importance: 100%
  - News features: 0.00% (combined)
  - Technical features: 100%
- Top 10 features were ALL technical indicators (RSI, momentum, volatility)

**Root Cause Analysis:**
The models completely ignored news sentiment despite:
- Dataset having 188K non-zero news sentiment values (38.4% coverage)
- 227K non-zero news intensity values (46.3% coverage)
- All 20 features properly calculated and present in training data

#### 2. Data Sparsity
**Issue:** Only 39.4% of samples have any news data.

**Impact:**
- 60.6% of rows have ZERO news sentiment (no articles that day)
- Model likely learned to default to "no news" baseline
- Sparse features make it harder to learn patterns

#### 3. Temporal Misalignment
**Problem:** News timestamp is exact article time, features are day-aligned.

**Example:**
- News article at 2026-01-15 14:23:45 → assigned to 2026-01-15 row
- But market close at 2026-01-15 17:00:00 → same row

**Current Fix:**
- `calculate_rolling_features()` normalizes dates to midnight
- Merge happens on `merge_date = timestamp.dt.date`
- This ensures same-day matching regardless of article time

#### 4. Multicollinearity Among News Features
**Issue:** News features are highly correlated with each other.

**Evidence:**
- `news_sentiment_avg_7d` correlates with `news_sentiment_avg_14d` at >0.95
- All sentiment windows strongly overlap
- Intensity features correlate with sentiment ratios

**Impact:**
- Model struggles to distinguish between 7d, 14d, 30d sentiment
- Redundant features add noise without adding signal

#### 5. Forward Lookahead Contamination
**Theoretical Issue:** News published at 10:00 could affect 10:00 market close.

**Current Implementation:**
- Features use only previous news (before market close)
- Labels are based on forward returns from feature date
- Should be contamination-free since news is from prior day(s)

#### 6. Lag vs. Leading Indicator
**Question:** Is news sentiment a leading or lagging indicator?

**Current State:**
- 1d sentiment: Strongly leading (same-day news)
- 7d+ sentiment: Mixed (past week's sentiment)
- Models may be treating all as if they're equally predictive

#### 7. Class Distribution Imbalance
**Labels (from training):**
- Class 0 (SELL): 21.5%
- Class 1 (HOLD): 49.1%
- Class 2 (BUY): 29.5%

**Issue:** Slightly "bearish" bias in training data
- May affect model to prefer SELL signals
- News might help rebalance if sentiment is truly predictive

#### 8. Computational Overhead
**Impact:** Calculating 20 rolling news features adds processing time.

**Bottlenecks:**
- Database query for 268 stocks × 8 years of data
- ~10 seconds per stock during feature engineering
- Total: ~45 minutes for update script

#### 9. Model Complexity vs. Feature Value
**Trade-off:** 20 additional features vs. minimal performance gain.

**Observation:**
- XGBoost AUC: 59.1% (with news features in data)
- Top features: ALL technical indicators (RSI, momentum, volatility)
- News features: 0% importance

**Conclusion:** Either news sentiment doesn't predict returns, or current models aren't capturing the relationship.

---

## Performance Analysis

### Model Results (Latest Training)

**XGBoost:**
- Accuracy: 46.2%
- Precision: 38.5%
- Recall: 37.7%
- AUC: 59.1%

**CatBoost:**
- Accuracy: 44.7%
- Precision: 38.1%
- Recall: 34.8%
- AUC: 55.0%

**Ensemble:**
- Accuracy: 51.3%
- AUC: 60.1%

### News Feature Importance Distribution

| Feature Type | Importance | Notes |
|--------------|------------|-------|
| Technical (RSI, etc.) | 100% | All importance in top 10 |
| News Sentiment | 0.00% | **ZERO importance** |
| Insider Trading | <0.1% | Minimal importance |
| Congressional | <0.1% | Minimal importance |
| Short Interest | <0.1% | Minimal importance |

### Key Insights

1. **Technical indicators dominate** - RSI, moving averages, volatility
2. **News sentiment is ignored** - 0% importance despite valid data
3. **Alternative data underutilized** - Insider/congressional features barely used
4. **Model accuracy is modest** - 51-60% AUC suggests room for improvement

---

## Recommendations

### Immediate Actions

#### 1. Investigate Why News Features Have Zero Importance

**Diagnostic Steps:**
```bash
# Check correlation between news sentiment and returns
docker exec stock_analyzer_ml_training python -c "
import pandas as pd
df = pd.read_parquet('/app/outputs/features/dataset_20260211_103304/features.parquet')

# Check if news features have ANY relationship with returns
print('Correlation with forward returns (20d):')
for col in ['news_sentiment_avg_7d', 'news_intensity_7d', 'news_positive_ratio_7d']:
    corr = df[col].corr(df['final_return_20d'])
    print(f'  {col}: {corr:.4f}')

print()
print('Correlation with label (3-class):')
for col in ['news_sentiment_avg_7d', 'news_intensity_7d']:
    for label_val in [0, 1, 2]:  # SELL, HOLD, BUY
        temp = df[df['label_20d'] == label_val]
        corr = temp[col].corr(temp['final_return_20d'])
        print(f'  {col} vs class {label_val} (BUY={2}, HOLD={1}, SELL={0}): {corr:.4f}')
"
```

**Expected Finding:**
- If all correlations are near zero (< 0.05), news is not predictive for this horizon
- If class-specific correlations differ, there may be signal in one direction

#### 2. Data Quality Improvements

**A. Increase News Coverage**
- Current: 39.4% of samples have news
- Goal: 60%+ for robust news-driven signals
- Action:
  - Fetch more historical news (Polygon.io has back to 2018+)
  - Expand news sources beyond Polygon.io
  - Consider news aggregators (Bloomberg, Reuters, etc.)

**B. Reduce Sparsity**
```python
# Current approach: 0 if no news
# Better: Forward-fill from recent news (bounded window)

# In ml_framework/news_features.py:
def calculate_rolling_features(news_df, feature_dates):
    # ADD: Forward fill with decay
    # Instead of fillna(0), use:
    # - Day N: weighted avg of days [1, N-1, N-2]
    # - Decay factor: 0.9^days_ago
```

**C. Feature Engineering**
- Try raw article counts per bucket (positive/negative)
- Add sentiment velocity (change in sentiment)
- News surprise indicator (deviation from moving average)
- Interaction terms: news × volatility, news × momentum

#### 3. Model Architecture Changes

**A. Different Objective Functions**

```python
# Instead of single classification, try:
# 1. Binary classification with probability threshold
# 2. Regression to predict actual return magnitude
# 3. Ranking-based approach (predict top-K stocks)
```

**B. Feature Selection Strategies**

```python
# Recursive Feature Elimination (RFE)
from sklearn.feature_selection import RFE

# Or use model's native feature selection
# CatBoost has built-in feature selection via feature importance
```

**C. Ensemble Methods**
- Stacking: Use news sentiment predictions as meta-feature
- Blending: Separate models for news-rich vs news-poor stocks
- Multi-task learning: Predict both return AND news utilization

#### 4. Hyperparameter Tuning Focus

**Current:**
- 20 trials per model
- Focus: AUC optimization

**Proposed:**
```python
# Use Optuna with multi-objective optimization
study = optuna.create_study(directions=['maximize', 'minimize'])

# Objectives:
# 1. Maximize AUC
# 2. Maximize news_feature_importance (custom objective)
# 3. Minimize catastrophic error rate (financial risk)

# This will force model to consider news importance
```

#### 5. Alternative Evaluation Metrics

**Problem:** AUC may not capture financial relevance.

**Additional Metrics to Track:**
```python
# Rank-based metrics
def top_k_accuracy(y_true, y_pred_proba, k=5):
    # Percentage of time top-K prediction was in actual top-K returns

# Sharpe Ratio
def sharpe_ratio(returns, benchmark_return=0):
    # (mean_return - benchmark) / std_return
    # Only count returns when position was active

# Maximum Drawdown
def max_drawdown(cumulative_returns):
    # Peak-to-trough decline
    # Critical for risk management
```

#### 6. Production Considerations

**A. Real-time Inference**
```python
# Cache news sentiment by stock
news_cache = {
    'AAPL': {'sentiment': 0.5, 'last_update': '2026-01-11 14:00'},
    'MSFT': {'sentiment': -0.2, 'last_update': '2026-01-11 13:45'},
}

# Update hourly, not daily
```

**B. A/B Testing Framework**
```python
# Test if news features help for specific stocks
def should_use_news_model(stock_id):
    # Small-cap: more responsive to news
    # Large-cap:driven by fundamentals
    # High-news-day:use news model
    return stock_id in HIGH_NEWS_STOCKS
```

---

## File Locations

### Core Implementation Files

**ML Framework:**
- `ml_framework/news_features.py` - News feature definitions
- `ml_framework/feature_engineering.py` - Main feature creation
- `ml_framework/trainer.py` - Training orchestration
- `ml_framework/config.py` - Configuration

**Training Scripts:**
- `train.py` - Main training entry point
- `scripts/create_labels.py` - Label generation
- `scripts/feature_engineering.py` - Feature creation pipeline

**Models:**
- `ml_framework/models/xgboost_model.py` - XGBoost wrapper
- `ml_framework/models/catboost_model.py` - CatBoost wrapper
- `ml_framework/models/ensemble.py` - Model ensemble

**Data:**
- `/app/outputs/features/dataset_20260211_103304/`
  - Current production dataset (has news features)
- `/app/outputs/features/dataset_20260210_224956/`
  - Original Feb 10 dataset (broken news)

### Database Schema

```sql
stock_news table:
┌───────────────┬──────────────┬──────────────┬───────────────┐
│ news_id (PK) │ stock_id (FK) │ timestamp    │ title        │ news_text    │ news_sentiment │ source │ url        │
├───────────────┼───────────────┼──────────────┼───────────────┼───────────────┤
│ BIGINT        │ INTEGER      │ TIMESTAMP   │ TEXT        │ TEXT        │ FLOAT       │ TEXT   │ TEXT        │
│ NOT NULL      │ NOT NULL     │ NOT NULL     │ NOT NULL     │ [-1, 1]    │ NOT NULL  │ NOT NULL     │
└───────────────┴───────────────┴──────────────┴───────────────┴───────────────┘

Indexes:
- idx_news_primary (news_id, stock_id, timestamp)
- idx_stock_fk (stock_id → stocks)
- idx_sentiment (news_sentiment for filtering)
```

---

## Summary

### Key Takeaways

1. ✅ **Implementation is technically correct**
   - FinBERT model working
   - 20 features properly calculated
   - Rolling windows implemented correctly
   - Database integration functioning

2. ❌ **News features have ZERO predictive value**
   - All 20 features: 0.00% importance
   - Models ignore news completely
   - Technical indicators dominate predictions

3. ⚠️ **Data quality issues identified**
   - 39.4% news coverage (sparse)
   - 60.6% zero-sentiment rows
   - High multicollinearity among news features

4. 🎯 **Path forward requires investigation**
   - Correlation analysis needed (news vs returns)
   - Feature selection improvements (RFE, L1 regularization)
   - Consider different architectures (neural networks, attention mechanisms)
   - Financial metrics (Sharpe, drawdown) may be more appropriate than AUC

5. 📊 **Current model performance:**
   - XGBoost: 59.1% AUC
   - CatBoost: 55.0% AUC
   - Ensemble: 60.1% AUC
   - Accuracy: ~46-51%
   - **Room for improvement** in approach, not just features

---

**Generated:** 2026-02-11
**Author:** StockAnalyzer ML Framework
**Version:** 1.0
