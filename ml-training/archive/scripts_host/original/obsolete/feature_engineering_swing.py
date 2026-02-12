#!/usr/bin/env python3
"""
Feature Engineering: Swing Trading Optimized

REMOVED (based on feature importance analysis):
- Harmonic indicators: mama, fama, tema, t3, trix
- Hilbert transforms: ht_trendline, ht_dcperiod, ht_dcperiod_signal, ht_trendmode
- Stochastic RSI: stochrsi_k, stochrsi_d
- Ultosc: ultosc
- Frontend-only features: All *_signal (BUY/SELL/HOLD strings) and *_reason columns
  NOTE: macd_signal is KEPT - it's the numeric MACD signal line, not a categorical signal

ADDED (swing-trading specific):
- MA crossovers (20/50/200 day)
- Price vs MA percentage distance
- Consecutive up/down days
- Gap patterns
- Market regime features (SPY trend, volatility)
- Multi-timeframe momentum

SECRET WEAPON: SEC Form 4 Insider Trading (12 features)
Research shows insider purchases predict +2-5% abnormal returns, especially:
- CEO/CTO/CFO purchases (executives know the business best)
- Cluster buying (3+ different insiders buying = very bullish)
- Buys near 52-week low (high conviction signal)
- Net buy ratio (more buys than sells = positive sentiment)
With 119K+ trades across 224 stocks, this is valuable alpha signal!

Target: High-quality swing-trading features with raw numeric values + insider alpha

Usage:
    python scripts/feature_engineering_swing.py
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/backend')
sys.path.insert(0, '/app/ml_training')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Import technical indicators
from app.services.technical_indicators import TechnicalIndicators

# Import insider features
from ml_framework.insider_features import InsiderFeatures

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://stockuser:stockpass123@database:5432/stock_analyzer')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# ============================================================
# FEATURE LIST
# ============================================================

# Features to EXCLUDE (confirmed low importance)
EXCLUDED_FEATURES = {
    # Harmonic indicators
    'mama', 'fama',
    'tema',
    't3',
    'trix',

    # Hilbert transforms
    'ht_trendline',
    'ht_dcperiod',
    'ht_dcperiod_signal',
    'ht_trendmode',

    # Stochastic RSI
    'stochrsi_k',
    'stochrsi_d',

    # Other low importance
    'ultosc',

    # NOTE: Insider trading features REMOVED from exclusion - they are the "secret weapon"!
    # Research shows insider buys predict +2-5% abnormal returns, especially:
    # - CEO/CTO/CFO purchases
    # - Cluster buying (3+ insiders)
    # - Buys near 52-week low
    # With 119K+ trades across 224 stocks, this is valuable alpha signal!

    # ============================================================
    # FRONTEND-ONLY FEATURES (categorical signals & reasons)
    # These are string columns meant for frontend display, not ML
    # ============================================================

    # Categorical signals (BUY/SELL/HOLD strings)
    'rsi_signal',       # RSI buy/sell/hold signal
    'bb_signal',        # Bollinger Bands signal
    'ma_signal',        # Moving Average crossover signal
    'macd_trend',       # MACD trend (BUY/SELL/HOLD)
    'adx_signal',       # ADX trend strength signal
    'psar_signal',      # Parabolic SAR signal
    'stoch_signal',     # Stochastic oscillator signal
    'cci_signal',       # CCI signal
    'obv_signal',       # OBV signal
    'vwap_signal',      # VWAP signal
    'ad_signal',        # Accumulation/Distribution signal
    'atr_signal',       # ATR signal
    'kc_signal',        # Keltner Channel signal
    'kama_signal',      # KAMA signal
    'tema_signal',      # TEMA signal
    't3_signal',        # T3 signal
    'ht_signal',        # Hilbert Transform signal
    'mfi_signal',       # MFI signal
    'willr_signal',     # Williams %R signal
    'roc_signal',       # ROC signal
    'cmo_signal',       # CMO signal
    'natr_signal',      # NATR signal
    'stddev_signal',    # Standard Deviation signal
    'linearreg_signal', # Linear Regression signal
    'aroon_signal',     # Aroon signal
    'stochrsi_signal',  # Stochastic RSI signal
    'ultosc_signal',    # Ultimate Oscillator signal
    'trix_signal',      # TRIX signal
    'bop_signal',       # BOP signal
    'adosc_signal',     # AD Oscillator signal
    'apo_signal',       # Absolute Price Oscillator signal
    'ppo_signal',       # Percentage Price Oscillator signal
    'mama_signal',      # MAMA signal
    'ht_trendmode_signal',  # Hilbert Trend Mode signal

    # NOTE: 'macd_signal' is NOT excluded - it's the numeric MACD signal line value

    # Signal reasons (human-readable explanations)
    'rsi_reason',       # RSI signal explanation
    'bb_reason',        # Bollinger Bands signal explanation
    'ma_reason',        # MA signal explanation
    'macd_reason',      # MACD signal explanation
    'adx_reason',       # ADX signal explanation
    'psar_reason',      # Parabolic SAR signal explanation
    'stoch_reason',     # Stochastic signal explanation
    'cci_reason',       # CCI signal explanation
    'obv_reason',       # OBV signal explanation
    'vwap_reason',      # VWAP signal explanation
    'ad_reason',        # A/D signal explanation
    'atr_reason',       # ATR signal explanation
    'kc_reason',        # Keltner Channel signal explanation
    'kama_reason',      # KAMA signal explanation
    'tema_reason',      # TEMA signal explanation
    't3_reason',        # T3 signal explanation
    'ht_reason',        # Hilbert Transform signal explanation
    'mfi_reason',       # MFI signal explanation
    'willr_reason',     # Williams %R signal explanation
    'roc_reason',       # ROC signal explanation
    'cmo_reason',       # CMO signal explanation
    'natr_reason',      # NATR signal explanation
    'stddev_reason',    # Standard Deviation signal explanation
    'linearreg_reason', # Linear Regression signal explanation
    'aroon_reason',     # Aroon signal explanation
    'stochrsi_reason',  # Stochastic RSI signal explanation
    'ultosc_reason',    # Ultimate Oscillator signal explanation
    'trix_reason',      # TRIX signal explanation
    'bop_reason',       # BOP signal explanation
    'adosc_reason',     # AD Oscillator signal explanation
    'apo_reason',       # Absolute Price Oscillator signal explanation
    'ppo_reason',       # Percentage Price Oscillator signal explanation
    'mama_reason',      # MAMA signal explanation
    'ht_trendmode_reason',  # Hilbert Trend Mode signal explanation
    'ht_dcperiod_reason',   # Hilbert DC Period signal explanation
}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def fetch_market_data() -> pd.DataFrame:
    """Fetch SPY and VIX data for market context"""
    print("\nFetching market context data...")

    try:
        # Get SPY data
        spy_query = text("""
            SELECT timestamp, close as spy_close
            FROM stock_prices
            WHERE stock_id = (SELECT id FROM stocks WHERE symbol = 'SPY')
              AND timeframe = '1d'
            ORDER BY timestamp ASC
        """)

        spy_df = pd.read_sql(spy_query, engine)
        spy_df['timestamp'] = pd.to_datetime(spy_df['timestamp'])
        print(f"  ✅ SPY data: {len(spy_df):,} days")

    except Exception as e:
        print(f"  ⚠️  Could not fetch SPY data: {e}")
        spy_df = None

    return spy_df


def add_swing_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add swing-trading specific features"""
    print("\nAdding swing-trading features...")

    df = df.copy()
    df = df.sort_values(['stock_id', 'timestamp']).reset_index(drop=True)

    # ============================================================
    # MA CROSSOVERS (20/50/200 day)
    # ============================================================
    print("  MA crossovers...")

    for ma_period in [20, 50, 200]:
        df[f'ma_{ma_period}'] = df.groupby('stock_id')['close'].transform(
            lambda x: x.rolling(window=ma_period, min_periods=1).mean()
        )

    # MA crossover signals
    df['ma_20_above_50'] = (df['ma_20'] > df['ma_50']).astype(int)
    df['ma_50_above_200'] = (df['ma_50'] > df['ma_200']).astype(int)

    # Price vs MA percentage distance
    df['price_above_ma20_pct'] = ((df['close'] - df['ma_20']) / df['ma_20']) * 100
    df['price_above_ma50_pct'] = ((df['close'] - df['ma_50']) / df['ma_50']) * 100
    df['price_above_ma200_pct'] = ((df['close'] - df['ma_200']) / df['ma_200']) * 100

    # ============================================================
    # CONSECUTIVE UP/DOWN DAYS
    # ============================================================
    print("  Consecutive up/down days...")

    # Calculate daily returns
    df['daily_return'] = df.groupby('stock_id')['close'].transform(
        lambda x: x.pct_change()
    )

    # Count consecutive up/down days
    def count_consecutive(sign, group):
        """Count consecutive occurrences of sign"""
        count = 0
        counts = []
        for s in sign:
            if s > 0:
                count += 1
            elif s < 0:
                count -= 1
            else:
                count = 0
            counts.append(count)
        return pd.Series(counts, index=group.index)

    df['consecutive_up_days'] = df.groupby('stock_id')['daily_return'].transform(
        lambda x: (x > 0).astype(int).groupby((x > 0).cumsum()).cumsum()
    )

    df['consecutive_down_days'] = df.groupby('stock_id')['daily_return'].transform(
        lambda x: (x < 0).astype(int).groupby((x < 0).cumsum()).cumsum()
    )

    # ============================================================
    # GAP PATTERNS
    # ============================================================
    print("  Gap patterns...")

    # Gap up: open > previous close by >2%
    df['gap_up'] = ((df['open'] - df['close'].shift(1)) / df['close'].shift(1) > 0.02).astype(int)

    # Gap down: open < previous close by >2%
    df['gap_down'] = ((df['open'] - df['close'].shift(1)) / df['close'].shift(1) < -0.02).astype(int)

    # Gap with volume confirmation
    df['gap_up_volume'] = df['gap_up'] & (df['volume'] > df['volume'].rolling(20).mean())
    df['gap_down_volume'] = df['gap_down'] & (df['volume'] > df['volume'].rolling(20).mean())

    # ============================================================
    # VOLATILITY FEATURES
    # ============================================================
    print("  Volatility features...")

    # Rolling volatility (standard deviation of returns)
    df['volatility_10d'] = df.groupby('stock_id')['daily_return'].transform(
        lambda x: x.rolling(10, min_periods=5).std()
    )

    df['volatility_20d'] = df.groupby('stock_id')['daily_return'].transform(
        lambda x: x.rolling(20, min_periods=10).std()
    )

    df['volatility_ratio'] = df['volatility_10d'] / df['volatility_20d']

    # ATR-based volatility
    if 'atr' in df.columns:
        df['atr_ratio_10d'] = df.groupby('stock_id')['atr'].transform(
            lambda x: x.rolling(10).mean()
        ) / df.groupby('stock_id')['atr'].transform(
            lambda x: x.rolling(20).mean()
        )

    # ============================================================
    # PRICE MOMENTUM (multi-timeframe)
    # ============================================================
    print("  Price momentum...")

    for period in [5, 10, 20, 60]:
        df[f'momentum_{period}d'] = df.groupby('stock_id')['close'].transform(
            lambda x: x.pct_change(period)
        )

    # Price velocity (rate of change of momentum)
    df['momentum_5d_1d'] = df['momentum_5d'] - df['momentum_5d'].shift(1)

    return df


