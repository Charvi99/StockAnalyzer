"""
Quick test to verify Chronos model can be imported
"""

import sys
sys.path.insert(0, '/backend')

print("Testing Chronos import...")

try:
    from ml_framework.models import ChronosModel
    print("✅ ChronosModel imported successfully")

    from ml_framework.config import ChronosConfig
    print("✅ ChronosConfig imported successfully")

    # Create config
    config = ChronosConfig()
    print(f"✅ Config created: model={config.model_name}, device={config.device}")

    print("\n" + "="*60)
    print("✅ CHRONOS READY FOR TRAINING!")
    print("="*60)
    print("\nNext step: cd /app && python train.py")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
