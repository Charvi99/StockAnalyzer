"""
Main Training Script

Orchestrates the entire ML training pipeline:
1. Load data
2. Train models (with optional tuning)
3. Create ensemble
4. Evaluate on test set
5. Save everything

Usage:
    python train.py --config configs/default.yaml
    python train.py --config configs/default.yaml --no-tuning
    python train.py --config configs/default.yaml --models xgboost,catboost
"""
import sys
import os
import argparse
from datetime import datetime

# Add backend to path
sys.path.insert(0, '/backend')

from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add ml-framework to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ml_framework.config import load_config
from ml_framework.trainer import ModelTrainer
from ml_framework.ensemble import Ensemble


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='StockAnalyzer ML Training Pipeline',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--config',
        type=str,
        default='configs/default.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--models',
        type=str,
        default=None,
        help='Comma-separated list of models to train (overrides config)'
    )
    parser.add_argument(
        '--no-tuning',
        action='store_true',
        help='Skip hyperparameter tuning'
    )
    parser.add_argument(
        '--tuning-trials',
        type=int,
        default=None,
        help='Number of tuning trials (overrides config)'
    )
    parser.add_argument(
        '--ensemble-method',
        type=str,
        default=None,
        choices=['majority_vote', 'weighted_average', 'stacking'],
        help='Ensemble method (overrides config)'
    )
    parser.add_argument(
        '--version',
        type=str,
        default=None,
        help='Model version (default: auto-generated)'
    )
    return parser.parse_args()


def main():
    """Main training pipeline"""
    args = parse_args()

    print("=" * 70)
    print(" " * 18)
    print("StockAnalyzer ML Training Pipeline")
    print(" " * 18)
    print("=" * 70)

    # Load configuration
    config = load_config(args.config)
    logger.info("✅ Configuration loaded")

    # Apply CLI overrides
    if args.models:
        models_list = args.models.split(',')
        # Only train specified models
        config.ensemble.models = models_list

    tune_models = not args.no_tuning
    if args.tuning_trials:
        config.training.n_trials = args.tuning_trials

    if args.ensemble_method:
        config.ensemble.method = args.ensemble_method

    # Initialize trainer
    trainer = ModelTrainer(config)
    logger.info("✅ Trainer initialized")

    # Load data
    features, labels = trainer.load_data()

    # Prepare data
    X_train, X_val, X_test, y_train, y_val, y_test = trainer.prepare_data(features, labels)

    # Train all models
    print("\n" + "=" * 70)
    print("TRAINING PHASE")
    print("=" * 70)

    print(f"\n📊 Training configuration:")
    print(f"   Models: {config.ensemble.models}")
    print(f"   Tuning: {'Enabled' if tune_models else 'Disabled'}")
    if tune_models:
        print(f"   Trials: {config.training.n_trials}")

    trainer.train_all_models(X_train, y_train, X_val, y_val, tune=tune_models)

    # Evaluate all models
    print("\n" + "=" * 70)
    print("EVALUATION PHASE")
    print("=" * 70)

    all_metrics = trainer.evaluate_all_models(X_test, y_test)

    # Print summary
    print("\n" + "=" * 70)
    print("MODEL COMPARISON")
    print("=" * 70)

    for model_name, metrics in all_metrics.items():
        print(f"\n{model_name.upper()}:")
        print(f"  Accuracy:  {metrics['accuracy']*100:.1f}%")
        print(f"  Precision: {metrics['precision']*100:.1f}%")
        print(f"  Recall:    {metrics['recall']*100:.1f}%")
        print(f"  AUC:       {metrics['auc']*100:.1f}%")

    # Create ensemble
    print("\n" + "=" * 70)
    print("ENSEMBLE CREATION")
    print("=" * 70)

    ensemble = Ensemble(trainer.models, method=config.ensemble.method)

    # Train meta-learner if using stacking
    if config.ensemble.method == "stacking":
        ensemble.train_meta_learner(X_val, y_val)
    elif config.ensemble.method == "weighted_average":
        ensemble.optimize_weights(X_val, y_val)

    # Evaluate ensemble
    ensemble_pred = ensemble.predict(X_test)
    ensemble_proba = ensemble.predict_proba(X_test)[:, 1]

    from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

    ensemble_metrics = {
        'accuracy': accuracy_score(y_test, ensemble_pred),
        'precision': precision_score(y_test, ensemble_pred, zero_division=0),
        'recall': recall_score(y_test, ensemble_pred, zero_division=0),
        'auc': roc_auc_score(y_test, ensemble_proba)
    }

    print(f"\nENSEMBLE PERFORMANCE:")
    print(f"  Accuracy:  {ensemble_metrics['accuracy']*100:.1f}%")
    print(f"  Precision: {ensemble_metrics['precision']*100:.1f}%")
    print(f"  Recall:    {ensemble_metrics['recall']*100:.1f}%")
    print(f"  AUC:       {ensemble_metrics['auc']*100:.1f}%")

    # Save everything
    print("\n" + "=" * 70)
    print("SAVE PHASE")
    print("=" * 70)

    version = args.version or f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    trainer.save_all_models(version)

    # Save ensemble
    ensemble_dir = config.data.models_dir / 'ensemble' / version
    ensemble_dir.mkdir(parents=True, exist_ok=True)
    ensemble.save(ensemble_dir)

    # Save ensemble to 'latest' as well
    ensemble_latest = config.data.models_dir / 'ensemble' / 'latest'
    ensemble_latest.mkdir(parents=True, exist_ok=True)
    ensemble.save(ensemble_latest)

    # Save configuration
    config.save(config.data.models_dir / f'config_{version}.yaml')

    print("\n" + "=" * 70)
    print("✅ TRAINING COMPLETE!")
    print("=" * 70)

    print(f"\nModels saved to: {config.data.models_dir}")
    print(f"Ensemble saved to: {ensemble_latest}")
    print(f"Config saved to: {config.data.models_dir / f'config_{version}.yaml'}")

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)

    print("""
1. Models are saved to: ./ml-models/ (shared with backend)
2. Backend can now load models for predictions
3. To use in backend:
   - Copy model files from /app/outputs/models/ to ./ml-models/
   - Update backend API to load models
   - Add /predict endpoint that uses ensemble

4. To improve performance:
   - Increase n_trials in config (currently 50)
   - Add more features (currently ~45)
   - Use GPU for TCN training
   - Add more training data
    """)


if __name__ == "__main__":
    main()
