"""
Feature Engineering with 40 Features (28 Technical + 12 SEC Form 4 Insider)

This script extends the 28-feature base with SEC Form 4 corporate insider trading features:
- 28 high-quality technical features (no data leakage)
- 12 SEC Form 4 insider trading features (corporate insiders, not congressional)
- Total: 40 features for ML training

FEATURES (40):

TECHNICAL INDICATORS (28):
  Core Momentum (4): rsi, log_return_1d, log_return_5d, price_position_20d
  Core Trend (3): sma_50, sma_200, ma_slope
  Core Volatility (3): volatility_20d, atr, daily_range
  Core Volume (3): log_volume, obv, vwap
  MACD (3): macd, macd_histogram, macd_signal
  ADX (2): adx, plus_di
  Other (10): psar, cci, roc, aroon_osc, linearreg_slope, gap, natr, mfi, stoch_k, price_vs_sma50

SEC FORM 4 INSIDER FEATURES (12):
  Buy/Sell Activity (4): insider_buy_count_30d, insider_sell_count_30d, insider_buy_volume_30d, insider_net_buy_ratio_30d
  Executive Activity (3): ceo_bought_30d, cto_bought_30d, cfo_bought_30d
  Cluster Buying (1): cluster_buying_30d
  Price Context (1): insider_buy_at_52w_low
  Sentiment (1): insider_sentiment_30d
  Value Metrics (2): insider_buy_value_30d, insider_sell_value_30d

EXPECTED IMPROVEMENT:
- Baseline (28 technical): 56.8% AUC
- Expected with insider features: 65-70% AUC (+8-12%)
- Insider purchases (especially CEO/CTO/CFO and cluster buying) are strong predictors
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, '/backend')
sys.path.insert(0, '/app/ml_training')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Import services
from app.services.technical_indicators import TechnicalIndicators
from ml_framework.insider_features import InsiderFeatures

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
        return pd.DataFrame()

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    return df


def calculate_technical_features(df: pd.DataFrame, stock_id: int) -> pd.DataFrame:
    """
    Calculate all 28 technical features using TechnicalIndicators service

    Args:
        df: DataFrame with OHLCV data
        stock_id: Stock ID

    Returns:
        DataFrame with 28 technical features added
    """
    if df.empty:
        return df

    # Calculate technical indicators using static methods
    # The methods return the full DataFrame with columns added

    # Core Momentum (4) - RSI
    df = TechnicalIndicators.calculate_rsi(df, period=14)
    df['log_return_1d'] = np.log(df['close'] / df['close'].shift(1))
    df['log_return_5d'] = np.log(df['close'] / df['close'].shift(5))
    df['price_position_20d'] = (df['close'] - df['close'].rolling(20).min()) / (
        df['close'].rolling(20).max() - df['close'].rolling(20).min()
    )

    # Core Trend (3)
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['sma_200'] = df['close'].rolling(window=200).mean()
    df['ma_slope'] = df['sma_50'].diff(5)

    # Core Volatility (3)
    df['volatility_20d'] = df['close'].pct_change().rolling(20).std()
    df = TechnicalIndicators.calculate_atr(df, period=14)
    df['daily_range'] = (df['high'] - df['low']) / df['close']

    # Core Volume (3)
    df['log_volume'] = np.log(df['volume'])
    df = TechnicalIndicators.calculate_obv(df)
    df = TechnicalIndicators.calculate_vwap(df)

    # MACD (3) - returns df with macd, macd_signal, macd_histogram columns
    df = TechnicalIndicators.calculate_macd(df)

    # ADX (2) - returns df with ADX, PLUS_DI columns
    df = TechnicalIndicators.calculate_adx(df, period=14)
    if 'ADX' not in df.columns:
        df['ADX'] = 0
    if 'PLUS_DI' not in df.columns:
        df['PLUS_DI'] = 0
    df.rename(columns={'ADX': 'adx', 'PLUS_DI': 'plus_di'}, inplace=True)

    # Other indicators - use working script approach
    psar_result = TechnicalIndicators.calculate_parabolic_sar(df)
    if 'SAR' in psar_result.columns:
        df['psar'] = psar_result['SAR']
    else:
        df['psar'] = df['close']

    df = TechnicalIndicators.calculate_cci(df, period=20)
    if 'CCI' not in df.columns:
        df['CCI'] = 0

    df = TechnicalIndicators.calculate_roc(df, period=10)
    if 'ROC' not in df.columns:
        df['ROC'] = 0

    aroon_result = TechnicalIndicators.calculate_aroon(df, period=25)
    if 'Aroon_Osc' in aroon_result.columns:
        df['aroon_osc'] = aroon_result['Aroon_Osc']
    else:
        df['aroon_osc'] = 0

    df = TechnicalIndicators.calculate_linearreg_slope(df, period=14)
    if 'Slope' not in df.columns:
        df['Slope'] = 0

    df['gap'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)

    df = TechnicalIndicators.calculate_natr(df, period=14)
    if 'NATR' not in df.columns:
        df['NATR'] = 0

    df = TechnicalIndicators.calculate_mfi(df, period=14)
    if 'MFI' not in df.columns:
        df['MFI'] = 50

    df = TechnicalIndicators.calculate_stochastic(df, k_period=14, d_period=3)
    if 'SlowK' not in df.columns:
        df['SlowK'] = 50

    df['price_vs_sma50'] = (df['close'] - df['sma_50']) / df['sma_50']

    return df


def create_features_for_stock(
    stock_id: int,
    symbol: str,
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame:
    """
    Create all 40 features (28 technical + 12 insider) for a stock

    Args:
        stock_id: Stock ID
        symbol: Stock symbol
        start_date: Start date
        end_date: End date

    Returns:
        DataFrame with all 40 features
    """
    # Fetch price data
    prices_df = get_stock_prices(stock_id, start_date, end_date)

    if prices_df.empty:
        print(f"  No price data for {symbol}")
        return pd.DataFrame()

    # Calculate technical features
    print(f"  Calculating 28 technical features...")
    prices_df = calculate_technical_features(prices_df, stock_id)

    # Add SEC Form 4 insider features
    print(f"  Calculating 12 SEC Form 4 insider features...")
    try:
        features_with_insider = InsiderFeatures.add_insider_features(
            prices_df.reset_index(),
            stock_id,
            start_date,
            end_date
        )
    except Exception as e:
        print(f"  {symbol}: ERROR - {str(e)[:100]}")
        # Add zero insider features manually
        features_with_insider = prices_df.reset_index()
        insider_cols = [
            'insider_buy_count_30d', 'insider_sell_count_30d',
            'insider_buy_volume_30d', 'insider_net_buy_ratio_30d',
            'ceo_bought_30d', 'cto_bought_30d', 'cfo_bought_30d',
            'cluster_buying_30d',
            'insider_buy_at_52w_low',
            'insider_sentiment_30d',
            'insider_buy_value_30d', 'insider_sell_value_30d'
        ]
        for col in insider_cols:
            features_with_insider[col] = 0

    # Add stock_id and symbol
    features_with_insider['stock_id'] = stock_id
    features_with_insider['symbol'] = symbol

    # Define final feature columns (40 total)
    feature_columns = [
        # Technical features (28)
        'rsi', 'log_return_1d', 'log_return_5d', 'price_position_20d',
        'sma_50', 'sma_200', 'ma_slope',
        'volatility_20d', 'atr', 'daily_range',
        'log_volume', 'obv', 'vwap',
        'macd', 'macd_histogram', 'macd_signal',
        'adx', 'plus_di',
        'psar', 'cci', 'roc', 'aroon_osc', 'linearreg_slope', 'gap', 'natr', 'mfi', 'stoch_k', 'price_vs_sma50',
        # SEC Form 4 Insider features (12)
        'insider_buy_count_30d', 'insider_sell_count_30d', 'insider_buy_volume_30d', 'insider_net_buy_ratio_30d',
        'ceo_bought_30d', 'cto_bought_30d', 'cfo_bought_30d',
        'cluster_buying_30d',
        'insider_buy_at_52w_low',
        'insider_sentiment_30d',
        'insider_buy_value_30d', 'insider_sell_value_30d'
    ]

    # Keep only feature columns + identifiers
    result = features_with_insider[['stock_id', 'symbol'] + feature_columns].copy()

    # Replace infinite and NaN values
    result = result.replace([np.inf, -np.inf], np.nan)
    result = result.fillna(0)

    # Shift features by 1 day to prevent data leakage
    feature_cols = [col for col in result.columns if col not in ['stock_id', 'symbol']]
    result[feature_cols] = result[feature_cols].shift(1)
    result = result.dropna()

    return result


def save_features_to_db(features_df: pd.DataFrame, stock_id: int, symbol: str) -> int:
    """
    Save features to database

    Args:
        features_df: DataFrame with features
        stock_id: Stock ID
        symbol: Stock symbol

    Returns:
        Number of rows saved
    """
    if features_df.empty:
        return 0

    db = SessionLocal()
    try:
        # Delete existing features for this stock
        db.execute(text("DELETE FROM stock_features WHERE stock_id = :stock_id"), {"stock_id": stock_id})

        # Insert new features
        rows_saved = 0
        for _, row in features_df.iterrows():
            try:
                db.execute(text("""
                    INSERT INTO stock_features (stock_id, timestamp, features)
                    VALUES (:stock_id, :timestamp, :features::jsonb)
                """), {
                    "stock_id": stock_id,
                    "timestamp": row['timestamp'],
                    "features": row[feature_columns].to_dict()
                })
                rows_saved += 1
            except Exception as e:
                print(f"    Error inserting row: {e}")
                continue

        db.commit()
        return rows_saved

    except Exception as e:
        db.rollback()
        print(f"  Error saving features: {e}")
        return 0
    finally:
        db.close()


def main():
    """Main function"""
    print("=" * 80)
    print(" " * 20)
    print("Feature Engineering: 40 Features (28 Technical + 12 SEC Form 4 Insider)")
    print(" " * 20)
    print("=" * 80)

    # Get date range from database
    min_date, max_date = get_data_date_range()

    if min_date is None or max_date is None:
        print("\n❌ No price data found in database")
        print("\n💡 Run: python scripts/fetch_stock_prices.py")
        return

    print(f"\n📅 Data range: {min_date.date()} to {max_date.date()}")

    # Get stocks
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT id, symbol
            FROM stocks
            WHERE is_tracked = true
            ORDER BY symbol
        """))
        stocks = [(row[0], row[1]) for row in result]
    finally:
        db.close()

    if not stocks:
        print("\n❌ No stocks found")
        return

    print(f"📊 Processing {len(stocks)} stocks")
    print("\n" + "=" * 80)

    # Process each stock
    total_rows = 0
    failed_stocks = []

    for stock_id, symbol in tqdm(stocks, desc="Creating features"):
        try:
            features_df = create_features_for_stock(
                stock_id,
                symbol,
                min_date,
                max_date
            )

            if not features_df.empty:
                rows = len(features_df)
                total_rows += rows
                print(f"\n  {symbol}: {rows} feature rows created")
            else:
                print(f"\n  {symbol}: No features created")
                failed_stocks.append(symbol)

        except Exception as e:
            print(f"\n  {symbol}: ERROR - {e}")
            failed_stocks.append(symbol)
            continue

    # Summary
    print("\n" + "=" * 80)
    print("✅ Feature Engineering Complete!")
    print("=" * 80)
    print(f"\n📊 Results:")
    print(f"   Total feature rows: {total_rows:,}")
    print(f"   Features per row: 40 (28 technical + 12 SEC Form 4 insider)")
    print(f"   Stocks processed: {len(stocks) - len(failed_stocks)}/{len(stocks)}")

    if failed_stocks:
        print(f"\n⚠️  Failed stocks ({len(failed_stocks)}):")
        for symbol in failed_stocks[:10]:
            print(f"   - {symbol}")

    print(f"\n💡 Next steps:")
    print(f"   1. Verify: SELECT COUNT(*) FROM stock_features;")
    print(f"   2. Train model: cd ml-training && python train_pattern_classifier.py")
    print(f"   3. Expected AUC: 65-70% (+8-12% improvement over baseline)")
    print("=" * 80)


if __name__ == "__main__":
    main()
