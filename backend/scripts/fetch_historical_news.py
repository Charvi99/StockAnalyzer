#!/usr/bin/env python3
"""
Fetch Historical News from Polygon.io API (Paid Tier)

This script fetches historical news articles for all tracked stocks
from Polygon.io API and stores them in the database with sentiment analysis.

PAID TIER BENEFITS:
- Unlimited API calls (or very high limits)
- Higher rate limits (faster fetching)
- Access to historical news (up to 5 years)

FEATURES:
- Fetches news from 2020-01-01 to present
- Max 5,000 articles per stock (~1,000 per year)
- Uses Polygon's built-in sentiment analysis (insights)
- 6-month batching for fast fetching (paid tier optimized)
- Progress tracking and resume capability
- Database deduplication (no duplicate articles)
- Detailed logging and statistics

Usage:
    # From ML container (recommended):
    docker exec stock_analyzer_ml_training python scripts/fetch_historical_news.py

    # Or from backend container:
    docker-compose exec backend python scripts/fetch_historical_news.py

Expected runtime: 20-30 minutes for 270 stocks with paid tier optimizations
- Max 5,000 articles per stock (~1,000 per year)
- Total articles: ~1.35M (if all stocks have max coverage)

Output:
    - News stored in `news` table
    - Sentiment extracted from Polygon insights
    - Ready for ML feature engineering
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import time

# Add backend to path (works from both containers)
sys.path.insert(0, '/backend')
sys.path.insert(0, '/app')

import pandas as pd
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Database connection
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://stockuser:stockpass123@database:5432/stock_analyzer'
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Polygon API
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')
POLYGON_BASE_URL = 'https://api.polygon.io'

# Date range for historical news (Polygon has ~5 years of historical data)
HISTORICAL_START_DATE = datetime(2020, 1, 1)
END_DATE = datetime.now()

# Batch settings (OPTIMIZED FOR PAID TIER)
BATCH_SIZE_MONTHS = 6  # Fetch 6 months at a time (much faster with paid tier)
MAX_ARTICLES_PER_REQUEST = 1000  # Max articles per API call
MAX_ARTICLES_PER_STOCK = 5000  # Max 5000 articles per stock total (~1000/year)
PAUSE_BETWEEN_REQUESTS = 0  # No pause (paid tier has unlimited calls)

# Progress tracking file (for resume capability)
PROGRESS_FILE = Path('/tmp/historical_news_progress.json')


# ============================================================================
# POLYGON NEWS FETCHER
# ============================================================================

class PolygonNewsFetcher:
    """Fetch news from Polygon.io API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = POLYGON_BASE_URL

    def fetch_news(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = MAX_ARTICLES_PER_REQUEST
    ) -> List[Dict]:
        """
        Fetch news articles for a symbol within date range

        Args:
            symbol: Stock ticker symbol
            start_date: Start date
            end_date: End date
            limit: Max articles to fetch

        Returns:
            List of news article dictionaries
        """
        url = f'{self.base_url}/v2/reference/news'

        params = {
            'ticker': symbol.upper(),
            'published_utc.gte': start_date.strftime('%Y-%m-%d'),
            'published_utc.lt': end_date.strftime('%Y-%m-%d'),
            'limit': limit,
            'order': 'asc',
            'sort': 'published_utc',
            'apiKey': self.api_key
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if data.get('status') != 'OK':
                logger.error(f"Polygon API error: {data.get('error', 'Unknown error')}")
                return []

            articles = data.get('results', [])
            return articles

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []

    def fetch_all_news(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        progress_callback=None,
        max_articles: int = MAX_ARTICLES_PER_STOCK
    ) -> List[Dict]:
        """
        Fetch all news for a symbol, handling pagination

        Fetches most recent first, then limits to max_articles (5000).

        Args:
            symbol: Stock ticker symbol
            start_date: Start date
            end_date: End date
            progress_callback: Optional callback for progress updates
            max_articles: Maximum articles to fetch per stock

        Returns:
            List of all news articles (most recent first, limited to max_articles)
        """
        all_articles = []
        current_date = end_date  # Start from most recent

        while current_date > start_date and len(all_articles) < max_articles:
            # Calculate batch start date (going backwards in time)
            batch_start = max(
                current_date - timedelta(days=31 * BATCH_SIZE_MONTHS),
                start_date
            )

            # Fetch batch (most recent first)
            articles = self.fetch_news(symbol, batch_start, current_date)

            if not articles:
                current_date = batch_start
                continue

            # Add articles (newest first)
            all_articles.extend(articles)

            # Progress callback
            if progress_callback:
                progress_callback(
                    symbol=symbol,
                    batch_start=batch_start,
                    batch_end=current_date,
                    articles_fetched=len(articles)
                )

            # Stop if we've reached the max
            if len(all_articles) >= max_articles:
                all_articles = all_articles[:max_articles]  # Trim to max
                break

            # Move to next batch (older news)
            current_date = batch_start

            # No pause needed for paid tier (PAUSE_BETWEEN_REQUESTS = 0)
            if PAUSE_BETWEEN_REQUESTS > 0:
                time.sleep(PAUSE_BETWEEN_REQUESTS)

        # Sort by published date ascending (oldest first for storage)
        all_articles.sort(key=lambda x: x.get('published_utc', ''))

        return all_articles


# ============================================================================
# NEWS SAVER
# ============================================================================

def save_articles_to_db(stock_id: int, articles: List[Dict]) -> Tuple[int, int, int]:
    """
    Save news articles to database (with deduplication)

    Args:
        stock_id: Stock ID
        articles: List of article dictionaries from Polygon

    Returns:
        Tuple of (created_count, skipped_count, error_count)
    """
    if not articles:
        return 0, 0, 0

    db = SessionLocal()
    created_count = 0
    skipped_count = 0
    error_count = 0

    try:
        for article in articles:
            try:
                # Check if article already exists
                existing = db.execute(
                    text("SELECT id FROM news WHERE article_id = :article_id"),
                    {'article_id': article.get('id')}
                ).fetchone()

                if existing:
                    skipped_count += 1
                    continue

                # Extract sentiment from Polygon insights
                insights = article.get('insights', [])
                ticker_insight = next(
                    (i for i in insights if i.get('ticker') == article.get('ticker')),
                    None
                )

                if ticker_insight:
                    # Use Polygon's sentiment
                    sentiment = ticker_insight.get('sentiment', 'neutral')
                    sentiment_reasoning = ticker_insight.get('sentiment_reasoning', None)
                    # Convert sentiment to score (-1.0 to 1.0)
                    sentiment_score = 0.7 if sentiment == 'positive' else (
                        -0.7 if sentiment == 'negative' else 0.0
                    )
                else:
                    # Fallback: neutral sentiment if no insights
                    sentiment = 'neutral'
                    sentiment_score = 0.0
                    sentiment_reasoning = None

                # Parse published_utc
                published_utc_str = article.get('published_utc', '')
                if published_utc_str:
                    published_utc = datetime.fromisoformat(
                        published_utc_str.replace('Z', '+00:00')
                    )
                else:
                    error_count += 1
                    continue

                # Insert article
                db.execute(
                    text("""
                        INSERT INTO news (
                            stock_id, article_id, publisher, title, author,
                            published_utc, article_url, image_url, description,
                            keywords, sentiment, sentiment_score, sentiment_reasoning,
                            ticker, created_at
                        ) VALUES (
                            :stock_id, :article_id, :publisher, :title, :author,
                            :published_utc, :article_url, :image_url, :description,
                            :keywords, :sentiment, :sentiment_score, :sentiment_reasoning,
                            :ticker, CURRENT_TIMESTAMP
                        )
                        ON CONFLICT (article_id) DO NOTHING
                    """),
                    {
                        'stock_id': stock_id,
                        'article_id': article.get('id'),
                        'publisher': article.get('publisher', {}).get('name'),
                        'title': article.get('title', '')[:500],  # Limit title length
                        'author': article.get('author', '')[:255],
                        'published_utc': published_utc,
                        'article_url': article.get('article_url', '')[:1000],
                        'image_url': article.get('image_url', '')[:1000],
                        'description': article.get('description', '')[:5000],
                        'keywords': article.get('keywords', []),
                        'sentiment': sentiment,
                        'sentiment_score': sentiment_score,
                        'sentiment_reasoning': sentiment_reasoning,
                        'ticker': article.get('ticker', '')
                    }
                )

                created_count += 1

            except Exception as e:
                logger.debug(f"Error saving article: {e}")
                error_count += 1
                continue

        db.commit()

    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
    finally:
        db.close()

    return created_count, skipped_count, error_count


# ============================================================================
# PROGRESS TRACKING
# ============================================================================

def save_progress(progress: Dict):
    """Save progress to file for resume capability"""
    import json
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2, default=str)


