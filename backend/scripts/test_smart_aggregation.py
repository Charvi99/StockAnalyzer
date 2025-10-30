"""
Test Script for Smart Aggregation (1h base timeframe)
Tests the complete multi-timeframe aggregation flow
"""
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, 'backend')
sys.path.insert(0, 'backend/app')

from app.services.timeframe_aggregator import TimeframeAggregator
from app.config.timeframe_config import TimeframeConfig


def generate_test_1h_data(num_days=30):
    """Generate test 1h OHLCV data"""
    print(f"\n{'='*60}")
    print(f"GENERATING TEST DATA: {num_days} days of 1h bars")
    print(f"{'='*60}")

    # Market hours: 9:30 AM - 4:00 PM ET = 6.5 hours/day
    # But we'll generate 24h for simplicity
    hours_per_day = 7  # Approximate market hours
    total_bars = num_days * hours_per_day

    # Generate timestamps (1h intervals)
    end_date = datetime.now()
    timestamps = pd.date_range(
        end=end_date,
        periods=total_bars,
        freq='1H'
    )

    # Generate realistic price data with trend
    base_price = 100.0
    trend = np.linspace(0, 20, total_bars)  # Uptrend
    noise = np.random.randn(total_bars) * 2
    close_prices = base_price + trend + noise

    # Generate OHLC from close
    df = pd.DataFrame({
        'close': close_prices,
        'open': close_prices + np.random.randn(total_bars) * 0.5,
        'high': close_prices + abs(np.random.randn(total_bars) * 1.5),
        'low': close_prices - abs(np.random.randn(total_bars) * 1.5),
        'volume': np.random.randint(1000000, 5000000, total_bars)
    }, index=timestamps)

    # Ensure high >= low
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)

    print(f"Generated {len(df)} 1h bars")
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    print(f"Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")

    return df


def test_aggregation(df_1h, target_timeframe):
    """Test aggregation to a specific timeframe"""
    print(f"\n{'-'*60}")
    print(f"TEST: Aggregating 1h -> {target_timeframe}")
    print(f"{'-'*60}")

    df_aggregated = TimeframeAggregator.get_aggregated_timeframe(
        df_1h, target_timeframe
    )

    if df_aggregated.empty:
        print(f"[FAIL] Aggregation returned empty DataFrame")
        return False

    print(f"[PASS] Aggregated {len(df_1h)} 1h bars -> {len(df_aggregated)} {target_timeframe} bars")
    print(f"       Date range: {df_aggregated.index.min()} to {df_aggregated.index.max()}")
    print(f"       Price range: ${df_aggregated['low'].min():.2f} - ${df_aggregated['high'].max():.2f}")

    # Validate aggregation
    is_valid = TimeframeAggregator.validate_aggregation(df_1h, df_aggregated)

    if is_valid:
        print(f"[PASS] Aggregation validation passed")
    else:
        print(f"[FAIL] Aggregation validation failed")
        return False

    # Check sample bars
    print(f"\nSample {target_timeframe} bars (last 3):")
    print(df_aggregated[['open', 'high', 'low', 'close', 'volume']].tail(3))

    return True


def test_all_timeframes():
    """Test all aggregated timeframes"""
    print("\n" + "="*60)
    print("SMART AGGREGATION TEST SUITE")
    print("Base Timeframe: 1 Hour")
    print("="*60)

    # Generate test data
    df_1h = generate_test_1h_data(num_days=90)  # 3 months of 1h data

    # Get aggregated timeframes
    aggregated_tfs = TimeframeConfig.get_aggregated_timeframes()

    print(f"\n{'='*60}")
    print(f"TESTING AGGREGATIONS")
    print(f"Aggregated timeframes: {', '.join(aggregated_tfs)}")
    print(f"{'='*60}")

    results = {}

    for tf in aggregated_tfs:
        success = test_aggregation(df_1h, tf)
        results[tf] = success

    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for tf, success in results.items():
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} {tf}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All aggregation tests passed!")
    else:
        print(f"\n[FAILURE] {total - passed} tests failed")

    # Print storage info
    print(f"\n{'='*60}")
    print("STORAGE INFORMATION")
    print(f"{'='*60}")

    storage_info = TimeframeConfig.get_storage_info()
    for key, value in storage_info.items():
        print(f"  {key}: {value}")

    return passed == total


def test_config():
    """Test TimeframeConfig"""
    print(f"\n{'='*60}")
    print("TEST: TimeframeConfig")
    print(f"{'='*60}")

    # Test base timeframe
    base_tf = TimeframeConfig.get_base_timeframe()
    print(f"Base timeframe: {base_tf}")
    assert base_tf == '1h', "Base timeframe should be 1h"
    print("[PASS] Base timeframe is 1h")

    # Test aggregated timeframes
    agg_tfs = TimeframeConfig.get_aggregated_timeframes()
    print(f"Aggregated timeframes: {agg_tfs}")
    expected = ['2h', '4h', '1d', '1w', '1mo']
    assert agg_tfs == expected, f"Expected {expected}, got {agg_tfs}"
    print("[PASS] Aggregated timeframes correct")

    # Test is_aggregated
    assert TimeframeConfig.is_aggregated('1d') == True
    assert TimeframeConfig.is_aggregated('1h') == False
    print("[PASS] is_aggregated() works correctly")

    # Test lookback
    lookback = TimeframeConfig.get_default_lookback('1h')
    print(f"Default lookback for 1h: {lookback} days")
    assert lookback == 90, f"Expected 90, got {lookback}"
    print("[PASS] Default lookback correct")

    print("\n[PASS] TimeframeConfig tests passed")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("SMART AGGREGATION IMPLEMENTATION TEST")
    print("Testing 1h base timeframe with aggregation to higher timeframes")
    print("="*60)

    # Test 1: Config
    config_ok = test_config()

    # Test 2: Aggregations
    aggregation_ok = test_all_timeframes()

    # Final result
    print("\n" + "="*60)
    print("FINAL RESULT")
    print("="*60)

    if config_ok and aggregation_ok:
        print("\n[SUCCESS] All tests passed!")
        print("\nSmart Aggregation is ready for production use.")
        print("\nNext steps:")
        print("1. Fetch 1h data from Polygon.io for your stocks")
        print("2. Use TimeframeService.get_price_data_smart() in your API")
        print("3. All higher timeframes (2h, 4h, 1d, 1w, 1mo) will be aggregated automatically")
        return 0
    else:
        print("\n[FAILURE] Some tests failed")
        print("Please review the errors above")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
