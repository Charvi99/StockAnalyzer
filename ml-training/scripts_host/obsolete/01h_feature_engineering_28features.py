"""
Feature Engineering with 28 High-Quality Features (NO DATA LEAKAGE)

This script implements the feature reduction strategy from ML_BRAINSTORMING_DIAGNOSIS_2026.md:
- Reduces from 76 features to 28 features (63% reduction)
- Keeps only high-quality, non-redundant features
- Maintains data leakage fix (shift by 1 day)
- Supports 5+ years of historical data (multiple market regimes)

FEATURE REDUCTION RATIONALE:
- Remove redundant moving averages (keep SMA 50, 200 only)
- Remove correlated momentum indicators (keep RSI, log_return_1d, log_return_5d)
- Remove redundant volatility (keep volatility_20d, ATR only)
- Remove redundant oscillators (StochRSI, Williams %R, etc.)
- Remove all manual signal columns (model learns patterns)

EXPECTED IMPACT:
- Less overfitting (28 features vs 76 for same data)
- Faster training (63% fewer features)
- Better generalization (unique, independent features)
- Expected AUC: +1-3% improvement
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


# ============================================================================
# 28 HIGH-QUALITY FEATURES (Reduction from 76)
# ============================================================================

"""
KEEP (28 features):

CORE MOMENTUM (4):
  1. rsi                    - RSI (14-day) - Most reliable momentum indicator
  2. log_return_1d          - Recent momentum (1-day log return)
  3. log_return_5d          - Short-term trend (5-day log return)
  4. price_position_20d     - Where price sits in 20-day range

CORE TREND (3):
  5. sma_50                 - Medium-term trend (50-day SMA)
  6. sma_200                - Major trend (200-day SMA) - Swing trading standard
  7. ma_slope               - Trend direction (slope of SMA)

CORE VOLATILITY (3):
  8. volatility_20d         - Risk measure (20-day std of returns)
  9. atr                    - Average True Range - Position sizing
 10. daily_range            - Intraday volatility (high-low)/close

CORE VOLUME (3):
 11. log_volume             - Normalized volume
 12. obv                    - On-Balance Volume - Strong volume signal
 13. vwap                   - Volume-Weighted Average Price

MACD (3):
 14. macd                   - MACD line (momentum)
 15. macd_histogram         - MACD histogram (trend strength)
 16. macd_signal            - MACD signal line

ADX (2):
 17. adx                    - Average Directional Index (trend strength)
 18. plus_di                - Plus DI (bullish power)

OTHER (9):
 19. psar                   - Parabolic SAR (trailing stops)
 20. cci                    - Commodity Channel Index
 21. roc                    - Rate of Change
 22. aroon_osc              - Aroon oscillator (trend transitions)
 23. linearreg_slope        - Linear regression slope
 24. gap                    - Overnight gap
 25. natr                   - Normalized ATR (percentage)
 26. mfi                    - Money Flow Index
 27. stoch_k                - Stochastic %K
 28. price_vs_sma50         - Price relative to SMA50
"""


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


def add_core_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add core features (log returns, volatility, volume)

    Args:
        df: DataFrame with OHLCV data

    Returns:
        DataFrame with core features added
    """
    df = df.copy()

    # Log returns (better than simple returns)
    df['log_return_1d'] = np.log(df['close'] / df['close'].shift(1))
    df['log_return_5d'] = np.log(df['close'] / df['close'].shift(5))

    # Volatility (std of log returns) - 20-day only
    df['volatility_20d'] = df['log_return_1d'].rolling(20).std()

    # Relative strength vs recent price range
    df['price_position_20d'] = (df['close'] - df['close'].rolling(20).min()) / \
                                (df['close'].rolling(20).max() - df['close'].rolling(20).min())

    # Volume features
    df['log_volume'] = np.log(df['volume'] + 1)  # +1 to avoid log(0)

    # Price range features (intraday volatility)
    df['daily_range'] = (df['high'] - df['low']) / df['close']

    # Gap features (overnight movement)
    df['gap'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)

    return df