def load_progress() -> Dict:
    """Load progress from file"""
    import json
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {}


def format_duration(seconds: float) -> str:
    """Format seconds to human-readable duration"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = seconds / 60
        return f"{mins:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main fetching function"""
    print("=" * 80)
    print(" " * 15)
    print("Historical News Fetcher (Polygon.io - Paid Tier)")
    print(" " * 15)
    print("=" * 80)

    # Check API key
    if not POLYGON_API_KEY or POLYGON_API_KEY == 'your_api_key_here':
        print("\n❌ ERROR: POLYGON_API_KEY not set!")
        print("   Please set POLYGON_API_KEY in your .env file")
        return

    print(f"\n📅 Date range: {HISTORICAL_START_DATE.date()} to {END_DATE.date()}")
    print(f"⏱️  Time span: {(END_DATE - HISTORICAL_START_DATE).days / 365:.1f} years")
    print(f"📰 Max articles per stock: {MAX_ARTICLES_PER_STOCK:,}")
    print(f"⚡ Batch size: {BATCH_SIZE_MONTHS} months per request (optimized for paid tier)")

    # Initialize fetcher
    fetcher = PolygonNewsFetcher(POLYGON_API_KEY)

    # Get tracked stocks
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT id, symbol
                FROM stocks
                WHERE is_tracked = true
                ORDER BY symbol
            """)
        )
        stocks = list(result)
    finally:
        db.close()

    print(f"\n📊 Fetching news for {len(stocks)} stocks")
    print(f"⚡ Paid tier: Unlimited API calls")

    # Load previous progress
    progress = load_progress()
    completed_symbols = set(progress.get('completed_symbols', []))

    if completed_symbols:
        print(f"\n🔄 Resuming from previous run: {len(completed_symbols)} stocks already completed")

    # Statistics
    total_created = 0
    total_skipped = 0
    total_errors = 0
    start_time = time.time()

    # Fetch news for each stock
    print("\n" + "=" * 80)
    print("FETCHING NEWS")
    print("=" * 80)

    for stock in tqdm(stocks, desc="Fetching stocks"):
        stock_id, symbol = stock

        # Skip if already completed
        if symbol in completed_symbols:
            logger.info(f"Skipping {symbol} (already completed)")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"Fetching news for {symbol}")
        logger.info(f"{'='*60}")

        # Fetch all articles
        articles = fetcher.fetch_all_news(
            symbol=symbol,
            start_date=HISTORICAL_START_DATE,
            end_date=END_DATE
        )

        if not articles:
            logger.warning(f"No articles found for {symbol}")
            progress['completed_symbols'] = progress.get('completed_symbols', [])
            progress['completed_symbols'].append(symbol)
            save_progress(progress)
            continue

        logger.info(f"Fetched {len(articles)} articles for {symbol}")

        # Save to database
        created, skipped, errors = save_articles_to_db(stock_id, articles)

        total_created += created
        total_skipped += skipped
        total_errors += errors

        logger.info(f"✅ {symbol}: Created {created}, Skipped {skipped}, Errors {errors}")

        # Update progress
        progress['completed_symbols'] = progress.get('completed_symbols', [])
        progress['completed_symbols'].append(symbol)
        progress['total_created'] = total_created
        progress['total_skipped'] = total_skipped
        progress['total_errors'] = total_errors
        save_progress(progress)

    # Calculate duration
    duration = time.time() - start_time

    # Print summary
    print("\n" + "=" * 80)
    print("✅ HISTORICAL NEWS FETCH COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Results:")
    print(f"   Total articles created: {total_created:,}")
    print(f"   Total articles skipped (duplicates): {total_skipped:,}")
    print(f"   Total errors: {total_errors:,}")
    print(f"   Duration: {format_duration(duration)}")
    print(f"   Average speed: {total_created / max(duration / 60, 1):.0f} articles/minute")

    # Verify database
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT
                    COUNT(*) as total_articles,
                    COUNT(DISTINCT stock_id) as stocks_with_news,
                    MIN(published_utc) as earliest,
                    MAX(published_utc) as latest
                FROM news
                WHERE sentiment_score IS NOT NULL
            """)
        ).fetchone()

        print(f"\n📰 Database Status:")
        print(f"   Total articles: {result[0]:,}")
        print(f"   Stocks with news: {result[1]}")
        print(f"   Date range: {result[2]} to {result[3]}")

    finally:
        db.close()

    # Cleanup progress file
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        print(f"\n🧹 Cleaned up progress file")

    print("\n💡 Next steps:")
    print(f"   1. Run feature engineering with news features:")
    print(f"      docker exec stock_analyzer_ml_training python scripts/feature_engineering.py")
    print(f"   2. Train ML model with news sentiment:")
    print(f"      docker exec stock_analyzer_ml_training python train.py")
    print(f"   3. Expected AUC improvement: +2-4%")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
