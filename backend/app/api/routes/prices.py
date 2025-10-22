from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.db.database import get_db
from app.models.stock import Stock, StockPrice
from app.schemas.stock import (
    StockPriceResponse,
    StockPriceListResponse,
    FetchDataRequest,
    FetchDataResponse,
    LatestPriceResponse
)
from app.services.stock_fetcher import StockDataFetcher

router = APIRouter(prefix="/stocks", tags=["prices"])


@router.post("/{stock_id}/fetch", response_model=FetchDataResponse)
def fetch_stock_data(
    stock_id: int,
    request: FetchDataRequest,
    db: Session = Depends(get_db)
):
    """
    Fetch historical stock data from Yahoo Finance and store in database

    - **stock_id**: ID of the stock to fetch data for
    - **period**: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    - **interval**: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
    """
    # Get stock from database
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock with id {stock_id} not found"
        )

    # Fetch and store data
    result = StockDataFetcher.fetch_and_store(
        db=db,
        stock_id=stock_id,
        symbol=stock.symbol,
        period=request.period,
        interval=request.interval
    )

    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['message']
        )

    return FetchDataResponse(**result)


@router.get("/{stock_id}/prices", response_model=StockPriceListResponse)
def get_stock_prices(
    stock_id: int,
    limit: int = Query(default=100, ge=1, le=10000),
    skip: int = Query(default=0, ge=0),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve historical prices for a stock

    - **stock_id**: ID of the stock
    - **limit**: Maximum number of records to return (1-10000)
    - **skip**: Number of records to skip (for pagination)
    - **start_date**: Filter prices from this date onwards
    - **end_date**: Filter prices up to this date
    """
    # Get stock from database
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock with id {stock_id} not found"
        )

    # Build query
    query = db.query(StockPrice).filter(StockPrice.stock_id == stock_id)

    # Apply date filters
    if start_date:
        query = query.filter(StockPrice.timestamp >= start_date)
    if end_date:
        query = query.filter(StockPrice.timestamp <= end_date)

    # Get total count
    total_records = query.count()

    # Get prices ordered by timestamp descending (most recent first)
    prices = query.order_by(StockPrice.timestamp.desc()).offset(skip).limit(limit).all()

    # Get period boundaries
    period_start = None
    period_end = None
    if prices:
        period_end = prices[0].timestamp  # Most recent (first in desc order)
        period_start = prices[-1].timestamp  # Oldest (last in desc order)

    return StockPriceListResponse(
        stock_id=stock_id,
        symbol=stock.symbol,
        prices=prices,
        total_records=total_records,
        period_start=period_start,
        period_end=period_end
    )


@router.get("/symbol/{symbol}/prices", response_model=StockPriceListResponse)
def get_stock_prices_by_symbol(
    symbol: str,
    limit: int = Query(default=100, ge=1, le=10000),
    skip: int = Query(default=0, ge=0),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve historical prices for a stock by symbol

    - **symbol**: Stock ticker symbol (e.g., 'AAPL')
    - **limit**: Maximum number of records to return (1-10000)
    - **skip**: Number of records to skip (for pagination)
    - **start_date**: Filter prices from this date onwards
    - **end_date**: Filter prices up to this date
    """
    # Get stock from database
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock with symbol {symbol} not found"
        )

    # Use the existing endpoint logic
    return get_stock_prices(stock.id, limit, skip, start_date, end_date, db)


@router.get("/{stock_id}/latest", response_model=LatestPriceResponse)
def get_latest_stock_price(stock_id: int, db: Session = Depends(get_db)):
    """
    Get the most recent price for a stock from Yahoo Finance (live data)

    - **stock_id**: ID of the stock
    """
    # Get stock from database
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock with id {stock_id} not found"
        )

    # Fetch latest price
    latest_price = StockDataFetcher.get_latest_price(stock.symbol)

    if not latest_price:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not fetch latest price for {stock.symbol}"
        )

    return LatestPriceResponse(**latest_price)


@router.delete("/{stock_id}/prices", status_code=status.HTTP_204_NO_CONTENT)
def delete_stock_prices(stock_id: int, db: Session = Depends(get_db)):
    """
    Delete all price data for a stock

    - **stock_id**: ID of the stock
    """
    # Get stock from database
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock with id {stock_id} not found"
        )

    # Delete all prices
    deleted_count = db.query(StockPrice).filter(StockPrice.stock_id == stock_id).delete()
    db.commit()

    return None
