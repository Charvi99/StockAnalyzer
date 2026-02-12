#!/bin/bash
#
# Stock Analyzer - Full ML Pipeline Refresh (5 Years Data)
#
# This script orchestrates the complete data refresh and ML training pipeline:
# 1. Add 500-600 diverse stocks with sectors
# 2. Fetch 5 years of historical data (paid Polygon.io)
# 3. Engineer features with 28 high-quality features
# 4. Train ML models
#
# Expected time: 2-4 hours (with paid Polygon.io API)
# Expected improvement: +6-11% AUC (56.8% → 63-68%)
#
# Usage:
#   docker-compose exec backend bash /app/scripts/run_full_ml_pipeline_5years.sh
#
# Or run from ml-training container:
#   bash /app/run_full_ml_pipeline_5years.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_header() {
    echo -e "${BLUE}"
    echo "================================================================================"
    echo " " "$1"
    echo "================================================================================"
    echo -e "${NC}"
}

print_step() {
    echo -e "${GREEN}"
    echo "▶ $1"
    echo -e "${NC}"
}

print_warning() {
    echo -e "${YELLOW}"
    echo "⚠️  $1"
    echo -e "${NC}"
}

print_error() {
    echo -e "${RED}"
    echo "❌ $1"
    echo -e "${NC}"
}

# ============================================================================
# STEP 0: Pre-flight checks
# ============================================================================

print_header "Stock Analyzer - Full ML Pipeline Refresh (5 Years)"

echo ""
echo "This will:"
echo "  1. Add 500-600 diverse stocks (S&P 500 + NASDAQ 100 + ETFs)"
echo "  2. Fetch 5 years of historical data (2019-2026)"
echo "  3. Engineer features with 28 high-quality features"
echo "  4. Train ML models (XGBoost, CatBoost, TCN, Chronos)"
echo ""
echo "Expected time: 2-4 hours"
echo "Expected improvement: +6-11% AUC (56.8% → 63-68%)"
echo ""

read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Check for POLYGON_API_KEY
if [ -z "$POLYGON_API_KEY" ]; then
    print_error "POLYGON_API_KEY environment variable not set!"
    echo "Please set: export POLYGON_API_KEY='your_key_here'"
    exit 1
fi

print_step "✅ Pre-flight checks passed"

# ============================================================================
# STEP 1: Add diverse stocks
# ============================================================================

print_header "STEP 1: Adding 500-600 Diverse Stocks"

cd /backend

python - <<'EOF'
import sys
sys.path.insert(0, '/backend')

# Check if add_diverse_stocks script exists
from pathlib import Path
script = Path('/backend/scripts/add_diverse_stocks_5years.py')

if not script.exists():
    print("❌ Script not found: add_diverse_stocks_5years.py")
    sys.exit(1)

# Run the script
import subprocess
result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    print_step "✅ Stocks added successfully"
else
    print_error "Failed to add stocks"
    exit 1
fi

# ============================================================================
# STEP 2: Fetch 5 years of historical data
# ============================================================================

print_header "STEP 2: Fetching 5 Years of Historical Data"

print_warning "This will take 1-2 hours (paid Polygon.io API)"
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted. You can run fetch_historical_data_5years.py manually later."
    exit 0
fi

python - <<'EOF'
import sys
sys.path.insert(0, '/backend')

from pathlib import Path
script = Path('/backend/scripts/fetch_historical_data_5years.py')

if not script.exists():
    print("❌ Script not found: fetch_historical_data_5years.py")
    sys.exit(1)

import subprocess
result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    print_step "✅ Historical data fetched successfully"
else
    print_error "Failed to fetch historical data"
    exit 1
fi

# ============================================================================
# STEP 3: Feature engineering (28 features)
# ============================================================================

print_header "STEP 3: Feature Engineering (28 High-Quality Features)"

cd /app  # ml-training directory

python scripts/01h_feature_engineering_28features.py

if [ $? -eq 0 ]; then
    print_step "✅ Feature engineering completed"
else
    print_error "Feature engineering failed"
    exit 1
fi

# ============================================================================
# STEP 4: Train ML models
# ============================================================================

print_header "STEP 4: Training ML Models"

print_warning "Training will take 30-60 minutes depending on your GPU"
echo ""
echo "Options:"
echo "  1. Train all models with tuning (recommended)"
echo "  2. Train all models WITHOUT tuning (faster, less optimal)"
echo "  3. Train only XGBoost + CatBoost (skip deep learning models)"
echo ""
read -p "Select option (1-3): " -n 1 -r
echo

case $REPLY in
    1)
        print_step "Training all models with hyperparameter tuning..."
        python train.py
        ;;
    2)
        print_step "Training all models WITHOUT tuning..."
        python train.py --no-tune
        ;;
    3)
        print_step "Training XGBoost + CatBoost only..."
        python train.py --models xgboost catboost
        ;;
    *)
        print_error "Invalid option. Training all models with tuning..."
        python train.py
        ;;
esac

if [ $? -eq 0 ]; then
    print_step "✅ Model training completed"
else
    print_error "Model training failed"
    exit 1
fi

# ============================================================================
# SUMMARY
# ============================================================================

print_header "✅ PIPELINE COMPLETE!"

echo ""
echo "Summary:"
echo "  ✓ Added 500-600 diverse stocks with sectors"
echo "  ✓ Fetched 5 years of historical data"
echo "  ✓ Created features with 28 high-quality features"
echo "  ✓ Trained ML models"
echo ""
echo "Expected improvements:"
echo "  • More samples: 130K → 250K+ (+92%)"
echo "  • More regimes: 1 → 5 market regimes"
echo "  • Fewer features: 76 → 28 (-63%)"
echo "  • Expected AUC: 56.8% → 63-68% (+6-11%)"
echo ""
echo "Next steps:"
echo "  1. Review model metrics in: /app/outputs/models/"
echo "  2. Test ensemble predictions"
echo "  3. Deploy best model to backend"
echo ""
echo "Files created:"
echo "  • Features: /app/outputs/features/features_*.parquet"
echo "  • Labels:   /app/outputs/features/labels_*.parquet"
echo "  • Models:   /app/outputs/models/*/latest/"
echo ""
echo "================================================================================"
