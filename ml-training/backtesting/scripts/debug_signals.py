"""
Debug script to trace signal generation issue.
"""
import sys
from pathlib import Path

# Add backtesting directory to path
backtest_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backtest_dir))

# Patch print to add timestamps
import builtins
original_print = builtins.print

def debug_print(*args, **kwargs):
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    original_print(f"[{timestamp}]", *args, **kwargs)

builtins.print = debug_print

# Now import and run
from config import BacktestConfig
from core.backtester import Backtester
from strategies.buy_and_hold import BuyAndHoldStrategy
from data import load_backtest_data

def main():
    print("=" * 70)
    print("DEBUG: SIGNAL GENERATION")
    print("=" * 70)

    # Create configuration
    config = BacktestConfig()
    config.period.test_start = "2024-01-02"  # Just test a few days
    config.period.test_end = "2024-01-05"

    print(f"\nConfiguration:")
    print(f"  Period: {config.period.test_start} to {config.period.test_end}")

    # Load data
    print("\n" + "=" * 70)
    print("LOADING DATA")
    print("=" * 70)

    data = load_backtest_data(config)

    # Check data structure
    print(f"\nData structure debug:")
    print(f"  Total symbols: {len(data)}")

    # Show sample of first 3 symbols
    for i, (symbol, df) in enumerate(list(data.items())[:3]):
        print(f"  Symbol {i+1}: {symbol}")
        print(f"    Index type: {type(df.index)}")
        print(f"    Shape: {df.shape}")
        print(f"    Date range: {df.index.min()} to {df.index.max()}")
        if len(df) > 0:
            print(f"    First date: {df.index[0]} (type: {type(df.index[0])})")
            print(f"    Last date: {df.index[-1]} (type: {type(df.index[-1])})")

    # Create strategy
    print("\n" + "=" * 70)
    print("INITIALIZING STRATEGY")
    print("=" * 70)

    strategy = BuyAndHoldStrategy(config)

    # Test signal generation on first trading day
    print("\n" + "=" * 70)
    print("TESTING SIGNAL GENERATION")
    print("=" * 70)

    from datetime import date
    test_date = date(2024, 1, 2)

    print(f"\nTest date: {test_date} (type: {type(test_date)})")

    # Generate signals
    signals = strategy.generate_signals(test_date, data)

    print(f"\nSignals generated: {len(signals)}")

    if len(signals) > 0:
        print(f"First 3 signals:")
        for i, sig in enumerate(signals[:3]):
            print(f"  {i+1}. {sig.symbol} - {sig.action} (confidence: {sig.confidence})")
    else:
        print("No signals generated! Checking data...")

        # Check if data has the test date
        for symbol, df in list(data.items())[:3]:
            print(f"\n  {symbol}:")
            print(f"    Index is DatetimeIndex: {isinstance(df.index, pd.DatetimeIndex)}")

            # Try different ways to access the date
            test_ts = pd.Timestamp(test_date)
            print(f"    Test timestamp: {test_ts}")

            if test_ts in df.index:
                print(f"    Found exact match!")
                row = df.loc[test_ts]
                print(f"    Row: {row[['open', 'close', 'volume']].to_dict()}")
            else:
                print(f"    No exact match")
                # Try finding nearby dates
                nearby = df.index[(df.index >= test_ts) & (df.index <= test_ts + pd.Timedelta(days=5))]
                print(f"    Nearby dates: {nearly.tolist()[:5]}")

if __name__ == "__main__":
    import pandas as pd
    main()
