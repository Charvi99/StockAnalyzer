"""
Feature Engineering Pipeline for ML Training (OPTIMIZED VERSION)

This script creates features for EACH historical date efficiently.
Calculates indicators ONCE per stock, then slices for each date.

Usage:
    python 01c_feature_engineering_optimized.py
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


def engineer_features_for_stock(stock_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Engineer features for all dates in range for a stock (OPTIMIZED)

    Calculates indicators ONCE, then slices for each date.

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

        # Filter to our date range
        indicators_filtered = indicators.loc[start_date:end_date]

        if indicators_filtered.empty:
            return None

        # Build feature rows for each date
        feature_rows = []

        for timestamp, row in indicators_filtered.iterrows():
            # Handle NaN values
            def safe_float(val, default=0.0):
                return float(val) if not pd.isna(val) else default

            features = {
                'stock_id': stock_id,
                'timestamp': timestamp,
                # RSI (3 features)
                'rsi': safe_float(row.get('rsi'), 50.0),
                'rsi_overbought': int(row.get('rsi', 50) > 70) if not pd.isna(row.get('rsi')) else 0,
                'rsi_oversold': int(row.get('rsi', 50) < 30) if not pd.isna(row.get('rsi')) else 0,
                # MACD (3 features)
                'macd': safe_float(row.get('macd')),
                'macd_signal': safe_float(row.get('macd_signal')),
                'macd_histogram': safe_float(row.get('macd_histogram')),
                # Bollinger Bands (3 features)
                'bb_upper': safe_float(row.get('bb_upper')),
                'bb_lower': safe_float(row.get('bb_lower')),
                'bb_position': safe_float(row.get('bb_position'), 0.5),
                # ATR (2 features)
                'atr': safe_float(row.get('atr')),
                'atr_ratio': safe_float(row.get('atr') / row.get('close', 1)) if not pd.isna(row.get('atr')) and not pd.isna(row.get('close')) else 0.0,
                # Moving Averages (3 features)
                'sma_20': safe_float(row.get('sma_20')),
                'sma_50': safe_float(row.get('sma_50')),
                'sma_200': safe_float(row.get('sma_200')),
                # Volume (1 feature)
                'volume_ratio': safe_float(row.get('volume_ratio'), 1.0),
            }

            # Add price history features
            current_close = safe_float(row.get('close', 0))

            # Lagged returns (5 features)
            for days in [1, 3, 5, 10, 20]:
                if len(indicators_filtered) > 0 and timestamp in indicators_filtered.index:
                    # Get position of current row
                    current_pos = indicators_filtered.index.get_loc(timestamp)
                    if current_pos > days:
                        past_close = indicators_filtered.iloc[current_pos - days]['close']
                        ret = (current_close - past_close) / past_close if past_close > 0 else 0.0
                        features[f'return_{days}d'] = float(ret)
                    else:
                        features[f'return_{days}d'] = 0.0
                else:
                    features[f'return_{days}d'] = 0.0

            # Rolling volatility (3 features)
            for period in [10, 20, 50]:
                if len(indicators_filtered) > 0:
                    current_pos = indicators_filtered.index.get_loc(timestamp)
                    if current_pos >= period:
                        # Calculate volatility from recent returns
                        recent_prices = indicators_filtered.iloc[current_pos-period:current_pos]['close']
                        returns = recent_prices.pct_change().dropna()
                        if len(returns) > 0:
                            vol = returns.std()
                            features[f'volatility_{period}d'] = float(vol)
                        else:
                            features[f'volatility_{period}d'] = 0.0
                    else:
                        features[f'volatility_{period}d'] = 0.0
                else:
                    features[f'volatility_{period}d'] = 0.0

            # Volume surge (1 feature)
            if len(indicators_filtered) > 0 and 'volume' in indicators_filtered.columns:
                current_pos = indicators_filtered.index.get_loc(timestamp)
                if current_pos >= 20:
                    avg_volume = indicators_filtered.iloc[current_pos-20:current_pos]['volume'].mean()
                    current_volume = row.get('volume', avg_volume)
                    features['volume_surge'] = int(current_volume > avg_volume * 1.5) if avg_volume > 0 else 0
                else:
                    features['volume_surge'] = 0
            else:
                features['volume_surge'] = 0

            feature_rows.append(features)

        if not feature_rows:
            return None

        return pd.DataFrame(feature_rows)

    except Exception as e:
        # Silently skip stocks with errors
        return None


def main():
    """Main feature engineering pipeline"""
    print("=" * 80)
    print("StockAnalyzer ML - Feature Engineering Pipeline (OPTIMIZED)")
    print("=" * 80)

    # Create outputs directory
    outputs_dir = Path('/app/outputs/features')
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Get date range (same as labels)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)  # 2 years

    # Get all tracked stocks
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT id FROM stocks WHERE is_tracked = true"))
        stock_ids = [row[0] for row in result]
    finally:
        db.close()

    print(f"\n📊 Processing {len(stock_ids)} stocks")
    print(f"📅 Date range: {start_date.date()} to {end_date.date()}")
    print(f"⏱️  Estimated time: 5-15 minutes")

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

    # Save to parquet
    output_file = outputs_dir / f'features_{datetime.now().strftime("%Y%m%d_%H%M%S")}.parquet'
    df.to_parquet(output_file, index=False)

    print(f"\n✅ Saved {len(df)} feature rows to {output_file}")
    print(f"📊 Features per row: {len(df.columns) - 2}")  # -2 for stock_id and timestamp
    print(f"📁 Output directory: {outputs_dir}")
    print(f"📅 Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"📈 Stocks: {df['stock_id'].nunique()}")
    if skipped_count > 0:
        print(f"⚠️  Skipped {skipped_count} stocks due to errors")
    print(f"\n✅ READY TO TRAIN!")
    print(f"\nNext step: cd /app && python train.py")


if __name__ == "__main__":
    main()
