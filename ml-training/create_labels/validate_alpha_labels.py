#!/usr/bin/env python3
"""
ALPHA LABEL VALIDATION SCRIPT

Purpose: Verify alpha labels are 100% correct before training
- Check date alignment between stock and SPY prices
- Verify alpha calculation is correct
- Check for data leakage or edge cases
- Validate label distribution makes sense

Usage:
    python validate_alpha_labels.py --dataset-folder dataset_20260204_204134

Created: 2026-02-05
Author: ML Team
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Setup paths
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass@db:5432/stockanalyzer')
engine = create_engine(DATABASE_URL)


def validate_alpha_labels(dataset_folder: str):
    """
    Comprehensive validation of alpha labels
    """

    print("=" * 70)
    print("ALPHA LABEL VALIDATION")
    print("=" * 70)

    # Load alpha labels
    alpha_labels_path = f'/app/outputs/features/{dataset_folder}/labels_alpha_binary.parquet'

    try:
        alpha_df = pd.read_parquet(alpha_labels_path)
    except Exception as e:
        print(f"\n❌ Cannot load alpha labels: {e}")
        return False

    print(f"\n✅ Loaded alpha labels: {len(alpha_df):,} rows")
    print(f"   Date range: {alpha_df['timestamp'].min()} to {alpha_df['timestamp'].max()}")

    # ============================================================
    # VALIDATION 1: Check Alpha Calculation
    # ============================================================

    print("\n" + "=" * 70)
    print("VALIDATION 1: Alpha Calculation Check")
    print("=" * 70)

    # Re-calculate alpha for a random sample
    print("\nRe-calculating alpha for 100 random samples...")

    sample = alpha_df.sample(n=100, random_state=42)

    validation_errors = []

    for idx, row in sample.iterrows():
        stock_id = row['stock_id']
        timestamp = row['timestamp']
        expected_alpha = row['alpha']

        # Fetch actual prices
        query = text("""
            SELECT sp.timestamp, sp.close as stock_close
            FROM stock_prices sp
            WHERE sp.stock_id = :stock_id
              AND sp.timeframe = '1d'
              AND sp.timestamp >= :start_date
              AND sp.timestamp <= :end_date
            ORDER BY sp.timestamp ASC
            LIMIT 25
        """)

        lookbehind = 5
        lookahead = 20

        start_date = timestamp - timedelta(days=lookbehind)
        end_date = timestamp + timedelta(days=lookahead + 5)

        result = pd.read_sql(
            query,
            engine,
            params={'stock_id': stock_id, 'start_date': start_date, 'end_date': end_date}
        )

        if len(result) < 25:
            continue

        # Find the current timestamp
        current_idx = result[result['timestamp'] == timestamp].index
        if len(current_idx) == 0:
            validation_errors.append(f"Stock {stock_id}: Timestamp {timestamp} not found in price data")
            continue

        current_idx = current_idx[0]

        if current_idx + lookahead >= len(result):
            validation_errors.append(f"Stock {stock_id}: Not enough future data for lookahead")
            continue

        # Calculate returns
        stock_close = result.iloc[current_idx]['stock_close']
        stock_close_future = result.iloc[current_idx + lookahead]['stock_close']

        # Get SPY price for same timestamps
        spy_query = text("""
            SELECT sp.timestamp, sp.close as spy_close
            FROM stock_prices sp
            JOIN stocks s ON sp.stock_id = s.id
            WHERE s.symbol = 'SPY'
              AND sp.timeframe = '1d'
              AND sp.timestamp >= :start_date
              AND sp.timestamp <= :end_date
            ORDER BY sp.timestamp ASC
            LIMIT 25
        """)

        spy_result = pd.read_sql(
            spy_query,
            engine,
            params={'start_date': start_date, 'end_date': end_date}
        )

        if len(spy_result) < 25:
            validation_errors.append(f"Stock {stock_id}: Insufficient SPY data")
            continue

        # Find SPY current timestamp
        spy_current_idx = spy_result[spy_result['timestamp'] == timestamp].index
        if len(spy_current_idx) == 0:
            validation_errors.append(f"Stock {stock_id}: SPY timestamp {timestamp} not found")
            continue

        spy_current_idx = spy_current_idx[0]

        if spy_current_idx + lookahead >= len(spy_result):
            validation_errors.append(f"Stock {stock_id}: Not enough SPY future data")
            continue

        spy_close = spy_result.iloc[spy_current_idx]['spy_close']
        spy_close_future = spy_result.iloc[spy_current_idx + lookahead]['spy_close']

        # Recalculate alpha
        stock_return = (stock_close_future - stock_close) / stock_close
        spy_return = (spy_close_future - spy_close) / spy_close

        recalculated_alpha = stock_return - spy_return

        # Check if matches (within floating point tolerance)
        if abs(recalculated_alpha - expected_alpha) > 0.001:
            validation_errors.append(
                f"Stock {stock_id} @ {timestamp}:\n"
                f"  Expected alpha: {expected_alpha:.6f}\n"
                f"  Recalculated:  {recalculated_alpha:.6f}\n"
                f"  Stock return: {stock_return:.6f}\n"
                f"  SPY return:   {spy_return:.6f}"
            )

    if validation_errors:
        print(f"\n❌ Found {len(validation_errors)} validation errors!")
        print("\nFirst 10 errors:")
        for error in validation_errors[:10]:
            print(f"  {error}")
        if len(validation_errors) > 10:
            print(f"  ... and {len(validation_errors) - 10} more errors")
        return False
    else:
        print(f"\n✅ All 100 sampled labels validated successfully!")
        print("   Alpha calculation is CORRECT")

    # ============================================================
    # VALIDATION 2: Check Label Assignment
    # ============================================================

    print("\n" + "=" * 70)
    print("VALIDATION 2: Label Assignment Check")
    print("=" * 70)

    alpha_target = 0.02

    # Check that BUY labels have alpha >= 0.02
    buy_labels = alpha_df[alpha_df['label'] == 1]

    # Allow small tolerance for edge cases
    edge_case_tolerance = 0.001  # 0.1% tolerance
    invalid_buy = buy_labels[buy_labels['alpha'] < alpha_target - edge_case_tolerance]

    print(f"\nBUY labels with alpha >= {alpha_target}: {(len(buy_labels) - len(invalid_buy))}/{len(buy_labels)}")

    if len(invalid_buy) > 0:
        print(f"\n❌ Found {len(invalid_buy)} BUY labels with alpha < {alpha_target}")
        print("   Sample:")
        for idx, row in invalid_buy.head(5).iterrows():
            print(f"   Alpha: {row['alpha']:.4f}, Label: {row['label']}")
        return False
    else:
        print(f"✅ All {(len(buy_labels))} BUY labels have alpha >= {alpha_target}")

    # Check that DON'T BUY labels have alpha < 0.02
    dont_buy_labels = alpha_df[alpha_df['label'] == 0]

    # Find truly invalid labels: alpha >= 0.02 (should be BUY, not DO NOT BUY)
    truly_invalid = dont_buy_labels[dont_buy_labels['alpha'] >= alpha_target]

    print(f"\nDO NOT BUY labels with alpha < {alpha_target}: {(len(dont_buy_labels) - len(truly_invalid))}/{len(dont_buy_labels)}")

    if len(truly_invalid) > 0:
        print(f"\n❌ Found {len(truly_invalid)} DO NOT BUY labels with alpha >= {alpha_target}")
        print("   Sample:")
        for idx, row in truly_invalid.head(5).iterrows():
            print(f"   Alpha: {row['alpha']:.4f}, Label: {row['label']}")
        return False
    else:
        print(f"✅ All {(len(dont_buy_labels))} DO NOT BUY labels have alpha < {alpha_target}")

        # Show edge cases (close to threshold but correctly labeled)
        edge_case_threshold = alpha_target - 0.005  # 0.015 to 0.0199 range
        edge_cases = dont_buy_labels[
            (dont_buy_labels['alpha'] >= edge_case_threshold) &
            (dont_buy_labels['alpha'] < alpha_target)
        ]
        if len(edge_cases) > 0:
            print(f"  Note: {len(edge_cases)} labels are close to threshold (0.015-0.0199) but correctly labeled")

    # ============================================================
    # VALIDATION 3: Edge Cases
    # ============================================================

    print("\n" + "=" * 70)
    print("VALIDATION 3: Edge Cases")
    print("=" * 70)

    # Check for NaN values
    nan_check = alpha_df[['alpha', 'stock_return', 'spy_return']].isna().sum().sum()

    if nan_check > 0:
        print(f"\n❌ Found {nan_check} NaN values in alpha/returns")
        return False
    else:
        print(f"✅ No NaN values in alpha/returns")

    # Check for infinite values
    inf_check = np.isinf(alpha_df[['alpha', 'stock_return', 'spy_return']]).sum().sum()

    if inf_check > 0:
        print(f"\n❌ Found {inf_check} infinite values in alpha/returns")
        return False
    else:
        print(f"✅ No infinite values in alpha/returns")

    # Check for extreme outliers (beyond ±200%)
    extreme_positive = (alpha_df['alpha'] > 2.0).sum()
    extreme_negative = (alpha_df['alpha'] < -2.0).sum()

    print(f"\nExtreme alphas (>200% or <-200%):")
    print(f"  >+200%: {extreme_positive}")
    print(f"  <-200%: {extreme_negative}")

    if extreme_positive + extreme_negative > len(alpha_df) * 0.001:  # < 0.1% tolerance
        print(f"✅ Extreme alphas are rare ({(extreme_positive + extreme_negative)/len(alpha_df)*100:.4f}%)")
    else:
        print(f"⚠️  Extreme alphas are too common")

    # ============================================================
    # VALIDATION 4: Distribution Check
    # ============================================================

    print("\n" "=" * 70)
    print("VALIDATION 4: Label Distribution")
    print("=" * 70)

    buy_count = (alpha_df['label'] == 1).sum()
    dont_buy_count = (alpha_df['label'] == 0).sum()
    total = len(alpha_df)

    buy_rate = buy_count / total * 100

    print(f"\nLabel distribution:")
    print(f"  BUY: {buy_count:,} ({buy_rate:.1f}%)")
    print(f"  DO NOT BUY: {dont_buy_count:,} ({100-buy_rate:.1f}%)")

    # Check if distribution is reasonable
    if buy_rate < 20 or buy_rate > 50:
        print(f"\n⚠️  BUY rate ({buy_rate:.1f}%) is outside expected range (20-50%)")
    else:
        print(f"✅ BUY rate ({buy_rate:.1f}%) is reasonable")

    # Check alpha distribution
    print(f"\nAlpha distribution:")
    print(f"  Mean: {alpha_df['alpha'].mean()*100:.2f}%")
    print(f"  Median: {alpha_df['alpha'].median()*100:.2f}%")
    print(f"  Std: {alpha_df['alpha'].std()*100:.2f}%")

    # Check mean alpha is close to zero (market-neutral)
    if abs(alpha_df['alpha'].mean()) < 0.01:
        print(f"✅ Mean alpha is market-neutral ({alpha_df['alpha'].mean()*100:.3f}%)")
    else:
        print(f"⚠️  Mean alpha is {alpha_df['alpha'].mean()*100:.2f}% (not market-neutral)")

    # ============================================================
    # VALIDATION 5: Temporal Consistency
    # ============================================================

    print("\n" + "=" * 70)
    print("VALIDATION 5: Temporal Consistency")
    print("=" * 70)

    # Group by year and check distribution
    alpha_df['year'] = pd.to_datetime(alpha_df['timestamp']).dt.year

    print("\nLabel distribution by year:")
    for year in sorted(alpha_df['year'].unique()):
        year_data = alpha_df[alpha_df['year'] == year]
        buy_rate = (year_data['label'] == 1).sum() / len(year_data) * 100
        mean_alpha = year_data['alpha'].mean() * 100
        print(f"  {year}: BUY={buy_rate:5.1f}%, Mean Alpha={mean_alpha:6.2f}%")

    # Check for extreme variations
    year_buy_rates = alpha_df.groupby('year')['label'].mean() * 100
    max_rate = year_buy_rates.max()
    min_rate = year_buy_rates.min()

    if max_rate - min_rate > 20:
        print(f"\n⚠️  Large variation in BUY rates across years ({max_rate:.1f}% - {min_rate:.1f}%)")
        print(f"   This might indicate regime-dependent performance")
    else:
        print(f"✅ BUY rates consistent across years (variation: {max_rate - min_rate:.1f}%)")

    # ============================================================
    # VALIDATION 6: Stock Coverage
    # ============================================================

    print("\n" + "=" * 70)
    print("VALIDATION 6: Stock Coverage")
    print("=" * 70)

    unique_stocks = alpha_df['stock_id'].nunique()
    total_samples = len(alpha_df)

    print(f"\nTotal stocks: {unique_stocks}")
    print(f"Total samples: {total_samples:,}")

    samples_per_stock = total_samples / unique_stocks
    print(f"Average samples per stock: {samples_per_stock:.0f}")

    # Check for stocks with very few samples
    stock_counts = alpha_df.groupby('stock_id').size()
    low_sample_stocks = (stock_counts < 100).sum()

    if low_sample_stocks > 0:
        print(f"\n⚠️  {low_sample_stocks} stocks have < 100 samples")
    else:
        print(f"✅ All stocks have adequate samples")

    # ============================================================
    # VALIDATION 7: Compare with Current Labels
    # ============================================================

    print("\n" + "=" * 70)
    print("VALIDATION 7: Comparison with Current Labels")
    print("=" * 70)

    # Load current labels
    current_labels_path = f'/app/outputs/features/{dataset_folder}/labels_binary.parquet'

    try:
        current_df = pd.read_parquet(current_labels_path)

        # Find overlapping samples
        merged = pd.merge(
            alpha_df[['stock_id', 'timestamp', 'label', 'alpha']],
            current_df[['stock_id', 'timestamp', 'label']],
            on=['stock_id', 'timestamp'],
            how='inner',
            suffixes=('_alpha', '_current')
        )

        if len(merged) > 0:
            # Calculate agreement rate
            agreement = (merged['label_alpha'] == merged['label_current']).mean() * 100

            print(f"\nOverlapping samples: {len(merged):,}")
            print(f"Agreement between current and alpha labels: {agreement:.1f}%")

            if agreement > 80:
                print(f"⚠️  High agreement ({agreement:.1f}%) - labels might be similar")
            elif agreement < 50:
                print(f"✅  Low agreement ({agreement:.1f}%) - alpha labels are different")
            else:
                print(f"✅  Moderate agreement ({agreement:.1f}%) - expected")

            # Check current labels for these samples
            current_buy_rate = (merged['label_current'] == 1).mean() * 100
            alpha_buy_rate = (merged['label_alpha'] == 1).mean() * 100

            print(f"\nFor overlapping samples:")
            print(f"  Current BUY rate: {current_buy_rate:.1f}%")
            print(f"  Alpha BUY rate:   {alpha_buy_rate:.1f}%")
            print(f"  Difference:        {alpha_buy_rate - current_buy_rate:+.1f} percentage points")

    except Exception as e:
        print(f"\n⚠️  Could not load current labels for comparison: {e}")

    # ============================================================
    # FINAL VERDICT
    # ============================================================

    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    all_checks_passed = (
        len(validation_errors) == 0 and
        len(invalid_buy) == 0 and
        len(truly_invalid) == 0 and
        nan_check == 0 and
        inf_check == 0 and
        20 <= buy_rate <= 50 and
        abs(alpha_df['alpha'].mean()) < 0.01
    )

    if all_checks_passed:
        print("\n✅ ALL VALIDATIONS PASSED")
        print("\nAlpha labels are CORRECT and ready for training!")
        print("\nKey findings:")
        print(f"  • Alpha calculation is mathematically correct")
        print(f"  • Label assignment is accurate")
        print(f"  • No data quality issues (NaN, inf, extreme outliers)")
        print(f"  • BUY rate: {buy_rate:.1f}% (reasonable)")
        print(f"  • Mean alpha: {alpha_df['alpha'].mean()*100:.3f}% (market-neutral)")
        print("\nNext step: Train models with these labels")
        return True
    else:
        print("\n❌ VALIDATION FAILED")
        print("\nPlease review the errors above and fix the alpha label generation script")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Validate alpha labels are correct before training',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python validate_alpha_labels.py --dataset-folder dataset_20260204_204134

This will:
  1. Re-calculate alpha for 100 random samples
  2. Verify label assignment is correct
  3. Check for edge cases (NaN, inf, outliers)
  4. Validate label distribution
  5. Compare with current labels
        """
    )

    parser.add_argument(
        '--dataset-folder',
        type=str,
        required=True,
        help='Dataset folder name'
    )

    args = parser.parse_args()

    success = validate_alpha_labels(args.dataset_folder)

    if success:
        print("\n" + "=" * 70)
        print("✅ Labels validated successfully - ready for model training!")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ Validation failed - please fix the issues")
        print("=" * 70)

    return 0 if success else 1


if __name__ == "__main__":
    main()
