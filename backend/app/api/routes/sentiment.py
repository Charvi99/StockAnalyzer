"""
Sentiment analysis routes for news and market sentiment
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import os

from app.db.database import get_db
from app.models.stock import Stock, SentimentScore
from app.schemas.ml_sentiment import (
    SentimentRequest, SentimentAnalysisResponse,
    MultipleSentimentRequest, MultipleSentimentResponse,
    SentimentScoreResponse, NewsArticle
)
from app.services.sentiment_service import SentimentService

router = APIRouter(prefix="/api/v1/sentiment", tags=["Sentiment Analysis"])


def get_sentiment_service():
    """Get sentiment service instance with Polygon API key from environment"""
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="POLYGON_API_KEY not configured")
    return SentimentService(polygon_api_key=api_key)


@router.post("/stocks/{stock_id}/analyze", response_model=SentimentAnalysisResponse)
async def analyze_stock_sentiment(
    stock_id: int,
    request: SentimentRequest,
    db: Session = Depends(get_db),
    sentiment_service: SentimentService = Depends(get_sentiment_service)
):
    """
    Analyze sentiment for a single stock

    - **stock_id**: ID of the stock to analyze
    - **limit_per_ticker**: Number of news articles to fetch (default: 50)
    - **threshold**: Confidence threshold for sentiment (default: 0.9)
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    try:
        # Perform sentiment analysis
        result = sentiment_service.analyze_sentiment(
            ticker=stock.symbol,
            limit_per_ticker=request.limit_per_ticker,
            threshold=request.threshold
        )

        # Save sentiment score to database
        sentiment_score = SentimentScore(
            stock_id=stock_id,
            timestamp=datetime.utcnow(),
            sentiment_index=result['sentiment_index'],
            positive_count=result['positive_count'],
            negative_count=result['negative_count'],
            neutral_count=result['neutral_count'],
            positive_pct=result['positive_pct'],
            negative_pct=result['negative_pct'],
            neutral_pct=result['neutral_pct'],
            total_articles=result['total_articles'],
            trend=result['trend']
        )
        db.add(sentiment_score)
        db.commit()
        db.refresh(sentiment_score)

        # Convert news to proper schema
        news_articles = [NewsArticle(**article) for article in result['news']]

        return SentimentAnalysisResponse(
            ticker=result['ticker'],
            sentiment_index=result['sentiment_index'],
            positive_count=result['positive_count'],
            negative_count=result['negative_count'],
            neutral_count=result['neutral_count'],
            positive_pct=result['positive_pct'],
            negative_pct=result['negative_pct'],
            neutral_pct=result['neutral_pct'],
            total_articles=result['total_articles'],
            trend=result['trend'],
            news=news_articles,
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {str(e)}")


@router.post("/analyze-multiple", response_model=MultipleSentimentResponse)
async def analyze_multiple_stocks(
    request: MultipleSentimentRequest,
    db: Session = Depends(get_db),
    sentiment_service: SentimentService = Depends(get_sentiment_service)
):
    """
    Analyze sentiment for multiple stocks

    - **tickers**: List of ticker symbols (max 10)
    - **limit_per_ticker**: Number of news articles per ticker (default: 50)
    - **threshold**: Confidence threshold (default: 0.9)
    """
    try:
        # Perform sentiment analysis for multiple tickers
        result = sentiment_service.analyze_multiple_tickers(
            tickers=request.tickers,
            limit_per_ticker=request.limit_per_ticker,
            threshold=request.threshold
        )

        # Save sentiment scores to database
        for ticker_result in result['tickers']:
            # Find stock by symbol
            stock = db.query(Stock).filter(Stock.symbol == ticker_result['ticker']).first()
            if stock:
                sentiment_score = SentimentScore(
                    stock_id=stock.id,
                    timestamp=datetime.utcnow(),
                    sentiment_index=ticker_result['sentiment_index'],
                    positive_count=ticker_result['positive_count'],
                    negative_count=ticker_result['negative_count'],
                    neutral_count=ticker_result['neutral_count'],
                    positive_pct=ticker_result['positive_pct'],
                    negative_pct=ticker_result['negative_pct'],
                    neutral_pct=ticker_result['neutral_pct'],
                    total_articles=ticker_result['total_articles'],
                    trend=ticker_result['trend']
                )
                db.add(sentiment_score)

        db.commit()

        # Convert news to proper schema
        news_articles = [NewsArticle(**article) for article in result['news']]

        return MultipleSentimentResponse(
            tickers=result['tickers'],
            news=news_articles,
            total_articles_analyzed=result['total_articles_analyzed'],
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {str(e)}")


@router.get("/stocks/{stock_id}/history")
async def get_sentiment_history(
    stock_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get historical sentiment scores for a stock

    - **stock_id**: ID of the stock
    - **limit**: Number of records to return (default: 10)
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Fetch sentiment history
    sentiment_scores = db.query(SentimentScore).filter(
        SentimentScore.stock_id == stock_id
    ).order_by(SentimentScore.timestamp.desc()).limit(limit).all()

    return {
        "stock_id": stock_id,
        "symbol": stock.symbol,
        "sentiment_history": [
            SentimentScoreResponse.from_orm(score) for score in sentiment_scores
        ]
    }


@router.get("/stocks/{stock_id}/latest", response_model=SentimentScoreResponse)
async def get_latest_sentiment(
    stock_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the latest sentiment score for a stock

    - **stock_id**: ID of the stock
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Fetch latest sentiment
    latest_sentiment = db.query(SentimentScore).filter(
        SentimentScore.stock_id == stock_id
    ).order_by(SentimentScore.timestamp.desc()).first()

    if not latest_sentiment:
        raise HTTPException(status_code=404, detail="No sentiment data available for this stock")

    return SentimentScoreResponse.from_orm(latest_sentiment)


@router.delete("/stocks/{stock_id}/history")
async def clear_sentiment_history(
    stock_id: int,
    db: Session = Depends(get_db)
):
    """
    Clear all sentiment history for a stock

    - **stock_id**: ID of the stock
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Delete all sentiment scores
    deleted_count = db.query(SentimentScore).filter(
        SentimentScore.stock_id == stock_id
    ).delete()

    db.commit()

    return {
        "message": f"Cleared sentiment history for {stock.symbol}",
        "records_deleted": deleted_count
    }
