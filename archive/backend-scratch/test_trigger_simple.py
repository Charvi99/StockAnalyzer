"""
Simple test to trigger analysis for a single stock
"""
import requests
import json

API_URL = "http://localhost:8080"


def test_trigger_single_stock():
    """Test triggering analysis for a single stock"""
    print("=" * 80)
    print("SIMPLE TRIGGER TEST")
    print("=" * 80)

    # Get first tracked stock
    print("\n[1] Getting first tracked stock...")
    stocks_response = requests.get(
        f"{API_URL}/api/v1/stocks/", params={"tracked_only": True, "limit": 1})
    stocks = stocks_response.json()

    if not stocks:
        print("   [ERROR] No tracked stocks found")
        return False

    stock_id = stocks[0]['id']
    symbol = stocks[0]['symbol']
    print(f"   Stock: {symbol} (ID: {stock_id})")

    # Trigger analysis
    print("\n[2] Triggering analysis...")
    payload = {
        "stock_ids": [stock_id],
        "priority_override": None
    }

    response = requests.post(
        f"{API_URL}/api/v1/analysis/trigger-batch",
        json=payload
    )

    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")

    if response.status_code == 200:
        data = response.json()
        print(f"\n   ✅ Success!")
        print(f"   Triggered: {data['triggered_count']}")
        print(f"   Task ID: {data['tasks'][0]['task_id']}")
        return True
    else:
        print(f"\n   ❌ Failed!")
        return False


if __name__ == "__main__":
    try:
        test_trigger_single_stock()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
