from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.models.stock import Stock
from app.schemas.stock import StockCreate, StockResponse, StockUpdate

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/", response_model=List[StockResponse])
def get_stocks(
    skip: int = 0,
    limit: int = 1000,
    tracked_only: bool = Query(default=True, description="Return only tracked stocks"),
    db: Session = Depends(get_db)
):
    """
    Retrieve all stocks with pagination

    By default returns only tracked stocks. Set tracked_only=false to get all stocks.
    """
    query = db.query(Stock)

    if tracked_only:
        query = query.filter(Stock.is_tracked == True)

    stocks = query.order_by(Stock.symbol).offset(skip).limit(limit).all()
    return stocks


@router.get("/{stock_id}", response_model=StockResponse)
def get_stock(stock_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific stock by ID
    """
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock with id {stock_id} not found"
        )
    return stock


@router.get("/symbol/{symbol}", response_model=StockResponse)
def get_stock_by_symbol(symbol: str, db: Session = Depends(get_db)):
    """
    Retrieve a specific stock by symbol
    """
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock with symbol {symbol} not found"
        )
    return stock


@router.post("/", response_model=StockResponse, status_code=status.HTTP_201_CREATED)
def create_stock(stock: StockCreate, db: Session = Depends(get_db)):
    """
    Create a new stock
    """
    # Check if stock already exists
    existing_stock = db.query(Stock).filter(Stock.symbol == stock.symbol.upper()).first()
    if existing_stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stock with symbol {stock.symbol} already exists"
        )

    # Create new stock
    db_stock = Stock(**stock.model_dump())
    db_stock.symbol = db_stock.symbol.upper()
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock


@router.patch("/{stock_id}", response_model=StockResponse)
def update_stock(stock_id: int, stock_update: StockUpdate, db: Session = Depends(get_db)):
    """
    Update a stock (e.g., track/untrack)
    """
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock with id {stock_id} not found"
        )

    # Update fields if provided
    update_data = stock_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(stock, field, value)

    db.commit()
    db.refresh(stock)
    return stock


@router.delete("/{stock_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stock(stock_id: int, db: Session = Depends(get_db)):
    """
    Delete a stock
    """
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock with id {stock_id} not found"
        )

    db.delete(stock)
    db.commit()
    return None
