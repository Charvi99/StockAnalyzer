"""
Feature Engineering Pipeline with Log Returns

This script adds log returns and other normalized features that improve ML performance.
Log returns are better because:
1. They are normally distributed (better for ML models)
2. They are additive over time
3. They are symmetric (gains and losses have same magnitude)
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


def add_log_returns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add log returns and other normalized features

    Args:
        df: DataFrame with OHLCV data

    Returns:
        DataFrame with log returns added
    """
    df = df.copy()

    # Log returns (better than simple returns)
    # log_return = ln(price_t / price_t-1)
    df['log_return_1d'] = np.log(df['close'] / df['close'].shift(1))

    # Multi-period log returns
    df['log_return_5d'] = np.log(df['close'] / df['close'].shift(5))
    df['log_return_10d'] = np.log(df['close'] / df['close'].shift(10))
    df['log_return_20d'] = np.log(df['close'] / df['close'].shift(20))

    # Volatility (std of log returns) - important feature
    df['volatility_10d'] = df['log_return_1d'].rolling(10).std()
    df['volatility_20d'] = df['log_return_1d'].rolling(20).std()
    df['volatility_60d'] = df['log_return_1d'].rolling(60).std()

    # Price momentum (using log returns)
    df['momentum_5d'] = df['log_return_5d']
    df['momentum_10d'] = df['log_return_10d']
    df['momentum_20d'] = df['log_return_20d']

    # Relative strength vs recent price range
    df['price_position_20d'] = (df['close'] - df['close'].rolling(20).min()) / \
                                (df['close'].rolling(20).max() - df['close'].rolling(20).min())

    # Volume features (log volume is more normal)
    df['log_volume'] = np.log(df['volume'] + 1)  # +1 to avoid log(0)
    df['volume_change'] = df['log_volume'] - df['log_volume'].shift(1)

    # Volume volatility
    df['volume_volatility_10d'] = df['volume_change'].rolling(10).std()

    # Price range features (intraday volatility)
    df['daily_range'] = (df['high'] - df['low']) / df['close']
    df['daily_range_mean_10d'] = df['daily_range'].rolling(10).mean()

    # Gap features (overnight movement)
    df['gap'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
    df['gap_up_5d_sum'] = (df['gap'] > 0).rolling(5).sum()
    df['gap_down_5d_sum'] = (df['gap'] < 0).rolling(5).sum()

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

    # Calculate ALL indicators
    try:
        # 1. Add technical indicators
        indicators = TechnicalIndicators.calculate_all_indicators(df)

        if indicators is None or indicators.empty:
            return None

        # 2. Add log returns and normalized features
        indicators = add_log_returns(indicators)

        # 3. Create labels
        labels = create_labels(indicators, stock_id)

        if labels.empty:
            return None

        # 4. Add features to labels - ONLY NUMERIC FEATURES
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
    print("StockAnalyzer ML - Feature Engineering with Log Returns")
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
    print(f"⏱️  Estimated time: < 2 minutes")
    print(f"✨ Added features: log returns, volatility, momentum, price position, volume")

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
    features_df = df[['stock_id', 'timestamp'] + feature_cols]
    features_file = outputs_dir / f'features_{datetime.now().strftime("%Y%m%d_%H%M%S")}.parquet'
    features_df.to_parquet(features_file, index=False)

    # Save labels
    labels_df = df[label_cols]
    labels_file = outputs_dir / f'labels_{datetime.now().strftime("%Y%m%d_%H%M%S")}.parquet'
    labels_df.to_parquet(labels_file, index=False)

    print(f"\n{'='*80}")
    print(f"✅ Feature Engineering Complete!")
    print(f"{'='*80}")
    print(f"\n📊 Results:")
    print(f"   Total samples: {len(df):,}")
    print(f"   Features per sample: {len(feature_cols)}")
    print(f"   Skipped stocks: {skipped_count}")
    print(f"   Positive class: {df['label'].mean()*100:.1f}%")
    print(f"\n✨ Key Log Return Features:")
    print(f"   - log_return_1d: 1-day log return")
    print(f"   - log_return_5d: 5-day log return")
    print(f"   - log_return_10d: 10-day log return")
    print(f"   - log_return_20d: 20-day log return")
    print(f"   - volatility_10d/20d/60d: Rolling volatility")
    print(f"   - momentum_5d/10d/20d: Price momentum")
    print(f"   - price_position_20d: Relative price position")
    print(f"   - log_volume: Log-transformed volume")
    print(f"   - gap: Overnight gap (open vs prev close)")
    print(f"\n📁 Saved to:")
    print(f"   Features: {features_file}")
    print(f"   Labels: {labels_file}")
    print(f"\n✅ Ready for ML training!")


if __name__ == "__main__":
    main()
