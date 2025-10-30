import requests
import time
from datetime import datetime

def test_dashboard():
    print(f"\n{'='*60}")
    print(f"Dashboard Performance Test - {datetime.now()}")
    print(f"{'='*60}\n")

    url = "http://localhost:8000/api/v1/analysis/dashboard"

    print(f"Making request to: {url}")
    print(f"Timeout: 300 seconds (5 minutes)")
    print(f"Starting at: {datetime.now().strftime('%H:%M:%S')}\n")

    start_time = time.time()

    try:
        # Increased timeout to 5 minutes to see if it eventually completes
        response = requests.get(url, timeout=300)

        elapsed = time.time() - start_time

        print(f"\n{'='*60}")
        print(f"SUCCESS!")
        print(f"{'='*60}")
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")

        if response.status_code == 200:
            data = response.json()
            print(f"Number of stocks: {len(data)}")
            print(f"Average time per stock: {elapsed/len(data):.3f} seconds")
        else:
            print(f"Error: {response.text[:500]}")

    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"TIMEOUT after {elapsed:.2f} seconds")
        print(f"{'='*60}")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"ERROR after {elapsed:.2f} seconds")
        print(f"{'='*60}")
        print(f"Error: {e}")

if __name__ == "__main__":
    test_dashboard()
