"""
Feature Engineering Pipeline for ML Training

This script:
1. Connects to the database
2. Fetches price data for all tracked stocks
3. Engineers 60+ features
4. Saves to parquet files for training

Usage:
    python 01_feature_engineering.py
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path (for imports)
sys.path.insert(0, '/backend')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Import your existing services
from app.services.technical_indicators import TechnicalIndicators
from app.services.chart_patterns import ChartPatternDetector
from app.services.candlestick_patterns import CandlestickPatternDetector
from app.services.market_regime import MarketRegimeService
from app.services.volume_analyzer import VolumeAnalyzer

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass@db:5432/stockanalyzer')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_stock_prices(stock_id: int, timeframe: str = '1d', lookback_days: int = 200) -> pd.DataFrame:
    """
    Fetch price data for a stock

    Args:
        stock_id: Stock ID
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
        params={'stock_id': stock_id, 'timeframe': timeframe, 'start_date': start_date, 'end_date': end_date}
    )

    if df.empty:
        return None

    # Convert timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    return df


def engineer_technical_features(df: pd.DataFrame) -> dict:
    """
    Extract technical indicator features (15 features)

    Args:
        df: DataFrame with OHLCV data

    Returns:
        Dict with 15 technical features
    """
    try:
        # Calculate all indicators using your existing service
        indicators = TechnicalIndicators.calculate_all_indicators(df)

        if indicators is None or indicators.empty:
            return None

        # Get latest values
        latest = indicators.iloc[-1]

        features = {
            # RSI (3 features)
            'rsi_value': float(latest['rsi']) if 'rsi' in latest else None,
            'rsi_overbought': int(latest['rsi'] > 70) if 'rsi' in latest else 0,
            'rsi_oversold': int(latest['rsi'] < 30) if 'rsi' in latest else 0,

            # MACD (3 features)
            'macd_value': float(latest['macd']) if 'macd' in latest else None,
            'macd_signal': float(latest['macd_signal']) if 'macd_signal' in latest else None,
            'macd_histogram': float(latest['macd_histogram']) if 'macd_histogram' in latest else None,

            # Bollinger Bands (3 features)
            'bb_upper': float(latest['bb_upper']) if 'bb_upper' in latest else None,
            'bb_lower': float(latest['bb_lower']) if 'bb_lower' in latest else None,
            'bb_position': float(latest['bb_position']) if 'bb_position' in latest else None,

            # ATR (2 features)
            'atr': float(latest['atr']) if 'atr' in latest else None,
            'atr_ratio': float(latest['atr'] / latest['close']) if 'atr' in latest and 'close' in latest else None,

            # Moving Averages (3 features)
            'sma_20': float(latest['sma_20']) if 'sma_20' in latest else None,
            'sma_50': float(latest['sma_50']) if 'sma_50' in latest else None,
            'sma_200': float(latest['sma_200']) if 'sma_200' in latest else None,

            # Volume (1 feature)
            'volume_ratio': float(latest['volume_ratio']) if 'volume_ratio' in latest else None,
        }

        return features

    except Exception as e:
        print(f"Error engineering technical features: {e}")
        return None


