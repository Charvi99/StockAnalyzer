#!/usr/bin/env python3
"""
Backtest Multi-Class Labels to Validate Trustworthiness

This script validates if the labels are predictive by checking:
1. Does STRONG BUY actually lead to positive returns?
2. Does STRONG SELL actually lead to negative returns?
3. What is the hit rate for each class?
4. Are the labels better than random?

Usage:
    python scripts/backtest.py --config configs/default.yaml
    python scripts/backtest.py --config configs/default.yaml --labels-file data/labels/labels_20240101.parquet
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from tqdm import tqdm

# Import config system
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml_framework.config import load_config


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Backtest Labels to Validate Predictive Power',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--config',
        type=str,
        default='configs/default.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--labels-file',
        type=str,
        default=None,
        help='Path to labels file (overrides auto-detect)'
    )
    parser.add_argument(
        '--lookaheads',
        type=str,
        default='20,30,40',
        help='Comma-separated lookahead periods to test'
    )
    return parser.parse_args()


def calculate_future_returns(df: pd.DataFrame, lookahead_days: int) -> pd.Series:
    """
    Calculate actual future returns for each sample

    Args:
        df: DataFrame with 'close' prices
        lookahead_days: Days to look ahead

    Returns:
        Series with future returns
    """
    returns = df['close'].pct_change(lookahead_days).shift(-lookahead_days)
    return returns


def backtest_labels(df: pd.DataFrame, label_column: str = 'label',
                   lookahead_days: int = 20) -> dict:
    """
    Backtest labels against actual returns

    Args:
        df: DataFrame with labels and prices
        label_column: Name of label column
        lookahead_days: Days to look ahead

    Returns:
        Dictionary with backtest metrics
    """
    # Calculate actual returns
    df = df.copy()
    df['future_return'] = calculate_future_returns(df, lookahead_days)

    # Remove rows without future returns
    df = df.dropna(subset=['future_return', label_column])

    if df.empty:
        return {}

    # Calculate metrics for each label class
    results = {}

    for label_value in sorted(df[label_column].unique()):
        label_data = df[df[label_column] == label_value]

        results[label_value] = {
            'count': len(label_data),
            'mean_return': label_data['future_return'].mean() * 100,  # Convert to percent
            'median_return': label_data['future_return'].median() * 100,
            'std_return': label_data['future_return'].std() * 100,
            'hit_rate': (label_data['future_return'] > 0).mean() * 100,
            'sharpe': (label_data['future_return'].mean() /
                     label_data['future_return'].std() * np.sqrt(252)
                     if label_data['future_return'].std() > 0 else 0)
        }

    # Calculate overall metrics
    results['overall'] = {
        'count': len(df),
        'mean_return': df['future_return'].mean() * 100,
        'hit_rate': (df['future_return'] > 0).mean() * 100
    }

    return results


def main():
    """Main backtest pipeline"""
    args = parse_args()

    # Load configuration
    config = load_config(args.config)

    labels_dir = Path(config.data.get('features_dir', 'data/features'))

    print("=" * 70)
    print(" " * 18)
    print("Label Backtesting Pipeline")
    print(" " * 18)
    print("=" * 70)

    # Find labels file
    if args.labels_file:
        labels_file = Path(args.labels_file)
    else:
        # Find latest labels file
        import glob
        label_files = sorted(labels_dir.glob('labels_*.parquet'))
        if not label_files:
            print("❌ No labels found!")
            print(f"   Run: python scripts/create_labels.py")
            return
        labels_file = label_files[-1]

    print(f"\n📂 Loading labels from: {labels_file.name}")
    df = pd.read_parquet(labels_file)

    print(f"📊 Total samples: {len(df):,}")
    print(f"📅 Date range: {df.index.min()} to {df.index.max()}")

    # Check label distribution
    if 'label' in df.columns:
        print("\n📈 Label distribution:")
        label_counts = df['label'].value_counts().sort_index()
        for label, count in label_counts.items():
            pct = count / len(df) * 100
            print(f"   Class {label}: {count:,} ({pct:.1f}%)")
    else:
        print("❌ No 'label' column found!")
        return

    # Parse lookahead periods
    lookaheads = [int(x) for x in args.lookaheads.split(',')]

    print("\n" + "=" * 70)
    print("BACKTESTING RESULTS")
    print("=" * 70)

    all_results = {}

    for lookahead in lookaheads:
        print(f"\n{'-' * 70}")
        print(f"LOOKAHEAD: {lookahead} days")
        print(f"{'-' * 70}")

        results = backtest_labels(df, 'label', lookahead)

        if not results:
            print(f"⚠️  Insufficient data for {lookahead}-day lookahead")
            continue

        all_results[lookahead] = results

        # Print results for each class
        for label_value in sorted(results.keys()):
            if label_value == 'overall':
                continue

            metrics = results[label_value]
            label_name = f"Class {label_value}"

            print(f"\n{label_name}:")
            print(f"  Count:         {metrics['count']:,}")
            print(f"  Mean Return:   {metrics['mean_return']:+.2f}%")
            print(f"  Median Return: {metrics['median_return']:+.2f}%")
            print(f"  Std Dev:       {metrics['std_return']:.2f}%")
            print(f"  Hit Rate:      {metrics['hit_rate']:.1f}%")
            print(f"  Sharpe:        {metrics['sharpe']:.2f}")

        # Print overall metrics
        if 'overall' in results:
            overall = results['overall']
            print(f"\nOVERALL:")
            print(f"  Mean Return: {overall['mean_return']:+.2f}%")
            print(f"  Hit Rate:    {overall['hit_rate']:.1f}%")

    # Assess label quality
    print("\n" + "=" * 70)
    print("LABEL QUALITY ASSESSMENT")
    print("=" * 70)

    if 20 in all_results and 'overall' in all_results[20]:
        overall_20 = all_results[20]['overall']
        print(f"\n20-day lookahead:")
        print(f"  Overall mean return: {overall_20['mean_return']:+.2f}%")
        print(f"  Overall hit rate:    {overall_20['hit_rate']:.1f}%")

        # Check if labels are predictive
        if 'label' in df.columns:
            positive_mean = all_results[20].get(1, {}).get('mean_return', 0)
            negative_mean = all_results[20].get(0, {}).get('mean_return', 0)

            print(f"\n  Class 1 (BUY) mean return:  {positive_mean:+.2f}%")
            print(f"  Class 0 (SELL) mean return: {negative_mean:+.2f}%")

            if positive_mean > negative_mean:
                print(f"  ✅ Labels are DIRECTIONALLY CORRECT")
                print(f"     Difference: {positive_mean - negative_mean:+.2f}%")
            else:
                print(f"  ⚠️  Labels may NOT be predictive")
                print(f"     Difference: {positive_mean - negative_mean:+.2f}%")

    # Save backtest results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = labels_dir / f'backtest_results_{timestamp}.txt'

    with open(results_file, 'w') as f:
        f.write("Backtest Results\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Labels file: {labels_file.name}\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for lookahead, results in all_results.items():
            f.write(f"\nLookahead: {lookahead} days\n")
            f.write("-" * 70 + "\n")
            for label_value, metrics in results.items():
                f.write(f"\nClass {label_value}:\n")
                for key, value in metrics.items():
                    f.write(f"  {key}: {value}\n")

    print(f"\n✅ Results saved to: {results_file}")

    print("\n" + "=" * 70)
    print("✅ BACKTESTING COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
