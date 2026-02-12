"""
Data loading for backtesting.

Loads historical OHLCV data and features for backtesting.
"""
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import glob


def load_backtest_data(config) -> Dict[str, pd.DataFrame]:
    """
    Load historical data for backtesting

    Args:
        config: BacktestConfig with data paths

    Returns:
        Dictionary of symbol -> DataFrame with OHLCV and features
    """
    # Find the features parquet file
    features_dir = config.data_dir

    # Look for dataset folder - prioritize enhanced dataset
    dataset_folders = sorted(
        Path(features_dir).glob('dataset_*/'),
        reverse=True  # Get latest first
    )

    # Filter to prioritize datasets - prefer backtest_tabnet, then lags, then enhanced
    preferred = [f for f in dataset_folders if 'backtest_tabnet' in f.name.lower()]
    if not preferred:
        preferred = [f for f in dataset_folders if 'lags' in f.name.lower()]
    if not preferred:
        preferred = [f for f in dataset_folders if 'enhanced' in f.name.lower()]
    if preferred:
        dataset_folder = preferred[0]
    elif dataset_folders:
        dataset_folder = dataset_folders[0]
    else:
        raise ValueError(
            f"No dataset folders found in {features_dir}. "
            "Run feature engineering first."
        )
    features_file = dataset_folder / 'features.parquet'

    if not features_file.exists():
        raise ValueError(f"No features.parquet found in {dataset_folder}")

    # Load features
    print(f"Loading features from: {features_file}")
    df = pd.read_parquet(features_file)

    # Remove duplicate columns if any
    if df.columns.duplicated().any():
        dup_cols = df.columns[df.columns.duplicated()].tolist()
        print(f"WARNING: Found duplicate columns: {dup_cols}, keeping first occurrence")
        df = df.loc[:, ~df.columns.duplicated()]

    # Rename columns to match expected format
    # Only rename stock_id to symbol if symbol doesn't already exist
    if 'stock_id' in df.columns and 'symbol' not in df.columns:
        df.rename(columns={'stock_id': 'symbol'}, inplace=True)
    elif 'symbol' not in df.columns:
        # Try to get symbol from other sources
        pass

    # Handle timestamp vs date column
    if 'timestamp' in df.columns:
        # Check if timestamp is numeric (Unix timestamp) or datetime
        if pd.api.types.is_numeric_dtype(df['timestamp']):
            # Convert numeric timestamp to datetime
            import numpy as np
            # Check if it's in seconds or milliseconds
            if df['timestamp'].max() > 1e10:  # Milliseconds
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:  # Seconds (unlikely for recent dates)
                df['date'] = pd.to_datetime(df['timestamp'], unit='s')
        else:
            df['date'] = pd.to_datetime(df['timestamp'])

        # Set date as index if it exists
        if 'date' in df.columns:
            df.set_index('date', inplace=True)
    elif 'date' not in df.columns and hasattr(df.index, 'to_datetime'):
        # Try to use existing index
        try:
            df.index = pd.to_datetime(df.index)
        except:
            pass

    # Convert index to datetime if needed
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # Filter by date range (test period only)
    start_date = pd.Timestamp(config.period.test_start)
    end_date = pd.Timestamp(config.period.test_end)

    # Filter to test period (plus some history for indicators)
    filter_start = start_date - pd.Timedelta(days=60)  # Add buffer for indicators
    df = df[(df.index >= filter_start) & (df.index <= end_date)]

    # Ensure we have the required columns
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Group by symbol and create dictionary
    data: Dict[str, pd.DataFrame] = {}

    # If symbol is a column, group by it; otherwise assume single symbol
    # Handle case where df['symbol'] might return DataFrame if there are duplicate column names
    if 'symbol' in df.columns:
        # Get the first 'symbol' column as a series
        symbol_series = df.loc[:, 'symbol']
        if isinstance(symbol_series, pd.DataFrame):
            # Multiple columns named 'symbol', use the first one
            symbol_series = symbol_series.iloc[:, 0]

        num_symbols = symbol_series.nunique()
        if num_symbols > 1:
            for symbol_val, symbol_df in df.groupby('symbol', group_keys=False):
                data[symbol_val] = symbol_df.copy()
        else:
            # Single symbol
            symbol_name = symbol_series.iloc[0]
            data[symbol_name] = df.copy()
    else:
        # symbol is not a column, might be in index or unknown
        symbol_name = 'UNKNOWN'
        data[symbol_name] = df.copy()

    print(f"Loaded {len(data)} symbols from {filter_start.date()} to {end_date.date()}")

    return data


def get_stock_list(data: Dict[str, pd.DataFrame],
                  min_price: float = 5.0,
                  min_volume: int = 100_000) -> List[str]:
    """
    Get list of tradeable stocks

    Args:
        data: Symbol -> DataFrame mapping
        min_price: Minimum stock price
        min_volume: Minimum average daily volume

    Returns:
        List of tradeable symbols
    """
    tradeable = []

    for symbol, df in data.items():
        # Calculate average volume
        avg_volume = df['volume'].mean()

        # Get current price (last close)
        current_price = df['close'].iloc[-1]

        if current_price >= min_price and avg_volume >= min_volume:
            tradeable.append(symbol)

    return tradeable
