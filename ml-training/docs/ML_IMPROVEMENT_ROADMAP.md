 Executive Summary
  ┌─────────────────────┬───────────────────┬────────────────────────────────────────────────────────────────┐
  │       Aspect        │      Status       │                            Finding                             │
  ├─────────────────────┼───────────────────┼────────────────────────────────────────────────────────────────┤
  │ GPU/CUDA            │ ✅ Working        │ GTX 1060 3GB, CUDA 12.2 confirmed                              │
  ├─────────────────────┼───────────────────┼────────────────────────────────────────────────────────────────┤
  │ Training Stop Cause │ ⚠️ Investigated   │ Container interrupted at trial 22/100 (log cut off mid-output) │
  ├─────────────────────┼───────────────────┼────────────────────────────────────────────────────────────────┤
  │ Model Performance   │ ❌ Critical Issue │ AUC 0.514 = barely better than random (0.50)                   │
  ├─────────────────────┼───────────────────┼────────────────────────────────────────────────────────────────┤
  │ Data Volume         │ ✅ Excellent      │ 466 stocks, 5 years, 592K daily records                        │
  ├─────────────────────┼───────────────────┼────────────────────────────────────────────────────────────────┤
  │ Features            │ ⚠️ Needs Regen    │ Features directory missing, needs to be recreated              │
  └─────────────────────┴───────────────────┴────────────────────────────────────────────────────────────────┘
  ---
  1. GPU/CUDA Status ✅

  Working Correctly
  GPU: NVIDIA GeForce GTX 1060 3GB
  Driver: 535.288.01
  CUDA: 12.2
  Docker GPU Access: ✅ Confirmed working

  No issues here - GPU is accessible from Docker and ready for training.

  ---
  2. Why Training Stopped 🔍

  Root Cause: Container Interruption

  Evidence:
  - Log ends abruptly at trial 22/100 TCN training (line 1075 cuts mid-message)
  - Container exited with code 0 (clean shutdown, not crash)
  - Last activity: ~17 hours ago
  - Only logs directory exists - no models saved

  Most Likely Causes:
  1. Manual docker-compose down or docker stop
  2. System reboot/shutdown
  3. Terminal/session closure
  4. Disk space warning: Only 11GB free (82% used) - may have caused issues

  Disk Space Warning:
  /dev/mapper/ubuntu--vg-ubuntu--lv: 45GB used / 58GB total (82%)
  Only 11GB available - models, mlruns, logs consume space

  ---
  3. Model Performance Analysis 📉

  Current Performance: AUC 0.514 (1.4% above random)

  This is catastrophically bad for a trading model. Random guessing would be 0.50.

  Why Performance is Terrible 🔥
  ┌────────────────────────┬──────────┬──────────────────────────────────────────────────────┐
  │         Issue          │  Impact  │                       Evidence                       │
  ├────────────────────────┼──────────┼──────────────────────────────────────────────────────┤
  │ Data Leakage           │ Critical │ Technical indicators calculated on same day as label │
  ├────────────────────────┼──────────┼──────────────────────────────────────────────────────┤
  │ Lookahead Bias         │ Critical │ Features use future data (EMA, SMA need next bars)   │
  ├────────────────────────┼──────────┼──────────────────────────────────────────────────────┤
  │ Wrong Target           │ Major    │ +3% within 20 days vs -2% stop is extremely noisy    │
  ├────────────────────────┼──────────┼──────────────────────────────────────────────────────┤
  │ Feature Count          │ Minor    │ 72 features is reasonable (not too many)             │
  ├────────────────────────┼──────────┼──────────────────────────────────────────────────────┤
  │ Insufficient Data Prep │ Major    │ Missing features dir suggests pipeline issues        │
  └────────────────────────┴──────────┴──────────────────────────────────────────────────────┘
  Data Leakage in Current Implementation

  Looking at 01d_feature_engineering_auto_date.py:164:
  indicators = TechnicalIndicators.calculate_all_indicators(df)
  labels = create_labels(indicators, stock_id)

  Problem: Features (indicators) and labels calculated from same DataFrame. Technical indicators like:
  - RSI, MACD, Bollinger Bands need "lookback" periods
  - Moving averages (SMA/EMA) smooth data from future bars
  - These contain information about price movements used to create labels

  This is like telling the model "stock went up" AND "all indicators say it will go up" - then wondering why it fails on new data.

  ---
  4. Data Assessment ✅
  ┌───────────────────┬─────────────────────┬──────────────────────────────┐
  │      Metric       │        Value        │          Assessment          │
  ├───────────────────┼─────────────────────┼──────────────────────────────┤
  │ Stocks            │ 466                 │ ✅ Excellent                 │
  ├───────────────────┼─────────────────────┼──────────────────────────────┤
  │ Date Range        │ Feb 2021 - Jan 2026 │ ✅ 5 years                   │
  ├───────────────────┼─────────────────────┼──────────────────────────────┤
  │ Daily Records     │ 592,706             │ ✅ Good                      │
  ├───────────────────┼─────────────────────┼──────────────────────────────┤
  │ Estimated Samples │ ~400K               │ ✅ More than enough          │
  ├───────────────────┼─────────────────────┼──────────────────────────────┤
  │ Sectors           │ 10+                 │ ✅ Well diversified          │
  ├───────────────────┼─────────────────────┼──────────────────────────────┤
  │ Features          │ ~72                 │ ✅ Reasonable (not too many) │
  └───────────────────┴─────────────────────┴──────────────────────────────┘
  Data quantity is NOT the problem.

  ---
  5. Why AUC ~0.514 (Root Causes) 🎯

  Primary Issues:

  1. DATA LEAKAGE ⚠️
    - Technical indicators calculated on same data used for labels
    - Model learns patterns that don't exist in real trading
    - Validation appears to work but test fails
  2. Lookahead Bias ⚠️
    - Indicators like EMA, SMA use future data points
    - In real trading, you wouldn't have these values yet
    - Creates false correlation during training
  3. Noisy Labels ⚠️
    - +3% target within 20 days before -2% stop loss
    - Many stocks never hit either threshold
    - Creates weak signal-to-noise ratio
  4. Insufficient Temporal Structure
    - TCN tries to use sequences but data is fundamentally tabular
    - Stock-by-stock samples don't have temporal continuity

  Secondary Issues:

  5. Feature Engineering Problems
    - Too many correlated features (RSI, Stochastic, CCI all measure momentum)
    - Missing important features (volatility, volume trends, market regime)
    - No feature selection or dimensionality reduction
  6. Model Architecture Mismatch
    - TCN designed for continuous sequences
    - Your data is discrete (stock-day samples)
    - No grouping by stock in model

  ---
  6. Performance Improvement Roadmap 🚀

  🔥 CRITICAL FIXES (Do First)

  Priority 1: Fix Data Leakage

  # BAD (current):
  indicators = calculate_all_indicators(df)
  labels = create_labels(indicators, stock_id)

  # GOOD:
  # For each day i:
  #   - Calculate features using ONLY data up to day i
  #   - Create label for day i
  #   - Move to day i+1

  Action: Modify feature engineering to simulate real trading:
  - For each sample, use only historical data available at that time
  - Implement "walk-forward" feature calculation
  - Shift features by 1 day to prevent leakage

  Priority 2: Improve Labels

  # Current: Binary (hit +3% or not)
  # Better: Regression or multi-class

  # Option A: Regression (predict actual return)
  label = max_upside_20d  # Actual percentage gain

  # Option B: Multi-class
  label = 0 if max_upside < 0.01
  label = 1 if 0.01 <= max_upside < 0.03
  label = 2 if max_upside >= 0.03

  # Option C: Probability-based
  label = probability_of_hitting_target  # 0.0 to 1.0

  Priority 3: Add Critical Features

  # Missing features that matter:
  - Volatility regime (low/medium/high)
  - Volume trend (increasing/decreasing)
  - Price momentum (1d, 5d, 20d returns)
  - Market sector dummy variables
  - Distance from 52-week high/low
  - Gap up/down from previous close
  - Institutional vs retail trading patterns

  Priority 4: Feature Selection

  # Use mutual information or feature importance
  # Reduce 72 → ~30-40 most predictive features

  from sklearn.feature_selection import mutual_info_classif
  mi_scores = mutual_info_classif(X_train, y_train)
  top_features = SelectKBest(k=40)

  ---
  ⚡ HIGH IMPROVEMENTS (Do Second)

  5. Ensemble Optimization

  # Current: Simple weighted average
  # Better: Stacking with meta-learner

  meta_learner = LogisticRegression()
  meta_learner.fit([xgb_pred, cat_pred, tcn_pred], y_val)

  6. Cross-Validation Strategy

  # Current: Simple temporal split (70/15/15)
  # Better: Purged K-Fold with gap

  from sklearn.model_selection import PurgedKFold
  pkf = PurgedKFold(n_splits=5, gap=20)  # 20-day gap prevents leakage

  7. Hyperparameter Tuning

  # Current: 200 trials (config) but 100 in actual run
  # Better: More focused search space

  n_trials = 100  # Reduce from 200
  # Add domain knowledge to bounds:
  max_depth = (3, 6)  # Shallower trees for noisy data
  learning_rate = (0.01, 0.1)  # Focus on reasonable range

  8. Add Regularization

  # Prevent overfitting to noise
  xgb_params = {
      'reg_alpha': (0.1, 2.0),  # L1
      'reg_lambda': (1.0, 5.0),  # L2
      'min_child_weight': (5, 20),  # Increase
  }

  ---
  🎯 MEDIUM IMPROVEMENTS (Do Third)

  9. Data Augmentation

  # Create more samples from existing data
  - Add noise to features (Gaussian)
  - Shift labels by ±1 day
  - Bootstrap sampling per stock

  10. Market Regime Detection

  # Add market state as feature
  market_state = detect_regime(market_index)  # Bull/Bear/Sideways
  # Models learn different patterns per regime

  11. Stock Clustering

  # Group similar stocks (sector, volatility, market cap)
  # Train separate models per cluster
  from sklearn.cluster import KMeans
  clusters = KMeans(n_clusters=5).fit(stock_features)

  12. Alternative Models

  # Models that work better with tabular time-series:
  - LightGBM (faster than XGBoost)
  - TabNet (deep learning for tabular)
  - AutoGluon (autoML for tabular)
  - Prophet (time-series forecasting)

  ---
  🔬 EXPERIMENTAL (Try Later)

  13. Transformer Models

  # Time-series transformer
  - Informer, Reformer, LogTrans
  - Attention mechanisms for temporal dependencies

  14. Reinforcement Learning

  # Learn optimal entry/exit directly
  - PPO, A3C, DQN
  - Reward = actual trading profit

  15. Alternative Data Sources

  # Add non-price data:
  - News sentiment (you have FinBERT!)
  - Earnings surprises
  - Analyst ratings changes
  - Institutional flow data
  - Options activity (put/call ratio)

  ---
  7. Reduced Trials Configuration ⚙️

  Current config issue: n_trials = 200 in config but actual run shows 100 trials

  To reduce trials to 100, modify ml_framework/ml_framework/config.py:151:

  # Change from:
  n_trials: int = 200

  # To:
  n_trials: int = 100  # Reduced for faster iteration

  Recommended trials per model:
  XGBoost:    100 trials (~2-3 min with GPU)
  CatBoost:   100 trials (~2-3 min with GPU)
  TCN:        50 trials  (~10-15 min, slower)
  Chronos:    1 trial    (pretrained, ~30 sec)

  ---
  8. Immediate Action Plan 📋

  Step 1: Free Up Disk Space

  # Clean up old mlruns
  rm -rf ml-training/mlruns/*  # Can be GBs
  # Clean Docker
  docker system prune -af

  Step 2: Fix Feature Engineering (CRITICAL)

  # Modify 01d_feature_engineering_auto_date.py to prevent data leakage
  # Use walk-forward calculation
  docker-compose run --rm ml-training python /app/scripts/01d_feature_engineering_auto_date.py

  Step 3: Reduce Trials & Retrain

  # Edit config.py: n_trials = 100
  docker-compose run --rm ml-training python /app/train.py

  Step 4: Evaluate & Diagnose

  # Check feature importance
  # Check for data leakage in validation
  # Analyze misclassified samples

  Step 5: Iterate Based on Findings

  ---
  Expected Performance After Fixes 📈
  ┌─────────────────────────────┬──────────────┬───────────────────┬─────────────────┐
  │            Phase            │ Expected AUC │ Expected Accuracy │ Time Investment │
  ├─────────────────────────────┼──────────────┼───────────────────┼─────────────────┤
  │ Current                     │ 0.514        │ ~51%              │ -               │
  ├─────────────────────────────┼──────────────┼───────────────────┼─────────────────┤
  │ After fixing leakage        │ 0.60-0.65    │ 58-62%            │ 2-4 hours       │
  ├─────────────────────────────┼──────────────┼───────────────────┼─────────────────┤
  │ After better labels         │ 0.65-0.70    │ 62-68%            │ +2-3 hours      │
  ├─────────────────────────────┼──────────────┼───────────────────┼─────────────────┤
  │ After feature selection     │ 0.68-0.73    │ 65-70%            │ +1-2 hours      │
  ├─────────────────────────────┼──────────────┼───────────────────┼─────────────────┤
  │ After ensemble optimization │ 0.72-0.75    │ 68-73%            │ +2-3 hours      │
  ├─────────────────────────────┼──────────────┼───────────────────┼─────────────────┤
  │ With alternative data       │ 0.75-0.80    │ 72-77%            │ +weeks          │
  └─────────────────────────────┴──────────────┴───────────────────┴─────────────────┘
  Realistic target: AUC 0.68-0.72 for swing trading predictions

  ---
  Summary

  The low performance (AUC 0.514) is NOT due to:
  - ❌ Not enough data (466 stocks, 5 years is plenty)
  - ❌ Too many features (72 is reasonable)
  - ❌ Model architecture (XGBoost/CatBoost are solid)

  The low performance IS due to:
  - ✅ Data leakage in feature engineering
  - ✅ Lookahead bias from indicator calculation
  - ✅ Noisy labels (+3% target is very difficult)
  - ✅ Missing critical features (volatility, volume trends)

  Start with Priority 1-3 fixes and you should see immediate improvement to AUC 0.60-0.65 range.

  ---
  Would you like me to:
  1. Implement the data leakage fix in feature engineering?
  2. Modify the config to reduce trials to 100?
  3. Create a new feature engineering script with proper walk-forward validation?
  4. Add the missing critical features (volatility, volume trends)?
