#!/bin/bash
# Full ML Training Pipeline with 200 trials
# This will run feature engineering + full model training

set -e

echo "======================================================================"
echo "        StockAnalyzer ML Full Training Pipeline"
echo "        200 trials per model - All 4 models"
echo "======================================================================"
echo ""

cd /home/jakub/StockAnalyzer

# Step 1: Run feature engineering
echo "Step 1: Running Feature Engineering..."
docker-compose run --rm ml-training python /app/scripts/01d_feature_engineering_auto_date.py

echo ""
echo "Step 2: Starting Full Training (XGBoost, CatBoost, TCN, Chronos)..."
echo "Expected time: 4-8 hours depending on GPU"
echo ""

# Step 2: Run full training
mkdir -p ~/training-logs
docker-compose run --rm ml-training python /app/train.py 2>&1 | tee ~/training-logs/FULL_TRAINING_$(date +%Y%m%d_%H%M%S).log

echo ""
echo "======================================================================"
echo "        Training Complete!"
echo "======================================================================"
echo ""
echo "Results saved to:"
echo "  - Models: /home/jakub/StockAnalyzer/ml-training/outputs/models/"
echo "  - Logs: ~/training-logs/FULL_TRAINING_*.log"
echo "  - MLFlow: /home/jakub/StockAnalyzer/ml-training/mlruns/"
