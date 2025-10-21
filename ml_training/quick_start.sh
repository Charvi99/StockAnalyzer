#!/bin/bash

echo "============================================================"
echo "Chart Pattern Recognition - Quick Start"
echo "============================================================"
echo ""

# Step 1: Export training data
echo "[1/4] Exporting training data from API..."
curl -s "http://localhost:8000/api/v1/chart-patterns/export/training-data?padding_candles=5" > training_data.json
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to export training data. Is the backend running?"
    exit 1
fi
echo "     ✓ Done! Saved to training_data.json"
echo ""

# Step 2: Check if dependencies are installed
echo "[2/4] Checking dependencies..."
python3 -c "import tensorflow" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "     TensorFlow not found. Installing dependencies..."
    pip3 install -r requirements.txt
else
    echo "     ✓ Dependencies already installed"
fi
echo ""

# Step 3: Train models
echo "[3/4] Training LSTM and GRU models..."
echo "     This may take 5-10 minutes..."
python3 train_pattern_models.py
if [ $? -ne 0 ]; then
    echo "ERROR: Training failed"
    exit 1
fi
echo ""

# Step 4: Show results
echo "[4/4] Training complete!"
echo ""
echo "============================================================"
echo "RESULTS"
echo "============================================================"
echo ""
echo "Check the outputs folder for:"
echo "  - outputs/models/      (trained models)"
echo "  - outputs/plots/       (visualizations)"
echo "  - outputs/results_*.txt (performance summary)"
echo ""
echo "To make predictions:"
echo "  python3 predict.py --model lstm --pattern-id 123"
echo ""
