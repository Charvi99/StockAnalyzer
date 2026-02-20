"""
Advanced Volatility Features

Creates additional volatility-based features since natr (Normalized ATR)
is consistently the top feature family.

Features to add:
1. Volatility Rank - stock's volatility percentile vs all stocks
2. Volatility Acceleration - 2nd derivative of volatility
3. Volatility Regime - clustering into low/medium/high volatility
4. Volatility Breakout - natr breaking above recent range
5. Volatility Convergence - volatility tightening before move
6. ATR multiple - ATR as multiple of stock price
7. Historical volatility percentile - vs last 20/60/252 days
"""
import pandas as pd
import numpy as np
from pathlib import Path


def add_volatility_rank(df, window=20):
    """
    Volatility Rank - stock's volatility percentile vs cross-section of stocks

    High volatility rank = stock is more volatile than usual
    Low volatility rank = stock is unusually calm
    """
    print("   Adding volatility_rank...")

    # Calculate cross-sectional percentile for each timestamp
    df['volatility_rank_20d'] = df.groupby('timestamp')['natr'].transform(
        lambda x: x.rank(pct=True)
    )

    return df


def add_volatility_acceleration(df):
    """
    Volatility Acceleration - 2nd derivative of volatility

    Positive = volatility accelerating (expansion phase)
    Negative = volatility decelerating (contraction phase)
    Zero = volatility stable
    """
    print("   Adding volatility_acceleration...")

    # First derivative: rate of change
    df['volatility_change'] = df.groupby('stock_id')['natr'].diff()

    # Second derivative: acceleration
    df['volatility_acceleration'] = df.groupby('stock_id')['volatility_change'].diff()

    # Clean up
    df.drop('volatility_change', axis=1, inplace=True)

    return df


def add_volatility_regime(df, window=20):
    """
    Volatility Regime - classify into low/medium/high using K-means

    Regimes:
    0 = Low volatility (consolidation)
    1 = Medium volatility (normal)
    2 = High volatility (expansion)
    """
    print("   Adding volatility_regime...")

    from sklearn.cluster import KMeans

    # Calculate rolling mean of natr for each stock
    df['natr_rolling_mean'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(window, min_periods=5).mean()
    )

    # Fill NaN with overall median
    global_median = df['natr_rolling_mean'].median()
    df['natr_rolling_mean'] = df['natr_rolling_mean'].fillna(global_median)

    # K-means clustering (3 regimes)
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df['volatility_regime'] = kmeans.fit_predict(
        df[['natr_rolling_mean']].values
    )

    # Clean up
    df.drop('natr_rolling_mean', axis=1, inplace=True)

    return df


def add_volatility_breakout(df, lookback=20):
    """
    Volatility Breakout - natr breaking above recent range

    Signals potential trend change or breakout.
    """
    print("   Adding volatility_breakout...")

    # Calculate rolling max of natr
    df['natr_rolling_max'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(lookback, min_periods=5).max()
    )

    # Breakout when current natr exceeds rolling max
    df['volatility_breakout'] = (
        df['natr'] > df['natr_rolling_max'].shift(1)
    ).astype(int)

    # Clean up
    df.drop('natr_rolling_max', axis=1, inplace=True)

    return df


def add_volatility_convergence(df, window=10):
    """
    Volatility Convergence - volatility tightening (Bollinger Band squeeze)

    Low convergence = volatility range widening (breakout imminent)
    High convergence = volatility tightening (consolidation)
    """
    print("   Adding volatility_convergence...")

    # Calculate rolling range of natr
    df['natr_rolling_max'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(window, min_periods=5).max()
    )
    df['natr_rolling_min'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(window, min_periods=5).min()
    )

    # Convergence = (max - min) / max
    df['volatility_convergence'] = (
        (df['natr_rolling_max'] - df['natr_rolling_min']) /
        df['natr_rolling_max'].replace(0, np.nan)
    )

    # Clean up
    df.drop(['natr_rolling_max', 'natr_rolling_min'], axis=1, inplace=True)

    return df


