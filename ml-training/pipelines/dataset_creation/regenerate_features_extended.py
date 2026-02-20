#!/usr/bin/env python3
"""
REGENERATE FEATURES FOR EXTENDED DATASET (2018-2025)

Purpose: After fetching 2018-2020 stock prices, regenerate features for
         the extended 2018-2025 period to include diverse market regimes.

Usage:
    python regenerate_features_extended.py --start-date 2018-01-01 --end-date 2025-12-31

Created: 2026-02-05
Author: ML Team
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Setup paths
sys.path.insert(0, '/app')

# Import feature engineering pipeline
from scripts.feature_engineering import FeatureEngineer
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass@db:5432/stockanalyzer')
engine = create_engine(DATABASE_URL)


def regenerate_extended_features(
    start_date: str = '2018-01-01',
    end_date: str = '2025-12-31',
    output_folder: str = None
):
    """
    Regenerate features for extended date range

    Args:
        start_date: Start date (default: 2018-01-01)
        end_date: End date (default: 2025-12-31)
        output_folder: Output folder name (auto-generated if None)
    """

    print("=" * 70)
    print("REGENERATING FEATURES FOR EXTENDED DATASET")
    print("=" * 70)

    print(f"\n📅 Date range: {start_date} to {end_date}")
    print(f"🎯 Target: Include diverse market regimes")

    # Check data availability
    print(f"\n📊 Checking data availability...")

    with engine.connect() as conn:
        # Check stock prices
        result = conn.execute(text('''
            SELECT
                COUNT(*) as records,
                COUNT(DISTINCT stock_id) as stocks,
                MIN(timestamp) as earliest,
                MAX(timestamp) as latest
            FROM stock_prices
            WHERE timestamp >= :start AND timestamp <= :end
        '''), {'start': start_date, 'end': end_date})
        row = result.fetchone()

        if not row or row[0] == 0:
            print(f"\n❌ No stock price data found for {start_date} to {end_date}")
            print(f"   Run fetch_historical_2018_2020.py first")
            return

        print(f"\n✅ Stock price data:")
        print(f"   Records: {row[0]:,}")
        print(f"   Stocks: {row[1]}")
        print(f"   Date range: {row[2]} to {row[3]}")

        # Check insider data
        result = conn.execute(text('''
            SELECT COUNT(*)
            FROM insider_trades
            WHERE trade_date >= :start AND trade_date <= :end
        '''), {'start': start_date, 'end': end_date})
        insider_count = result.fetchone()[0]

        print(f"\n✅ Insider trading data:")
        print(f"   Records: {insider_count:,}")

        # Get stock list
        result = conn.execute(text('''
            SELECT id, symbol
            FROM stocks
            ORDER BY symbol
        '''))
        stocks = result.fetchall()
        print(f"\n   Stocks to process: {len(stocks)}")

    # Initialize feature engineer
    print(f"\n🔧 Initializing feature engineering pipeline...")

    feature_engineer = FeatureEngineer(
        engine=engine,
        lookback_days=50,
        fetch_insider_data=False  # Insider data already in DB
    )

    # Generate features
    print(f"\n🔄 Generating features...")
    print("-" * 70)

    features_df = feature_engineer.generate_features_for_stocks(
        stocks=[s[0] for s in stocks],
        start_date=start_date,
        end_date=end_date
    )

    if features_df is None or len(features_df) == 0:
        print("\n❌ Feature generation failed!")
        return

    print(f"\n✅ Generated {len(features_df):,} samples with {len(features_df.columns)} features")

    # Determine output folder
    if output_folder is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder = f'dataset_extended_{timestamp}'

    output_path = Path(f'/app/outputs/features/{output_folder}')
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\n📂 Output folder: {output_folder}")

    # Save features
    features_file = output_path / 'features.parquet'
    print(f"💾 Saving features to {features_file}...")

    features_df.to_parquet(features_file, index=False)

    print(f"✅ Saved {len(features_df):,} samples with {len(features_df.columns)} features")

    # Save metadata
    import json
    metadata = {
        'start_date': start_date,
        'end_date': end_date,
        'total_samples': len(features_df),
        'total_features': len(features_df.columns),
        'total_stocks': len(stocks),
        'feature_columns': list(features_df.columns),
        'created_at': datetime.now().isoformat()
    }

    metadata_file = output_path / 'metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"✅ Metadata saved to {metadata_file}")

    print(f"\n" + "=" * 70)
    print("EXTENDED DATASET READY")
    print("=" * 70)
    print(f"\n📊 Dataset summary:")
    print(f"   Period: {start_date} to {end_date} (8 years)")
    print(f"   Samples: {len(features_df):,}")
    print(f"   Features: {len(features_df.columns)}")
    print(f"   Stocks: {len(stocks)}")

    # Check market regimes covered
    print(f"\n📈 Market regimes included:")
    print(f"   2018: Trade war, volatility")
    print(f"   2019: Trade war escalation, corrections")
    print(f"   2020: COVID crash, recovery")
    print(f"   2021-2025: Bull market recovery")

    return output_folder


def regenerate_alpha_labels_extended(dataset_folder: str):
    """
    Regenerate alpha labels for extended dataset

    Args:
        dataset_folder: Dataset folder name
    """

    print("\n" + "=" * 70)
    print("CREATING ALPHA LABELS FOR EXTENDED DATASET")
    print("=" * 70)

    # Import alpha label creation
    sys.path.insert(0, '/app/ml-training/create_labels')
    from create_alpha_labels import create_alpha_labels

    # Create alpha labels
    alpha_labels = create_alpha_labels(
        dataset_folder=dataset_folder,
        features_file='features.parquet'
    )

    print(f"\n✅ Alpha labels created:")
    print(f"   Total: {len(alpha_labels):,}")
    print(f"   BUY: {(alpha_labels['label'] == 1).sum():,} ({(alpha_labels['label'] == 1).sum()/len(alpha_labels)*100:.1f}%)")
    print(f"   Mean alpha: {alpha_labels['alpha'].mean()*100:.2f}%")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Regenerate features for extended dataset (2018-2025)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python regenerate_features_extended.py
  python regenerate_features_extended.py --start-date 2018-01-01 --end-date 2025-12-31

This script:
  1. Checks data availability for 2018-2025
  2. Regenerates features using existing pipeline
  3. Creates extended dataset with diverse market regimes
  4. Generates alpha labels for extended period

Prerequisites:
  - Stock price data for 2018-2025 (run fetch_historical_2018_2020.py first)
  - Insider trading data (already available 2001-2026)

Expected time: 30-60 minutes (depends on number of stocks)
        """
    )

    parser.add_argument(
        '--start-date',
        type=str,
        default='2018-01-01',
        help='Start date (default: 2018-01-01)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        default='2025-12-31',
        help='End date (default: 2025-12-31)'
    )

    args = parser.parse_args()

    print(f"⏰ Start time: {datetime.now().strftime('%H:%M:%S')}")

    # Regenerate features
    dataset_folder = regenerate_extended_features(
        start_date=args.start_date,
        end_date=args.end_date
    )

    # Regenerate alpha labels
    regenerate_alpha_labels_extended(dataset_folder)

    print(f"\n✅ Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"\n📂 Dataset folder: {dataset_folder}")
    print(f"\nNext steps:")
    print(f"  1. Train models with extended dataset")
    print(f"  2. Compare performance: 2018-2025 vs 2021-2025")
    print(f"  3. Validate on different market regimes")


if __name__ == "__main__":
    main()
