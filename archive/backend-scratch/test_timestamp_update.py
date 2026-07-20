"""Test if fetch timestamp updates work"""
from app.db.database import SessionLocal
from app.tasks.fetcher_tasks import fetch_stock_data_incremental
from app.models.stock import Stock
from datetime import datetime, timedelta, timezone

db = SessionLocal()

# Get a medium-priority stock
stock = db.query(Stock).filter(
    Stock.is_tracked == True,
    Stock.priority == 'medium'
).first()

if stock:
    print(f"Testing with {stock.symbol} (priority: {stock.priority})")
    print(f"Before: last_fetch_at={stock.last_fetch_at}, next_fetch_at={stock.next_fetch_at}")

    # Simulate what the fetch task does
    result = fetch_stock_data_incremental(db, stock.id, stock.symbol, '1h')

    if result['status'] == 'success':
        # Update timestamps
        stock.last_fetch_at = datetime.now(timezone.utc)
        if stock.priority == 'high':
            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=1)
        elif stock.priority == 'medium':
            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=4)
        else:  # low priority
            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=24)
        db.commit()

        print(f"\nAfter: last_fetch_at={stock.last_fetch_at}, next_fetch_at={stock.next_fetch_at}")
        print(f"✅ Timestamps updated successfully!")
        print(f"Next fetch in {(stock.next_fetch_at - stock.last_fetch_at).total_seconds() / 3600} hours")
    else:
        print(f"❌ Fetch failed: {result}")
else:
    print("No medium-priority stocks found")

db.close()