def add_atr_multiple(df):
    """
    ATR Multiple - ATR as percentage of stock price

    Higher multiple = more volatile relative to price
    Lower multiple = stock is expensive (low volatility)
    """
    print("   Adding atr_multiple...")

    # atr_normalized is ATR / close, so we already have this
    # Just rename for clarity if needed
    if 'atr_normalized' in df.columns:
        df['atr_multiple'] = df['atr_normalized']

    return df


def add_historical_volatility_percentile(df, windows=[20, 60, 252]):
    """
    Historical Volatility Percentile - current natr vs historical distribution

    For each window, shows where current volatility ranks historically.
    High percentile = stock is more volatile than usual for this period
    Low percentile = stock is unusually calm
    """
    print("   Adding historical_volatility_percentile...")

    for window in windows:
        col_name = f'natr_percentile_{window}d'

        # Calculate rolling rank percentile
        df[col_name] = df.groupby('stock_id')['natr'].transform(
            lambda x: x.rolling(window, min_periods=5).rank(pct=True)
        )

    return df


def add_volatility_momentum(df, short=5, long=20):
    """
    Volatility Momentum - is volatility expanding or contracting?

    Positive = volatility expanding (increasing uncertainty)
    Negative = volatility contracting (stabilizing)
    """
    print("   Adding volatility_momentum...")

    # Rate of change of natr
    df['volatility_momentum'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.pct_change(short)
    )

    # Compare short vs long term
    df[f'natr_{short}d'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(short).mean()
    )
    df[f'natr_{long}d'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(long).mean()
    )

    df['volatility_trend'] = df[f'natr_{short}d'] - df[f'natr_{long}d']

    # Clean up
    df.drop([f'natr_{short}d', f'natr_{long}d'], axis=1, inplace=True)

    return df


def add_volatility_features(df):
    """
    Add all advanced volatility features to dataframe.
    """
    print("=" * 70)
    print("ADDING ADVANCED VOLATILITY FEATURES")
    print("=" * 70)

    required_cols = ['stock_id', 'timestamp', 'natr', 'atr_normalized', 'close']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    print(f"\nInput shape: {df.shape}")

    # Add features
    df = add_volatility_rank(df)
    df = add_volatility_acceleration(df)
    df = add_volatility_regime(df)
    df = add_volatility_breakout(df)
    df = add_volatility_convergence(df)
    df = add_atr_multiple(df)
    df = add_historical_volatility_percentile(df)
    df = add_volatility_momentum(df)

    print(f"\n✅ Output shape: {df.shape}")
    print(f"   Added: {df.shape[1] - len(required_cols)} new features")

    return df


def main():
    """Test the volatility features on existing data"""
    print("=" * 70)
    print("ADVANCED VOLATILITY FEATURES - TEST")
    print("=" * 70)

    # Load existing features
    features_file = "/app/outputs/features/dataset_filtered_20260209_130311/features.parquet"

    print(f"\n📂 Loading features from: {features_file}")
    df = pd.read_parquet(features_file)

    # Add close column if it exists (for ATR multiple)
    if 'close' not in df.columns and 'Close' in df.columns:
        df['close'] = df['Close']
    elif 'close' not in df.columns and 'adj_close' in df.columns:
        df['close'] = df['adj_close']

    # Check required columns
    required = ['stock_id', 'timestamp', 'natr']
    missing = [col for col in required if col not in df.columns]
    if missing:
        print(f"❌ Missing required columns: {missing}")
        print("   Cannot add volatility features")
        return

    # Take sample for testing
    print(f"\n📊 Taking sample of 100,000 rows for testing...")
    df_sample = df.head(100000).copy()

    # Add features
    df_features = add_volatility_features(df_sample)

    # Show new features
    new_features = [col for col in df_features.columns if col not in df.columns]
    print(f"\n✅ New features added ({len(new_features)}):")
    for feat in new_features[:20]:
        print(f"   - {feat}")
    if len(new_features) > 20:
        print(f"   ... and {len(new_features) - 20} more")

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("1. Test these features on a sample")
    print("2. If they look good, add to full dataset")
    print("3. Retrain model and check feature importance")
    print("4. Keep the ones that add predictive power")
    print("=" * 70)


if __name__ == "__main__":
    main()
