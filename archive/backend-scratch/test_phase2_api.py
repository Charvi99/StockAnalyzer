"""
Test Phase 2 API endpoints

Tests:
1. POST /api/v1/analysis/check-completeness
2. POST /api/v1/analysis/trigger-batch
"""
import requests
import json

API_URL = "http://localhost:8080"


def test_check_completeness():
    """Test the check-completeness endpoint"""
    print("=" * 80)
    print("TEST 1: Check Completeness Endpoint")
    print("=" * 80)

    # Get some stock IDs first
    print("\n[1] Getting first 10 tracked stocks...")
    stocks_response = requests.get(
        f"{API_URL}/api/v1/stocks/", params={"tracked_only": True, "limit": 10})
    stocks = stocks_response.json()
    stock_ids = [s['id'] for s in stocks]
    print(f"   Stock IDs: {stock_ids}")

    # Test basic completeness check
    print("\n[2] Checking completeness (basic)...")
    payload = {
        "stock_ids": stock_ids,
        "max_age_hours": 24,
        "min_score_threshold": 0.80,
        "include_component_details": False
    }

    response = requests.post(
        f"{API_URL}/api/v1/analysis/check-completeness",
        json=payload
    )

    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"   Total Checked: {data['total_checked']}")
        print(f"   Needs Analysis: {data['needs_analysis_count']}")

        print("\n   Sample Results (first 3):")
        for stock in data['stocks'][:3]:
            print(f"   - {stock['symbol']}: score={stock['analysis_score']:.2f}, "
                  f"complete={stock['analysis_complete']}, needs_refresh={stock['needs_refresh']}")
            if stock['missing_components']:
                print(
                    f"     Missing: {', '.join(stock['missing_components'])}")
    else:
        print(f"   [ERROR] {response.text}")
        return False

    # Test with detailed components
    print("\n[3] Checking completeness (with component details)...")
    payload['include_component_details'] = True
    payload['stock_ids'] = stock_ids[:3]  # Just 3 stocks for detailed check

    response = requests.post(
        f"{API_URL}/api/v1/analysis/check-completeness",
        json=payload
    )

    if response.status_code == 200:
        data = response.json()
        stock = data['stocks'][0]
        print(f"   Stock: {stock['symbol']}")
        print(f"   Analysis Score: {stock['analysis_score']:.2f}")

        if stock.get('components'):
            print("   Component Details:")
            for comp_name, comp_data in stock['components'].items():
                status = "[STALE]" if comp_data['is_stale'] else "[FRESH]"
                age = f"({comp_data['age_hours']:.1f}h)" if comp_data['age_hours'] else "(never)"
                print(f"     {comp_name}: {status} {age}")
    else:
        print(f"   [ERROR] {response.text}")
        return False

    print("\n[SUCCESS] Check-completeness endpoint working!")
    return True


def test_trigger_batch():
    """Test the trigger-batch endpoint"""
    print("\n" + "=" * 80)
    print("TEST 2: Trigger Batch Analysis Endpoint")
    print("=" * 80)

    # Get a few incomplete stocks
    print("\n[1] Finding incomplete stocks...")
    stocks_response = requests.get(
        f"{API_URL}/api/v1/stocks/", params={"tracked_only": True, "limit": 100})
    stocks = stocks_response.json()

    # Use check-completeness to find stocks needing analysis
    stock_ids = [s['id'] for s in stocks[:20]]  # Check first 20
    check_payload = {
        "stock_ids": stock_ids,
        "max_age_hours": 24,
        "min_score_threshold": 0.80,
        "include_component_details": False
    }

    check_response = requests.post(
        f"{API_URL}/api/v1/analysis/check-completeness",
        json=check_payload
    )

    if check_response.status_code != 200:
        print(
            f"   [ERROR] Failed to check completeness: {check_response.text}")
        return False

    completeness_data = check_response.json()
    incomplete_stocks = [
        s for s in completeness_data['stocks'] if s['needs_refresh']]

    if not incomplete_stocks:
        print(
            "   [WARNING] No incomplete stocks found, using first 3 stocks anyway for testing")
        test_stock_ids = stock_ids[:3]
    else:
        test_stock_ids = [s['stock_id']
                          for s in incomplete_stocks[:3]]  # Just 3 for testing

    print(f"   Will trigger analysis for {len(test_stock_ids)} stocks")

    # Trigger analysis
    print("\n[2] Triggering batch analysis...")
    trigger_payload = {
        "stock_ids": test_stock_ids,
        "priority_override": None  # Use stock's own priority
    }

    response = requests.post(
        f"{API_URL}/api/v1/analysis/trigger-batch",
        json=trigger_payload
    )

    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"   Message: {data['message']}")
        print(f"   Triggered Count: {data['triggered_count']}")

        print("\n   Triggered Tasks:")
        for task in data['tasks']:
            print(
                f"   - {task['symbol']} (ID: {task['stock_id']}): task_id={task['task_id'][:16]}..., priority={task['priority']}")

        print("\n[SUCCESS] Trigger-batch endpoint working!")
        print(
            f"\n[INFO] {data['triggered_count']} analysis tasks are now running in Celery workers")
        print(
            "[INFO] Check Flower dashboard at http://localhost:6380 to monitor progress")
        return True
    else:
        print(f"   [ERROR] {response.text}")
        return False


def main():
    """Run all Phase 2 tests"""
    print("\n" + "=" * 80)
    print("PHASE 2 API ENDPOINT TESTS")
    print("=" * 80)

    try:
        # Test check-completeness endpoint
        if not test_check_completeness():
            print("\n[FAILED] Check-completeness test failed")
            return

        # Test trigger-batch endpoint
        if not test_trigger_batch():
            print("\n[FAILED] Trigger-batch test failed")
            return

        print("\n" + "=" * 80)
        print("[SUCCESS] All Phase 2 API tests passed!")
        print("=" * 80)

        print("\nPhase 2 Complete! Next steps:")
        print("1. Check Celery Flower dashboard: http://localhost:6380")
        print("2. Monitor task progress")
        print("3. Verify analysis_score updates after tasks complete")
        print("4. Ready to move to Phase 3: Frontend Auto-Trigger")

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Could not connect to backend at http://localhost:8080")
        print("Make sure Docker containers are running: docker-compose up")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