def engineer_pattern_features(df: pd.DataFrame, stock_id: int, db_session) -> dict:
    """
    Extract pattern features (14 features)

    Args:
        df: DataFrame with OHLCV data
        stock_id: Stock ID
        db_session: Database session

    Returns:
        Dict with 14 pattern features
    """
    features = {}

    # Default values
    default_pattern_features = {
        'chart_bullish_count': 0, 'chart_bearish_count': 0, 'chart_pattern_total': 0,
        'chart_max_confidence': 0, 'chart_avg_confidence': 0,
        'head_shoulders': 0, 'double_top': 0, 'double_bottom': 0,
        'cs_bullish_count': 0, 'cs_bearish_count': 0,
        'cs_doji': 0, 'cs_engulfing_bullish': 0, 'cs_engulfing_bearish': 0, 'cs_hammer': 0
    }

    # Ensure timestamp is index (required for pattern detectors)
    try:
        if 'timestamp' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            df = df.set_index('timestamp')
        elif df.index.name != 'timestamp':
            df.index.name = 'timestamp'
    except Exception as e:
        print(f"  Warning: Could not set timestamp as index: {e}")
        return default_pattern_features

    # Chart patterns (8 features)
    try:
        chart_detector = ChartPatternDetector(df.copy())
        chart_patterns = chart_detector.detect_all_patterns()

        # Count patterns
        bullish_patterns = [p for p in chart_patterns if p.get('signal') == 'bullish']
        bearish_patterns = [p for p in chart_patterns if p.get('signal') == 'bearish']

        features.update({
            'chart_bullish_count': len(bullish_patterns),
            'chart_bearish_count': len(bearish_patterns),
            'chart_pattern_total': len(chart_patterns),
            'chart_max_confidence': max([p.get('confidence_score', 0) for p in chart_patterns]) if chart_patterns else 0,
            'chart_avg_confidence': np.mean([p.get('confidence_score', 0) for p in chart_patterns]) if chart_patterns else 0,
            'head_shoulders': int(any(p.get('pattern_name') == 'Head and Shoulders' for p in chart_patterns)),
            'double_top': int(any(p.get('pattern_name') == 'Double Top' for p in chart_patterns)),
            'double_bottom': int(any(p.get('pattern_name') == 'Double Bottom' for p in chart_patterns)),
        })
    except Exception as e:
        # Silently use defaults (pattern detection is optional)
        features.update({k: 0 for k in [
            'chart_bullish_count', 'chart_bearish_count', 'chart_pattern_total',
            'chart_max_confidence', 'chart_avg_confidence',
            'head_shoulders', 'double_top', 'double_bottom'
        ]})

    # Candlestick patterns (6 features)
    try:
        cs_detector = CandlestickPatternDetector(df.copy())
        cs_patterns = cs_detector.detect_all_patterns()

        bullish_cs = [p for p in cs_patterns if p.get('signal') == 'bullish']
        bearish_cs = [p for p in cs_patterns if p.get('signal') == 'bearish']

        features.update({
            'cs_bullish_count': len(bullish_cs),
            'cs_bearish_count': len(bearish_cs),
            'cs_doji': int(any(p.get('pattern') == 'Doji' for p in cs_patterns)),
            'cs_engulfing_bullish': int(any(p.get('pattern') == 'Bullish Engulfing' for p in cs_patterns)),
            'cs_engulfing_bearish': int(any(p.get('pattern') == 'Bearish Engulfing' for p in cs_patterns)),
            'cs_hammer': int(any(p.get('pattern') == 'Hammer' for p in cs_patterns)),
        })
    except Exception as e:
        # Silently use defaults (candlestick detection is optional)
        features.update({k: 0 for k in [
            'cs_bullish_count', 'cs_bearish_count',
            'cs_doji', 'cs_engulfing_bullish', 'cs_engulfing_bearish', 'cs_hammer'
        ]})

    return features


def engineer_market_features(stock_id: int, db_session) -> dict:
    """
    Extract market context features (6 features)

    Args:
        stock_id: Stock ID
        db_session: Database session

    Returns:
        Dict with 6 market features
    """
    try:
        # Market regime (4 features)
        regime_service = MarketRegimeService(db_session)
        regime = regime_service.detect_market_regime(stock_id)

        regime_features = {
            'regime_trend': int(regime['regime'] == 'trend'),
            'regime_range': int(regime['regime'] == 'range'),
            'regime_bullish': int(regime['direction'] == 'bullish'),
            'regime_bearish': int(regime['direction'] == 'bearish'),
        }

        # TODO: Add SPY trend, VIX level, sector relative strength (2 more features)
        # For now, set to 0
        market_features = {
            'spy_above_200ma': 0,  # TODO
            'vix_level': 0,  # TODO
        }

        return {**regime_features, **market_features}

    except Exception as e:
        print(f"Error engineering market features: {e}")
        # Set defaults
        return {
            'regime_trend': 0, 'regime_range': 0, 'regime_bullish': 0, 'regime_bearish': 0,
            'spy_above_200ma': 0, 'vix_level': 0
        }


