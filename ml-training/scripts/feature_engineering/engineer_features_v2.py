"""
Feature Engineering 2.0 - Add Sector & Advanced Volatility Features

Combines:
1. Sector ETF data (9 Select Sector SPDRs)
2. Advanced volatility features (volatility rank, regime, breakout, etc.)
3. Sector-relative features (stock vs sector performance)

Creates an enhanced feature set for training.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from ml_framework.config import Config


# Sector ETF mappings
SECTOR_ETFs = {
    'Technology': 'XLK',
    'Financial': 'XLF',
    'Healthcare': 'XLV',
    'Energy': 'XLE',
    'Industrial': 'XLI',
    'Materials': 'XLB',
    'Consumer Staples': 'XLP',
    'Utilities': 'XLU',
    'Real Estate': 'XLRE'
}


def load_stock_data(dataset_folder):
    """Load stock features"""
    dataset_path = Path("/app/outputs/features") / dataset_folder
    features_file = dataset_path / "features.parquet"

    print(f"📂 Loading stock data from: {features_file}")
    df = pd.read_parquet(features_file)
    print(f"   Loaded {len(df)} rows, {len(df.columns)} columns")

    return df


def load_sector_data():
    """Load sector ETF data"""
    sector_file = Path("/app/outputs/sector_data/sector_etf_data.parquet")

    if not sector_file.exists():
        raise FileNotFoundError(
            f"Sector data not found at {sector_file}\n"
            "Run: python scripts/fetch_sector_etf_data.py"
        )

    print(f"📂 Loading sector data from: {sector_file}")
    df = pd.read_parquet(sector_file)

    # Normalize timestamp to date only (remove timezone)
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
    df['timestamp'] = df['timestamp'].dt.normalize()

    print(f"   Loaded {len(df)} rows, {len(df.columns)} columns")
    print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    return df


def add_sector_features(stock_df, sector_df):
    """
    Add sector-relative features to stock data.

    For each stock, we need to know which sector it belongs to.
    Since we don't have that mapping, we'll use SPY (market) as proxy
    or create features for each sector ETF.
    """
    print("\n🔧 Adding sector features...")

    # Merge sector data on timestamp
    # We'll create features for each sector ETF
    results = []

    for sector, etf_symbol in SECTOR_ETFs.items():
        print(f"   Processing {sector} sector ({etf_symbol})...")

        # Get sector ETF data
        sector_data = sector_df[sector_df['symbol'] == etf_symbol][
            ['timestamp', 'sector_return_5d', 'sector_return_10d',
             'sector_return_20d', 'sector_return_60d', 'sector_rsi',
             'sector_volatility_10d', 'sector_volatility_20d']
        ].copy()

        # Rename feature columns to include sector name (but NOT timestamp)
        rename_map = {
            'sector_return_5d': f'{sector.lower()}_sector_return_5d',
            'sector_return_10d': f'{sector.lower()}_sector_return_10d',
            'sector_return_20d': f'{sector.lower()}_sector_return_20d',
            'sector_return_60d': f'{sector.lower()}_sector_return_60d',
            'sector_rsi': f'{sector.lower()}_sector_rsi',
            'sector_volatility_10d': f'{sector.lower()}_sector_volatility_10d',
            'sector_volatility_20d': f'{sector.lower()}_sector_volatility_20d',
        }
        sector_data = sector_data.rename(columns=rename_map)

        # Merge with stock data
        merged = pd.merge(
            stock_df[['stock_id', 'timestamp']],
            sector_data,
            on='timestamp',
            how='left'
        )

        # Forward fill sector data (weekends, holidays)
        sector_cols = [col for col in merged.columns if col.startswith(f'{sector.lower()}_')]
        merged[sector_cols] = merged[sector_cols].fillna(method='ffill').fillna(method='bfill')

        results.append(merged)

    # Combine all sector features
    # This creates wide format with one column per sector per feature
    all_sectors = results[0]
    for df in results[1:]:
        all_sectors = pd.merge(
            all_sectors,
            df,
            on=['stock_id', 'timestamp'],
            how='outer'
        )

    # Select final sector features (use Technology as primary for now)
    # In production, you'd map each stock to its actual sector
    final_sector_cols = [
        'technology_sector_return_20d',
        'technology_sector_return_60d',
        'technology_sector_rsi',
        'financial_sector_return_20d',
        'financial_sector_return_60d',
    ]

    # Ensure columns exist
    available_sectors = [col for col in final_sector_cols if col in all_sectors.columns]
    print(f"   Selected {len(available_sectors)} sector features")

    # Merge back to original dataframe
    stock_df = pd.merge(
        stock_df,
        all_sectors[['stock_id', 'timestamp'] + available_sectors],
        on=['stock_id', 'timestamp'],
        how='left'
    )

    # Fill missing sector data
    stock_df[available_sectors] = stock_df[available_sectors].fillna(0)

    print(f"   ✅ Added {len(available_sectors)} sector features")

    return stock_df


def add_volatility_features(df):
    """Add advanced volatility features"""
    print("\n🔧 Adding advanced volatility features...")

    # 1. Volatility rank (cross-sectional percentile)
    df['volatility_rank_20d'] = df.groupby('timestamp')['natr'].transform(
        lambda x: x.rank(pct=True)
    )

    # 2. Volatility acceleration
    df['volatility_acceleration'] = df.groupby('stock_id')['natr'].diff().diff()

    # 3. Volatility trend (short vs long term)
    df['natr_5d'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(5, min_periods=3).mean()
    )
    df['natr_20d'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(20, min_periods=10).mean()
    )
    df['volatility_trend'] = df['natr_5d'] - df['natr_20d']

    # 4. Volatility regime (k-means clustering)
    from sklearn.cluster import KMeans
    df['natr_rolling_mean'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(20, min_periods=5).mean()
    )
    global_mean = df['natr_rolling_mean'].median()
    df['natr_rolling_mean'] = df['natr_rolling_mean'].fillna(global_mean)

    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df['volatility_regime'] = kmeans.fit_predict(df[['natr_rolling_mean']].values)

    # 5. Volatility breakout
    df['natr_rolling_max'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(20, min_periods=5).max()
    )
    df['volatility_breakout'] = (
        df['natr'] > df['natr_rolling_max'].shift(1)
    ).astype(int)

    # 6. Volatility convergence (Bollinger squeeze)
    df['natr_rolling_max'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(10, min_periods=5).max()
    )
    df['natr_rolling_min'] = df.groupby('stock_id')['natr'].transform(
        lambda x: x.rolling(10, min_periods=5).min()
    )
    df['volatility_convergence'] = (
        (df['natr_rolling_max'] - df['natr_rolling_min']) /
        df['natr_rolling_max'].replace(0, np.nan)
    )

    # 7. Historical volatility percentiles
    for window in [20, 60]:
        df[f'natr_percentile_{window}d'] = df.groupby('stock_id')['natr'].transform(
            lambda x: x.rolling(window, min_periods=5).rank(pct=True)
        )

    # Clean up temporary columns
    temp_cols = ['natr_rolling_mean', 'natr_5d', 'natr_20d',
                  'natr_rolling_max', 'natr_rolling_min']
    df.drop(columns=[col for col in temp_cols if col in df.columns], inplace=True)

    print(f"   ✅ Added 8 advanced volatility features")

    return df


def create_enhanced_dataset(dataset_folder):
    """Create enhanced dataset with new features"""
    print("=" * 80)
    print("FEATURE ENGINEERING 2.0 - SECTOR + VOLATILITY FEATURES")
    print("=" * 80)

    # Load data
    stock_df = load_stock_data(dataset_folder)
    sector_df = load_sector_data()

    original_features = len(stock_df.columns)
    print(f"\n📊 Original dataset: {stock_df.shape}")
    print(f"   Features: {original_features}")

    # Add sector features
    stock_df = add_sector_features(stock_df, sector_df)

    # Add volatility features
    stock_df = add_volatility_features(stock_df)

    new_features = len(stock_df.columns)
    added_features = new_features - original_features

    print(f"\n✅ Enhanced dataset: {stock_df.shape}")
    print(f"   Total features: {new_features}")
    print(f"   Added features: {added_features}")

    # Save enhanced dataset
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = Path(f"/app/outputs/features/dataset_enhanced_{timestamp}")
    output_folder.mkdir(parents=True, exist_ok=True)

    # Save features
    features_file = output_folder / "features.parquet"
    stock_df.to_parquet(features_file, index=False)

    # Copy label files
    source_folder = Path("/app/outputs/features") / dataset_folder
    for label_file in source_folder.glob("labels_*.parquet"):
        import shutil
        shutil.copy(label_file, output_folder / label_file.name)

    # Copy metadata
    metadata_file = source_folder / "metadata.json"
    if metadata_file.exists():
        import shutil
        shutil.copy(metadata_file, output_folder / "metadata.json")

    print(f"\n✅ Saved enhanced dataset to: {output_folder.name}")
    print(f"   Location: /app/outputs/features/{output_folder.name}")

    return output_folder.name


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Add sector and volatility features")
    parser.add_argument(
        '--dataset-folder',
        type=str,
        default='dataset_filtered_20260209_130311',
        help='Source dataset folder'
    )

    args = parser.parse_args()

    try:
        new_folder = create_enhanced_dataset(args.dataset_folder)

        print("\n" + "=" * 80)
        print("✅ FEATURE ENGINEERING COMPLETE!")
        print("=" * 80)
        print(f"\nNew enhanced dataset: {new_folder}")
        print("\nReady to train with:")
        print(f"  python train.py --trials 30 --dataset-folder {new_folder} --label-type binary")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
