#!/usr/bin/env python3
"""
Feature Engineering Pipeline

This script:
1. Connects to the database
2. Fetches price data for all tracked stocks
3. Engineers 60+ features
4. Saves to parquet files for training

Usage:
    python scripts/create_features.py --config configs/default.yaml
    python scripts/create_features.py --config configs/default.yaml --stocks AAPL,MSFT,GOOGL
    python scripts/create_features.py --config configs/default.yaml --lookback 500
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path (for imports)
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Import config system
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml_framework.config import load_config

# Import your existing services
from app.services.technical_indicators import TechnicalIndicators
from app.services.chart_patterns import ChartPatternDetector
from app.services.candlestick_patterns import CandlestickPatternDetector
from app.services.market_regime import MarketRegimeService
from app.services.volume_analyzer import VolumeAnalyzer


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Feature Engineering Pipeline for ML Training',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--config',
        type=str,
        default='configs/default.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--stocks',
        type=str,
        default=None,
        help='Comma-separated list of stock symbols (overrides config)'
    )
    parser.add_argument(
        '--lookback',
        type=int,
        default=None,
        help='Number of days to look back (overrides config)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for features (overrides config)'
    )
    return parser.parse_args()


def get_stock_prices(stock_id: int, engine, timeframe: str = '1d',
                     lookback_days: int = 200) -> pd.DataFrame:
    """
    Fetch price data for a stock

    Args:
        stock_id: Stock ID
        engine: Database engine
        timeframe: '1d' for daily, '1h' for hourly
        lookback_days: Number of days to look back

    Returns:
        DataFrame with OHLCV data
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)

    query = text("""
        SELECT timestamp, open, high, low, close, volume
        FROM stock_prices
        WHERE stock_id = :stock_id
          AND timeframe = :timeframe
          AND timestamp >= :start_date
          AND timestamp <= :end_date
        ORDER BY timestamp ASC
    """)

    df = pd.read_sql(
        query,
        engine,
        params={
            'stock_id': stock_id,
            'timeframe': timeframe,
            'start_date': start_date,
            'end_date': end_date
        }
    )

    if df.empty:
        return pd.DataFrame()

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.set_index('timestamp')


def engineer_features(df: pd.DataFrame, stock_id: int, engine) -> pd.DataFrame:
    """
    Engineer features for a single stock

    Args:
        df: Price data
        stock_id: Stock ID
        engine: Database engine

    Returns:
        DataFrame with features
    """
    if df.empty or len(df) < 50:
        return pd.DataFrame()

    # Initialize services
    tech_indicators = TechnicalIndicators()
    pattern_detector = ChartPatternDetector()
    candlestick_detector = CandlestickPatternDetector()
    regime_service = MarketRegimeService()
    volume_analyzer = VolumeAnalyzer()

    features = pd.DataFrame(index=df.index)

    # Basic price features
    features['stock_id'] = stock_id
    features['returns'] = df['close'].pct_change()
    features['volume'] = df['volume']
    features['volume_change'] = df['volume'].pct_change()

    # Technical indicators
    indicators = tech_indicators.calculate_all(df)
    for col in indicators.columns:
        features[col] = indicators[col]

    # Chart patterns
    patterns = pattern_detector.detect_patterns(df)
    for pattern_name in pattern_detector.PATTERN_TYPES:
        if pattern_name in patterns.columns:
            features[f'pattern_{pattern_name}'] = patterns[pattern_name]

    # Candlestick patterns
    candlestick_patterns = candlestick_detector.detect_patterns(df)
    for pattern_name in candlestick_detector.PATTERN_TYPES:
        if pattern_name in candlestick_patterns.columns:
            features[f'candle_{pattern_name}'] = candlestick_patterns[pattern_name]

    # Market regime
    regime = regime_service.detect_regime(df)
    features['regime'] = regime['regime']

    # Volume analysis
    volume_features = volume_analyzer.analyze_volume(df)
    for col in volume_features.columns:
        features[f'volume_{col}'] = volume_features[col]

    return features.dropna()


def main():
    """Main feature engineering pipeline"""
    args = parse_args()

    # Load configuration
    config = load_config(args.config)

    # Apply CLI overrides
    stocks = args.stocks.split(',') if args.stocks else config.data.get('stocks', [])
    lookback_days = args.lookback if args.lookback else config.data.get('lookback_days', 200)
    output_dir = Path(args.output_dir) if args.output_dir else Path(config.data.get('features_dir', 'data/features'))

    print("=" * 70)
    print(" " * 20)
    print("Feature Engineering Pipeline")
    print(" " * 20)
    print("=" * 70)

    # Database connection
    database_url = os.getenv('DATABASE_URL', config.data.get('database_url',
        'postgresql://stockuser:stockpass@db:5432/stockanalyzer'))
    engine = create_engine(database_url)

    # Get stocks to process
    if stocks:
        # Use provided stock symbols
        query = text("SELECT id, symbol FROM stocks WHERE symbol = ANY(:symbols)")
        stocks_df = pd.read_sql(query, engine, params={'symbols': stocks})
    else:
        # Get all active stocks
        query = text("""
            SELECT id, symbol FROM stocks
            WHERE is_active = true
            ORDER BY symbol
        """)
        stocks_df = pd.read_sql(query, engine)

    if stocks_df.empty:
        print("❌ No stocks found!")
        return

    print(f"\n📊 Processing {len(stocks_df)} stocks")
    print(f"⏱️  Lookback period: {lookback_days} days")
    print(f"💾 Output directory: {output_dir}\n")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process each stock
    all_features = []

    for _, stock in tqdm(stocks_df.iterrows(), total=len(stocks_df), desc="Processing stocks"):
        stock_id = stock['id']
        symbol = stock['symbol']

        # Fetch prices
        prices = get_stock_prices(stock_id, engine, lookback_days=lookback_days)

        if prices.empty:
            print(f"⚠️  No data for {symbol}")
            continue

        # Engineer features
        features = engineer_features(prices, stock_id, engine)

        if not features.empty:
            features['symbol'] = symbol
            all_features.append(features)
            print(f"✅ {symbol}: {len(features)} features")
        else:
            print(f"⚠️  {symbol}: Insufficient data for features")

    if not all_features:
        print("\n❌ No features generated!")
        return

    # Combine all features
    print("\n" + "=" * 70)
    print("COMBINING FEATURES")
    print("=" * 70)

    combined = pd.concat(all_features, axis=0)

    # Save to parquet
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'features_{timestamp}.parquet'

    combined.to_parquet(output_file, index=True)

    print(f"\n✅ Features saved to: {output_file}")
    print(f"   Total samples: {len(combined):,}")
    print(f"   Total features: {len(combined.columns) - 2}")  # Exclude stock_id and symbol

    print("\n" + "=" * 70)
    print("✅ FEATURE ENGINEERING COMPLETE!")
    print("=" * 70)

    print("\nNext steps:")
    print("1. Run: python scripts/create_labels.py")
    print("2. Then: python train.py")


if __name__ == "__main__":
    main()
