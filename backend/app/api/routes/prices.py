from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import pandas as pd
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
from app.services.timeframe_service import TimeframeService
from app.config.timeframe_config import TimeframeConfig

router = APIRouter(prefix="/stocks", tags=["prices"])


@router.post("/{stock_id}/fetch", response_model=FetchDataResponse)
def fetch_stock_data(
    stock_id: int,
    request: FetchDataRequest,
    db: Session = Depends(get_db)
):
    """
    Fetch historical stock data from Polygon.io and store in database

    **Smart Aggregation Strategy**: Only fetches base timeframe (1h).
    Higher timeframes (2h, 4h, 1d, 1w, 1mo) are aggregated on-the-fly.

    - **stock_id**: ID of the stock to fetch data for
    - **period**: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    - **interval**: Data interval - use "1h" (base timeframe)
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
    timeframe: str = Query(default="1d", regex="^(1h|2h|4h|1d|1w|1mo)$"),
    limit: int = Query(default=100, ge=1, le=10000),
    skip: int = Query(default=0, ge=0),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve historical prices for a stock with multi-timeframe support

    **Smart Aggregation**: Supports all timeframes (1h, 2h, 4h, 1d, 1w, 1mo).
    Higher timeframes are aggregated from 1h base data automatically.

    - **stock_id**: ID of the stock
    - **timeframe**: Timeframe (1h, 2h, 4h, 1d, 1w, 1mo) - default: 1d
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

    # Use smart aggregation to get data
    try:
        df = TimeframeService.get_price_data_smart(
            db=db,
            stock_id=stock_id,
            timeframe=timeframe
        )

        if df.empty:
            return StockPriceListResponse(
                stock_id=stock_id,
                symbol=stock.symbol,
                prices=[],
                total_records=0,
                period_start=None,
                period_end=None
            )

        # Apply date filters
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]

        # Get total count before pagination
        total_records = len(df)

        # Sort by timestamp descending (most recent first)
        df = df.sort_index(ascending=False)

        # Apply pagination
        df = df.iloc[skip:skip+limit]

        # Convert DataFrame to list of dictionaries
        prices_list = []
        for timestamp, row in df.iterrows():
            prices_list.append({
                'id': 0,  # Not applicable for aggregated data
                'stock_id': stock_id,
                'timeframe': timeframe,
                'timestamp': timestamp,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']),
                'adjusted_close': float(row['close'])
            })

        # Get period boundaries
        period_start = None
        period_end = None
        if prices_list:
            period_end = prices_list[0]['timestamp']  # Most recent
            period_start = prices_list[-1]['timestamp']  # Oldest

        return StockPriceListResponse(
            stock_id=stock_id,
            symbol=stock.symbol,
            prices=prices_list,
            total_records=total_records,
            period_start=period_start,
            period_end=period_end
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving prices: {str(e)}"
        )


@router.get("/symbol/{symbol}/prices", response_model=StockPriceListResponse)
def get_stock_prices_by_symbol(
    symbol: str,
    timeframe: str = Query(default="1d", regex="^(1h|2h|4h|1d|1w|1mo)$"),
    limit: int = Query(default=100, ge=1, le=10000),
    skip: int = Query(default=0, ge=0),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve historical prices for a stock by symbol with multi-timeframe support

    **Smart Aggregation**: Supports all timeframes (1h, 2h, 4h, 1d, 1w, 1mo).
    Higher timeframes are aggregated from 1h base data automatically.

    - **symbol**: Stock ticker symbol (e.g., 'AAPL')
    - **timeframe**: Timeframe (1h, 2h, 4h, 1d, 1w, 1mo) - default: 1d
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
    return get_stock_prices(stock.id, timeframe, limit, skip, start_date, end_date, db)


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