def engineer_price_history_features(df: pd.DataFrame) -> dict:
    """
    Extract price history features (10 features)

    Args:
        df: DataFrame with OHLCV data

    Returns:
        Dict with 10 price history features
    """
    try:
        if len(df) < 20:
            return {f'return_{d}d': 0 for d in [1, 3, 5, 10, 20]}

        features = {}

        # Lagged returns (5 features)
        current_close = df['close'].iloc[-1]
        for days in [1, 3, 5, 10, 20]:
            if len(df) > days:
                past_close = df['close'].iloc[-days-1]
                ret = (current_close - past_close) / past_close
                features[f'return_{days}d'] = float(ret)
            else:
                features[f'return_{days}d'] = 0.0

        # Rolling volatility (3 features)
        for period in [10, 20, 50]:
            if len(df) > period:
                returns = df['close'].pct_change().dropna()
                vol = returns.tail(period).std()
                features[f'volatility_{period}d'] = float(vol)
            else:
                features[f'volatility_{period}d'] = 0.0

        # Volume features (2 features)
        avg_volume = df['volume'].tail(20).mean()
        current_volume = df['volume'].iloc[-1]
        features['volume_ratio'] = float(current_volume / avg_volume) if avg_volume > 0 else 1.0
        features['volume_surge'] = int(current_volume > avg_volume * 1.5) if avg_volume > 0 else 0

        return features

    except Exception as e:
        print(f"Error engineering price history features: {e}")
        return {}


def engineer_features_for_stock(stock_id: int, db_session) -> dict:
    """
    Engineer all features for a single stock

    Args:
        stock_id: Stock ID
        db_session: Database session

    Returns:
        Dict with all features (45 total currently)
    """
    # Get price data
    df = get_stock_prices(stock_id)

    if df is None or len(df) < 60:
        print(f"Insufficient data for stock {stock_id}")
        return None

    # Engineer features
    technical = engineer_technical_features(df)
    patterns = engineer_pattern_features(df, stock_id, db_session)
    market = engineer_market_features(stock_id, db_session)
    price_history = engineer_price_history_features(df)

    # Combine all features
    all_features = {
        'stock_id': stock_id,
        'timestamp': datetime.now(),
        **(technical or {}),
        **patterns,
        **market,
        **price_history,
    }

    return all_features


def main():
    """Main feature engineering pipeline"""
    print("=" * 60)
    print("StockAnalyzer ML - Feature Engineering Pipeline")
    print("=" * 60)

    # Create outputs directory
    outputs_dir = Path('/app/outputs/features')
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Get all tracked stocks
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT id FROM stocks WHERE is_tracked = true"))
        stock_ids = [row[0] for row in result]
    finally:
        db.close()

    print(f"\n📊 Found {len(stock_ids)} tracked stocks")

    # Engineer features for each stock
    all_features = []
    skipped_count = 0

    for stock_id in tqdm(stock_ids, desc="Processing stocks"):
        db = SessionLocal()
        try:
            features = engineer_features_for_stock(stock_id, db)
            if features:
                all_features.append(features)
            else:
                skipped_count += 1
        except Exception as e:
            # Silently skip stocks with errors (pattern detection failures are common)
            skipped_count += 1
        finally:
            db.close()

    # Convert to DataFrame
    df = pd.DataFrame(all_features)

    # Save to parquet
    output_file = outputs_dir / f'features_{datetime.now().strftime("%Y%m%d_%H%M%S")}.parquet'
    df.to_parquet(output_file, index=False)

    print(f"\n✅ Saved {len(df)} feature rows to {output_file}")
    print(f"📊 Features per row: {len(df.columns) - 2}")  # -2 for stock_id and timestamp
    print(f"📁 Output directory: {outputs_dir}")
    if skipped_count > 0:
        print(f"⚠️  Skipped {skipped_count} stocks due to errors")


if __name__ == "__main__":
    main()
