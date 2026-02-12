#!/usr/bin/env python
"""
Quick test script to verify resource manager and bug fixes

This script tests:
1. Hardware detection
2. Adaptive parameter calculation
3. Memory usage estimation
4. TCN data preparation with chunking
"""
import sys
sys.path.insert(0, '/backend')

import logging
import numpy as np
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("=" * 70)
print(" " * 15)
print("ML Training Bug Fix Verification")
print(" " * 15)
print("=" * 70)

# Test 1: Resource Manager
print("\n" + "=" * 70)
print("TEST 1: Resource Manager")
print("=" * 70)

from ml_framework.resource_manager import get_resource_manager

rm = get_resource_manager()

# Test adaptive parameters
print("\n📊 Adaptive Parameters:")
print(f"   TCN batch size: {rm.get_safe_batch_size('tcn')}")
print(f"   TCN max trials: {rm.get_max_trials('tcn', 100)}")
print(f"   XGBoost max trials: {rm.get_max_trials('xgboost', 100)}")
print(f"   Safe sequence length: {rm.get_safe_sequence_length(60)}")
print(f"   TCN channels: {rm.get_tcn_num_channels()}")

# Test memory estimation
print("\n💾 Memory Estimation (100K samples, 95 features):")
usage = rm.estimate_memory_usage(100000, 95)
print(f"   DataFrame: {usage['dataframe_gb']:.2f}GB")
print(f"   Sequences: {usage['sequence_gb']:.2f}GB")
print(f"   Total: {usage['total_gb']:.2f}GB")
print(f"   Available RAM: {usage['available_gb']:.2f}GB")
if usage['gpu_available_gb'] > 0:
    print(f"   Available GPU: {usage['gpu_available_gb']:.2f}GB")

# Test 2: TCN Data Preparation (with chunking)
print("\n" + "=" * 70)
print("TEST 2: TCN Data Preparation (Chunking)")
print("=" * 70)

from ml_framework.models.tcn_model import TCNModel
from ml_framework.config import TCNConfig

# Create synthetic data
print("\n📝 Creating synthetic data (10K samples, 95 features)...")
X_dummy = pd.DataFrame(np.random.randn(10000, 95))
y_dummy = np.random.randint(0, 2, 10000)

# Create TCN model
config = TCNConfig()
model = TCNModel(config)

print("🔧 Testing prepare_data() with chunking...")
try:
    dataloader = model.prepare_data(X_dummy, y_dummy)
    print(f"✅ Success! Created dataloader with {len(dataloader)} batches")

    # Check first batch
    for X_batch, y_batch in dataloader:
        print(f"   First batch shape: {X_batch.shape}")
        break

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Memory Check
print("\n" + "=" * 70)
print("TEST 3: Memory Check Before Training")
print("=" * 70)

n_samples = 100000
n_features = 95

print(f"\nChecking memory for {n_samples} samples, {n_features} features...")
if rm.check_memory_before_training('tcn', n_samples, n_features):
    print("✅ Memory check passed!")
else:
    print("❌ Memory check failed - not enough memory")

# Test 4: Current Memory Usage
print("\n" + "=" * 70)
print("TEST 4: Current Memory Usage")
print("=" * 70)

current = rm.get_current_memory_usage()
print(f"\n📊 Current Usage:")
print(f"   RAM: {current['ram_used_gb']:.2f}GB / {current['ram_available_gb']:.2f}GB ({current['ram_percent']:.1f}%)")
if 'gpu_used_gb' in current:
    print(f"   GPU: {current['gpu_used_gb']:.2f}GB used / {current['gpu_free_gb']:.2f}GB free")

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

print("""
✅ If all tests passed, the bug fixes are working correctly!

Next steps:
1. Run a quick training test: python train.py --trials 5
2. If successful, run full training: python train.py
3. Monitor logs for any issues

Expected training time on your hardware:
- XGBoost: ~15 min (100 trials)
- CatBoost: ~20 min (100 trials)
- TCN: ~30 min (15-30 trials, adaptive)
- Chronos: ~10 min
- Total: ~1.25 hours
""")

print("=" * 70)
print("✅ Test Complete!")
print("=" * 70)