def add_market_context_features(df: pd.DataFrame, spy_df: pd.DataFrame = None) -> pd.DataFrame:
    """Add market regime/context features"""
    print("\nAdding market context features...")

    if spy_df is None:
        print("  ⚠️  No SPY data available, skipping market context")
        return df

    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    spy_df['timestamp'] = pd.to_datetime(spy_df['timestamp'])

    # Merge SPY data
    df = df.merge(
        spy_df[['timestamp', 'spy_close']],
        on='timestamp',
        how='left'
    )

    # Fill missing SPY data with forward fill
    df['spy_close'] = df['spy_close'].fillna(method='ffill')

    # ============================================================
    # SPY MOVING AVERAGES
    # ============================================================
    print("  SPY moving averages...")

    df['spy_ma_20'] = df['spy_close'].rolling(window=20, min_periods=1).mean()
    df['spy_ma_50'] = df['spy_close'].rolling(window=50, min_periods=1).mean()
    df['spy_ma_200'] = df['spy_close'].rolling(window=200, min_periods=1).mean()

    # SPY trend
    df['spy_uptrend'] = (df['spy_ma_20'] > df['spy_ma_50']).astype(int)
    df['spy_uptrend_long'] = (df['spy_ma_50'] > df['spy_ma_200']).astype(int)

    # SPY vs price (relative performance)
    df['spy_return_5d'] = df['spy_close'].pct_change(5)
    df['spy_return_20d'] = df['spy_close'].pct_change(20)
    df['stock_vs_spy_5d'] = df.groupby('stock_id')['close'].transform(
        lambda x: x.pct_change(5)
    ) - df['spy_return_5d']

    # ============================================================
    # MARKET REGIME (based on SPY)
    # ============================================================
    print("  Market regime...")

    # Bull market: SPY above 200MA
    df['market_regime_bull'] = (df['spy_close'] > df['spy_ma_200']).astype(int)

    # Correction phase: SPY between 50MA and 200MA
    df['market_regime_correction'] = (
        (df['spy_close'] > df['spy_ma_50']) &
        (df['spy_close'] < df['spy_ma_200'])
    ).astype(int)

    # Bear market: SPY below 200MA
    df['market_regime_bear'] = (df['spy_close'] < df['spy_ma_200']).astype(int)

    # ============================================================
    # VOLATILITY REGIME (using ATR)
    # ============================================================
    print("  Volatility regime...")

    if 'atr' in df.columns:
        # Normalize ATR by rolling mean to detect volatility expansion
        df['atr_normalized'] = df.groupby('stock_id')['atr'].transform(
            lambda x: x / x.rolling(60, min_periods=30).mean()
        )

        df['volatility_expansion'] = (df['atr_normalized'] > 1.5).astype(int)
        df['volatility_contraction'] = (df['atr_normalized'] < 0.67).astype(int)

    return df


