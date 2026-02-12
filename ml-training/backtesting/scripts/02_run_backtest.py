"""
Run a backtest with a single strategy.

Usage:
    python scripts/02_run_backtest.py --strategy buy_and_hold
    python scripts/02_run_backtest.py --strategy binary_ml --model-path /app/outputs/models/catboost/v1.0.0-binary/model.cbm
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add backtesting directory to path
backtest_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backtest_dir))

# Now imports should work
from config import BacktestConfig
from core.backtester import Backtester
from strategies.buy_and_hold import BuyAndHoldStrategy
from strategies.sma_crossover import SMACrossoverStrategy
from strategies.macd_strategy import MACDStrategy
from strategies.random_strategy import RandomStrategy

# Import ML strategies if available
try:
    from strategies.binary_ml_strategy import BinaryMLStrategy
    BINARY_ML_AVAILABLE = True
except ImportError:
    BINARY_ML_AVAILABLE = False

try:
    from strategies.tabnet_ml_strategy import TabNetMLStrategy
    TABNET_AVAILABLE = True
except ImportError:
    TABNET_AVAILABLE = False


# Strategy registry
STRATEGIES = {
    'buy_and_hold': BuyAndHoldStrategy,
    'sma_crossover': SMACrossoverStrategy,
    'macd': MACDStrategy,
    'random': RandomStrategy,
}

if BINARY_ML_AVAILABLE:
    STRATEGIES['binary_ml'] = BinaryMLStrategy
if TABNET_AVAILABLE:
    STRATEGIES['tabnet_ml'] = TabNetMLStrategy


def parse_args():
    parser = argparse.ArgumentParser(
        description='Run backtest with single strategy',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Buy & Hold
  python scripts/02_run_backtest.py --strategy buy_and_hold

  # SMA Crossover
  python scripts/02_run_backtest.py --strategy sma_crossover --fast 20 --slow 50

  # Binary ML (CatBoost/XGBoost)
  python scripts/02_run_backtest.py --strategy binary_ml \\
      --model-path /app/outputs/models/catboost/v1.0.0-binary/model.cbm \\
      --confidence 0.6

  # TabNet ML
  python scripts/02_run_backtest.py --strategy tabnet_ml \\
      --model-path /app/outputs/models/tabnet/latest \\
      --confidence 0.5

  # Random
  python scripts/02_run_backtest.py --strategy random --probability 0.02
        """
    )
    parser.add_argument(
        '--strategy',
        type=str,
        default='buy_and_hold',
        choices=list(STRATEGIES.keys()),
        help='Strategy to test'
    )

    # ML-specific arguments
    parser.add_argument(
        '--model-path',
        type=str,
        default=None,
        help='Path to trained ML model (for binary_ml strategy)'
    )
    parser.add_argument(
        '--model-type',
        type=str,
        default='catboost',
        choices=['catboost', 'xgboost', 'tabnet'],
        help='Model type (default: catboost)'
    )
    parser.add_argument(
        '--confidence',
        type=float,
        default=0.6,
        help='Confidence threshold for ML strategy (default: 0.6)'
    )

    # SMA Crossover arguments
    parser.add_argument(
        '--fast',
        type=int,
        default=20,
        help='Fast SMA period (default: 20)'
    )
    parser.add_argument(
        '--slow',
        type=int,
        default=50,
        help='Slow SMA period (default: 50)'
    )

    # Random strategy arguments
    parser.add_argument(
        '--probability',
        type=float,
        default=0.02,
        help='Buy probability for random strategy (default: 0.02)'
    )
    parser.add_argument(
        '--hold-days',
        type=int,
        default=20,
        help='Hold days for random strategy (default: 20)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        help='Test start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='Test end date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--initial-cash',
        type=float,
        default=100_000,
        help='Initial portfolio value'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory (default: auto-generated)'
    )

    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 70)
    print(" " * 20)
    print("BACKTESTING ENGINE")
    print(" " * 20)
    print("=" * 70)

    # Create configuration
    config = BacktestConfig()

    # Override defaults if provided
    if args.start_date:
        config.period.test_start = args.start_date
    if args.end_date:
        config.period.test_end = args.end_date
    if args.initial_cash:
        config.initial_cash = args.initial_cash

    print(f"\nConfiguration:")
    print(f"  Period: {config.period.test_start} to {config.period.test_end}")
    print(f"  Initial Cash: ${config.initial_cash:,.2f}")
    print(f"  Strategy: {args.strategy}")

    # Load data
    print("\n" + "=" * 70)
    print("LOADING DATA")
    print("=" * 70)

    from data import load_backtest_data

    data = load_backtest_data(config)

    # Create strategy
    print("\n" + "=" * 70)
    print("INITIALIZING STRATEGY")
    print("=" * 70)

    # Create strategy based on type
    if args.strategy == 'buy_and_hold':
        strategy = BuyAndHoldStrategy(config)

    elif args.strategy == 'sma_crossover':
        strategy = SMACrossoverStrategy(config, fast_period=args.fast, slow_period=args.slow)

    elif args.strategy == 'macd':
        strategy = MACDStrategy(config)

    elif args.strategy == 'random':
        strategy = RandomStrategy(config, buy_probability=args.probability, hold_days=args.hold_days)

    elif args.strategy == 'binary_ml':
        if args.model_path is None:
            # Try to find default model
            model_dir = Path(config.models_dir) / 'catboost' / 'v1.0.0-binary'
            model_file = model_dir / 'model.cbm'
            if not model_file.exists():
                raise ValueError(f"No model found at {model_file}. Please specify --model-path")
            args.model_path = str(model_file)

        strategy = BinaryMLStrategy(
            config,
            model_path=args.model_path,
            model_type=args.model_type,
            confidence_threshold=args.confidence
        )

    elif args.strategy == 'tabnet_ml':
        if args.model_path is None:
            # Try to find default TabNet model
            model_dir = Path(config.models_dir) / 'tabnet' / 'latest'
            if not model_dir.exists():
                raise ValueError(f"No TabNet model found at {model_dir}. Please specify --model-path")
            args.model_path = str(model_dir)

        strategy = TabNetMLStrategy(
            config,
            model_path=args.model_path,
            confidence_threshold=args.confidence
        )

    else:
        raise ValueError(f"Unknown strategy: {args.strategy}")

    # Run backtest
    print("\n" + "=" * 70)
    print("RUNNING BACKTEST")
    print("=" * 70)

    backtester = Backtester(config)
    result = backtester.run(strategy, data)

    # Print results
    print(result.get_summary())

    # Save results
    print("\n" + "=" * 70)
    print("SAVING RESULTS")
    print("=" * 70)

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(config.output_dir) / f"{args.strategy}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    backtester.save_results(result, output_dir)

    print("\n" + "=" * 70)
    print("✅ BACKTEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
