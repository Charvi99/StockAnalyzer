"""
Test script for Polygon market hours integration
"""
import os
import sys

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Load environment variables
from pathlib import Path
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from app.services.polygon_fetcher import PolygonFetcher
from app.utils.market_hours import (
    is_market_open,
    is_market_holiday,
    is_weekend,
    get_market_status_info
)

def test_polygon_fetcher():
    """Test Polygon API methods"""
    print("=" * 60)
    print("Testing Polygon Market Data API")
    print("=" * 60)

    fetcher = PolygonFetcher()
    print("✅ Polygon client initialized\n")

    # Test market status
    print("1. Testing market status...")
    status = fetcher.get_market_status()
    if status:
        print(f"   Market: {status.get('market', 'N/A')}")
        exchanges = status.get('exchanges', {})
        print(f"   NYSE: {exchanges.get('nyse', 'N/A')}")
        print(f"   NASDAQ: {exchanges.get('nasdaq', 'N/A')}")
        print(f"   After Hours: {status.get('after_hours', False)}")
    else:
        print("   ❌ No status returned")

    # Test market holidays
    print("\n2. Testing market holidays...")
    holidays = fetcher.get_market_holidays()
    if holidays:
        print(f"   Found {len(holidays)} upcoming holidays:")
        for i, h in enumerate(holidays[:5]):
            date = h.get('date', 'N/A')
            name = h.get('name', 'Unknown')
            print(f"   {i+1}. {date} - {name}")
    else:
        print("   No holidays found")

def test_market_hours_utils():
    """Test market hours utility functions"""
    print("\n" + "=" * 60)
    print("Testing Market Hours Utilities")
    print("=" * 60)

    # Test is_market_open
    print("\n1. Testing is_market_open()...")
    is_open = is_market_open(use_polygon=True)
    print(f"   Market Open (Polygon): {is_open}")

    is_open_fallback = is_market_open(use_polygon=False)
    print(f"   Market Open (Fallback): {is_open_fallback}")

    # Test is_weekend
    print("\n2. Testing is_weekend()...")
    weekend = is_weekend()
    print(f"   Is Weekend: {weekend}")

    # Test is_market_holiday
    print("\n3. Testing is_market_holiday()...")
    holiday = is_market_holiday()
    print(f"   Is Holiday: {holiday}")

    # Test comprehensive market status
    print("\n4. Testing get_market_status_info()...")
    info = get_market_status_info()
    print(f"   Status: {info.get('status', 'N/A')}")
    print(f"   Status Detail: {info.get('status_detail', 'N/A')}")
    print(f"   Current Time (ET): {info.get('current_time_et', 'N/A')}")
    print(f"   Market Hours: {info.get('market_open_time', 'N/A')} - {info.get('market_close_time', 'N/A')}")

    # Show Polygon data if available
    if 'polygon' in info:
        print("\n   Polygon Real-Time Data:")
        polygon_data = info['polygon']
        exchanges = polygon_data.get('exchanges', {})
        print(f"     NYSE: {exchanges.get('nyse', 'N/A')}")
        print(f"     NASDAQ: {exchanges.get('nasdaq', 'N/A')}")
        print(f"     Server Time: {polygon_data.get('server_time', 'N/A')}")

if __name__ == '__main__':
    try:
        test_polygon_fetcher()
        test_market_hours_utils()
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