def filter_features(df: pd.DataFrame) -> pd.DataFrame:
    """Remove excluded features from dataframe"""
    print(f"\nFiltering features...")

    # Get all feature columns (exclude metadata)
    feature_cols = [col for col in df.columns if col not in ['stock_id', 'timestamp', 'label']]

    # Filter out excluded features
    kept_features = [f for f in feature_cols if f not in EXCLUDED_FEATURES]
    removed_features = [f for f in feature_cols if f in EXCLUDED_FEATURES]

    print(f"  Original features: {len(feature_cols)}")
    print(f"  Kept: {len(kept_features)}")
    print(f"  Removed: {len(removed_features)}")

    if removed_features:
        print(f"\n  Removed features:")
        for f in removed_features:
            print(f"    - {f}")

    # Select only kept columns
    columns_to_keep = ['stock_id', 'timestamp'] + kept_features
    if 'label' in df.columns:
        columns_to_keep.append('label')

    return df[columns_to_keep]


def main():
    """Main feature engineering pipeline"""
    print("=" * 70)
    print(" " * 12)
    print("Swing Trading Feature Engineering")
    print(" " * 12)
    print("=" * 70)

    # ============================================================
    # CONFIGURATION
    # ============================================================

    start_date = datetime.now() - timedelta(days=365*5)  # 5 years of data
    end_date = datetime.now()

    print(f"\nDate range: {start_date.date()} to {end_date.date()}")

    # ============================================================
    # GET STOCKS
    # ============================================================

    print("\n" + "=" * 70)
    print("FETCHING STOCK LIST")
    print("=" * 70)

    query = text("""
        SELECT id, symbol
        FROM stocks
        WHERE is_tracked = true
        ORDER BY symbol
    """)

    stocks_df = pd.read_sql(query, engine)
    print(f"Found {len(stocks_df)} stocks")

    # ============================================================
    # FETCH PRICE DATA
    # ============================================================

    print("\n" + "=" * 70)
    print("FETCHING PRICE DATA")
    print("=" * 70)

    ti = TechnicalIndicators()
    all_features = []

    for stock in tqdm(stocks_df.itertuples(), desc="Processing stocks"):
        stock_id = stock.id
        symbol = stock.symbol

        try:
            # Fetch price data
            query = text("""
                SELECT timestamp, open, high, low, close, volume
                FROM stock_prices
                WHERE stock_id = :stock_id
                  AND timeframe = '1d'
                  AND timestamp >= :start_date
                  AND timestamp <= :end_date
                ORDER BY timestamp ASC
            """)

            params = {
                'stock_id': stock_id,
                'start_date': start_date,
                'end_date': end_date
            }

            df = pd.read_sql(query, engine, params=params)

            if df.empty or len(df) < 100:
                print(f"  ⚠️  {symbol}: Insufficient data ({len(df)} days), skipping")
                continue

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.dropna()

            # Add technical indicators using the service
            df = ti.calculate_all_indicators(df)

            # Add SEC Form 4 insider trading features (secret weapon!)
            df = InsiderFeatures.add_insider_features(df, stock_id, start_date, end_date)

            # Add stock_id
            df['stock_id'] = stock_id

            all_features.append(df)

        except Exception as e:
            print(f"  ❌ {symbol}: Error - {e}")
            continue

    if not all_features:
        print("\n❌ No features generated!")
        return

    # Combine all features
    print(f"\nCombining features from {len(all_features)} stocks...")
    final_df = pd.concat(all_features, ignore_index=True)

    # Count insider trading activity
    insider_cols = [c for c in final_df.columns if 'insider' in c]
    if insider_cols:
        ceo_buys = final_df['ceo_bought_30d'].sum() if 'ceo_bought_30d' in final_df.columns else 0
        cluster_buys = final_df['cluster_buying_30d'].sum() if 'cluster_buying_30d' in final_df.columns else 0
        print(f"  🕵️  Insider Trading: {ceo_buys:.0f} CEO buys, {cluster_buys:.0f} cluster buys detected")

    # ============================================================
    # ADD SWING-SPECIFIC FEATURES
    # ============================================================

    final_df = add_swing_features(final_df)

    # ============================================================
    # ADD MARKET CONTEXT FEATURES
    # ============================================================

    spy_df = fetch_market_data()
    final_df = add_market_context_features(final_df, spy_df)

    # ============================================================
    # FILTER FEATURES
    # ============================================================

    final_df = filter_features(final_df)

    # ============================================================
    # SAVE FEATURES
    # ============================================================

    print("\n" + "=" * 70)
    print("SAVING FEATURES")
    print("=" * 70)

    output_dir = Path('/app/outputs/features')
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f'features_swing_{timestamp}.parquet'

    final_df.to_parquet(output_file, index=False)

    print(f"\n✅ Saved {len(final_df)} rows with {len(final_df.columns)-2} features")
    print(f"   File: {output_file}")
    print(f"   Size: {output_file.stat().st_size / (1024**2):.1f} MB")

    # Print feature list
    print(f"\nFinal feature list ({len(final_df.columns)-2} features):")
    feature_cols = [col for col in final_df.columns if col not in ['stock_id', 'timestamp']]
    for i, feature in enumerate(feature_cols, 1):
        print(f"  {i:2d}. {feature}")

    print("\n" + "=" * 70)
    print("✅ FEATURE ENGINEERING COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
