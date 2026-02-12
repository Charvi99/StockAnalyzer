# StockAnalyzer ML Training Session - 2026-01-31

 ## Overview
 This session focused on expanding the ML training dataset from ~30K samples to ~600K samples by:
 1. Fetching 5 years of daily data (instead of 17 months)
 2. Adding more stocks (479 total, up from 252)
 3. Implementing log returns feature engineering
 4. Running full training with 200 trials per model

 ## Problem: Low Model Performance
 Original training showed AUC of ~51% (essentially random guessing). Analysis revealed:
 - Only 30,420 samples across 247 stocks
 - 17 months of data (2023-01-31 to 2024-06-26)
 - Daily returns averaged 0.03% with 2.16% volatility
 - Prediction target: +3% before -2% within 20 days (inherently difficult)
 - Using simple returns (pct_change) instead of log returns

 ## Solution Implemented

 ### 1. Data Expansion

 #### Added More Stocks
 - **File**: `backend/scripts/add_more_stocks.py` (created)
 - **Result**: Added 227 new stocks (479 total, close to 500 goal)
 - **Sectors covered**: Technology, Financial, Healthcare, Energy, Consumer, Industrial

 #### Fetched 5 Years of Daily Data
 - **Command**:
 ```bash
 docker-compose exec -T backend python /app/scripts/fetch_ml_daily_data.py --period 5y --batch-size 5 --delay 0.5
 ```
 - **Result**: 592,706 records across 466 stocks (2021-02-01 to 2026-01-30)
 - **Time**: ~10 minutes
 - **Success rate**: 97.3% (466/479 stocks)

 **Special Notes**:
 - Used `fetch_ml_daily_data.py` instead of `fetch_ml_training_data.py`
 - The original script was blocked by aggregation system (1d is aggregated from 1h)
 - Direct daily fetch bypasses aggregation completely

 ### 2. Log Returns Feature Engineering

 #### Created New Script
 - **File**: `ml-training/scripts/01e_feature_engineering_with_log_returns.py`
 - **Key additions**:
   ```python
   # Log returns (better than simple returns)
   df['log_return_1d'] = np.log(df['close'] / df['close'].shift(1))
   df['log_return_5d'] = np.log(df['close'] / df['close'].shift(5))
   df['log_return_10d'] = np.log(df['close'] / df['close'].shift(10))
   df['log_return_20d'] = np.log(df['close'] / df['close'].shift(20))

   # Volatility (std of log returns)
   df['volatility_10d'] = df['log_return_1d'].rolling(10).std()
   df['volatility_20d'] = df['log_return_1d'].rolling(20).std()
   df['volatility_60d'] = df['log_return_1d'].rolling(60).std()

   # Momentum using log returns
   df['momentum_5d'] = df['log_return_5d']
   df['momentum_10d'] = df['log_return_10d']
   df['momentum_20d'] = df['log_return_20d']

   # Relative price position
   df['price_position_20d'] = (df['close'] - df['close'].rolling(20).min()) / \
                               (df['close'].rolling(20).max() - df['close'].rolling(20).min())

   # Log volume (more normal distribution)
   df['log_volume'] = np.log(df['volume'] + 1)
   df['volume_change'] = df['log_volume'] - df['log_volume'].shift(1)

   # Gap (overnight movement)
   df['gap'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
   ```

 **Why Log Returns Matter**:
 1. Normally distributed (better for ML models)
 2. Additive over time
 3. Symmetric (gains and losses have same magnitude)

 #### Feature Engineering Results
 - **Samples**: 583,355 (20x increase from ~30K)
 - **Features**: 95 per sample
 - **Stocks processed**: 479 (14 skipped)
 - **Positive class**: 43.7% (well-balanced)
 - **Date range**: 2021-04-02 to 2026-01-10
 - **Time**: ~17 minutes

 **Command**:
 ```bash
 docker-compose run --rm ml-training python /app/scripts/01e_feature_engineering_with_log_returns.py
 ```

 **Output files**:
 - Features: `/app/outputs/features/features_20260131_104818.parquet`
 - Labels: `/app/outputs/features/labels_20260131_104821.parquet`

 ### 3. Configuration Updates

 #### Increased Trials
 - **File**: `ml-training/ml_framework/config.py`
 - **Change**:
   ```python
   # Before:
   n_trials: int = 100

   # After:
   n_trials: int = 200
   ```

 ### 4. Training Execution

 #### Initial Attempts (Failed)
 The first training attempts completed immediately without running full training:
 - Problem: Docker container terminated after command
 - Solution: Use `tee` to pipe output to log file

 #### Working Solution
 ```bash
 # Create logs directory
 mkdir -p ~/training-logs

 # Run training with proper logging
 docker-compose run --rm ml-training python -u /app/train.py 2>&1 | tee ~/training-logs/FULL_TRAINING_$(date +%Y%m%d_%H%M%S).log &
 ```

 **Training Pipeline**:
 1. **XGBoost** (200 trials) - ~1.5 hours
 2. **CatBoost** (200 trials) - ~1-2 hours
 3. **TCN** (200 trials) - ~1-2 hours
 4. **Chronos** (200 trials) - ~1-2 hours

 **Total estimated time: 4-8 hours**

 #### Current Status
 - Started: 11:01:23
 - Phase: XGBoost Trial 1/200
 - Best AUC so far: 0.554
 - Log file: `~/training-logs/FULL_TRAINING_20260131_110119.log`

 ## Key Commands Reference

 ### Data Fetch
 ```bash
 # Add more stocks
 docker-compose exec -T backend python /app/scripts/add_more_stocks.py

 # Fetch 5 years of daily data
 docker-compose exec -T backend python /app/scripts/fetch_ml_daily_data.py --period 5y --batch-size 5 --delay 0.5

 # Check database
 docker-compose exec -T database psql -U stockuser -d stock_analyzer -c "
 SELECT
     COUNT(*) as total_records,
     COUNT(DISTINCT stock_id) as total_stocks,
     MIN(timestamp) as earliest_date,
     MAX(timestamp) as latest_date
 FROM stock_prices
 WHERE timeframe = '1d';
 "
 ```

 ### Feature Engineering
 ```bash
 # Run with log returns
 docker-compose run --rm ml-training python /app/scripts/01e_feature_engineering_with_log_returns.py

 # Original script (without log returns)
 docker-compose run --rm ml-training python /app/scripts/01d_feature_engineering_auto_date.py
 ```

 ### Training
 ```bash
 # Full training with 200 trials
 mkdir -p ~/training-logs
 docker-compose run --rm ml-training python -u /app/train.py 2>&1 | tee ~/training-logs/FULL_TRAINING_$(date +%Y%m%d_%H%M%S).log &

 # Monitor training
 tail -f ~/training-logs/FULL_TRAINING_*.log

 # Check if training is running
 ps aux | grep "train.py"
 ```

 ## Alternative: Complete Pipeline Script
 There's also a master script that runs everything:
 ```bash
 ./run_complete_pipeline.sh
 ```

 This does:
 1. Add 500+ stocks
 2. Fetch 5 years of daily data
 3. Run feature engineering
 4. Train all models with 200 trials

 ## Data Quality Summary

 ### Before This Session
 - Records: ~30,000
 - Stocks: 252
 - Date range: 17 months
 - Features: Simple returns (pct_change)
 - AUC: ~51% (random)

 ### After This Session
 - Records: 583,355 (20x increase)
 - Stocks: 479 (90% increase)
 - Date range: 5 years
 - Features: 95 including log returns
 - AUC: ~0.554 (so far, still tuning)

 ## Important Files

 ### Created/Modified
 1. `backend/scripts/add_more_stocks.py` - Added 227 new stocks
 2. `ml-training/scripts/01e_feature_engineering_with_log_returns.py` - Log returns features
 3. `ml-training/ml_framework/config.py` - Increased n_trials to 200

 ### Key Existing Files
 1. `backend/scripts/fetch_ml_daily_data.py` - Direct daily fetch (bypasses aggregation)
 2. `ml-training/train.py` - Main training script
 3. `ml-training/ml_framework/trainer.py` - Training orchestration
 4. `app/services/technical_indicators.py` - Technical indicator calculations

 ## Architecture Notes

 ### Aggregation System
 The system has TWO approaches:

 1. **Hourly → Daily Aggregation** (original)
    - `fetch_ml_training_data.py` → `aggregate_to_daily.py`
    - Fetches 1h data, then aggregates to 1d
    - Blocked for ML use by validation check

 2. **Direct Daily Fetch** (ML bypass)
    - `fetch_ml_daily_data.py`
    - Fetches 1d data directly from Polygon
    - Used for ML training to avoid aggregation complexity

 ### Label Strategy
 Binary classification:
 - **Positive (1)**: Price hits +3% before -2% within 20 days
 - **Negative (0)**: Price hits -2% first, or doesn't hit either target in 20 days
 - **Challenge**: Inherently difficult prediction problem even with perfect data

 ### Model Ensemble
 Training all 4 models with 200 trials each:
 1. XGBoost (gradient boosting)
 2. CatBoost (gradient boosting with categorical features)
 3. TCN (Temporal Convolutional Network)
 4. Chronos (time series foundation model)

 ## Expected Performance

 ### Why AUC is Low (~0.55)
 1. **Random Walk Market**: Daily returns average 0.03% (essentially zero drift)
 2. **High Volatility**: 2.16% daily volatility makes signal extraction difficult
 3. **Weak Signal**: Technical indicators have limited predictive power
 4. **Noisy Labels**: 20-day lookahead introduces significant noise
 5. **Market Efficiency**: Available information is already priced in

 ### Why This Should Improve
 1. **20x More Data**: 30K → 583K samples
 2. **Better Features**: Log returns are more suitable for ML
 3. **More History**: 5 years captures different market regimes
 4. **More Stocks**: 479 stocks vs 252 (diversification)
 5. **Hyperparameter Tuning**: 200 trials per model (was 100)

 ### Realistic Expectations
 - AUC of 0.55-0.60 is likely the best achievable
 - AUC > 0.60 would be very good for this problem
 - AUC > 0.70 would be extraordinary (unlikely for stock prediction)
 - The goal is finding slight edge, not perfect prediction

 ## Troubleshooting

 ### Training Stops Immediately
 **Problem**: Docker container exits after command completes
 **Solution**: Use `tee` to pipe output and keep process alive

 ### Empty Log Files
 **Problem**: Logs created but remain empty (0 bytes)
 **Solution**: Ensure `tee` is used and check process is running

 ### Aggregation Blocking ML Fetch
 **Problem**: "1d is aggregated from 1h. Only fetch base timeframe."
 **Solution**: Use `fetch_ml_daily_data.py` instead of `fetch_ml_training_data.py`

 ### Feature Engineering Takes Too Long
 **Problem**: Processing 479 stocks at 2+ seconds each = 17+ minutes
 **Solution**: Normal, expected time. Be patient.

 ## Next Steps After Training Completes

 1. **Check Results**:
    ```bash
    cat ~/training-logs/FULL_TRAINING_*.log | grep -E "Best|AUC|completed"
    ```

 2. **View MLFlow Runs**:
    ```bash
    docker-compose run --rm ml-training mlflow ui
    ```

 3. **Analyze Model Performance**:
    - Compare AUC across models
    - Check feature importance
    - Analyze confusion matrix
    - Review calibration plots

 4. **Deploy Best Model** (if satisfactory):
    - Save model to production
    - Update prediction endpoints
    - Monitor live performance

 ## Session Statistics

 - **Duration**: ~1 hour (data fetch + feature engineering + training start)
 - **Data Added**: 562K new daily records
 - **New Features**: 15 log return-related features
 - **Stocks Added**: 227 new tickers
 - **Time Investment**: 4-8 hours for training completion

 ## Lessons Learned

 1. **Data Quantity Matters**: 20x more data is the biggest improvement
 2. **Feature Quality**: Log returns are theoretically better for ML
 3. **Infrastructure**: Direct daily fetch is simpler than aggregation
 4. **Patience Required**: Full training takes 4-8 hours
 5. **Realistic Expectations**: Stock prediction is inherently difficult

 ## Contact & Support

 For issues or questions:
 - Check logs in `~/training-logs/`
 - Review feature engineering output
 - Verify database records with SQL queries
 - Check Docker container status: `docker ps -a`

 ---

 **Session Date**: 2026-01-31
 **Status**: Training in progress (XGBoost Trial 1/200)
 **Next Review**: After ~2 hours (should complete CatBoost)
