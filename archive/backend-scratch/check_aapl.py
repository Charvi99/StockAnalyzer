from app.db.database import SessionLocal
from app.models.stock import Stock, StockPrice
from sqlalchemy import desc

db = SessionLocal()
stock = db.query(Stock).filter(Stock.symbol == 'AAPL').first()
if stock:
    print(f'AAPL ID: {stock.id}, Priority: {stock.priority}, Score: {stock.priority_score}')
    latest = db.query(StockPrice).filter(
        StockPrice.stock_id == stock.id,
        StockPrice.timeframe == '1d'
    ).order_by(desc(StockPrice.timestamp)).first()
    print(f'Latest price in DB: {latest.close if latest else "None"}')
    print(f'Timestamp: {latest.timestamp if latest else "None"}')
else:
    print("AAPL not found")
db.close()
