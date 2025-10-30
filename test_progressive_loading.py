import requests
import time
from datetime import datetime

def test_progressive_loading():
    print(f"\n{'='*70}")
    print(f"PROGRESSIVE LOADING TEST - {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*70}\n")

    base_url = "http://localhost:8000/api/v1"

    # STEP 1: Load basic stock info (FAST)
    print("STEP 1: Loading basic stock info...")
    step1_start = time.time()

    stocks_response = requests.get(f"{base_url}/stocks/")
    stocks = stocks_response.json()

    step1_time = time.time() - step1_start
    print(f"  [OK] Loaded {len(stocks)} stocks in {step1_time:.2f} seconds")
    print(f"  -> User sees all stock tiles immediately!")
    print(f"  -> Example: {stocks[0]['symbol']} - {stocks[0]['name']}\n")

    # STEP 2: Load analysis data in chunks
    print("STEP 2: Loading analysis data in chunks...")
    chunk_size = 50
    total_stocks = len(stocks)
    chunks_needed = (total_stocks + chunk_size - 1) // chunk_size

    step2_start = time.time()
    total_analyzed = 0

    for chunk_num in range(chunks_needed):
        offset = chunk_num * chunk_size
        chunk_start = time.time()

        response = requests.get(
            f"{base_url}/analysis/dashboard/chunk",
            params={"offset": offset, "limit": chunk_size}
        )
        chunk_data = response.json()
        chunk_time = time.time() - chunk_start

        total_analyzed += len(chunk_data)
        progress_pct = (total_analyzed / total_stocks) * 100

        print(f"  Chunk {chunk_num + 1}/{chunks_needed}: "
              f"+{len(chunk_data)} stocks in {chunk_time:.2f}s | "
              f"Progress: {total_analyzed}/{total_stocks} ({progress_pct:.0f}%)")

        # First chunk shows immediately
        if chunk_num == 0:
            print(f"  -> First batch of tiles updated! ({chunk_time:.2f}s from start)\n")

    step2_time = time.time() - step2_start
    total_time = step1_time + step2_time

    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"Step 1 (Basic Info):    {step1_time:.2f}s  <- USER SEES SOMETHING!")
    print(f"Step 2 (Analysis):      {step2_time:.2f}s  <- Progressive updates")
    print(f"Total Time:             {total_time:.2f}s")
    print(f"\nUser Experience:")
    print(f"  * Page shows content in:     {step1_time:.2f}s")
    print(f"  * First tiles analyzed in:   ~{step1_time + (step2_time/chunks_needed):.2f}s")
    print(f"  * All tiles complete in:     {total_time:.2f}s")
    print(f"\nOld approach would take ~95-115 seconds with blank screen!")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    test_progressive_loading()