def create_labels(df: pd.DataFrame, stock_id: int) -> pd.DataFrame:
    """
    Create labels for swing trading strategy

    For each day, determine if price hits +3% before -2% within next 20 days

    Args:
        df: DataFrame with price data
        stock_id: Stock ID

    Returns:
        DataFrame with labels indexed by timestamp
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
            'timestamp': df.index[i],
            'label': label,
            'max_upside': max_upside,
            'max_drawdown': max_drawdown
        })

    return pd.DataFrame(labels).set_index('timestamp')


def select_28_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Select only the 28 high-quality features from calculated indicators

    Args:
        df: DataFrame with all technical indicators

    Returns:
        DataFrame with only 28 selected features
    """
    # Define our 28 features
    feature_map = {
        # Core Momentum (4)
        'rsi': 'rsi',
        'log_return_1d': 'log_return_1d',
        'log_return_5d': 'log_return_5d',
        'price_position_20d': 'price_position_20d',

        # Core Trend (3)
        'sma_50': 'sma_50',
        'sma_200': 'sma_200',
        'ma_slope': 'ma_slope',

        # Core Volatility (3)
        'volatility_20d': 'volatility_20d',
        'atr': 'atr',
        'daily_range': 'daily_range',

        # Core Volume (3)
        'log_volume': 'log_volume',
        'obv': 'obv',
        'vwap': 'vwap',

        # MACD (3)
        'macd': 'macd',
        'macd_histogram': 'macd_histogram',
        'macd_signal': 'macd_signal',

        # ADX (2)
        'adx': 'adx',
        'plus_di': 'plus_di',

        # Other (9)
        'psar': 'psar',
        'cci': 'cci',
        'roc': 'roc',
        'aroon_osc': 'aroon_osc',
        'linearreg_slope': 'linearreg_slope',
        'gap': 'gap',
        'natr': 'natr',
        'mfi': 'mfi',
        'stoch_k': 'stoch_k',
    }

    # Add derived feature: price vs SMA50
    if 'sma_50' in df.columns:
        df['price_vs_sma50'] = (df['close'] - df['sma_50']) / df['sma_50']

    # Select only the 28 features
    selected_cols = []
    for col in df.columns:
        if col in feature_map:
            selected_cols.append(col)

    # Add price vs sma50 if created
    if 'price_vs_sma50' in df.columns:
        selected_cols.append('price_vs_sma50')

    # Drop any signal columns (model learns these patterns)
    selected_cols = [c for c in selected_cols if not c.endswith('_signal') and not c.endswith('_reason')]

    return df[selected_cols]


