"""
Create labels using SIMPLE ALPHA threshold (NOT quantile-based)

Simple Alpha: label = 1 if stock outperforms SPY by X% (e.g., 2%)
Alpha-Quantile: label = 1 if stock is in top 30% of alpha performers

This creates TRUE alpha labels with balanced classes, not extreme quantile selection.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass123@database:5432/stock_analyzer')
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
    return df


def fetch_spy_prices(start_date: datetime, end_date: datetime):
    """Fetch SPY price data"""
    # SPY stock_id is typically 1 or can be found by symbol
    query = text("""
        SELECT timestamp, close
        FROM stock_prices
        WHERE stock_id = (SELECT id FROM stocks WHERE symbol = 'SPY' LIMIT 1)
          AND timeframe = '1d'
          AND timestamp >= :start_date
          AND timestamp <= :end_date
        ORDER BY timestamp ASC
    """)

    with engine.connect() as conn:
        df = pd.read_sql(
            query,
            conn,
            params={'start_date': start_date, 'end_date': end_date}
        )
    return df


def get_all_stocks():
    """Get all tracked stocks"""
    query = text("""
        SELECT id, symbol
        FROM stocks
        WHERE is_tracked = true
        ORDER BY symbol
    """)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df


def calculate_forward_returns(prices_df: pd.DataFrame, forward_days: int = 20) -> pd.DataFrame:
    """Calculate forward returns for each date"""
    df = prices_df.copy()
    df['forward_close'] = df['close'].shift(-forward_days)
    df['forward_return'] = (df['forward_close'] - df['close']) / df['close']
    return df


def create_simple_alpha_labels(
    start_date: datetime,
    end_date: datetime,
    forward_days: int = 20,
    alpha_threshold: float = 0.02  # 2% outperformance
):
    """
    Create labels using SIMPLE ALPHA threshold.

    Label = 1 if stock_return - spy_return > alpha_threshold
    Label = 0 otherwise

    This is DIFFERENT from alpha-quantile which uses percentile-based threshold.
    """
    print(f"Creating SIMPLE ALPHA labels (threshold={alpha_threshold:.1%}, {forward_days}d forward)")

    # Fetch SPY data once
    print("Fetching SPY data...")
    spy_df = fetch_spy_prices(start_date, end_date)
    spy_df = calculate_forward_returns(spy_df, forward_days)
    spy_df = spy_df[['timestamp', 'forward_return']].rename(columns={'forward_return': 'spy_return'})

    # Get all stocks
    stocks_df = get_all_stocks()
    print(f"Processing {len(stocks_df)} stocks...")

    all_labels = []

    for idx, row in stocks_df.iterrows():
        stock_id = row['id']
        symbol = row['symbol']

        if (idx + 1) % 50 == 0:
            print(f"  Processed {idx + 1}/{len(stocks_df)} stocks...")

        # Fetch stock prices
        prices_df = fetch_stock_prices(stock_id, start_date, end_date)

        if len(prices_df) < forward_days + 10:
            continue  # Skip if not enough data

        # Calculate forward returns
        prices_df = calculate_forward_returns(prices_df, forward_days)

        # Merge with SPY returns
        merged = pd.merge(
            prices_df[['timestamp', 'forward_return']],
            spy_df,
            on='timestamp',
            how='inner'
        )

        # Drop NaN values (last forward_days rows won't have forward_return)
        merged = merged.dropna()

        if len(merged) == 0:
            continue

        # Calculate alpha (stock return - SPY return)
        merged['alpha'] = merged['forward_return'] - merged['spy_return']

        # Create label: 1 if alpha > threshold, else 0
        merged['label'] = (merged['alpha'] > alpha_threshold).astype(int)

        # Add stock_id
        merged['stock_id'] = stock_id

        # Select columns
        labels_df = merged[['timestamp', 'stock_id', 'label', 'alpha', 'forward_return', 'spy_return']]
        all_labels.append(labels_df)

    # Combine all labels
    print("\nCombining labels...")
    final_df = pd.concat(all_labels, ignore_index=True)

    # Print statistics
    print("\n" + "="*70)
    print(f"SIMPLE ALPHA LABELS ({forward_days}d forward, threshold={alpha_threshold:.1%})")
    print("="*70)
    print(f"Total samples: {len(final_df):,}")
    print(f"\nLabel distribution:")
    print(final_df['label'].value_counts())
    print(f"\nLabel percentages:")
    print(final_df['label'].value_counts(normalize=True) * 100)

    buy_count = (final_df['label'] == 1).sum()
    buy_pct = buy_count / len(final_df) * 100
    print(f"\nBUY signals: {buy_count:,} ({buy_pct:.1f}%)")

    # Alpha statistics
    print(f"\nAlpha statistics:")
    print(final_df['alpha'].describe())

    # Threshold statistics
    threshold_count = (final_df['alpha'] > alpha_threshold).sum()
    print(f"\nSamples above threshold ({alpha_threshold:.1%}): {threshold_count:,} ({threshold_count/len(final_df)*100:.1f}%)")

    return final_df


def main():
    """Create labels with different simple alpha thresholds"""
    print("="*70)
    print("SIMPLE ALPHA LABEL CREATION")
    print("="*70)
    print("\nThis creates BALANCED alpha labels using FIXED thresholds.")
    print("Unlike alpha-quantile (top 30%), this identifies stocks that")
    print("consistently outperform SPY by a specific margin.")
    print("\n")

    # Date range (matching existing labels)
    start_date = datetime(2018, 1, 1)
    end_date = datetime(2026, 1, 31)

    # Test multiple thresholds
    thresholds = [0.01, 0.015, 0.02, 0.025, 0.03]  # 1%, 1.5%, 2%, 2.5%, 3%

    results = []

    for threshold in thresholds:
        print(f"\n{'='*70}")
        print(f"Testing threshold: {threshold:.1%}")
        print(f"{'='*70}\n")

        try:
            labels_df = create_simple_alpha_labels(
                start_date=start_date,
                end_date=end_date,
                forward_days=20,
                alpha_threshold=threshold
            )

            # Save labels
            output_file = f"/app/labels/labels_simple_alpha_{int(threshold*100)}pct.parquet"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            labels_df.to_parquet(output_file, index=False)

            buy_pct = (labels_df['label'] == 1).sum() / len(labels_df) * 100

            results.append({
                'threshold': f"{threshold:.1%}",
                'threshold_value': threshold,
                'total_samples': len(labels_df),
                'buy_count': (labels_df['label'] == 1).sum(),
                'buy_pct': buy_pct,
                'file': output_file
            })

            print(f"\n✅ Saved to: {output_file}")

        except Exception as e:
            print(f"\n❌ Error with threshold {threshold:.1%}: {e}")
            import traceback
            traceback.print_exc()

    # Summary table
    print("\n" + "="*70)
    print("SUMMARY: All Thresholds Tested")
    print("="*70)
    print()

    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))

    print("\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)
    print("\nFor balanced classes (~50% BUY), use threshold closest to 50% BUY rate.")
    print("For conservative approach (~35-40% BUY), use higher threshold (2-2.5%).")
    print("\nNext steps:")
    print("1. Choose threshold based on desired class balance")
    print("2. Update feature engineering to merge these labels")
    print("3. Train model with: --label-type simple_alpha_<threshold>pct")


if __name__ == "__main__":
    main()
