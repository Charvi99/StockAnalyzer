from app.db.database import SessionLocal
from app.models.stock import StockPrice
from sqlalchemy import distinct, func

db = SessionLocal()

# Check what timeframes exist
timeframes = db.query(distinct(StockPrice.timeframe)).all()
print("Available timeframes:", [t[0] for t in timeframes])

# Count records per timeframe
for tf in ['1h', '1d', '1w', '1mo']:
    count = db.query(StockPrice).filter(StockPrice.timeframe == tf).count()
    print(f"{tf}: {count} records")

# Check how many stocks have 1d data
stocks_with_1d = db.query(func.count(distinct(StockPrice.stock_id))).filter(
    StockPrice.timeframe == '1d'
).scalar()
print(f"\nStocks with 1d data: {stocks_with_1d}")

# Check how many stocks have 1h data
stocks_with_1h = db.query(func.count(distinct(StockPrice.stock_id))).filter(
    StockPrice.timeframe == '1h'
).scalar()
print(f"Stocks with 1h data: {stocks_with_1h}")

db.close()