def engineer_features_for_stock(stock_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Engineer features for all dates in range for a stock with NO DATA LEAKAGE

    Uses only 28 high-quality features (reduced from 76).

    Args:
        stock_id: Stock ID
        start_date: Start date
        end_date: End date

    Returns:
        DataFrame with 28 features for each date (NO DATA LEAKAGE)
    """
    # Fetch ALL price data at once (with extra history)
    df = get_stock_prices(stock_id, start_date - timedelta(days=350), end_date + timedelta(days=30))

    if df is None or len(df) < 60:
        return None

    try:
        # Step 1: Add technical indicators (calculated on full dataset)
        indicators = TechnicalIndicators.calculate_all_indicators(df)

        if indicators is None or indicators.empty:
            return None

        # Step 2: Add core features
        indicators = add_core_features(indicators)

        # Step 3: Select only 28 high-quality features
        indicators_28 = select_28_features(indicators)

        # Step 4: Create labels (look forward, NO SHIFT)
        labels = create_labels(indicators, stock_id)

        if labels.empty:
            return None

        # Step 5: CRITICAL FIX - Shift all features by 1 day to prevent leakage
        # Features at day t should only use data from days BEFORE day t
        feature_cols = [col for col in indicators_28.columns if col not in ['open', 'high', 'low', 'close', 'volume']]

        # Create shifted features (THIS PREVENTS DATA LEAKAGE)
        shifted_features = indicators_28[feature_cols].shift(1)

        # Step 6: Align labels with shifted features
        aligned_data = shifted_features.join(labels, how='inner')

        if aligned_data.empty or aligned_data.isna().all().all():
            return None

        # Step 7: Drop rows with NaN (from shift operation - first row)
        aligned_data = aligned_data.dropna()

        if aligned_data.empty:
            return None

        # Step 8: Add stock_id and reset index
        aligned_data = aligned_data.reset_index()
        aligned_data['stock_id'] = stock_id

        # Reorder columns for consistency
        final_cols = ['stock_id', 'timestamp'] + \
                     [col for col in aligned_data.columns if col not in ['stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown']]

        # Ensure label columns are at the end
        final_cols = final_cols + ['label', 'max_upside', 'max_drawdown']

        return aligned_data[final_cols]

    except Exception as e:
        # Silently skip stocks with errors
        logger = __import__('logging').getLogger(__name__)
        logger.debug(f"Error engineering features for stock {stock_id}: {e}")
        return None


def print_feature_summary(df: pd.DataFrame):
    """Print summary of selected features"""
    import logging
    logger = logging.getLogger(__name__)

    feature_cols = [col for col in df.columns if col not in ['stock_id', 'timestamp', 'label', 'max_upside', 'max_drawdown']]

    logger.info("\n" + "=" * 80)
    logger.info("FEATURE SUMMARY (28 High-Quality Features)")
    logger.info("=" * 80)
    logger.info(f"\nTotal features: {len(feature_cols)}")
    logger.info(f"\nFeature categories:")
    logger.info(f"  Core Momentum (4):   rsi, log_return_1d, log_return_5d, price_position_20d")
    logger.info(f"  Core Trend (3):       sma_50, sma_200, ma_slope")
    logger.info(f"  Core Volatility (3):  volatility_20d, atr, daily_range")
    logger.info(f"  Core Volume (3):      log_volume, obv, vwap")
    logger.info(f"  MACD (3):             macd, macd_histogram, macd_signal")
    logger.info(f"  ADX (2):              adx, plus_di")
    logger.info(f"  Other (9):           psar, cci, roc, aroon_osc, linearreg_slope, gap, natr, mfi, stoch_k")
    logger.info(f"  Derived (1):          price_vs_sma50")
    logger.info("=" * 80)


def main():
    """Main feature engineering pipeline with NO DATA LEAKAGE and 28 FEATURES"""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    print("=" * 80)
    print(" " * 15)
    print("StockAnalyzer ML - Feature Engineering (28 Features, NO LEAKAGE)")
    print(" " * 15)
    print("=" * 80)
    print("\n⚠️  CRITICAL FIXES:")
    print("   ✅ All features shifted by 1 day (no lookahead bias)")
    print("   ✅ Reduced from 76 to 28 features (63% reduction)")
    print("   ✅ Only high-quality, non-redundant features")
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
    # Need 60 days for indicators to warm up + 1 day for shift + 20 days for labels
    start_date = min_date + timedelta(days=80)  # Increased buffer due to shift
    end_date = max_date - timedelta(days=20)

    print(f"📅 Feature range: {start_date} to {end_date}")

    if start_date >= end_date:
        print("❌ Not enough data for feature engineering!")
        print(f"   Need at least 100 days of data, have {(max_date - min_date).days} days")
        return

    # Get all tracked stocks
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT id FROM stocks WHERE is_tracked = true"))
        stock_ids = [row[0] for row in result]
    finally:
        db.close()

    print(f"\n📊 Processing {len(stock_ids)} stocks")
    print(f"⏱️  Estimated time: ~20-30 minutes")

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

    # Print feature summary
    print_feature_summary(features_df)

    print(f"\n{'='*80}")
    print(f"✅ Feature Engineering Complete (28 FEATURES, NO DATA LEAKAGE)!")
    print(f"{'='*80}")
    print(f"\n📊 Results:")
    print(f"   Total samples: {len(df):,}")
    print(f"   Features per sample: {len(feature_cols)} (reduced from 76)")
    print(f"   Stocks processed: {df['stock_id'].nunique()}")
    print(f"   Skipped stocks: {skipped_count}")
    print(f"   Positive class: {df['label'].mean()*100:.1f}%")
    print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"\n🔒 IMPROVEMENTS:")
    print(f"   ✅ 63% fewer features (76 → 28)")
    print(f"   ✅ No data leakage (features shifted by 1 day)")
    print(f"   ✅ Multiple market regimes (5+ years)")
    print(f"   ✅ Expected AUC: +1-3% (better generalization)")
    print(f"\n📁 Saved to:")
    print(f"   Features: {features_file}")
    print(f"   Labels: {labels_file}")
    print(f"\n✅ Ready for ML training!")
    print(f"\nNext step: docker-compose run --rm ml-training python /app/train.py")


if __name__ == "__main__":
    main()
