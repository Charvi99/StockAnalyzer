#!/usr/bin/env python3
"""
Create Swing Trading Labels

This script creates labels for supervised learning.
Target: Will stock hit +3% within 20 days before hitting -2%?

Usage:
    python scripts/create_labels.py --config configs/default.yaml
    python scripts/create_labels.py --config configs/default.yaml --profit-target 0.05
    python scripts/create_labels.py --config configs/default.yaml --lookahead 30
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from tqdm import tqdm

# Import config system
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml_framework.config import load_config


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Create Swing Trading Labels for ML Training',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--config',
        type=str,
        default='configs/default.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--profit-target',
        type=float,
        default=None,
        help='Profit target as decimal (e.g., 0.03 for 3%%, overrides config)'
    )
    parser.add_argument(
        '--stop-loss',
        type=float,
        default=None,
        help='Stop loss as decimal (e.g., 0.02 for 2%%, overrides config)'
    )
    parser.add_argument(
        '--lookahead',
        type=int,
        default=None,
        help='Lookahead period in days (overrides config)'
    )
    parser.add_argument(
        '--features-file',
        type=str,
        default=None,
        help='Path to features file (overrides auto-detect)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for labels (overrides config)'
    )
    return parser.parse_args()


def get_stock_prices(stock_id: int, engine, start_date: datetime,
                     end_date: datetime) -> pd.DataFrame:
    """Fetch price data for a stock"""
    query = text("""
        SELECT timestamp, close
        FROM stock_prices
        WHERE stock_id = :stock_id
          AND timeframe = '1d'
          AND timestamp >= :start_date
          AND timestamp <= :end_date
        ORDER BY timestamp ASC
    """)

    df = pd.read_sql(
        query,
        engine,
        params={'stock_id': stock_id, 'start_date': start_date, 'end_date': end_date}
    )

    if df.empty:
        return pd.DataFrame()

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.set_index('timestamp')


def create_labels(df: pd.DataFrame, profit_target: float, stop_loss: float,
                 lookahead_days: int) -> pd.DataFrame:
    """
    Create swing trading labels

    For each row, checks if the stock hits:
    - profit_target before stop_loss within lookahead_days -> label 1 (BUY)
    - stop_loss before profit_target within lookahead_days -> label 0 (SELL/DON'T BUY)

    Args:
        df: Price data with 'close' column
        profit_target: Profit target (e.g., 0.03 for +3%)
        stop_loss: Stop loss (e.g., 0.02 for -2%)
        lookahead_days: Maximum days to look ahead

    Returns:
        DataFrame with labels
    """
    labels = pd.DataFrame(index=df.index)
    labels['close'] = df['close']
    labels['label'] = np.nan

    for i in range(len(df) - lookahead_days):
        current_price = df['close'].iloc[i]
        future_prices = df['close'].iloc[i+1:i+lookahead_days+1]

        # Calculate returns
        returns = (future_prices - current_price) / current_price

        # Check if profit target is hit first
        profit_hit = (returns >= profit_target)
        stop_hit = (returns <= -stop_loss)

        if profit_hit.any():
            # Find first profit hit
            first_profit_idx = profit_hit.idxmax()
            # Check if stop was hit before profit
            if stop_hit[:first_profit_idx].any():
                labels['label'].iloc[i] = 0
            else:
                labels['label'].iloc[i] = 1
        elif stop_hit.any():
            labels['label'].iloc[i] = 0
        # If neither is hit, label remains NaN (no signal)

    return labels.dropna()


def main():
    """Main label creation pipeline"""
    args = parse_args()

    # Load configuration
    config = load_config(args.config)

    # Apply CLI overrides
    profit_target = args.profit_target if args.profit_target is not None else \
                    config.data.get('label_profit_target', 0.03)
    stop_loss = args.stop_loss if args.stop_loss is not None else \
               config.data.get('label_stop_loss', 0.02)
    lookahead_days = args.lookahead if args.lookahead is not None else \
                    config.data.get('label_lookahead_days', 20)

    features_dir = Path(config.data.get('features_dir', 'data/features'))
    output_dir = Path(args.output_dir) if args.output_dir else features_dir

    print("=" * 70)
    print(" " * 22)
    print("Label Creation Pipeline")
    print(" " * 22)
    print("=" * 70)

    print(f"\n📊 Parameters:")
    print(f"   Profit target: +{profit_target*100:.1f}%")
    print(f"   Stop loss:     {stop_loss*100:.1f}%")
    print(f"   Lookahead:     {lookahead_days} days")

    # Database connection
    database_url = os.getenv('DATABASE_URL', config.data.get('database_url',
        'postgresql://stockuser:stockpass@db:5432/stockanalyzer'))
    engine = create_engine(database_url)

    # Find features file
    if args.features_file:
        features_file = Path(args.features_file)
    else:
        # Find latest features file
        import glob
        feature_files = sorted(features_dir.glob('features_*.parquet'))
        if not feature_files:
            print("❌ No features found!")
            print(f"   Run: python scripts/create_features.py")
            return
        features_file = feature_files[-1]

    print(f"\n📂 Loading features from: {features_file.name}")
    features_df = pd.read_parquet(features_file)

    print(f"   Total samples: {len(features_df):,}")

    # Get unique stocks
    if 'stock_id' in features_df.columns:
        stock_ids = features_df['stock_id'].unique()
    else:
        print("❌ No stock_id column in features!")
        return

    print(f"   Unique stocks: {len(stock_ids)}")

    # Create labels for each stock
    print("\n" + "=" * 70)
    print("CREATING LABELS")
    print("=" * 70)

    all_labels = []

    for stock_id in tqdm(stock_ids, desc="Processing stocks"):
        # Get price data for this stock
        stock_data = features_df[features_df['stock_id'] == stock_id]
        if stock_data.empty:
            continue

        # Get date range
        start_date = stock_data.index.min()
        end_date = stock_data.index.max() + timedelta(days=lookahead_days + 10)

        # Fetch prices
        prices = get_stock_prices(stock_id, engine, start_date, end_date)

        if prices.empty or len(prices) < lookahead_days + 10:
            continue

        # Create labels
        labels = create_labels(prices, profit_target, stop_loss, lookahead_days)

        if not labels.empty:
            labels['stock_id'] = stock_id
            all_labels.append(labels)

    if not all_labels:
        print("\n❌ No labels generated!")
        return

    # Combine all labels
    print("\n" + "=" * 70)
    print("COMBINING LABELS")
    print("=" * 70)

    combined = pd.concat(all_labels, axis=0)

    # Merge with features
    print("\n📊 Merging labels with features...")
    final_df = features_df.join(combined[['label']], how='inner')

    print(f"   Final samples: {len(final_df):,}")
    print(f"   Positive labels (BUY): {(final_df['label'] == 1).sum():,}")
    print(f"   Negative labels (SELL): {(final_df['label'] == 0).sum():,}")

    label_dist = final_df['label'].value_counts(normalize=True)
    print(f"\n📈 Label distribution:")
    print(f"   BUY (1):  {label_dist.get(1, 0)*100:.1f}%")
    print(f"   SELL (0): {label_dist.get(0, 0)*100:.1f}%")

    # Save to parquet
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'labels_{timestamp}.parquet'

    final_df.to_parquet(output_file, index=True)

    print(f"\n✅ Labels saved to: {output_file}")

    print("\n" + "=" * 70)
    print("✅ LABEL CREATION COMPLETE!")
    print("=" * 70)

    print("\nNext steps:")
    print("1. Review label distribution")
    print("2. Run: python train.py")


if __name__ == "__main__":
    main()
