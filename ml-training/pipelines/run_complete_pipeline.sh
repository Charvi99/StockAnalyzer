#!/bin/bash
# Complete ML Training Pipeline
# 1. Add stocks (500+ total)
# 2. Fetch 5 years of daily data
# 3. Run feature engineering
# 4. Train all models with 200 trials

set -e

echo "======================================================================"
echo "        StockAnalyzer ML - Complete Training Pipeline"
echo "        500+ stocks, 5 years data, 200 trials per model"
echo "======================================================================"
echo ""

cd /home/jakub/StockAnalyzer

# Step 1: Add more stocks
echo "Step 1: Adding more stocks (500+ total)..."
docker-compose exec -T backend python /app/scripts/add_more_stocks.py

echo ""
echo "Step 2: Fetching 5 years of daily data (direct from Polygon)..."
echo "Expected time: ~50-80 minutes for 500+ stocks"
echo ""

# Step 2: Fetch 5 years of daily data directly
mkdir -p ~/training-logs
docker-compose exec -T backend python /app/scripts/fetch_ml_daily_data.py --period 5y --batch-size 5 --delay 0.5 | tee ~/training-logs/FETCH_DAILY_$(date +%Y%m%d_%H%M%S).log

echo ""
echo "Step 3: Running Feature Engineering..."
echo ""

# Step 3: Run feature engineering
docker-compose run --rm ml-training python /app/scripts/01d_feature_engineering_auto_date.py | tee ~/training-logs/FEATURE_ENGINEERING_$(date +%Y%m%d_%H%M%S).log

echo ""
echo "Step 4: Starting Full Training (XGBoost, CatBoost, TCN, Chronos)..."
echo "Expected time: 4-8 hours depending on GPU"
echo ""

# Step 4: Run full training
docker-compose run --rm ml-training python /app/train.py 2>&1 | tee ~/training-logs/FULL_TRAINING_$(date +%Y%m%d_%H%M%S).log

echo ""
echo "======================================================================"
echo "        Training Complete!"
echo "======================================================================"
echo ""
echo "Results saved to:"
echo "  - Models: /home/jakub/StockAnalyzer/ml-training/outputs/models/"
echo "  - Logs: ~/training-logs/"
echo "  - MLFlow: /home/jakub/StockAnalyzer/ml-training/mlruns/"
