"""
Feature Engineering Pipeline with Auto Date Detection

This script automatically detects the date range from the database
and creates features for ML training.
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Import your existing services
from app.services.technical_indicators import TechnicalIndicators

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass123@database:5432/stock_analyzer')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_data_date_range() -> tuple[datetime, datetime]:
    """
    Detect the actual date range from the database

    Returns:
        (min_date, max_date) tuple
    """
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT
                MIN(timestamp) as min_date,
                MAX(timestamp) as max_date
            FROM stock_prices
            WHERE timeframe = '1d'
        """))
        row = result.fetchone()
        if row and row[0] and row[1]:
            return row[0], row[1]
        return None, None
    finally:
        db.close()


def get_stock_prices(stock_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Fetch price data for a stock with extra history for indicators

    Args:
        stock_id: Stock ID
        start_date: Start date for features
        end_date: End date for features

    Returns:
        DataFrame with OHLCV data (indexed by timestamp)
    """
    # Need extra history for indicators (300 days to be safe)
    query_start = start_date - timedelta(days=300)

    query = text("""
        SELECT timestamp, open, high, low, close, volume
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
        params={'stock_id': stock_id, 'start_date': query_start, 'end_date': end_date}
    )

    if df.empty:
        return None

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    return df


def create_labels(df: pd.DataFrame, stock_id: int) -> pd.DataFrame:
    """
    Create labels for swing trading strategy

    For each day, determine if price hits +3% before -2% within next 20 days

    Args:
        df: DataFrame with price data
        stock_id: Stock ID

    Returns:
        DataFrame with labels
    """
    labels = []

    for i in range(len(df) - 20):  # Need 20 days lookahead
        current_price = df['close'].iloc[i]
        max_upside = 0
        max_drawdown = 0
        label = 0  # Default: didn't hit target

        # Look ahead up to 20 days
        for j in range(i + 1, min(i + 21, len(df))):
            future_price = df['close'].iloc[j]
            upside = (future_price - current_price) / current_price
            drawdown = (future_price - current_price) / current_price

            max_upside = max(max_upside, upside)
            max_drawdown = min(max_drawdown, drawdown)

            # Check if we hit target (+3%)
            if upside >= 0.03:
                label = 1
                break
            # Check if we hit stop loss (-2%)
            if drawdown <= -0.02:
                break

        labels.append({
            'stock_id': stock_id,
            'timestamp': df.index[i],
            'label': label,
            'max_upside': max_upside,
            'max_drawdown': max_drawdown
        })

    return pd.DataFrame(labels)


def engineer_features_for_stock(stock_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Engineer features for all dates in range for a stock

    Args:
        stock_id: Stock ID
        start_date: Start date
        end_date: End date

    Returns:
        DataFrame with features for each date
    """
    # Fetch ALL price data at once
    df = get_stock_prices(stock_id, start_date - timedelta(days=50), end_date + timedelta(days=30))

    if df is None or len(df) < 60:
        return None

    # Calculate ALL indicators ONCE for the entire dataset
    try:
        indicators = TechnicalIndicators.calculate_all_indicators(df)

        if indicators is None or indicators.empty:
            return None

        # Create labels
        labels = create_labels(indicators, stock_id)

        if labels.empty:
            return None

        # Add features to labels - ONLY NUMERIC FEATURES
        # Filter out string/object columns (signals, reasons, etc.)
        feature_cols = [
            col for col in indicators.columns
            if col not in ['open', 'high', 'low', 'close', 'volume']
            and pd.api.types.is_numeric_dtype(indicators[col])
        ]

        feature_rows = []
        for idx, label_row in labels.iterrows():
            timestamp = label_row['timestamp']
            if timestamp in indicators.index:
                row_data = {
                    'stock_id': stock_id,
                    'timestamp': timestamp,
                    'label': label_row['label'],
                    'max_upside': label_row['max_upside'],
                    'max_drawdown': label_row['max_drawdown']
                }

                # Add all NUMERIC features at this timestamp
                for col in feature_cols:
                    if col in indicators.columns:
                        row_data[col] = indicators.loc[timestamp, col]

                feature_rows.append(row_data)

        if not feature_rows:
            return None

        return pd.DataFrame(feature_rows)

    except Exception as e:
        # Silently skip stocks with errors
        return None


def main():
    """Main feature engineering pipeline"""
    print("=" * 80)
    print("StockAnalyzer ML - Feature Engineering (Auto Date Detection)")
    print("=" * 80)

    # Create outputs directory
    outputs_dir = Path('/app/outputs/features')
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Detect date range from database
    min_date, max_date = get_data_date_range()

    if min_date is None or max_date is None:
        print("❌ No data found in database!")
        return

    print(f"\n📅 Detected data range: {min_date} to {max_date}")

    # Add buffer for indicators and labels
    start_date = min_date + timedelta(days=60)  # Need 60 days for indicators to warm up
    end_date = max_date - timedelta(days=20)  # Need 20 days for label calculation

    print(f"📅 Feature range: {start_date} to {end_date}")

    if start_date >= end_date:
        print("❌ Not enough data for feature engineering!")
        print(f"   Need at least 80 days of data, have {(max_date - min_date).days} days")
        return

    # Get all tracked stocks
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT id FROM stocks WHERE is_tracked = true"))
        stock_ids = [row[0] for row in result]
    finally:
        db.close()

    print(f"\n📊 Processing {len(stock_ids)} stocks")
    print(f"⏱️  Estimated time: < 1 minute")

    # Engineer features for each stock
    all_features = []
    skipped_count = 0

    for stock_id in tqdm(stock_ids, desc="Processing stocks"):
        try:
            features_df = engineer_features_for_stock(stock_id, start_date, end_date)

            if features_df is not None and not features_df.empty:
                all_features.append(features_df)
            else:
                skipped_count += 1
        except Exception as e:
            skipped_count += 1

    # Combine all features
    if not all_features:
        print("\n❌ No features created!")
        return

    df = pd.concat(all_features, ignore_index=True)

    # Separate features and labels
    label_cols = ['stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown']
    feature_cols = [col for col in df.columns if col not in label_cols]

    # Save features (without label columns)
    output_file = outputs_dir / f'features_{datetime.now().strftime("%Y%m%d_%H%M%S")}.parquet'
    df[['stock_id', 'timestamp'] + feature_cols].to_parquet(output_file, index=False)

    # Save labels separately
    labels_file = outputs_dir / f'labels_{datetime.now().strftime("%Y%m%d_%H%M%S")}.parquet'
    df[label_cols].to_parquet(labels_file, index=False)

    print(f"\n✅ Saved {len(df)} feature rows to {output_file}")
    print(f"📊 Features per row: {len(feature_cols)}")
    print(f"📁 Output directory: {outputs_dir}")
    print(f"📅 Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"📈 Stocks: {df['stock_id'].nunique()}")
    print(f"📊 Positive labels (hit +3%): {df['label'].sum()} ({100*df['label'].mean():.1f}%)")
    if skipped_count > 0:
        print(f"⚠️  Skipped {skipped_count} stocks due to errors")
    print(f"\n✅ READY TO TRAIN!")
    print(f"\nNext step: docker-compose run --rm ml-training python /app/train.py")


if __name__ == "__main__":
    main()
