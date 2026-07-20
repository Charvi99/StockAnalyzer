from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import logging

from app.db.database import get_db
from app.models.news import News
from app.models.stock import Stock
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== SCHEMAS ====================

class NewsCreate(BaseModel):
    """Schema for creating a news article"""
    article_id: str
    publisher: Optional[str] = None
    title: str
    author: Optional[str] = None
    published_utc: datetime
    article_url: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None


class NewsResponse(BaseModel):
    """Schema for news article response"""
    id: int
    stock_id: int
    article_id: str
    publisher: Optional[str]
    title: str
    author: Optional[str]
    published_utc: datetime
    article_url: Optional[str]
    image_url: Optional[str]
    description: Optional[str]
    keywords: Optional[List[str]]
    sentiment: Optional[str]
    sentiment_score: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NewsBulkCreateRequest(BaseModel):
    """Schema for bulk creating news articles"""
    articles: List[NewsCreate]


class NewsBulkCreateResponse(BaseModel):
    """Schema for bulk create response"""
    success: bool
    created_count: int
    skipped_count: int
    error_count: int
    message: str


# ==================== ROUTES ====================

@router.post("/stocks/{stock_id}/news", response_model=NewsResponse)
def create_news_article(
    stock_id: int,
    news: NewsCreate,
    db: Session = Depends(get_db)
):
    """
    Create a single news article for a stock.
    Skips if article_id already exists (no duplicates).
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock with id {stock_id} not found")

    # Check if article already exists
    existing = db.query(News).filter(News.article_id == news.article_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Article with id {news.article_id} already exists")

    # Create news article
    db_news = News(
        stock_id=stock_id,
        article_id=news.article_id,
        publisher=news.publisher,
        title=news.title,
        author=news.author,
        published_utc=news.published_utc,
        article_url=news.article_url,
        image_url=news.image_url,
        description=news.description,
        keywords=news.keywords,
        sentiment=news.sentiment,
        sentiment_score=news.sentiment_score
    )

    db.add(db_news)
    db.commit()
    db.refresh(db_news)

    logger.info(f"Created news article {news.article_id} for stock {stock_id} ({stock.symbol})")
    return db_news


@router.post("/stocks/{stock_id}/news/bulk", response_model=NewsBulkCreateResponse)
def bulk_create_news_articles(
    stock_id: int,
    request: NewsBulkCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Bulk create news articles for a stock.
    Skips articles that already exist (by article_id).
    Returns count of created, skipped, and errors.
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock with id {stock_id} not found")

    created_count = 0
    skipped_count = 0
    error_count = 0

    for news in request.articles:
        try:
            # Check if article already exists
            existing = db.query(News).filter(News.article_id == news.article_id).first()
            if existing:
                skipped_count += 1
                continue

            # Create news article
            db_news = News(
                stock_id=stock_id,
                article_id=news.article_id,
                publisher=news.publisher,
                title=news.title,
                author=news.author,
                published_utc=news.published_utc,
                article_url=news.article_url,
                image_url=news.image_url,
                description=news.description,
                keywords=news.keywords,
                sentiment=news.sentiment,
                sentiment_score=news.sentiment_score
            )

            db.add(db_news)
            created_count += 1

        except Exception as e:
            logger.error(f"Error creating news article {news.article_id}: {e}")
            error_count += 1

    # Commit all at once
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error committing news articles for stock {stock_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save news articles to database")

    logger.info(f"Bulk created {created_count} news articles for stock {stock_id} ({stock.symbol}), skipped {skipped_count}, errors {error_count}")

    return NewsBulkCreateResponse(
        success=True,
        created_count=created_count,
        skipped_count=skipped_count,
        error_count=error_count,
        message=f"Created {created_count} articles, skipped {skipped_count} duplicates, {error_count} errors"
    )


@router.get("/stocks/{stock_id}/news", response_model=List[NewsResponse])
def get_news_articles(
    stock_id: int,
    limit: int = Query(10, ge=1, le=100, description="Number of articles to return"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
    db: Session = Depends(get_db)
):
    """
    Get news articles for a stock.
    Returns most recent articles first.
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock with id {stock_id} not found")

    # Get news articles
    news_articles = db.query(News)\
        .filter(News.stock_id == stock_id)\
        .order_by(News.published_utc.desc())\
        .offset(offset)\
        .limit(limit)\
        .all()

    return news_articles


@router.delete("/stocks/{stock_id}/news/old")
def delete_old_news_articles(
    stock_id: int,
    days: int = Query(14, ge=1, le=365, description="Delete articles older than this many days"),
    db: Session = Depends(get_db)
):
    """
    Delete old news articles for a stock.
    Default: 14 days retention.
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock with id {stock_id} not found")

    # Calculate cutoff date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Delete old articles
    deleted_count = db.query(News)\
        .filter(News.stock_id == stock_id)\
        .filter(News.published_utc < cutoff_date)\
        .delete()

    db.commit()

    logger.info(f"Deleted {deleted_count} news articles older than {days} days for stock {stock_id} ({stock.symbol})")

    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} articles older than {days} days"
    }


@router.delete("/news/old")
def delete_all_old_news_articles(
    days: int = Query(14, ge=1, le=365, description="Delete articles older than this many days"),
    db: Session = Depends(get_db)
):
    """
    Delete old news articles for ALL stocks.
    Default: 14 days retention.
    This is typically called by a scheduled Celery task.
    """
    # Calculate cutoff date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Delete old articles
    deleted_count = db.query(News)\
        .filter(News.published_utc < cutoff_date)\
        .delete()

    db.commit()

    logger.info(f"Deleted {deleted_count} news articles older than {days} days (all stocks)")

    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} articles older than {days} days across all stocks"
    }


@router.get("/news/stats")
def get_news_statistics(db: Session = Depends(get_db)):
    """
    Get statistics about news articles in the database.
    """
    total_articles = db.query(News).count()

    # Articles by age
    now = datetime.now(timezone.utc)
    last_24h = db.query(News).filter(News.published_utc >= now - timedelta(days=1)).count()
    last_7d = db.query(News).filter(News.published_utc >= now - timedelta(days=7)).count()
    last_14d = db.query(News).filter(News.published_utc >= now - timedelta(days=14)).count()
    last_30d = db.query(News).filter(News.published_utc >= now - timedelta(days=30)).count()

    # Oldest and newest articles
    oldest = db.query(News).order_by(News.published_utc.asc()).first()
    newest = db.query(News).order_by(News.published_utc.desc()).first()

    return {
        "total_articles": total_articles,
        "articles_by_age": {
            "last_24h": last_24h,
            "last_7d": last_7d,
            "last_14d": last_14d,
            "last_30d": last_30d
        },
        "oldest_article": {
            "date": oldest.published_utc if oldest else None,
            "title": oldest.title if oldest else None
        } if oldest else None,
        "newest_article": {
            "date": newest.published_utc if newest else None,
            "title": newest.title if newest else None
        } if newest else None
    }
