"""
Main Training Script

Orchestrates the entire ML training pipeline:
1. Load data
2. Train models (with optional tuning)
3. Create ensemble
4. Evaluate on test set
5. Save everything

Usage:
    python train.py                          # Train all models
    python train.py --models xgboost catboost # Train only specific models
    python train.py --no-tune                # Skip hyperparameter tuning
    python train.py --models tcn --no-tune   # Quick train TCN without tuning
"""
import sys
import argparse
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
sys.path.insert(0, '/app/ml-framework')

from ml_framework.config import Config, DEFAULT_CONFIG
from ml_framework.trainer import ModelTrainer
from ml_framework.ensemble import Ensemble
from ml_framework.resource_manager import get_resource_manager

# Available models
AVAILABLE_MODELS = ['xgboost', 'catboost', 'tcn', 'chronos']


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Train StockAnalyzer ML models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train.py                          # Train all models
  python train.py --models xgboost catboost # Train only specific models
  python train.py --no-tune                # Skip hyperparameter tuning
  python train.py --models tcn --no-tune   # Quick train TCN without tuning
        """
    )

    parser.add_argument(
        '--models',
        nargs='+',
        choices=AVAILABLE_MODELS,
        default=None,
        help='Models to train (default: all models). Choose from: %(choices)s'
    )

    parser.add_argument(
        '--no-tune',
        action='store_true',
        help='Skip hyperparameter tuning (use default params from config)'
    )

    parser.add_argument(
        '--trials',
        type=int,
        default=None,
        help='Number of Optuna trials (overrides config default)'
    )

    return parser.parse_args()


def main():
    """Main training pipeline"""

    # Parse command line arguments
    args = parse_args()

    print("=" * 70)
    print(" " * 18)
    print("StockAnalyzer ML Training Pipeline")
    print(" " * 18)
    print("=" * 70)

    # Hardware Detection & Adaptive Configuration
    print("\n" + "=" * 70)
    print("HARDWARE DETECTION")
    print("=" * 70)

    resource_manager = get_resource_manager()

    # Load configuration (will be adapted based on hardware)
    config = DEFAULT_CONFIG

    # Override config if custom trials specified
    if args.trials:
        config.training.n_trials = args.trials
        logger.info(f"Using {args.trials} trials for all models")

    # Determine which models to train
    models_to_train = args.models if args.models else AVAILABLE_MODELS

    # Adaptive Configuration (adjust based on hardware)
    print("\n" + "=" * 70)
    print("ADAPTIVE CONFIGURATION")
    print("=" * 70)

    if not args.no_tune:
        # Adjust trials based on hardware if not manually specified
        if args.trials is None:
            original_trials = config.training.n_trials
            for model in models_to_train:
                adaptive_trials = resource_manager.get_max_trials(model, original_trials)
                if model == 'xgboost':
                    config.xgboost.n_estimators = resource_manager.get_safe_n_estimators('xgboost')
                elif model == 'catboost':
                    config.catboost.iterations = resource_manager.get_safe_n_estimators('catboost')
                elif model == 'tcn':
                    config.tcn.batch_size = resource_manager.get_safe_batch_size('tcn', config.tcn.batch_size)
                    config.tcn.num_channels = resource_manager.get_tcn_num_channels(config.tcn.num_channels)
                    print(f"TCN: num_channels={config.tcn.num_channels}, batch_size={config.tcn.batch_size}")

    print(f"\nModels to train: {', '.join(models_to_train)}")
    print(f"Hyperparameter tuning: {'Off' if args.no_tune else 'On'}")
    print(f"Trials: {args.trials if args.trials else config.training.n_trials}")
    print()

    # Override config models list
    config.ensemble.models = models_to_train

    logger.info("✅ Configuration loaded")

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

    trainer.train_all_models(X_train, y_train, X_val, y_val, tune=not args.no_tune)

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

    # Create ensemble (only if multiple models were trained)
    print("\n" + "=" * 70)
    if len(trainer.models) > 1:
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

        save_ensemble = True
    else:
        print("ENSEMBLE CREATION SKIPPED")
        print("=" * 70)
        print("Only one model trained - skipping ensemble creation")
        save_ensemble = False

    # Save everything
    print("\n" + "=" * 70)
    print("SAVE PHASE")
    print("=" * 70)

    version = "v1.0.0"
    trainer.save_all_models(version)

    # Save ensemble (only if created)
    if save_ensemble:
        ensemble_dir = config.data.models_dir / 'ensemble' / version
        ensemble_dir.mkdir(parents=True, exist_ok=True)
        ensemble.save(ensemble_dir)

        # Save ensemble to 'latest' as well
        ensemble_latest = config.data.models_dir / 'ensemble' / 'latest'
        ensemble_latest.mkdir(parents=True, exist_ok=True)
        ensemble.save(ensemble_latest)
        print(f"Ensemble saved to: {ensemble_latest}")
    else:
        print("Ensemble not saved (only one model trained)")

    # Save configuration
    config.save(config.data.models_dir / f'config_{version}.yaml')

    print("\n" + "=" * 70)
    print("✅ TRAINING COMPLETE!")
    print("=" * 70)

    print(f"\nModels saved to: {config.data.models_dir}")
    print(f"Config saved to: {config.data.models_dir / f'config_{version}.yaml'}")

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)

    print("""
Usage examples:
  python train.py                          # Train all models
  python train.py --models xgboost catboost # Train only specific models
  python train.py --no-tune                # Skip hyperparameter tuning
  python train.py --models tcn --no-tune   # Quick train TCN without tuning
  python train.py --trials 50              # Use 50 trials instead of default

1. Models are saved to: ./ml-models/ (shared with backend)
2. Backend can now load models for predictions
3. To use in backend:
   - Copy model files from /app/outputs/models/ to ./ml-models/
   - Update backend API to load models
   - Add /predict endpoint that uses ensemble

4. To improve performance:
   - Increase n_trials with --trials flag
   - Add more features (currently ~45)
   - Use GPU for TCN training
   - Add more training data
    """)


if __name__ == "__main__":
    main()
