#!/usr/bin/env python3
"""
Feature Engineering: Unified ML Pipeline Script (ALPHA-OPTIMIZED)

This is THE SINGLE feature engineering script for the StockAnalyzer ML pipeline.
Now includes all enhancements for ALPHA prediction (stock selection) instead of BETA (market timing).

REMOVED (based on feature importance analysis):
- Harmonic indicators: mama, fama, tema, t3, trix
- Hilbert transforms: ht_trendline, ht_dcperiod, ht_dcperiod_signal, ht_trendmode
- Stochastic RSI: stochrsi_k, stochrsi_d
- Ultosc: ultosc
- Frontend-only features: All *_signal (BUY/SELL/HOLD strings) and *_reason columns
  NOTE: macd_signal is KEPT - it's the numeric MACD signal line, not a categorical signal

NEW IN THIS VERSION (Alpha-Optimized):
- REMOVED raw SPY features (spy_close, spy_ma_*, spy_uptrend*) - these cause beta learning!
- ADDED relative SPY features (stock_vs_spy_*) - forces model to learn stock-specific alpha
- ADDED enhanced insider features (14 new features) - makes insider data interpretable
- EXTENDED date range to 2018-2025 (8 years including critical market regimes)

ADDED (swing-trading specific):
- MA crossovers (20/50/200 day)
- Price vs MA percentage distance
- Consecutive up/down days
- Gap patterns
- Market regime features (SPY trend, volatility)
- Multi-timeframe momentum

SECRET WEAPON: SEC Form 4 Insider Trading (12 base features + 14 enhanced features)
Research shows insider purchases predict +2-5% abnormal returns, especially:
- CEO/CTO/CFO purchases (executives know the business best)
- Cluster buying (3+ different insiders buying = very bullish)
- Buys near 52-week low (high conviction signal)
- Net buy ratio (more buys than sells = positive sentiment)
With 119K+ trades across 224 stocks, this is valuable alpha signal!

Target: High-quality swing-trading features with raw numeric values + insider alpha + relative SPY
Output: ~139 features (OHLCV + indicators + swing + enhanced insider + relative SPY + minimal SPY context)

Usage:
    python scripts/feature_engineering.py

Changes on 2026-02-05 (Alpha Optimization):
- Integrated all enhanced features from separate scripts
- Transformed SPY to relative features
- Date range extended to 2018-2025
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


def add_enhanced_insider_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add enhanced insider features that make the data interpretable for the model.

    Categories:
    1. Unusual Activity (is this insider activity historically unusual?)
    2. Value + Price Context (are insiders buying at dips/lows?)
    3. Executive Clusters (multiple insiders buying together?)
    4. Market Context (contrarian signals)

    Created: 2026-02-05
    """
    print("\n" + "=" * 70)
    print("ADDING ENHANCED INSIDER FEATURES")
    print("=" * 70)

    df = df.copy()
    df = df.sort_values(['stock_id', 'timestamp']).reset_index(drop=True)

    # ============================================================
    # CATEGORY 1: UNUSUAL ACTIVITY FEATURES
    # ============================================================

    print("\n📊 Category 1: Unusual Activity Features")

    # 1. Unusual buying (top 20% historically for this stock)
    if 'insider_buy_count_30d' in df.columns:
        df['insider_buy_unusual_80'] = df.groupby('stock_id')['insider_buy_count_30d'].transform(
            lambda x: (x > x.rolling(252, min_periods=60).quantile(0.80)).astype(int)
        )
        df['insider_buy_unusual_90'] = df.groupby('stock_id')['insider_buy_count_30d'].transform(
            lambda x: (x > x.rolling(252, min_periods=60).quantile(0.90)).astype(int)
        )
        print("  ✓ insider_buy_unusual_80 (top 20% historically)")
        print("  ✓ insider_buy_unusual_90 (top 10% historically)")

    # 2. Unusual selling
    if 'insider_sell_count_30d' in df.columns:
        df['insider_sell_unusual_80'] = df.groupby('stock_id')['insider_sell_count_30d'].transform(
            lambda x: (x > x.rolling(252, min_periods=60).quantile(0.80)).astype(int)
        )
        print("  ✓ insider_sell_unusual_80 (top 20% selling)")

    # 3. Unusual value (insiders spending big money)
    if 'insider_buy_value_30d' in df.columns:
        df['insider_value_unusual_80'] = df.groupby('stock_id')['insider_buy_value_30d'].transform(
            lambda x: (x > x.rolling(252, min_periods=60).quantile(0.80)).astype(int)
        )
        print("  ✓ insider_value_unusual_80 (top 20% by value)")

    # ============================================================
    # CATEGORY 2: VALUE + PRICE CONTEXT FEATURES
    # ============================================================

    print("\n📊 Category 2: Value + Price Context Features")

    # 4. Insiders buying at dip (RSI < 30)
    if 'insider_buy_count_30d' in df.columns and 'rsi' in df.columns:
        df['insider_buying_dip'] = (
            (df['insider_buy_count_30d'] > 0) &
            (df['rsi'] < 30)
        ).astype(int)
        print("  ✓ insider_buying_dip (buying + RSI<30)")

    # 5. Insiders buying at oversold (RSI < 20)
    if 'insider_buy_count_30d' in df.columns and 'rsi' in df.columns:
        df['insider_buying_oversold'] = (
            (df['insider_buy_count_30d'] > 0) &
            (df['rsi'] < 20)
        ).astype(int)
        print("  ✓ insider_buying_oversold (buying + RSI<20)")

    # 6. Insiders buying at 52-week low
    if 'insider_buy_count_30d' in df.columns and 'close' in df.columns:
        # Calculate 52-week low
        df['price_52w_low'] = df.groupby('stock_id')['close'].transform(
            lambda x: x.rolling(252, min_periods=60).min()
        )
        df['near_52w_low'] = (df['close'] <= df['price_52w_low'] * 1.05).astype(int)

        df['insider_at_52w_low'] = (
            (df['insider_buy_count_30d'] > 0) &
            (df['near_52w_low'] > 0)
        ).astype(int)
        print("  ✓ insider_at_52w_low (buying near 52-week low)")

    # 7. Insiders buying below 200-day MA
    if 'insider_buy_count_30d' in df.columns and 'ma_200' in df.columns:
        df['insider_below_ma200'] = (
            (df['insider_buy_count_30d'] > 0) &
            (df['close'] < df['ma_200'])
        ).astype(int)
        print("  ✓ insider_below_ma200 (buying below 200MA)")

    # 7b. Insiders selling when price is up
    if 'insider_sell_count_30d' in df.columns and 'momentum_20d' in df.columns:
        df['insider_sell_when_up'] = (
            (df['insider_sell_count_30d'] > 0) &
            (df['momentum_20d'] > 0.10)
        ).astype(int)
        print("  ✓ insider_sell_when_up (selling after 10% rise)")

    # ============================================================
    # CATEGORY 3: EXECUTIVE CLUSTER FEATURES
    # ============================================================

    print("\n📊 Category 3: Executive Cluster Features")

    # 8. Strong conviction (high count + high value + sentiment)
    if 'insider_buy_count_30d' in df.columns and 'insider_buy_value_30d' in df.columns and 'insider_sentiment_30d' in df.columns:
        df['insider_conviction_strong'] = (
            (df['insider_buy_count_30d'] > 0) &
            (df['insider_buy_value_30d'] > 0) &
            (df['insider_sentiment_30d'] > 0.7)
        ).astype(int)
        print("  ✓ insider_conviction_strong (high count + value + sentiment)")

    # 9. Insider momentum (buying increasing)
    if 'insider_buy_count_30d' in df.columns:
        df['insider_buy_momentum'] = df.groupby('stock_id')['insider_buy_count_30d'].transform(
            lambda x: x.diff(5) > 0
        ).fillna(0).astype(int)
        print("  ✓ insider_buy_momentum (buying increasing)")

    # 10. Insiders selling at high
    if 'insider_sell_count_30d' in df.columns and 'momentum_20d' in df.columns:
        df['insider_sell_at_high'] = (
            (df['insider_sell_count_30d'] > 0) &
            (df['momentum_20d'] > 0.10)
        ).astype(int)
        print("  ✓ insider_sell_at_high (selling after 10% rise)")

    # ============================================================
    # CATEGORY 4: MARKET CONTEXT FEATURES
    # ============================================================

    print("\n📊 Category 4: Market Context Features")

    # 11. Insider buying in bear market (contrarian signal)
    if 'insider_buy_count_30d' in df.columns and 'spy_return_20d' in df.columns:
        df['insider_buy_bear_market'] = (
            (df['insider_buy_count_30d'] > 0) &
            (df['spy_return_20d'] < -0.05)
        ).astype(int)
        print("  ✓ insider_buy_bear_market (buying when SPY down 5%)")

    # 12. Insider contrarian (bullish insiders + bearish market)
    if 'insider_sentiment_30d' in df.columns and 'spy_return_20d' in df.columns:
        df['insider_contrarian'] = (
            (df['insider_sentiment_30d'] > 0.6) &
            (df['spy_return_20d'] < -0.03)
        ).astype(int)
        print("  ✓ insider_contrarian (bullish insiders + bearish market)")

    print(f"\n✅ Created 14 enhanced insider features")
    return df


