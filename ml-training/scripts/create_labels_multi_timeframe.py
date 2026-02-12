#!/usr/bin/env python3
"""
Multi-Timeframe Label Creator

Creates alpha-quantile labels for different timeframes (10, 20, 30 days)
to compare predictability across different horizons.

Alpha-Quantile: Top 30% of alpha performers (stock_return - spy_return)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sys
import json

# Add backend to path
sys.path.insert(0, '/backend')

from sqlalchemy import create_engine, text
from tqdm import tqdm
import os

# Try multiple database hostnames
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass123@database:5432/stock_analyzer')

# Fix hostname if needed
if 'postgresql://stockuser:stockpass@db:' in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace('@db:', '@database:')

engine = create_engine(DATABASE_URL)


def fetch_stock_prices(stock_id: int, start_date: datetime, end_date: datetime):
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

    with engine.connect() as conn:
        df = pd.read_sql(
            query,
            conn,
            params={'stock_id': stock_id, 'start_date': start_date, 'end_date': end_date}
        )

    if df.empty:
        return None

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def fetch_spy_data(start_date: datetime, end_date: datetime):
    """Fetch SPY (market) data"""
    # Find SPY stock_id
    with engine.connect() as conn:
        query = text("SELECT id FROM stocks WHERE symbol = 'SPY'")
        result = conn.execute(query)
        spy_row = result.fetchone()

    if not spy_row:
        raise ValueError("SPY not found in stocks table")

    spy_id = spy_row[0]

    query = text("""
        SELECT timestamp, close
        FROM stock_prices
        WHERE stock_id = :spy_id
          AND timeframe = '1d'
          AND timestamp >= :start_date
          AND timestamp <= :end_date
        ORDER BY timestamp ASC
    """)

    with engine.connect() as conn:
        df = pd.read_sql(
            query,
            conn,
            params={'spy_id': spy_id, 'start_date': start_date, 'end_date': end_date}
        )

    if df.empty:
        return None

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.rename(columns={'close': 'spy_close'})
    return df


def create_alpha_quantile_labels_multi_timeframe(
    dataset_folder: str,
    timeframes: list = [10, 20, 30],
    top_percentile: float = 0.70
):
    """
    Create alpha-quantile labels for multiple timeframes

    Args:
        dataset_folder: Dataset folder with existing labels
        timeframes: List of day horizons [10, 20, 30]
        top_percentile: Percentile for BUY (0.70 = top 30%)
    """
    print("=" * 70)
    print("MULTI-TIMEFRAME ALPHA-QUANTILE LABEL CREATOR")
    print("=" * 70)

    dataset_path = Path("/app/outputs/features") / dataset_folder

    # Load existing features to get stock_id and timestamp
    features_file = dataset_path / "features.parquet"
    if not features_file.exists():
        raise FileNotFoundError(f"Features not found: {features_file}")

    print(f"\n📂 Loading features from: {features_file}")
    features_df = pd.read_parquet(features_file)
    print(f"   Loaded {len(features_df):,} rows")

    # Get unique stock_ids and date range
    stock_ids = features_df['stock_id'].unique().tolist()
    min_date = features_df['timestamp'].min()
    max_date = features_df['timestamp'].max()

    # Add buffer for lookahead
    max_lookahead = max(timeframes) + 10
    start_date = min_date - timedelta(days=50)
    end_date = max_date + timedelta(days=max_lookahead)

    print(f"   Stock IDs: {len(stock_ids)}")
    print(f"   Date range: {min_date.date()} to {max_date.date()}")
    print(f"   Timeframes: {timeframes} days")

    # Fetch SPY data
    print(f"\n📊 Fetching SPY data...")
    spy_df = fetch_spy_data(start_date, end_date)
    if spy_df is None:
        raise ValueError("Could not fetch SPY data")

    spy_df = spy_df.rename(columns={'spy_close': 'close'})
    print(f"   SPY data: {len(spy_df)} rows")

    # Create labels for each timeframe
    all_labels = {}

    for lookahead_days in timeframes:
        print(f"\n{'='*70}")
        print(f"CREATING LABELS: {lookahead_days}-DAY RETURN")
        print(f"{'='*70}")

        labels_list = []

        for stock_id in tqdm(stock_ids, desc=f"Stocks ({lookahead_days}d)"):
            # Fetch stock prices
            prices = fetch_stock_prices(stock_id, start_date, end_date)

            if prices is None or len(prices) < lookahead_days + 10:
                continue

            # Merge with SPY data
            merged = pd.merge(
                prices[['timestamp', 'close']],
                spy_df[['timestamp', 'close']].rename(columns={'close': 'spy_close'}),
                on='timestamp',
                how='inner'
            )

            if len(merged) < lookahead_days:
                continue

            # Calculate returns for each timestamp
            for i in range(len(merged) - lookahead_days):
                current_timestamp = merged.iloc[i]['timestamp']
                current_price = merged.iloc[i]['close']
                current_spy_close = merged.iloc[i]['spy_close']

                # Check if this timestamp is in our features
                if current_timestamp < min_date or current_timestamp > max_date:
                    continue

                # Calculate forward return
                future_idx = i + lookahead_days
                if future_idx >= len(merged):
                    continue

                future_price = merged.iloc[future_idx]['close']
                future_spy_close = merged.iloc[future_idx]['spy_close']

                # Calculate returns
                stock_return = (future_price - current_price) / current_price
                spy_return = (future_spy_close - current_spy_close) / current_spy_close
                alpha = stock_return - spy_return

                labels_list.append({
                    'timestamp': current_timestamp,
                    'stock_id': stock_id,
                    'stock_return': stock_return,
                    'spy_return': spy_return,
                    'alpha': alpha
                })

        if not labels_list:
            print(f"   ⚠️  No labels created for {lookahead_days}-day timeframe")
            continue

        # Create DataFrame
        df_labels = pd.DataFrame(labels_list)

        # Calculate alpha threshold (70th percentile)
        threshold = df_labels['alpha'].quantile(top_percentile)

        # Create labels
        df_labels['label'] = (df_labels['alpha'] > threshold).astype(int)

        print(f"\n   Threshold: {threshold:.4f} ({threshold*100:.2f}%)")
        print(f"   Total samples: {len(df_labels):,}")
        print(f"   BUY (label=1): {(df_labels['label']==1).sum():,} ({(df_labels['label']==1).mean()*100:.1f}%)")
        print(f"   NO BUY (label=0): {(df_labels['label']==0).sum():,} ({(df_labels['label']==0).mean()*100:.1f}%)")

        # Save labels
        output_file = dataset_path / f"labels_alpha_quantile_{lookahead_days}d.parquet"
        df_labels.to_parquet(output_file, index=False)
        print(f"   ✅ Saved to: {output_file.name}")

        all_labels[lookahead_days] = {
            'file': output_file,
            'threshold': threshold,
            'buy_count': int((df_labels['label']==1).sum()),
            'total_count': len(df_labels),
            'buy_pct': (df_labels['label']==1).mean() * 100
        }

    # Update metadata
    metadata_file = dataset_path / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        metadata['alpha_quantile_timeframes'] = all_labels

        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    # Summary
    print(f"\n{'='*70}")
    print("✅ MULTI-TIMEFRAME LABELS CREATED!")
    print(f"{'='*70}")

    print(f"\n📊 Summary:")
    for days, info in all_labels.items():
        print(f"   {days}d: {info['buy_count']:,} BUY ({info['buy_pct']:.1f}%)")

    print(f"\n💡 Next steps:")
    print(f"   Train each timeframe:")
    for days in all_labels.keys():
        print(f"   python train.py --dataset-folder {dataset_folder} --label-type alpha_quantile_{days}d --trials 30")

    print(f"\n   Or train all in parallel (different terminals)")
    print(f"{'='*70}")

    return all_labels


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Create Alpha-Quantile Labels for Multiple Timeframes',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--dataset-folder',
        type=str,
        default='dataset_enhanced_20260209_132053',
        help='Dataset folder name'
    )

    parser.add_argument(
        '--timeframes',
        type=int,
        nargs='+',
        default=[10, 20, 30],
        help='Timeframes in days (default: 10 20 30)'
    )

    parser.add_argument(
        '--top-percentile',
        type=float,
        default=0.70,
        help='Percentile for BUY (default: 0.70 = top 30%%)'
    )

    args = parser.parse_args()

    try:
        create_alpha_quantile_labels_multi_timeframe(
            args.dataset_folder,
            args.timeframes,
            args.top_percentile
        )
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
