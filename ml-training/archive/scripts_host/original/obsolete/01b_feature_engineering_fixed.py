"""
Feature Engineering Pipeline for ML Training (FIXED VERSION)

This script creates features for EACH historical date, not just once per stock.
Features are aligned with labels for proper training.

Usage:
    python 01b_feature_engineering_fixed.py
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

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
        DataFrame with OHLCV data
    """
    # Need extra history for indicators (200 days)
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


def calculate_features_for_row(df: pd.DataFrame, current_idx: int) -> Dict:
    """
    Calculate features for a single row (date) using historical data up to that point

    Args:
        df: DataFrame with price history (indexed by timestamp)
        current_idx: Index of current row to calculate features for

    Returns:
        Dict with features
    """
    try:
        # Get historical data up to current point
        historical_df = df.iloc[:current_idx+1].copy()

        if len(historical_df) < 60:
            return None

        # Calculate indicators
        indicators = TechnicalIndicators.calculate_all_indicators(historical_df)

        if indicators is None or indicators.empty:
            return None

        # Get latest values
        latest = indicators.iloc[-1]

        # Features (simplified - just technical for now)
        features = {
            'rsi': float(latest['rsi']) if 'rsi' in latest and not pd.isna(latest['rsi']) else 50.0,
            'rsi_overbought': int(latest['rsi'] > 70) if 'rsi' in latest and not pd.isna(latest['rsi']) else 0,
            'rsi_oversold': int(latest['rsi'] < 30) if 'rsi' in latest and not pd.isna(latest['rsi']) else 0,
            'macd': float(latest['macd']) if 'macd' in latest and not pd.isna(latest['macd']) else 0.0,
            'macd_signal': float(latest['macd_signal']) if 'macd_signal' in latest and not pd.isna(latest['macd_signal']) else 0.0,
            'macd_histogram': float(latest['macd_histogram']) if 'macd_histogram' in latest and not pd.isna(latest['macd_histogram']) else 0.0,
            'bb_upper': float(latest['bb_upper']) if 'bb_upper' in latest and not pd.isna(latest['bb_upper']) else 0.0,
            'bb_lower': float(latest['bb_lower']) if 'bb_lower' in latest and not pd.isna(latest['bb_lower']) else 0.0,
            'bb_position': float(latest['bb_position']) if 'bb_position' in latest and not pd.isna(latest['bb_position']) else 0.5,
            'atr': float(latest['atr']) if 'atr' in latest and not pd.isna(latest['atr']) else 0.0,
            'sma_20': float(latest['sma_20']) if 'sma_20' in latest and not pd.isna(latest['sma_20']) else 0.0,
            'sma_50': float(latest['sma_50']) if 'sma_50' in latest and not pd.isna(latest['sma_50']) else 0.0,
            'sma_200': float(latest['sma_200']) if 'sma_200' in latest and not pd.isna(latest['sma_200']) else 0.0,
            'volume_ratio': float(latest['volume_ratio']) if 'volume_ratio' in latest and not pd.isna(latest['volume_ratio']) else 1.0,
        }

        # Add price-based features
        current_close = historical_df['close'].iloc[-1]

        # Lagged returns
        for days in [1, 3, 5, 10, 20]:
            if len(historical_df) > days:
                past_close = historical_df['close'].iloc[-days-1]
                ret = (current_close - past_close) / past_close
                features[f'return_{days}d'] = float(ret)
            else:
                features[f'return_{days}d'] = 0.0

        # Rolling volatility
        for period in [10, 20, 50]:
            if len(historical_df) > period:
                returns = historical_df['close'].pct_change().dropna()
                vol = returns.tail(period).std()
                features[f'volatility_{period}d'] = float(vol)
            else:
                features[f'volatility_{period}d'] = 0.0

        return features

    except Exception as e:
        return None


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
    # Fetch price data
    df = get_stock_prices(stock_id, start_date, end_date)

    if df is None or len(df) < 60:
        return None

    # Filter to date range
    df_filtered = df.loc[start_date:end_date]

    if len(df_filtered) == 0:
        return None

    # Calculate features for each date
    all_features = []

    # Get the index in the full df for each filtered date
    for date in tqdm(df_filtered.index, desc=f"Stock {stock_id}", leave=False):
        # Find position of this date in full df
        idx = df.index.get_loc(date)

        # Calculate features using all data up to this point
        features = calculate_features_for_row(df, idx)

        if features:
            features['stock_id'] = stock_id
            features['timestamp'] = date
            all_features.append(features)

    if not all_features:
        return None

    return pd.DataFrame(all_features)


def main():
    """Main feature engineering pipeline"""
    print("=" * 80)
    print("StockAnalyzer ML - Feature Engineering Pipeline (FIXED)")
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


if __name__ == "__main__":
    main()
