"""
Sentiment analysis routes for news and market sentiment

NOTE: This module has been refactored to use Polygon API sentiment data
that is automatically extracted during news fetching. The old FinBERT-based
sentiment analysis has been removed. Sentiment data is now stored directly
in the News table with sentiment, sentiment_score, and sentiment_reasoning fields.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import logging

from app.db.database import get_db
from app.models.stock import Stock, SentimentScore
from app.models.news import News
from app.schemas.ml_sentiment import (
    SentimentRequest, SentimentAnalysisResponse,
    MultipleSentimentRequest, MultipleSentimentResponse,
    SentimentScoreResponse, NewsArticle
)

router = APIRouter(prefix="/api/v1/sentiment", tags=["Sentiment Analysis"])
logger = logging.getLogger(__name__)


@router.post("/stocks/{stock_id}/analyze", response_model=SentimentAnalysisResponse)
async def analyze_stock_sentiment(
    stock_id: int,
    request: SentimentRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze sentiment for a single stock using stored Polygon API sentiment data

    - **stock_id**: ID of the stock to analyze
    - **limit_per_ticker**: Number of news articles to fetch (default: 50)
    - **threshold**: Not used anymore (kept for API compatibility)
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    try:
        # Get recent news articles with sentiment from database
        news_articles = db.query(News).filter(
            News.stock_id == stock_id,
            News.sentiment_score.isnot(None)
        ).order_by(News.published_utc.desc()).limit(request.limit_per_ticker).all()

        if not news_articles:
            raise HTTPException(status_code=404, detail="No sentiment data available. News may not have been fetched yet.")

        # Calculate sentiment statistics
        positive_count = sum(1 for article in news_articles if article.sentiment == 'positive')
        negative_count = sum(1 for article in news_articles if article.sentiment == 'negative')
        neutral_count = sum(1 for article in news_articles if article.sentiment == 'neutral')
        total_articles = len(news_articles)

        positive_pct = (positive_count / total_articles) * 100 if total_articles > 0 else 0
        negative_pct = (negative_count / total_articles) * 100 if total_articles > 0 else 0
        neutral_pct = (neutral_count / total_articles) * 100 if total_articles > 0 else 0

        # Calculate sentiment index (-100 to 100)
        avg_sentiment_score = sum(float(article.sentiment_score) for article in news_articles) / total_articles
        sentiment_index = avg_sentiment_score * 100  # Convert -1.0..1.0 to -100..100

        # Determine trend (simplified)
        trend = "bullish" if sentiment_index > 20 else ("bearish" if sentiment_index < -20 else "neutral")

        # Save sentiment score to database
        sentiment_score = SentimentScore(
            stock_id=stock_id,
            timestamp=datetime.utcnow(),
            sentiment_index=sentiment_index,
            positive_count=positive_count,
            negative_count=negative_count,
            neutral_count=neutral_count,
            positive_pct=positive_pct,
            negative_pct=negative_pct,
            neutral_pct=neutral_pct,
            total_articles=total_articles,
            trend=trend
        )
        db.add(sentiment_score)
        db.commit()
        db.refresh(sentiment_score)

        # Convert news to schema format
        news_response = [
            NewsArticle(
                article_id=article.article_id,
                title=article.title,
                publisher=article.publisher,
                author=article.author,
                published_utc=article.published_utc,
                article_url=article.article_url,
                image_url=article.image_url,
                description=article.description,
                sentiment=article.sentiment,
                sentiment_score=float(article.sentiment_score),
                keywords=article.keywords or []
            )
            for article in news_articles
        ]

        return SentimentAnalysisResponse(
            ticker=stock.symbol,
            sentiment_index=sentiment_index,
            positive_count=positive_count,
            negative_count=negative_count,
            neutral_count=neutral_count,
            positive_pct=positive_pct,
            negative_pct=negative_pct,
            neutral_pct=neutral_pct,
            total_articles=total_articles,
            trend=trend,
            news=news_response,
            timestamp=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {str(e)}")


@router.post("/analyze-multiple", response_model=MultipleSentimentResponse)
async def analyze_multiple_stocks(
    request: MultipleSentimentRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze sentiment for multiple stocks using stored Polygon API sentiment data

    - **tickers**: List of ticker symbols (max 10)
    - **limit_per_ticker**: Number of news articles per ticker (default: 50)
    - **threshold**: Not used anymore (kept for API compatibility)
    """
    if len(request.tickers) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 tickers allowed")

    try:
        ticker_results = []
        all_news = []
        total_articles = 0

        for ticker in request.tickers:
            # Find stock by symbol
            stock = db.query(Stock).filter(Stock.symbol == ticker).first()
            if not stock:
                logger.warning(f"Stock {ticker} not found, skipping")
                continue

            # Get recent news articles with sentiment
            news_articles = db.query(News).filter(
                News.stock_id == stock.id,
                News.sentiment_score.isnot(None)
            ).order_by(News.published_utc.desc()).limit(request.limit_per_ticker).all()

            if not news_articles:
                logger.warning(f"No sentiment data for {ticker}, skipping")
                continue

            # Calculate sentiment statistics
            positive_count = sum(1 for article in news_articles if article.sentiment == 'positive')
            negative_count = sum(1 for article in news_articles if article.sentiment == 'negative')
            neutral_count = sum(1 for article in news_articles if article.sentiment == 'neutral')
            articles_count = len(news_articles)

            positive_pct = (positive_count / articles_count) * 100 if articles_count > 0 else 0
            negative_pct = (negative_count / articles_count) * 100 if articles_count > 0 else 0
            neutral_pct = (neutral_count / articles_count) * 100 if articles_count > 0 else 0

            # Calculate sentiment index
            avg_sentiment_score = sum(float(article.sentiment_score) for article in news_articles) / articles_count
            sentiment_index = avg_sentiment_score * 100

            # Determine trend
            trend = "bullish" if sentiment_index > 20 else ("bearish" if sentiment_index < -20 else "neutral")

            ticker_results.append({
                'ticker': ticker,
                'sentiment_index': sentiment_index,
                'positive_count': positive_count,
                'negative_count': negative_count,
                'neutral_count': neutral_count,
                'positive_pct': positive_pct,
                'negative_pct': negative_pct,
                'neutral_pct': neutral_pct,
                'total_articles': articles_count,
                'trend': trend
            })

            # Save sentiment score to database
            sentiment_score = SentimentScore(
                stock_id=stock.id,
                timestamp=datetime.utcnow(),
                sentiment_index=sentiment_index,
                positive_count=positive_count,
                negative_count=negative_count,
                neutral_count=neutral_count,
                positive_pct=positive_pct,
                negative_pct=negative_pct,
                neutral_pct=neutral_pct,
                total_articles=articles_count,
                trend=trend
            )
            db.add(sentiment_score)

            # Add to combined news list
            all_news.extend(news_articles)
            total_articles += articles_count

        db.commit()

        # Convert news to schema format
        news_response = [
            NewsArticle(
                article_id=article.article_id,
                title=article.title,
                publisher=article.publisher,
                author=article.author,
                published_utc=article.published_utc,
                article_url=article.article_url,
                image_url=article.image_url,
                description=article.description,
                sentiment=article.sentiment,
                sentiment_score=float(article.sentiment_score),
                keywords=article.keywords or []
            )
            for article in all_news[:100]  # Limit to 100 most recent
        ]

        return MultipleSentimentResponse(
            tickers=ticker_results,
            news=news_response,
            total_articles_analyzed=total_articles,
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Multiple sentiment analysis failed: {e}")
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


@router.get("/stocks/{stock_id}/news-with-reasoning")
async def get_news_with_sentiment_reasoning(
    stock_id: int,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Get recent news articles with sentiment reasoning from Polygon API

    - **stock_id**: ID of the stock
    - **limit**: Number of articles to return (default: 20)

    Returns news articles with sentiment, sentiment_score, and sentiment_reasoning
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Fetch news with sentiment reasoning
    news_articles = db.query(News).filter(
        News.stock_id == stock_id,
        News.sentiment_reasoning.isnot(None)
    ).order_by(News.published_utc.desc()).limit(limit).all()

    return {
        "stock_id": stock_id,
        "symbol": stock.symbol,
        "articles": [
            {
                "article_id": article.article_id,
                "title": article.title,
                "publisher": article.publisher,
                "published_utc": article.published_utc,
                "article_url": article.article_url,
                "sentiment": article.sentiment,
                "sentiment_score": float(article.sentiment_score) if article.sentiment_score else None,
                "sentiment_reasoning": article.sentiment_reasoning,
                "description": article.description
            }
            for article in news_articles
        ],
        "total_articles": len(news_articles)
    }


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
