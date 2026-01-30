from app.db.database import SessionLocal
from app.models.stock import Stock, StockPrice
from sqlalchemy import desc
from datetime import datetime, timezone

db = SessionLocal()

# Check AAPL priority
stock = db.query(Stock).filter(Stock.symbol == 'AAPL').first()
print(f"AAPL Priority: {stock.priority}, Score: {stock.priority_score}")
print(f"Priority updated at: {stock.priority_updated_at}")
print()

# Check latest 1h data
latest_1h = db.query(StockPrice).filter(
    StockPrice.stock_id == stock.id,
    StockPrice.timeframe == '1h'
).order_by(desc(StockPrice.timestamp)).first()
print(f"Latest 1h data: {latest_1h.close if latest_1h else 'None'}")
print(f"Timestamp: {latest_1h.timestamp if latest_1h else 'None'}")
print()

# Check latest 1d data
latest_1d = db.query(StockPrice).filter(
    StockPrice.stock_id == stock.id,
    StockPrice.timeframe == '1d'
).order_by(desc(StockPrice.timestamp)).first()
print(f"Latest 1d data: {latest_1d.close if latest_1d else 'None'}")
print(f"Timestamp: {latest_1d.timestamp if latest_1d else 'None'}")
print()

# Check how old the data is
if latest_1h:
    age_hours = (datetime.now(timezone.utc) - latest_1h.timestamp.replace(tzinfo=timezone.utc)).total_seconds() / 3600
    print(f"1h data age: {age_hours:.1f} hours old")

db.close()