def add_relative_spy_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw SPY features to relative features to force
    the model to learn stock-specific alpha instead of beta.

    Removes: spy_close, spy_ma_*, spy_uptrend*, etc.
    Adds: stock_vs_spy_*, rsi_vs_spy, etc.
    Keeps: spy_return_* for alpha calculation context

    Created: 2026-02-05
    """
    print("\n" + "=" * 70)
    print("TRANSFORMING SPY TO RELATIVE FEATURES (ALPHA-OPTIMIZED)")
    print("=" * 70)

    df = df.copy()

    # ============================================================
    # CREATE RELATIVE FEATURES
    # ============================================================

    print("\n🔄 Creating relative features (stock vs SPY)...")

    # 1. Stock vs SPY price ratio
    if 'spy_close' in df.columns and 'close' in df.columns:
        df['stock_vs_spy_ratio'] = df['close'] / df['spy_close']
        print("  ✓ stock_vs_spy_ratio (stock price / SPY price)")

    # 2. Stock vs SPY momentum (relative strength)
    if 'spy_return_20d' in df.columns and 'momentum_20d' in df.columns:
        df['stock_vs_spy_momentum'] = df['momentum_20d'] - df['spy_return_20d']
        print("  ✓ stock_vs_spy_momentum (stock momentum - SPY return)")

    # 3. Stock vs SPY volatility ratio
    if 'volatility_20d' in df.columns and 'spy_return_20d' in df.columns:
        # Calculate SPY 20-day volatility
        df_sorted = df.sort_values(['stock_id', 'timestamp'])

        # SPY volatility from returns
        df_sorted['spy_vol_20d'] = df_sorted.groupby('stock_id')['spy_return_20d'].transform(
            lambda x: x.rolling(20, min_periods=10).std()
        )

        df['stock_vs_spy_volatility'] = df_sorted['volatility_20d'] / (df_sorted['spy_vol_20d'] + 1e-6)

        print("  ✓ stock_vs_spy_volatility (stock vol / SPY vol)")

    # 4. Relative RSI (stock RSI - SPY RSI)
    if 'rsi' in df.columns and 'spy_return_20d' in df.columns:
        # Calculate SPY RSI approximation
        spy_returns = df['spy_return_20d']
        gains = spy_returns.where(spy_returns > 0, 0)
        losses = -spy_returns.where(spy_returns < 0, 0)

        avg_gain = gains.rolling(14).mean()
        avg_loss = losses.rolling(14).mean()

        df['spy_rsi'] = 100 - (100 / (1 + avg_gain / (avg_loss + 1e-6)))

        df['rsi_vs_spy'] = df['rsi'] - df['spy_rsi']
        print("  ✓ rsi_vs_spy (stock RSI - SPY RSI)")

    # ============================================================
    # REMOVE RAW SPY FEATURES (that cause beta learning)
    # ============================================================

    print("\n🗑️  Removing raw SPY features (to prevent beta learning)...")

    spy_features_to_remove = [
        'spy_close',           # Raw SPY price
        'spy_ma_200',          # SPY 200-day MA
        'spy_ma_50',           # SPY 50-day MA
        'spy_ma_20',           # SPY 20-day MA
        'spy_uptrend',         # SPY uptrend flag
        'spy_uptrend_long',    # SPY long-term uptrend
        'spy_downtrend',       # SPY downtrend flag (if exists)
    ]

    features_before = len(df.columns)
    df = df.drop(columns=[f for f in spy_features_to_remove if f in df.columns], errors='ignore')
    features_after = len(df.columns)

    removed_count = features_before - features_after
    if removed_count > 0:
        print(f"  Removed {removed_count} raw SPY features")
        for f in spy_features_to_remove:
            if f in df.columns:
                print(f"    - {f}")
    else:
        print("  (No raw SPY features found to remove)")

    # ============================================================
    # KEEP MINIMAL SPY CONTEXT (for alpha calculation)
    # ============================================================

    spy_features_to_keep = [
        'spy_return_5d',
        'spy_return_20d',
        'spy_return_60d',
    ]

    kept_spy = [f for f in spy_features_to_keep if f in df.columns]
    if kept_spy:
        print(f"\n✅ Keeping {len(kept_spy)} SPY features for alpha context:")
        for f in kept_spy:
            print(f"   - {f}")

    print(f"\n✅ Transformed SPY → Relative (stock vs SPY)")
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

    # Use 2018-2025 extended dataset (includes critical market regimes)
    start_date = datetime(2018, 1, 1)  # Extended to 2018 for 8 years of data
    end_date = datetime.now()

    print(f"\nDate range: {start_date.date()} to {end_date.date()} ({(end_date - start_date).days // 365} years)")
    print(f"  Including: 2018-2020 (trade war, corrections, COVID)")
    print(f"             2021-2025 (bull market)")

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
    # ADD ENHANCED INSIDER FEATURES (ALPHA-OPTIMIZED)
    # ============================================================

    final_df = add_enhanced_insider_features(final_df)

    # ============================================================
    # TRANSFORM SPY TO RELATIVE FEATURES (ALPHA-OPTIMIZED)
    # ============================================================

    final_df = add_relative_spy_features(final_df)

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
    dataset_folder = output_dir / f'dataset_{timestamp}'
    dataset_folder.mkdir(exist_ok=True)

    output_file = dataset_folder / 'features.parquet'

    final_df.to_parquet(output_file, index=False)

    print(f"\n✅ Saved {len(final_df)} rows with {len(final_df.columns)-2} features")
    print(f"   Dataset folder: {dataset_folder.name}/")
    print(f"   File: features.parquet")
    print(f"   Size: {output_file.stat().st_size / (1024**2):.1f} MB")

    # Save metadata
    metadata = {
        'created_at': datetime.now().isoformat(),
        'num_samples': len(final_df),
        'num_features': len(final_df.columns) - 2,
        'features': list([col for col in final_df.columns if col not in ['stock_id', 'timestamp']])
    }

    import json
    metadata_file = dataset_folder / 'metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"   Metadata: metadata.json")

    # Print feature list
    print(f"\nFinal feature list ({len(final_df.columns)-2} features):")
    feature_cols = [col for col in final_df.columns if col not in ['stock_id', 'timestamp']]
    for i, feature in enumerate(feature_cols, 1):
        print(f"  {i:2d}. {feature}")

    print("\n" + "=" * 70)
    print("✅ FEATURE ENGINEERING COMPLETE!")
    print("=" * 70)
    print(f"\n💡 Next steps:")
    print(f"   python scripts/create_labels.py --type binary --dataset-folder {dataset_folder.name}")
    print(f"   python scripts/create_labels.py --type 3class --dataset-folder {dataset_folder.name}")
    print(f"   python scripts/create_labels.py --type 5class --dataset-folder {dataset_folder.name}")
    print(f"\n   Or train directly:")
    print(f"   python train.py --dataset-folder {dataset_folder.name} --label-type binary")


if __name__ == "__main__":
    main()
