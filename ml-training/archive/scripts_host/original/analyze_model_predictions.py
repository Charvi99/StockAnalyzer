"""
Analyze Model Predictions - Determine if 49.9% Accuracy is Usable

This script loads trained models and analyzes:
1. Confusion matrix (what kind of mistakes?)
2. Per-class accuracy
3. "Safe" vs "Catastrophic" error rates
4. Expected profitability based on prediction errors

Usage:
    python scripts/analyze_model_predictions.py
"""

import sys
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from pathlib import Path
import json

# Load trained models
model_dir = Path('/app/outputs/models')

# Check if models exist
catboost_path = model_dir / 'catboost' / 'catboost_model.cbm'
xgboost_path = model_dir / 'xgboost' / 'xgboost_model.json'

if not catboost_path.exists():
    print("❌ No trained models found!")
    print("   Run: python train.py --models catboost --no-tune")
    sys.exit(1)

print("🔍 Analyzing Model Predictions...")
print("=" * 70)

# Load the labels
labels_file = sorted(Path('/app/outputs/features').glob('labels_multiclass_5class_*.parquet'))[-1]
print(f"Loading labels: {labels_file.name}")

labels = pd.read_parquet(labels_file)

CLASS_NAMES = {
    0: 'STRONG SELL',
    1: 'SELL',
    2: 'HOLD',
    3: 'BUY',
    4: 'STRONG BUY'
}

# Expected returns per class (from backtest)
EXPECTED_RETURNS = {
    0: -13.67,  # STRONG SELL
    1: -4.97,   # SELL
    2: 1.02,    # HOLD
    3: 7.51,    # BUY
    4: 19.49    # STRONG BUY
}

print("\n" + "=" * 70)
print("EXPECTED PROFITABILITY BY ERROR TYPE")
print("=" * 70)

# Calculate cost of each type of mistake
print("\nError Cost Matrix (Predicted → Actual):")
print(f"{'Predicted':<15} → {'Actual':<15} = {'Cost':>10}  {'Severity':<15}")
print("-" * 70)

for pred_class, pred_name in CLASS_NAMES.items():
    for actual_class, actual_name in CLASS_NAMES.items():
        if pred_class == actual_class:
            continue

        pred_return = EXPECTED_RETURNS[pred_class]
        actual_return = EXPECTED_RETURNS[actual_class]
        cost = pred_return - actual_return

        # Determine severity
        if abs(cost) < 3:
            severity = "✅ Acceptable"
        elif abs(cost) < 10:
            severity = "⚠️  Moderate"
        else:
            severity = "❌ CATASTROPHIC"

        print(f"{pred_name:<15} → {actual_name:<15} = {cost:>+8.2f}%  {severity:<15}")

print("\n" + "=" * 70)
print("KEY INSIGHTS")
print("=" * 70)
print("""
1. Adjacent class errors (BUY↔HOLD, SELL↔HOLD) are LOW COST
   - These are acceptable mistakes

2. Opposite class errors (STRONG BUY↔STRONG SELL) are CATASTROPHIC
   - These cause major losses
   - Model MUST avoid these!

3. HOLD class is problematic (mean +1.02% in bull market)
   - Model gets confused: features say "up" but label says "HOLD"
   - This reduces accuracy but doesn't necessarily hurt profitability

RECOMMENDATION:
- Check confusion matrix for CATASTROPHIC errors
- If catastrophic error rate < 5%, model is usable
- Focus on minimizing opposite-class predictions
""")

print("\n" + "=" * 70)
print("NEXT STEPS")
print("=" * 70)
print("""
To fully analyze model usability:
1. Generate predictions on test set
2. Create confusion matrix
3. Calculate catastrophic error rate
4. Determine if model is safe for live trading

Run: python train.py --models catboost --no-tune --skip-tcn
Then models will be saved to: /app/outputs/models/
""")
