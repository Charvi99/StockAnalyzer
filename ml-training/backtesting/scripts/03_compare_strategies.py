"""
Compare multiple strategies side-by-side.

Usage:
    python scripts/03_compare_strategies.py --strategies buy_and_hold sma_crossover binary_ml
"""
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import pandas as pd

# Add backtesting directory to path
backtest_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backtest_dir))

# Imports
from config import BacktestConfig
from core.backtester import Backtester
from strategies.buy_and_hold import BuyAndHoldStrategy
from strategies.sma_crossover import SMACrossoverStrategy
from strategies.macd_strategy import MACDStrategy
from strategies.random_strategy import RandomStrategy

# Import ML strategy if available
try:
    from strategies.binary_ml_strategy import BinaryMLStrategy
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


def parse_args():
    parser = argparse.ArgumentParser(
        description='Compare multiple strategies',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare baselines
  python scripts/03_compare_strategies.py --strategies buy_and_hold sma_crossover macd random

  # Compare with ML
  python scripts/03_compare_strategies.py \\
      --strategies buy_and_hold sma_crossover binary_ml \\
      --model-path /app/outputs/models/catboost/v1.0.0-binary/model.cbm
        """
    )

    parser.add_argument(
        '--strategies',
        type=str,
        nargs='+',
        default=['buy_and_hold', 'sma_crossover', 'macd', 'random'],
        choices=['buy_and_hold', 'sma_crossover', 'macd', 'random', 'binary_ml'],
        help='Strategies to compare'
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
        choices=['catboost', 'xgboost'],
        help='Model type (default: catboost)'
    )

    parser.add_argument(
        '--confidence',
        type=float,
        default=0.6,
        help='Confidence threshold for ML strategy (default: 0.6)'
    )

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

    parser.add_argument(
        '--probability',
        type=float,
        default=0.02,
        help='Buy probability for random strategy (default: 0.02)'
    )

    return parser.parse_args()


def create_strategy(strategy_name: str, config: BacktestConfig, args) -> object:
    """Create a strategy instance"""

    if strategy_name == 'buy_and_hold':
        return BuyAndHoldStrategy(config)

    elif strategy_name == 'sma_crossover':
        return SMACrossoverStrategy(config, fast_period=args.fast, slow_period=args.slow)

    elif strategy_name == 'macd':
        return MACDStrategy(config)

    elif strategy_name == 'random':
        return RandomStrategy(config, buy_probability=args.probability, hold_days=20)

    elif strategy_name == 'binary_ml':
        if args.model_path is None:
            # Try to find default model
            model_dir = Path(config.models_dir) / 'catboost' / 'v1.0.0-binary'
            model_file = model_dir / 'model.cbm'
            if not model_file.exists():
                raise ValueError(f"No model found at {model_file}. Please specify --model-path")
            args.model_path = str(model_file)

        return BinaryMLStrategy(
            config,
            model_path=args.model_path,
            model_type=args.model_type,
            confidence_threshold=args.confidence
        )

    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")


def flatten_metrics(metrics: dict, prefix: str = '') -> dict:
    """Flatten nested metrics dict"""
    flat = {}
    for key, value in metrics.items():
        full_key = f"{prefix}_{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten_metrics(value, full_key))
        else:
            flat[full_key] = value
    return flat


def main():
    args = parse_args()

    print("=" * 70)
    print(" " * 20)
    print("STRATEGY COMPARISON")
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
    print(f"  Strategies: {', '.join(args.strategies)}")

    # Load data once
    print("\n" + "=" * 70)
    print("LOADING DATA")
    print("=" * 70)

    from data import load_backtest_data
    data = load_backtest_data(config)

    # Run backtests
    results = {}
    backtester = Backtester(config)

    for strategy_name in args.strategies:
        print("\n" + "=" * 70)
        print(f"TESTING: {strategy_name.upper()}")
        print("=" * 70)

        try:
            # Create strategy
            strategy = create_strategy(strategy_name, config, args)

            # Run backtest
            result = backtester.run(strategy, data)

            # Store results
            results[strategy_name] = result

        except Exception as e:
            print(f"❌ Error running {strategy_name}: {e}")
            import traceback
            traceback.print_exc()

    # Print comparison table
    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)

    # Build comparison DataFrame
    comparison_data = []

    for name, result in results.items():
        metrics = result.metrics

        # Extract key metrics
        row = {
            'Strategy': name.replace('_', ' ').title(),
            'Total Return': metrics.get('total_return', 'N/A'),
            'CAGR': metrics.get('cagr', 'N/A'),
            'Volatility': metrics.get('volatility', 'N/A'),
            'Max DD': metrics.get('max_drawdown', 'N/A'),
            'Sharpe': metrics.get('sharpe_ratio', 'N/A'),
            'Trades': metrics.get('total_trades', 'N/A'),
            'Win Rate': metrics.get('win_rate', 'N/A'),
        }

        # Calculate final portfolio value
        if not result.history_df.empty:
            final_value = result.history_df['total_value'].iloc[-1]
            row['Final Value'] = f"${final_value:,.0f}"

        comparison_data.append(row)

    # Create DataFrame and display
    df = pd.DataFrame(comparison_data)

    # Format numeric columns
    for col in df.columns:
        if col == 'Strategy' or col == 'Final Value':
            continue
        # Check if values are strings (formatted) or numeric
        if df[col].dtype == 'object':
            continue
        # Format as percentage if it looks like one
        try:
            vals = df[col].dropna()
            if len(vals) > 0 and abs(vals.iloc[0]) < 10:
                df[col] = df[col].apply(lambda x: f"{x:.1%}" if pd.notna(x) else 'N/A')
        except:
            pass

    print(df.to_string(index=False))

    # Save results
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(config.output_dir) / f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Save individual backtest results
    for name, result in results.items():
        result_dir = output_dir / name
        result_dir.mkdir(exist_ok=True)
        backtester.save_results(result, result_dir)

    # Save comparison table
    comparison_file = output_dir / 'comparison.csv'
    df.to_csv(comparison_file, index=False)

    # Save comparison as JSON
    comparison_json = output_dir / 'comparison.json'
    with open(comparison_json, 'w') as f:
        # Convert results to serializable format
        summary = {}
        for name, result in results.items():
            metrics = result.metrics
            summary[name] = {
                'total_return': str(metrics.get('total_return', 'N/A')),
                'cagr': str(metrics.get('cagr', 'N/A')),
                'volatility': str(metrics.get('volatility', 'N/A')),
                'max_drawdown': str(metrics.get('max_drawdown', 'N/A')),
                'sharpe_ratio': str(metrics.get('sharpe_ratio', 'N/A')),
                'total_trades': metrics.get('total_trades', 0),
                'win_rate': str(metrics.get('win_rate', 'N/A')),
            }

            # Add final value
            if not result.history_df.empty:
                summary[name]['final_value'] = float(result.history_df['total_value'].iloc[-1])

        json.dump(summary, f, indent=2)

    print(f"\nResults saved to: {output_dir}")
    print(f"  - comparison.csv")
    print(f"  - comparison.json")
    print(f"  - Individual results in subdirectories")

    print("\n" + "=" * 70)
    print("✅ COMPARISON COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
