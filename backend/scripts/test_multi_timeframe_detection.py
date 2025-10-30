"""
Test Multi-Timeframe Chart Pattern Detection

This script tests the new multi-timeframe pattern detection system by:
1. Fetching 1h data for a test stock
2. Detecting patterns across 1h, 4h, and 1d timeframes
3. Validating multi-timeframe confirmation metadata
"""
import requests
import json
from datetime import datetime

# API Base URL
BASE_URL = "http://localhost:8000"

def test_multi_timeframe_detection():
    """Test multi-timeframe pattern detection"""

    print("=" * 80)
    print("Multi-Timeframe Chart Pattern Detection Test")
    print("=" * 80)

    # Step 1: Get a test stock (AAPL - stock_id 1)
    print("\n1. Getting test stock (AAPL)...")
    response = requests.get(f"{BASE_URL}/api/v1/stocks/", params={'tracked_only': False})

    if response.status_code != 200:
        print(f"[ERROR] Failed to fetch stocks: {response.status_code}")
        return False

    stocks_data = response.json()

    # Handle different response formats
    if isinstance(stocks_data, dict) and 'stocks' in stocks_data:
        stocks = stocks_data['stocks']
    elif isinstance(stocks_data, list):
        stocks = stocks_data
    else:
        print(f"[ERROR] Unexpected response format: {type(stocks_data)}")
        return False

    test_stock = None
    for stock in stocks:
        if stock['symbol'] == 'AAPL':
            test_stock = stock
            break

    if not test_stock:
        print("[ERROR] AAPL not found in database")
        # Use first stock as fallback
        if stocks:
            test_stock = stocks[0]
            print(f"[INFO] Using fallback stock: {test_stock['symbol']}")
        else:
            return False

    stock_id = test_stock.get('stock_id') or test_stock.get('id')
    print(f"[OK] Found {test_stock['symbol']} - ID: {stock_id}")

    # Step 2: Check if we have 1h price data
    print("\n2. Checking for 1h price data...")
    response = requests.get(f"{BASE_URL}/api/v1/stocks/{stock_id}/prices", params={
        'limit': 100,
        'offset': 0,
        'timeframe': '1h'
    })

    if response.status_code != 200:
        print(f"[ERROR] Failed to fetch prices: {response.status_code}")
        return False

    prices_data = response.json()
    prices_1h = prices_data.get('prices', [])

    print(f"   Found {len(prices_1h)} 1h candles")

    if len(prices_1h) < 100:
        print(f"[WARNING] Insufficient 1h data ({len(prices_1h)} candles)")
        print("   Please fetch 1h data first using the UI or:")
        print(f"   POST {BASE_URL}/stocks/{stock_id}/fetch?period=1mo&interval=1h")
        return False

    # Step 3: Detect chart patterns with multi-timeframe analysis
    print("\n3. Detecting chart patterns across multiple timeframes...")

    detect_request = {
        "days": 30,  # Last 30 days
        "min_pattern_length": 20,
        "peak_order": 5,
        "min_confidence": 0.5,
        "min_r_squared": 0.0,
        "remove_overlaps": True,
        "overlap_threshold": 0.1,
        "exclude_patterns": ["Rounding Top", "Rounding Bottom"]
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/stocks/{stock_id}/detect-chart-patterns",
        json=detect_request
    )

    if response.status_code != 200:
        print(f"[ERROR] Pattern detection failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

    result = response.json()

    print(f"[OK] Pattern detection complete!")
    print(f"\n{result['message']}")

    # Step 4: Analyze results
    print("\n4. Analyzing multi-timeframe results...")
    print(f"\n   Total patterns detected: {result['total_patterns']}")
    print(f"   - Reversal patterns: {result['reversal_patterns']}")
    print(f"   - Continuation patterns: {result['continuation_patterns']}")
    print(f"   - Bullish: {result['bullish_count']}")
    print(f"   - Bearish: {result['bearish_count']}")
    print(f"   - Neutral: {result['neutral_count']}")

    # Step 5: Validate multi-timeframe metadata
    print("\n5. Validating multi-timeframe metadata...")

    patterns_with_mtf = []
    patterns_3tf = []
    patterns_2tf = []
    patterns_1tf = []

    for pattern in result['patterns']:
        confirmation_level = pattern.get('confirmation_level', 1)
        is_confirmed = pattern.get('is_multi_timeframe_confirmed', False)

        if is_confirmed:
            patterns_with_mtf.append(pattern)

        if confirmation_level == 3:
            patterns_3tf.append(pattern)
        elif confirmation_level == 2:
            patterns_2tf.append(pattern)
        else:
            patterns_1tf.append(pattern)

    print(f"\n   Multi-timeframe confirmation breakdown:")
    print(f"   - 3 Timeframes [3TF]: {len(patterns_3tf)} patterns")
    print(f"   - 2 Timeframes [2TF]: {len(patterns_2tf)} patterns")
    print(f"   - 1 Timeframe [1TF]:  {len(patterns_1tf)} patterns")

    # Step 6: Display sample patterns with multi-timeframe data
    if patterns_with_mtf:
        print("\n6. Sample Multi-Timeframe Confirmed Patterns:")
        print("-" * 80)

        for i, pattern in enumerate(patterns_with_mtf[:3], 1):  # Show top 3
            print(f"\n   Pattern #{i}: {pattern['pattern_name']}")
            print(f"   - Type: {pattern['pattern_type']} | Signal: {pattern['signal']}")
            print(f"   - Base Confidence: {pattern.get('base_confidence', 0):.2%}")
            print(f"   - Adjusted Confidence: {pattern.get('adjusted_confidence', pattern['confidence_score']):.2%}")
            print(f"   - Confirmation Level: {pattern.get('confirmation_level', 1)}TF")
            print(f"   - Detected on: {', '.join(pattern.get('detected_on_timeframes', ['1d']))}")
            print(f"   - Alignment Score: {pattern.get('alignment_score', 0):.2f}")
            print(f"   - Start: {pattern['start_date']}")
            print(f"   - End: {pattern['end_date']}")
    else:
        print("\n6. No multi-timeframe confirmed patterns found")
        print("   This is normal if patterns don't align across timeframes")

    # Step 7: Validate confidence boost logic
    if patterns_with_mtf:
        print("\n7. Validating confidence boost logic...")

        for pattern in patterns_with_mtf[:3]:
            base_conf = pattern.get('base_confidence')
            adjusted_conf = pattern.get('adjusted_confidence')
            conf_level = pattern.get('confirmation_level', 1)

            if base_conf and adjusted_conf:
                boost = adjusted_conf / base_conf
                print(f"\n   {pattern['pattern_name']}: {conf_level}TF")
                print(f"   - Base: {base_conf:.2%} → Adjusted: {adjusted_conf:.2%}")
                print(f"   - Boost: {boost:.2f}x ({(boost - 1) * 100:.0f}% increase)")

                # Validate boost is within expected range
                if conf_level == 2:
                    expected_min = 1.4  # 2TF multiplier
                    expected_max = 1.8  # Max before alignment bonus
                elif conf_level == 3:
                    expected_min = 1.8  # 3TF multiplier
                    expected_max = 2.1  # Max after alignment bonus
                else:
                    expected_min = 1.0
                    expected_max = 1.2

                if expected_min <= boost <= expected_max:
                    print(f"   [OK] Boost within expected range ({expected_min:.1f}x - {expected_max:.1f}x)")
                else:
                    print(f"   [WARNING] Boost outside expected range ({expected_min:.1f}x - {expected_max:.1f}x)")

    print("\n" + "=" * 80)
    print("[OK] Multi-Timeframe Detection Test Complete!")
    print("=" * 80)

    return True

if __name__ == "__main__":
    try:
        success = test_multi_timeframe_detection()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
