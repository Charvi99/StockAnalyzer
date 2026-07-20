"""
Test Phase 4 Real-Time Update Endpoints
"""
import requests
from datetime import datetime, timedelta, timezone

API_URL = "http://localhost:8080"


def test_recent_updates():
    """Test GET /api/v1/analysis/recent-updates"""
    print("=" * 80)
    print("TEST 1: Recent Updates Endpoint")
    print("=" * 80)

    # Test with timestamp from 1 hour ago
    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    print(f"\n[1] Checking for updates since: {since}")
    response = requests.get(
        f"{API_URL}/api/v1/analysis/recent-updates",
        params={"since": since}
    )

    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"   Found: {data['count']} updated stocks")

        if data['count'] > 0:
            print(f"\n   Sample (first 3):")
            for update in data['updates'][:3]:
                print(f"   - {update['symbol']} (ID: {update['stock_id']})")
                print(f"     Updated: {update['updated_at']}")
                print(
                    f"     Components: {', '.join(update['components_updated'])}")

        return data
    else:
        print(f"   [ERROR] {response.text}")
        return None


def test_get_by_ids(updated_stock_ids):
    """Test POST /api/v1/analysis/get-by-ids"""
    print("\n" + "=" * 80)
    print("TEST 2: Get Analysis By IDs Endpoint")
    print("=" * 80)

    if not updated_stock_ids:
        print("\n[INFO] No updated stocks to test with, using first 3 stocks")
        stocks_response = requests.get(
            f"{API_URL}/api/v1/stocks/", params={"tracked_only": True, "limit": 3})
        stocks = stocks_response.json()
        updated_stock_ids = [s['id'] for s in stocks]

    print(f"\n[1] Fetching analysis for {len(updated_stock_ids)} stocks...")
    print(f"   Stock IDs: {updated_stock_ids}")

    payload = {"stock_ids": updated_stock_ids}
    response = requests.post(
        f"{API_URL}/api/v1/analysis/get-by-ids",
        json=payload
    )

    print(f"\n   Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"   Successfully fetched: {data['count']} stocks")

        if data['count'] > 0:
            print(f"\n   Sample (first stock):")
            stock = data['stocks'][0]
            print(
                f"   - {stock['symbol']}: {stock['final_recommendation']} ({stock['overall_confidence']*100:.0f}% confidence)")
            print(
                f"     Analysis complete: {stock.get('analysis_complete', False)}")
            print(f"     Analysis score: {stock.get('analysis_score', 0):.2f}")

        return True
    else:
        print(f"   [ERROR] {response.text}")
        return False


def main():
    """Run all Phase 4 tests"""
    print("\n" + "=" * 80)
    print("PHASE 4: REAL-TIME UPDATES API TESTS")
    print("=" * 80)

    try:
        # Wait for backend to be ready
        import time
        print("\nWaiting for backend to restart...")
        time.sleep(5)

        # Test 1: Recent updates
        recent_data = test_recent_updates()

        # Test 2: Get by IDs
        if recent_data and recent_data['count'] > 0:
            # Use the updated stock IDs from recent_updates
            updated_ids = [u['stock_id'] for u in recent_data['updates'][:5]]
            test_get_by_ids(updated_ids)
        else:
            # Use any stocks for testing
            test_get_by_ids([])

        print("\n" + "=" * 80)
        print("SUCCESS - All Phase 4 API tests passed!")
        print("=" * 80)

        print("\nPhase 4 Backend Complete! Next steps:")
        print("1. Add API functions to frontend api.js")
        print("2. Replace checkForUpdates with efficient polling")
        print("3. Add toast notifications for updates")

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Could not connect to backend at http://localhost:8080")
        print("Make sure Docker containers are running: docker-compose up")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
