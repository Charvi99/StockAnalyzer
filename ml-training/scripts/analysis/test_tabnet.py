#!/usr/bin/env python
"""
Quick test script for TabNet integration

Tests:
1. Check if pytorch-tabnet is installed
2. Test TabNet with 5 trials on 3Class dataset
3. Compare with XGBoost/CatBoost baseline

Usage:
    python test_tabnet.py

Expected:
    - TabNet AUC: 55-60% (if working correctly)
    - XGBoost/CatBoost AUC: 55-57% (baseline)
"""
import sys
from pathlib import Path

# Setup paths
ml_framework_path = Path(__file__).parent / 'ml_framework'
sys.path.insert(0, str(ml_framework_path))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_tabnet():
    """Check if TabNet is available"""
    try:
        from pytorch_tabnet.tab_model import TabNetClassifier
        logger.info("✅ pytorch-tabnet is installed")
        return True
    except ImportError:
        logger.error("❌ pytorch-tabnet is NOT installed")
        logger.error("Install with: pip install pytorch-tabnet")
        return False

def test_import():
    """Test TabNet model import"""
    try:
        from ml_framework.models import TabNetModel, check_tabnet_available
        logger.info("✅ TabNetModel imported successfully")
        return check_tabnet_available()
    except Exception as e:
        logger.error(f"❌ Failed to import TabNetModel: {e}")
        return False

def run_quick_test():
    """Run TabNet with 5 trials"""
    try:
        from ml_framework.config import Config
        from ml_framework.trainer import ModelTrainer

        logger.info("=" * 60)
        logger.info("Quick TabNet Test (5 trials)")
        logger.info("=" * 60)

        # Create config
        config = Config()

        # Override for quick test
        config.training.n_trials = 5
        config.data.dataset_folder = None  # Auto-detect latest
        config.data.label_type = "3class"

        # Create trainer
        trainer = ModelTrainer(config)

        # Load data
        features, labels = trainer.load_data()
        logger.info(f"✅ Loaded {len(features)} samples")

        # Prepare data
        data = trainer.prepare_data(features, labels)
        X_train, X_val, X_test, y_train, y_val, y_test = data['regular']

        # Train TabNet
        logger.info("\n" + "=" * 60)
        logger.info("Training TabNet (5 trials)")
        logger.info("=" * 60)

        tabnet_model = trainer.train_model(
            'tabnet',
            X_train, y_train, X_val, y_val,
            tune=True
        )

        if tabnet_model is None:
            logger.error("❌ TabNet training failed")
            return False

        # Evaluate on test set
        test_metrics = tabnet_model.evaluate(X_test, y_test)

        logger.info("\n" + "=" * 60)
        logger.info("TabNet Test Results")
        logger.info("=" * 60)
        logger.info(f"Test AUC:       {test_metrics['auc']:.4f}")
        logger.info(f"Test Accuracy:  {test_metrics['accuracy']:.4f}")
        logger.info(f"Test Precision: {test_metrics['precision']:.4f}")
        logger.info(f"Test Recall:    {test_metrics['recall']:.4f}")

        # Compare with baseline (quick XGBoost test)
        logger.info("\n" + "=" * 60)
        logger.info("Baseline Comparison (XGBoost - 5 trials)")
        logger.info("=" * 60)

        xgb_model = trainer.train_model(
            'xgboost',
            X_train, y_train, X_val, y_val,
            tune=True
        )

        if xgb_model:
            xgb_metrics = xgb_model.evaluate(X_test, y_test)
            logger.info(f"XGBoost Test AUC:       {xgb_metrics['auc']:.4f}")
            logger.info(f"XGBoost Test Accuracy:  {xgb_metrics['accuracy']:.4f}")

            # Compare
            logger.info("\n" + "=" * 60)
            logger.info("Comparison")
            logger.info("=" * 60)
            auc_diff = test_metrics['auc'] - xgb_metrics['auc']
            if auc_diff > 0:
                logger.info(f"✅ TabNet beats XGBoost by {auc_diff:.2%} AUC")
            elif auc_diff < 0:
                logger.info(f"⚠️  XGBoost beats TabNet by {-auc_diff:.2%} AUC")
            else:
                logger.info(f"🟰 Tie: Both at {test_metrics['auc']:.2%} AUC")

        logger.info("\n" + "=" * 60)
        logger.info("✅ TabNet test complete!")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test flow"""
    print("\n" + "=" * 60)
    print("TabNet Integration Test")
    print("=" * 60)

    # Step 1: Check installation
    print("\n[1/3] Checking pytorch-tabnet installation...")
    if not check_tabnet():
        print("\n❌ Please install pytorch-tabnet first:")
        print("   pip install pytorch-tabnet")
        print("   OR")
        print("   docker-compose exec ml-training pip install pytorch-tabnet")
        return False

    # Step 2: Test imports
    print("\n[2/3] Testing TabNetModel import...")
    if not test_import():
        return False

    # Step 3: Run quick training test
    print("\n[3/3] Running quick training test (5 trials)...")
    success = run_quick_test()

    if success:
        print("\n" + "=" * 60)
        print("✅ All tests passed! TabNet is ready to use.")
        print("=" * 60)
        print("\nTo train with more trials:")
        print("  python train.py --models tabnet --trials 30")
        print("\nTo train all models including TabNet:")
        print("  python train.py --models xgboost catboost tabnet --trials 30")
    else:
        print("\n" + "=" * 60)
        print("❌ Tests failed. Please check the errors above.")
        print("=" * 60)

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
