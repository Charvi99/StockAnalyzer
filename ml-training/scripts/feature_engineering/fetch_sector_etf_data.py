"""
Fetch Sector ETF Data

Fetches historical OHLCV data for 9 Select Sector SPDR ETFs going back to 2018.

Sector ETFs:
- XLK: Technology
- XLF: Financial
- XLV: Healthcare
- XLE: Energy
- XLI: Industrial
- XLB: Materials
- XLP: Consumer Staples
- XLU: Utilities
- XLRE: Real Estate

Data Sources:
1. Polygon.io (if available for ETFs)
2. Yahoo Finance (via yfinance, free, reliable back to 2018)
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Try Polygon first, fall back to Yahoo Finance
try:
    import pandas as pd
    HAS_POLYGON = True
except ImportError:
    HAS_POLYGON = False

try:
    import yfinance as yf
    HAS_YFINANCE = True
    print("✅ yfinance available")
except ImportError:
    HAS_YFINANCE = False
    print("❌ yfinance not available")

# Sector ETF definitions
SECTOR_ETFs = {
    'XLK': 'Technology',
    'XLF': 'Financial',
    'XLV': 'Healthcare',
    'XLE': 'Energy',
    'XLI': 'Industrial',
    'XLB': 'Materials',
    'XLP': 'Consumer Staples',
    'XLU': 'Utilities',
    'XLRE': 'Real Estate'
}


def fetch_from_yfinance(symbols, start_date='2018-01-01', end_date=None):
    """
    Fetch sector ETF data from Yahoo Finance using yfinance.

    Yahoo Finance has reliable historical data going back to 2018.
    """
    if not HAS_YFINANCE:
        raise ImportError("yfinance not installed. Install with: pip install yfinance")

    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    print(f"📥 Fetching data from Yahoo Finance...")
    print(f"   Symbols: {', '.join(symbols)}")
    print(f"   Date range: {start_date} to {end_date}")

    all_data = {}

    for symbol in symbols:
        try:
            print(f"\n   Fetching {symbol}...")
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date)

            if hist.empty:
                print(f"   ⚠️  No data for {symbol}")
                continue

            # Reset index to get date as column
            hist = hist.reset_index()
            hist.rename(columns={'Date': 'timestamp'}, inplace=True)

            # Standardize column names
            hist['symbol'] = symbol
            hist['timestamp'] = pd.to_datetime(hist['timestamp'])

            all_data[symbol] = hist
            print(f"   ✅ {symbol}: {len(hist)} rows from {hist['timestamp'].min()} to {hist['timestamp'].max()}")

        except Exception as e:
            print(f"   ❌ Error fetching {symbol}: {e}")

    if not all_data:
        raise ValueError("No data fetched from any symbol")

    # Combine all data
    df = pd.concat(all_data.values(), ignore_index=True)

    print(f"\n✅ Fetched {len(df)} total rows across {len(all_data)} symbols")
    return df


def fetch_from_polygon(symbols, api_key=None, start_date='2018-01-01', end_date=None):
    """
    Fetch sector ETF data from Polygon.io.

    Note: Polygon's free tier may have limitations on historical data depth.
    """
    if not api_key:
        raise ValueError("Polygon API key required")

    print(f"📥 Fetching data from Polygon.io...")
    print(f"   Symbols: {', '.join(symbols)}")
    print(f"   Date range: {start_date} to {end_date or 'present'}")

    # TODO: Implement Polygon fetching if their free tier supports ETF historical data
    raise NotImplementedError("Polygon ETF fetching not yet implemented. Use Yahoo Finance instead.")


def calculate_sector_features(df):
    """
    Calculate sector-based features for each sector ETF.

    Features:
    - sector_return_5d, sector_return_10d, sector_return_20d, sector_return_60d
    - sector_volatility_10d, sector_volatility_20d
    - sector_momentum (short vs long term)
    - sector_rsi (14-day RSI)
    - sector_volume_ratio (vs 20-day average)
    """
    print(f"\n🔧 Calculating sector features...")

    df = df.sort_values(['symbol', 'timestamp'])

    results = []

    for symbol in df['symbol'].unique():
        symbol_df = df[df['symbol'] == symbol].copy()

        # Price-based returns
        for days in [5, 10, 20, 60]:
            symbol_df[f'sector_return_{days}d'] = symbol_df['Close'].pct_change(days)

        # Volatility
        for window in [10, 20]:
            symbol_df[f'sector_volatility_{window}d'] = (
                symbol_df['Close'].pct_change().rolling(window).std() * np.sqrt(252)
            )

        # Momentum (convergence/divergence)
        symbol_df['sector_momentum_5_20'] = (
            symbol_df['sector_return_5d'] - symbol_df['sector_return_20d']
        )

        # RSI
        delta = symbol_df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        symbol_df['sector_rsi'] = 100 - (100 / (1 + rs))

        # Volume ratio
        symbol_df['sector_volume_avg20d'] = symbol_df['Volume'].rolling(20).mean()
        symbol_df['sector_volume_ratio'] = (
            symbol_df['Volume'] / symbol_df['sector_volume_avg20d']
        )

        results.append(symbol_df)

    df = pd.concat(results, ignore_index=True)

    print(f"   ✅ Calculated sector features")
    return df


def save_sector_data(df, output_dir):
    """Save sector ETF data"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "sector_etf_data.parquet"
    df.to_parquet(output_file, index=False)

    print(f"\n✅ Saved sector data to: {output_file}")
    print(f"   Shape: {df.shape}")
    print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"   Symbols: {df['symbol'].unique()}")

    return output_file


def main():
    print("=" * 70)
    print("FETCH SECTOR ETF DATA (2018-Present)")
    print("=" * 70)

    # Configuration
    symbols = list(SECTOR_ETFs.keys())
    start_date = '2018-01-01'
    end_date = None  # Current date
    output_dir = "/app/outputs/sector_data"

    # Fetch data
    if HAS_YFINANCE:
        df = fetch_from_yfinance(symbols, start_date, end_date)
    else:
        raise ImportError("Need yfinance installed. Install with: pip install yfinance")

    # Calculate sector features
    df = calculate_sector_features(df)

    # Save data
    save_sector_data(df, output_dir)

    # Summary
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("1. Sector ETF data saved to /app/outputs/sector_data/sector_etf_data.parquet")
    print("2. Use this data to create sector-relative features for your stocks")
    print("3. Example features to create:")
    print("   - stock_vs_sector_return = stock_return_20d / sector_return_20d")
    print("   - sector_relative_strength = stock_performance - sector_performance")
    print("   - sector_momentum_alignment = stock and sector moving same direction")
    print("=" * 70)


if __name__ == "__main__":
    main()
