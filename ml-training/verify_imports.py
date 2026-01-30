"""
Quick test to verify all ML framework imports work
"""

import sys
sys.path.insert(0, '/backend')

print("Testing imports...")

try:
    print("1. Testing config.py...")
    from ml_framework.config import Config, DEFAULT_CONFIG
    print("   ✅ config.py OK")

    print("2. Testing base.py...")
    from ml_framework.base import BaseModel
    print("   ✅ base.py OK")

    print("3. Testing tuner.py...")
    from ml_framework.tuner import HyperparameterTuner
    print("   ✅ tuner.py OK")

    print("4. Testing trainer.py...")
    from ml_framework.trainer import ModelTrainer
    print("   ✅ trainer.py OK")

    print("5. Testing ensemble.py...")
    from ml_framework.ensemble import Ensemble
    print("   ✅ ensemble.py OK")

    print("6. Testing XGBoostModel...")
    from ml_framework.models import XGBoostModel
    print("   ✅ XGBoostModel OK")

    print("7. Testing CatBoostModel...")
    from ml_framework.models import CatBoostModel
    print("   ✅ CatBoostModel OK")

    print("8. Testing TCNModel...")
    from ml_framework.models import TCNModel
    print("   ✅ TCNModel OK")

    print("\n" + "="*60)
    print("✅ ALL IMPORTS SUCCESSFUL!")
    print("="*60)
    print("\nYou are ready to start training!")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
