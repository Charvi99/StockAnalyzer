"""
Fetcher tasks for automatic data retrieval from Polygon.io

These tasks run in the background to fetch:
- Stock prices (1h, 1d timeframes)
- News articles
- Dividends, splits, short interest
- Market status
"""
from celery import group
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from app.celery_app import celery_app
from app.db.database import SessionLocal
from app.models.stock import Stock
from app.services.polygon_fetcher import PolygonFetcher
import logging
import os

logger = logging.getLogger(__name__)

# Initialize Polygon fetcher (shared across all tasks)
_polygon_fetcher = None

def get_polygon_fetcher() -> PolygonFetcher:
    """Get or create Polygon fetcher instance"""
    global _polygon_fetcher
    if _polygon_fetcher is None:
        api_key = os.getenv('POLYGON_API_KEY')
        _polygon_fetcher = PolygonFetcher(api_key=api_key)
    return _polygon_fetcher

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_last_timestamp(db, stock_id: int, timeframe: str):
    """
    Get the last stored timestamp for a stock + timeframe combination

    Args:
        db: Database session
        stock_id: Stock ID
        timeframe: Timeframe string (e.g., '1h', '1d')

    Returns:
        datetime | None: Last timestamp or None if no data exists
    """
    from app.models.stock import StockPrice
    from sqlalchemy import select, func

    result = db.execute(
        select(func.max(StockPrice.timestamp))
        .where(StockPrice.stock_id == stock_id)
        .where(StockPrice.timeframe == timeframe)
    ).scalar()

    return result


def calculate_fetch_range(last_timestamp, timeframe: str, lookback_hours: int = 24):
    """
    Calculate the date range to fetch based on last stored data

    Args:
        last_timestamp: Last stored timestamp (None if no data exists)
        timeframe: Timeframe string
        lookback_hours: Default lookback if no data (default: 24 hours)

    Returns:
        tuple: (from_date, to_date)
    """
    now = datetime.now(timezone.utc)

    if last_timestamp is None:
        # No data exists - fetch default lookback period
        from_date = now - timedelta(hours=lookback_hours)
        logger.info(f"No existing data - fetching {lookback_hours}h lookback")
    else:
        # Make last_timestamp timezone-aware if it isn't
        if last_timestamp.tzinfo is None:
            last_timestamp = last_timestamp.replace(tzinfo=timezone.utc)

        # Fetch from 1 hour before last timestamp (overlap for safety)
        from_date = last_timestamp - timedelta(hours=1)
        logger.info(f"Last data: {last_timestamp}, fetching from {from_date} (1h overlap)")

    return from_date, now


def fetch_stock_data_incremental(db, stock_id: int, symbol: str, timeframe: str) -> dict:
    """
    Fetch stock data incrementally based on last stored timestamp

    Args:
        db: Database session
        stock_id: Stock ID
        symbol: Stock symbol
        timeframe: Timeframe string (e.g., '1h', '1d')

    Returns:
        dict: Status with bars_fetched count
    """
    from app.models.timeframe import Timeframe
    from app.models.stock import StockPrice

    try:
        # Get Polygon fetcher
        polygon = get_polygon_fetcher()

        # Get last stored timestamp
        last_timestamp = get_last_timestamp(db, stock_id, timeframe)

        # Calculate fetch range
        from_date, to_date = calculate_fetch_range(last_timestamp, timeframe)

        # Convert timeframe to Polygon API parameters
        multiplier, timespan = Timeframe.to_polygon_params(timeframe)

        # Format dates for Polygon API (YYYY-MM-DD)
        from_str = from_date.strftime('%Y-%m-%d')
        to_str = to_date.strftime('%Y-%m-%d')

        logger.info(f"📊 Fetching {symbol} {timeframe}: {from_str} to {to_str} (multiplier={multiplier}, timespan={timespan})")

        # Fetch data from Polygon API
        aggs = polygon.client.get_aggs(
            ticker=symbol.upper(),
            multiplier=multiplier,
            timespan=timespan,
            from_=from_str,
            to=to_str,
            limit=50000  # Max results
        )

        if not aggs or len(aggs) == 0:
            logger.warning(f"⚠️ No data returned from Polygon for {symbol} {timeframe}")
            return {
                'status': 'no_data',
                'symbol': symbol,
                'timeframe': timeframe,
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat(),
                'bars_fetched': 0
            }

        # Store fetched data in database
        bars_inserted = 0
        bars_updated = 0

        for bar in aggs:
            # Polygon returns timestamps in milliseconds
            bar_timestamp = datetime.fromtimestamp(bar.timestamp / 1000, tz=timezone.utc)

            # Check if price record already exists (handles 1-hour overlap)
            existing_price = db.query(StockPrice).filter(
                StockPrice.stock_id == stock_id,
                StockPrice.timeframe == timeframe,
                StockPrice.timestamp == bar_timestamp
            ).first()

            if existing_price:
                # Update existing record
                existing_price.open = float(bar.open)
                existing_price.high = float(bar.high)
                existing_price.low = float(bar.low)
                existing_price.close = float(bar.close)
                existing_price.volume = int(bar.volume)
                existing_price.adjusted_close = float(bar.close)
                bars_updated += 1
            else:
                # Insert new record
                price = StockPrice(
                    stock_id=stock_id,
                    timeframe=timeframe,
                    timestamp=bar_timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume),
                    adjusted_close=float(bar.close)
                )
                db.add(price)
                bars_inserted += 1

        db.commit()

        logger.info(f"✅ {symbol} {timeframe}: Inserted {bars_inserted}, Updated {bars_updated} bars")

        return {
            'status': 'success',
            'symbol': symbol,
            'timeframe': timeframe,
            'from_date': from_date.isoformat(),
            'to_date': to_date.isoformat(),
            'last_timestamp': last_timestamp.isoformat() if last_timestamp else None,
            'bars_fetched': len(aggs),
            'bars_inserted': bars_inserted,
            'bars_updated': bars_updated
        }

    except Exception as e:
        logger.error(f"❌ Error fetching {symbol} {timeframe}: {str(e)}")
        db.rollback()
        return {
            'status': 'error',
            'symbol': symbol,
            'timeframe': timeframe,
            'error': str(e)
        }


# ============================================
# FETCHING TASKS (with adaptive incremental logic)
# ============================================

@celery_app.task(bind=True, max_retries=3)
def fetch_high_priority_stocks(self):
    """
    Fetch price data for all high-priority stocks (every hour)

    Uses adaptive incremental fetching:
    - Queries last stored timestamp for each stock
    - Fetches only new data since last update
    - Includes 1-hour overlap for safety
    - Handles missing data automatically
    - Checks market hours before fetching (respects weekends/holidays)

    With Stocks Starter plan (100 req/min), fetches ALL tracked stocks
    TODO: Implement priority system to determine which stocks are high-priority
    """
    from app.utils.market_hours import should_fetch_data

    logger.info("🚀 Starting fetch_high_priority_stocks task")

    # Check if market allows fetching
    market_check = should_fetch_data(priority='high')
    logger.info(f"📊 Market Status: {market_check['market_status']} - {market_check['reason']}")
    logger.info(f"🕐 Current Time (ET): {market_check['current_time_et']}")

    if not market_check['should_fetch']:
        logger.info(f"⏸️ Skipping fetch - {market_check['reason']}")
        if 'next_open' in market_check:
            logger.info(f"⏰ Market opens: {market_check['next_open']}")
        return {
            'status': 'skipped',
            'reason': market_check['reason'],
            'market_status': market_check['market_status'],
            'current_time_et': market_check['current_time_et']
        }

    db = SessionLocal()
    try:
        # Get high-priority tracked stocks
        stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.priority == 'high'
        ).all()

        if not stocks:
            logger.warning("⚠️ No tracked stocks found")
            return {
                'status': 'no_stocks',
                'message': 'No tracked stocks found in database'
            }

        logger.info(f"📊 Fetching 1h data for {len(stocks)} stocks")

        # Fetch data for each stock
        results = []
        success_count = 0
        success_stock_ids = []  # IDs fetched OK → analyzed once after the batch (H1 fix)
        error_count = 0

        import time

        for idx, stock in enumerate(stocks):
            try:
                # Fetch 1h timeframe for high-priority stocks
                result = fetch_stock_data_incremental(db, stock.id, stock.symbol, '1h')
                results.append(result)

                if result['status'] == 'success':
                    success_count += 1

                    # Update fetch timing for countdown timer
                    try:
                        stock.last_fetch_at = datetime.now(timezone.utc)
                        if stock.priority == 'high':
                            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=1)
                        elif stock.priority == 'medium':
                            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=4)
                        else:  # low priority
                            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=24)
                        db.commit()
                        logger.debug(f"Updated fetch timing for {stock.symbol}: next fetch at {stock.next_fetch_at}")
                    except Exception as e:
                        logger.warning(f"Failed to update fetch timing for {stock.symbol}: {e}")

                    # After successful fetch, aggregate to daily/weekly/monthly timeframes
                    from app.services.timeframe_aggregator import TimeframeAggregator
                    logger.info(f"📊 Aggregating timeframes for {stock.symbol}...")
                    agg_results = TimeframeAggregator.aggregate_all_and_save_to_db(db, stock.id, days_lookback=90)
                    logger.info(f"Aggregation results for {stock.symbol}: {agg_results}")

                    # After aggregation, calculate and cache indicators for daily timeframe
                    from app.services.indicator_cache_service import IndicatorCacheService
                    logger.info(f"💾 Caching indicators for {stock.symbol}...")
                    cache_success = IndicatorCacheService.calculate_and_cache(db, stock.id, timeframe='1d')
                    logger.info(f"Cache {'✅ success' if cache_success else '❌ failed'} for {stock.symbol}")

                    # H1 fix: do NOT queue per-stock analysis here. The batch task
                    # (analyze_<priority>_priority_stocks) is queued once after this whole
                    # fetch loop completes and analyzes every successfully-fetched stock —
                    # queuing here too caused each stock to be analyzed twice per cycle.
                    success_stock_ids.append(stock.id)

                elif result['status'] == 'error':
                    error_count += 1

                # Rate limiting: 100 req/min = 0.6s between requests
                # Add 1s delay to be safe and avoid hitting rate limit
                if idx < len(stocks) - 1:  # Don't sleep after last request
                    time.sleep(1)

            except Exception as e:
                logger.error(f"❌ Error fetching {stock.symbol}: {str(e)}")
                error_count += 1
                results.append({
                    'status': 'error',
                    'symbol': stock.symbol,
                    'error': str(e)
                })
                # Still sleep to maintain rate limit
                if idx < len(stocks) - 1:
                    time.sleep(1)

        # Calculate totals
        total_bars_inserted = sum(r.get('bars_inserted', 0) for r in results if r['status'] == 'success')
        total_bars_updated = sum(r.get('bars_updated', 0) for r in results if r['status'] == 'success')

        logger.info(f"✅ Fetch complete: {success_count} success, {error_count} errors")
        logger.info(f"📊 Total bars: {total_bars_inserted} inserted, {total_bars_updated} updated")

        # Trigger analysis ONLY after the full fetch batch completes, and only for stocks
        # that were freshly fetched (H1 fix: was double-scheduled per-stock, and re-analyzed
        # stocks whose fetch had failed).
        if success_count > 0:
            from app.tasks.analysis_tasks import analyze_high_priority_stocks
            logger.info(f"🔬 Queuing analysis for {len(success_stock_ids)} freshly-fetched high-priority stocks...")
            analyze_high_priority_stocks.apply_async(args=[success_stock_ids], countdown=30)

        return {
            'status': 'completed',
            'stocks_processed': len(stocks),
            'success_count': success_count,
            'error_count': error_count,
            'total_bars_inserted': total_bars_inserted,
            'total_bars_updated': total_bars_updated,
            'details': results
        }

    except Exception as e:
        logger.error(f"❌ Fatal error in fetch_high_priority_stocks: {str(e)}")
        # Retry task if it fails
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes

    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3)
def fetch_medium_priority_stocks(self):
    """
    Fetch price data for all medium-priority stocks (every 4 hours)

    Uses adaptive incremental fetching with 1h timeframe
    Checks market hours before fetching (respects weekends/holidays)
    """
    from app.utils.market_hours import should_fetch_data

    logger.info("🚀 Starting fetch_medium_priority_stocks task")

    # Check if market allows fetching
    market_check = should_fetch_data(priority='medium')
    logger.info(f"📊 Market Status: {market_check['market_status']} - {market_check['reason']}")
    logger.info(f"🕐 Current Time (ET): {market_check['current_time_et']}")

    if not market_check['should_fetch']:
        logger.info(f"⏸️ Skipping fetch - {market_check['reason']}")
        if 'next_open' in market_check:
            logger.info(f"⏰ Market opens: {market_check['next_open']}")
        return {
            'status': 'skipped',
            'reason': market_check['reason'],
            'market_status': market_check['market_status'],
            'current_time_et': market_check['current_time_et']
        }

    db = SessionLocal()
    try:
        # Get medium-priority tracked stocks
        stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.priority == 'medium'
        ).all()

        if not stocks:
            logger.warning("⚠️ No medium-priority stocks found")
            return {
                'status': 'no_stocks',
                'message': 'No medium-priority stocks found'
            }

        logger.info(f"📊 Fetching 1h data for {len(stocks)} medium-priority stocks")

        results = []
        success_count = 0
        success_stock_ids = []  # IDs fetched OK → analyzed once after the batch (H1 fix)
        error_count = 0

        import time

        for idx, stock in enumerate(stocks):
            try:
                result = fetch_stock_data_incremental(db, stock.id, stock.symbol, '1h')
                results.append(result)

                if result['status'] == 'success':
                    success_count += 1

                    # Update fetch timing for countdown timer
                    try:
                        stock.last_fetch_at = datetime.now(timezone.utc)
                        if stock.priority == 'high':
                            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=1)
                        elif stock.priority == 'medium':
                            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=4)
                        else:  # low priority
                            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=24)
                        db.commit()
                        logger.debug(f"Updated fetch timing for {stock.symbol}: next fetch at {stock.next_fetch_at}")
                    except Exception as e:
                        logger.warning(f"Failed to update fetch timing for {stock.symbol}: {e}")

                    # After successful fetch, aggregate to daily/weekly/monthly timeframes
                    from app.services.timeframe_aggregator import TimeframeAggregator
                    logger.info(f"📊 Aggregating timeframes for {stock.symbol}...")
                    agg_results = TimeframeAggregator.aggregate_all_and_save_to_db(db, stock.id, days_lookback=90)
                    logger.info(f"Aggregation results for {stock.symbol}: {agg_results}")

                    # After aggregation, calculate and cache indicators for daily timeframe
                    from app.services.indicator_cache_service import IndicatorCacheService
                    logger.info(f"💾 Caching indicators for {stock.symbol}...")
                    cache_success = IndicatorCacheService.calculate_and_cache(db, stock.id, timeframe='1d')
                    logger.info(f"Cache {'✅ success' if cache_success else '❌ failed'} for {stock.symbol}")

                    # H1 fix: do NOT queue per-stock analysis here. The batch task
                    # (analyze_<priority>_priority_stocks) is queued once after this whole
                    # fetch loop completes and analyzes every successfully-fetched stock —
                    # queuing here too caused each stock to be analyzed twice per cycle.
                    success_stock_ids.append(stock.id)

                elif result['status'] == 'error':
                    error_count += 1

                if idx < len(stocks) - 1:
                    time.sleep(1)

            except Exception as e:
                logger.error(f"❌ Error fetching {stock.symbol}: {str(e)}")
                error_count += 1
                results.append({'status': 'error', 'symbol': stock.symbol, 'error': str(e)})
                if idx < len(stocks) - 1:
                    time.sleep(1)

        total_bars_inserted = sum(r.get('bars_inserted', 0) for r in results if r['status'] == 'success')
        total_bars_updated = sum(r.get('bars_updated', 0) for r in results if r['status'] == 'success')

        logger.info(f"✅ Fetch complete: {success_count} success, {error_count} errors")

        # Trigger analysis only after the full fetch batch completes, and only for freshly
        # fetched stocks (H1 fix).
        if success_count > 0:
            from app.tasks.analysis_tasks import analyze_medium_priority_stocks
            logger.info(f"🔬 Queuing analysis for {len(success_stock_ids)} freshly-fetched medium-priority stocks...")
            analyze_medium_priority_stocks.apply_async(args=[success_stock_ids], countdown=30)

        return {
            'status': 'completed',
            'stocks_processed': len(stocks),
            'success_count': success_count,
            'error_count': error_count,
            'total_bars_inserted': total_bars_inserted,
            'total_bars_updated': total_bars_updated
        }

    except Exception as e:
        logger.error(f"❌ Fatal error in fetch_medium_priority_stocks: {str(e)}")
        raise self.retry(exc=e, countdown=300)

    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3)
def fetch_low_priority_stocks(self):
    """
    Fetch daily price data for low-priority stocks (once daily)

    Uses adaptive incremental fetching with 1d timeframe
    Checks market hours before fetching (respects weekends/holidays)
    """
    from app.utils.market_hours import should_fetch_data

    logger.info("🚀 Starting fetch_low_priority_stocks task")

    # Check if market allows fetching
    market_check = should_fetch_data(priority='low')
    logger.info(f"📊 Market Status: {market_check['market_status']} - {market_check['reason']}")
    logger.info(f"🕐 Current Time (ET): {market_check['current_time_et']}")

    if not market_check['should_fetch']:
        logger.info(f"⏸️ Skipping fetch - {market_check['reason']}")
        if 'next_open' in market_check:
            logger.info(f"⏰ Market opens: {market_check['next_open']}")
        return {
            'status': 'skipped',
            'reason': market_check['reason'],
            'market_status': market_check['market_status'],
            'current_time_et': market_check['current_time_et']
        }

    db = SessionLocal()
    try:
        # Get low-priority tracked stocks
        stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.priority == 'low'
        ).all()

        if not stocks:
            logger.warning("⚠️ No low-priority stocks found")
            return {
                'status': 'no_stocks',
                'message': 'No low-priority stocks found'
            }

        logger.info(f"📊 Fetching 1d data for {len(stocks)} low-priority stocks")

        results = []
        success_count = 0
        success_stock_ids = []  # IDs fetched OK → analyzed once after the batch (H1 fix)
        error_count = 0

        import time

        for idx, stock in enumerate(stocks):
            try:
                # Fetch daily data for low-priority stocks
                result = fetch_stock_data_incremental(db, stock.id, stock.symbol, '1d')
                results.append(result)

                if result['status'] == 'success':
                    success_count += 1
                    success_stock_ids.append(stock.id)  # analyzed once after the batch (H1 fix)

                    # Update fetch timing for countdown timer
                    try:
                        stock.last_fetch_at = datetime.now(timezone.utc)
                        if stock.priority == 'high':
                            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=1)
                        elif stock.priority == 'medium':
                            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=4)
                        else:  # low priority
                            stock.next_fetch_at = stock.last_fetch_at + timedelta(hours=24)
                        db.commit()
                        logger.debug(f"Updated fetch timing for {stock.symbol}: next fetch at {stock.next_fetch_at}")
                    except Exception as e:
                        logger.warning(f"Failed to update fetch timing for {stock.symbol}: {e}")

                elif result['status'] == 'error':
                    error_count += 1

                if idx < len(stocks) - 1:
                    time.sleep(1)

            except Exception as e:
                logger.error(f"❌ Error fetching {stock.symbol}: {str(e)}")
                error_count += 1
                results.append({'status': 'error', 'symbol': stock.symbol, 'error': str(e)})
                if idx < len(stocks) - 1:
                    time.sleep(1)

        total_bars_inserted = sum(r.get('bars_inserted', 0) for r in results if r['status'] == 'success')
        total_bars_updated = sum(r.get('bars_updated', 0) for r in results if r['status'] == 'success')

        logger.info(f"✅ Fetch complete: {success_count} success, {error_count} errors")

        # Trigger analysis only after the full fetch batch completes, and only for freshly
        # fetched stocks.
        if success_count > 0:
            from app.tasks.analysis_tasks import analyze_low_priority_stocks
            logger.info(f"🔬 Queuing analysis for {len(success_stock_ids)} freshly-fetched low-priority stocks...")
            analyze_low_priority_stocks.apply_async(args=[success_stock_ids], countdown=30)

        return {
            'status': 'completed',
            'stocks_processed': len(stocks),
            'success_count': success_count,
            'error_count': error_count,
            'total_bars_inserted': total_bars_inserted,
            'total_bars_updated': total_bars_updated
        }

    except Exception as e:
        logger.error(f"❌ Fatal error in fetch_low_priority_stocks: {str(e)}")
        raise self.retry(exc=e, countdown=300)

    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3)
def fetch_high_priority_news(self):
    """
    Fetch news for high-priority stocks (every 2 hours)
    
    Fetches last 2 hours of news articles and performs basic sentiment analysis
    """
    from app.db.database import SessionLocal
    from app.models.stock import Stock
    from app.models.news import News
    from datetime import datetime, timedelta, timezone
    import time
    
    logger.info("📰 Starting news fetch for high-priority stocks")
    
    db = SessionLocal()
    try:
        polygon = get_polygon_fetcher()
        
        # Get all high-priority stocks
        stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.priority == 'high'
        ).all()
        
        # Calculate date filter (last 2 hours, but Polygon news API only accepts date, not datetime)
        published_after = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime('%Y-%m-%d')
        
        total_articles = 0
        success_count = 0
        error_count = 0
        
        for idx, stock in enumerate(stocks):
            try:
                # Fetch news articles
                articles = polygon.fetch_news(
                    symbol=stock.symbol,
                    limit=5,  # Max 5 articles per stock
                    published_after=published_after
                )
                
                # Save articles to database
                saved_count = 0
                for article in articles:
                    # Check if article already exists
                    existing = db.query(News).filter(
                        News.article_id == article['id']
                    ).first()
                    
                    if not existing:
                        # Extract sentiment from Polygon insights (per-ticker sentiment with reasoning)
                        insights = article.get('insights', [])
                        ticker_insight = next((i for i in insights if i.get('ticker') == stock.symbol), None)

                        if ticker_insight:
                            # Use Polygon's sentiment
                            sentiment = ticker_insight.get('sentiment', 'neutral')
                            sentiment_reasoning = ticker_insight.get('sentiment_reasoning', None)
                            # Convert sentiment to score (-1.0 to 1.0)
                            sentiment_score = 0.7 if sentiment == 'positive' else (-0.7 if sentiment == 'negative' else 0.0)
                        else:
                            # Fallback to simple keyword sentiment if no insights
                            sentiment, sentiment_score = analyze_sentiment(article.get('title', ''))
                            sentiment_reasoning = None

                        db_news = News(
                            stock_id=stock.id,
                            article_id=article['id'],
                            publisher=article.get('publisher', {}).get('name'),
                            title=article['title'],
                            author=article.get('author'),
                            published_utc=datetime.fromisoformat(article['published_utc'].replace('Z', '+00:00')),
                            article_url=article.get('article_url'),
                            image_url=article.get('image_url'),
                            description=article.get('description'),
                            keywords=article.get('keywords', []),
                            sentiment=sentiment,
                            sentiment_score=sentiment_score,
                            sentiment_reasoning=sentiment_reasoning,
                            ticker=stock.symbol
                        )
                        db.add(db_news)
                        saved_count += 1
                
                db.commit()
                
                total_articles += saved_count
                success_count += 1
                
                logger.info(f"✅ {stock.symbol}: Fetched {len(articles)} articles, saved {saved_count} new")
                
            except Exception as e:
                logger.error(f"❌ Error fetching news for {stock.symbol}: {e}")
                error_count += 1
                db.rollback()
            
            # Rate limiting: 1s between requests
            if idx < len(stocks) - 1:
                time.sleep(1)
        
        logger.info(f"✅ News fetch complete: {success_count} stocks processed, {total_articles} new articles, {error_count} errors")
        
        return {
            'status': 'completed',
            'stocks_processed': len(stocks),
            'success_count': success_count,
            'error_count': error_count,
            'total_articles_saved': total_articles
        }
        
    except Exception as e:
        logger.error(f"❌ Error in fetch_high_priority_news: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


def analyze_sentiment(text: str) -> tuple:
    """
    Simple sentiment analysis based on keywords
    
    Returns:
        tuple: (sentiment, sentiment_score) where sentiment is 'positive', 'negative', 'neutral'
               and sentiment_score is float between -1.0 and 1.0
    """
    if not text:
        return 'neutral', 0.0
    
    text_lower = text.lower()
    
    # Simple keyword-based sentiment (can be improved with VADER or ML later)
    positive_words = ['gain', 'surge', 'rally', 'profit', 'beat', 'exceed', 'strong', 'growth', 'upgrade', 'bullish', 'outperform', 'buy']
    negative_words = ['loss', 'drop', 'plunge', 'miss', 'weak', 'decline', 'downgrade', 'bearish', 'sell', 'underperform', 'crash', 'fall']
    
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    total = positive_count + negative_count
    
    if total == 0:
        return 'neutral', 0.0
    
    score = (positive_count - negative_count) / total
    
    if score > 0.3:
        return 'positive', round(score, 4)
    elif score < -0.3:
        return 'negative', round(score, 4)
    else:
        return 'neutral', round(score, 4)

@celery_app.task(bind=True, max_retries=3)
def fetch_medium_priority_news(self):
    """
    Fetch news for medium-priority stocks (every 8 hours)
    
    Fetches last 8 hours of news articles and performs basic sentiment analysis
    """
    from app.db.database import SessionLocal
    from app.models.stock import Stock
    from app.models.news import News
    from datetime import datetime, timedelta, timezone
    import time
    
    logger.info("📰 Starting news fetch for medium-priority stocks")
    
    db = SessionLocal()
    try:
        polygon = get_polygon_fetcher()
        
        # Get all medium-priority stocks
        stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.priority == 'medium'
        ).all()
        
        # Calculate date filter (last 8 hours, but Polygon news API only accepts date, not datetime)
        published_after = (datetime.now(timezone.utc) - timedelta(hours=8)).strftime('%Y-%m-%d')
        
        total_articles = 0
        success_count = 0
        error_count = 0
        
        for idx, stock in enumerate(stocks):
            try:
                # Fetch news articles
                articles = polygon.fetch_news(
                    symbol=stock.symbol,
                    limit=5,  # Max 5 articles per stock
                    published_after=published_after
                )
                
                # Save articles to database
                saved_count = 0
                for article in articles:
                    # Check if article already exists
                    existing = db.query(News).filter(
                        News.article_id == article['id']
                    ).first()
                    
                    if not existing:
                        # Extract sentiment from Polygon insights (per-ticker sentiment with reasoning)
                        insights = article.get('insights', [])
                        ticker_insight = next((i for i in insights if i.get('ticker') == stock.symbol), None)

                        if ticker_insight:
                            # Use Polygon's sentiment
                            sentiment = ticker_insight.get('sentiment', 'neutral')
                            sentiment_reasoning = ticker_insight.get('sentiment_reasoning', None)
                            # Convert sentiment to score (-1.0 to 1.0)
                            sentiment_score = 0.7 if sentiment == 'positive' else (-0.7 if sentiment == 'negative' else 0.0)
                        else:
                            # Fallback to simple keyword sentiment if no insights
                            sentiment, sentiment_score = analyze_sentiment(article.get('title', ''))
                            sentiment_reasoning = None

                        db_news = News(
                            stock_id=stock.id,
                            article_id=article['id'],
                            publisher=article.get('publisher', {}).get('name'),
                            title=article['title'],
                            author=article.get('author'),
                            published_utc=datetime.fromisoformat(article['published_utc'].replace('Z', '+00:00')),
                            article_url=article.get('article_url'),
                            image_url=article.get('image_url'),
                            description=article.get('description'),
                            keywords=article.get('keywords', []),
                            sentiment=sentiment,
                            sentiment_score=sentiment_score,
                            sentiment_reasoning=sentiment_reasoning,
                            ticker=stock.symbol
                        )
                        db.add(db_news)
                        saved_count += 1
                
                db.commit()
                
                total_articles += saved_count
                success_count += 1
                
                logger.info(f"✅ {stock.symbol}: Fetched {len(articles)} articles, saved {saved_count} new")
                
            except Exception as e:
                logger.error(f"❌ Error fetching news for {stock.symbol}: {e}")
                error_count += 1
                db.rollback()
            
            # Rate limiting: 1s between requests
            if idx < len(stocks) - 1:
                time.sleep(1)
        
        logger.info(f"✅ News fetch complete: {success_count} stocks processed, {total_articles} new articles, {error_count} errors")
        
        return {
            'status': 'completed',
            'stocks_processed': len(stocks),
            'success_count': success_count,
            'error_count': error_count,
            'total_articles_saved': total_articles
        }
        
    except Exception as e:
        logger.error(f"❌ Error in fetch_medium_priority_news: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3)
def fetch_dividends_batch(self):
    """
    Fetch dividends for all tracked stocks (weekly on Sunday)
    
    Fetches last year of dividend history for all stocks
    """
    from app.db.database import SessionLocal
    from app.models.stock import Stock
    from app.models.dividend import Dividend
    from datetime import date
    import time
    
    logger.info("💰 Starting dividends fetch for all tracked stocks")
    
    db = SessionLocal()
    try:
        polygon = get_polygon_fetcher()
        
        # Get all tracked stocks (not filtered by priority - weekly task)
        stocks = db.query(Stock).filter(Stock.is_tracked == True).all()
        
        total_dividends = 0
        success_count = 0
        error_count = 0
        
        for idx, stock in enumerate(stocks):
            try:
                # Fetch dividend history
                dividends = polygon.fetch_dividends(
                    symbol=stock.symbol,
                    limit=50  # Last 50 dividends (covers several years for most stocks)
                )
                
                # Save dividends to database
                saved_count = 0
                for div in dividends:
                    # Check if dividend already exists
                    ex_date = date.fromisoformat(div['ex_dividend_date'])
                    
                    existing = db.query(Dividend).filter(
                        Dividend.stock_id == stock.id,
                        Dividend.ex_dividend_date == ex_date
                    ).first()
                    
                    if not existing:
                        db_dividend = Dividend(
                            stock_id=stock.id,
                            ex_dividend_date=ex_date,
                            payment_date=date.fromisoformat(div['pay_date']) if div.get('pay_date') else None,
                            record_date=date.fromisoformat(div['record_date']) if div.get('record_date') else None,
                            declaration_date=date.fromisoformat(div['declaration_date']) if div.get('declaration_date') else None,
                            cash_amount=float(div['cash_amount']),
                            frequency=div.get('frequency'),
                            dividend_type=div.get('dividend_type')
                        )
                        db.add(db_dividend)
                        saved_count += 1
                
                db.commit()
                
                total_dividends += saved_count
                success_count += 1
                
                if len(dividends) > 0:
                    logger.info(f"✅ {stock.symbol}: Fetched {len(dividends)} dividends, saved {saved_count} new")
                
            except Exception as e:
                logger.error(f"❌ Error fetching dividends for {stock.symbol}: {e}")
                error_count += 1
                db.rollback()
            
            # Rate limiting: 1s between requests
            if idx < len(stocks) - 1:
                time.sleep(1)
        
        logger.info(f"✅ Dividends fetch complete: {success_count} stocks processed, {total_dividends} new dividends, {error_count} errors")
        
        return {
            'status': 'completed',
            'stocks_processed': len(stocks),
            'success_count': success_count,
            'error_count': error_count,
            'total_dividends_saved': total_dividends
        }
        
    except Exception as e:
        logger.error(f"❌ Error in fetch_dividends_batch: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3)
def fetch_splits_batch(self):
    """
    Fetch stock splits for all tracked stocks (weekly on Monday)
    
    Fetches stock split history for all stocks
    """
    from app.db.database import SessionLocal
    from app.models.stock import Stock
    from app.models.stock_split import StockSplit
    from datetime import date
    import time
    
    logger.info("✂️ Starting stock splits fetch for all tracked stocks")
    
    db = SessionLocal()
    try:
        polygon = get_polygon_fetcher()
        
        # Get all tracked stocks (not filtered by priority - weekly task)
        stocks = db.query(Stock).filter(Stock.is_tracked == True).all()
        
        total_splits = 0
        success_count = 0
        error_count = 0
        
        for idx, stock in enumerate(stocks):
            try:
                # Fetch split history
                splits = polygon.fetch_splits(
                    symbol=stock.symbol,
                    limit=50  # Last 50 splits (covers many years)
                )
                
                # Save splits to database
                saved_count = 0
                for split in splits:
                    # Check if split already exists
                    exec_date = date.fromisoformat(split['execution_date'])
                    
                    existing = db.query(StockSplit).filter(
                        StockSplit.stock_id == stock.id,
                        StockSplit.execution_date == exec_date
                    ).first()
                    
                    if not existing:
                        split_from = float(split['split_from'])
                        split_to = float(split['split_to'])
                        split_ratio = split_to / split_from if split_from > 0 else 0
                        
                        db_split = StockSplit(
                            stock_id=stock.id,
                            execution_date=exec_date,
                            split_from=split_from,
                            split_to=split_to,
                            split_ratio=split_ratio
                        )
                        db.add(db_split)
                        saved_count += 1
                
                db.commit()
                
                total_splits += saved_count
                success_count += 1
                
                if len(splits) > 0:
                    logger.info(f"✅ {stock.symbol}: Fetched {len(splits)} splits, saved {saved_count} new")
                
            except Exception as e:
                logger.error(f"❌ Error fetching splits for {stock.symbol}: {e}")
                error_count += 1
                db.rollback()
            
            # Rate limiting: 1s between requests
            if idx < len(stocks) - 1:
                time.sleep(1)
        
        logger.info(f"✅ Splits fetch complete: {success_count} stocks processed, {total_splits} new splits, {error_count} errors")
        
        return {
            'status': 'completed',
            'stocks_processed': len(stocks),
            'success_count': success_count,
            'error_count': error_count,
            'total_splits_saved': total_splits
        }
        
    except Exception as e:
        logger.error(f"❌ Error in fetch_splits_batch: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3)
def fetch_short_interest_batch(self):
    """
    Fetch short interest data for all tracked stocks (weekly on Tuesday)
    
    Note: Short interest data is not available from Polygon.io.
    This task is a placeholder for future integration with FINRA or other providers.
    """
    logger.info("📊 Short interest fetching not yet available from Polygon.io")
    logger.info("📊 Future implementation will integrate with FINRA or alternative provider")
    
    return {
        'status': 'not_available',
        'message': 'Short interest data not available from Polygon.io. Requires FINRA integration.'
    }

@celery_app.task
def fetch_market_status():
    """
    Fetch current market status (every hour)

    TODO: Implement market status check
    """
    logger.info("fetch_market_status - Not yet implemented")
    return {'status': 'placeholder', 'message': 'Market status check not yet implemented'}

# ============================================
# TEST TASK (to verify Celery is working)
# ============================================

@celery_app.task
def test_fetch_task():
    """
    Test task to verify Celery worker is running and can access database

    Returns:
        dict: Status and stock count
    """
    logger.info("Running test_fetch_task")
    db = SessionLocal()
    try:
        stock_count = db.query(Stock).count()
        logger.info(f"Found {stock_count} stocks in database")
        return {
            'status': 'success',
            'message': 'Celery worker is running!',
            'stock_count': stock_count,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error in test_fetch_task: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }
    finally:
        db.close()


@celery_app.task
def test_adaptive_fetch(symbol: str = 'AAPL', timeframe: str = '1h'):
    """
    Test the adaptive incremental fetching logic (dry run - no API call)

    Args:
        symbol: Stock symbol to test (default: AAPL)
        timeframe: Timeframe to test (default: 1h)

    Returns:
        dict: Detailed information about what would be fetched
    """
    logger.info(f"Testing adaptive fetch for {symbol} {timeframe}")
    db = SessionLocal()
    try:
        # Get stock
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            return {
                'status': 'error',
                'message': f'Stock {symbol} not found in database'
            }

        # Get last timestamp
        last_timestamp = get_last_timestamp(db, stock.id, timeframe)

        # Calculate what would be fetched
        from_date, to_date = calculate_fetch_range(last_timestamp, timeframe)

        # Get total bars currently stored
        from app.models.stock import StockPrice
        total_bars = db.query(StockPrice).filter(
            StockPrice.stock_id == stock.id,
            StockPrice.timeframe == timeframe
        ).count()

        return {
            'status': 'success',
            'symbol': symbol,
            'stock_id': stock.id,
            'timeframe': timeframe,
            'last_stored_timestamp': last_timestamp.isoformat() if last_timestamp else 'No data yet',
            'would_fetch_from': from_date.isoformat(),
            'would_fetch_to': to_date.isoformat(),
            'hours_to_fetch': (to_date - from_date).total_seconds() / 3600,
            'total_bars_stored': total_bars,
            'explanation': (
                f"{'No existing data - will fetch 24h lookback' if last_timestamp is None else f'Last bar at {last_timestamp.isoformat()}, will fetch from 1h before (overlap) to now'}"
            )
        }
    except Exception as e:
        logger.error(f"Error in test_adaptive_fetch: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }
    finally:
        db.close()


@celery_app.task
def test_fetch_single_stock(symbol: str = 'AAPL', timeframe: str = '1h'):
    """
    Test fetching real data for a single stock (makes actual API call)

    Args:
        symbol: Stock symbol to test (default: AAPL)
        timeframe: Timeframe to test (default: 1h)

    Returns:
        dict: Result of the fetch operation
    """
    logger.info(f"🧪 Testing real fetch for {symbol} {timeframe}")
    db = SessionLocal()
    try:
        # Get stock
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            return {
                'status': 'error',
                'message': f'Stock {symbol} not found in database'
            }

        # Perform actual fetch
        result = fetch_stock_data_incremental(db, stock.id, stock.symbol, timeframe)

        return result

    except Exception as e:
        logger.error(f"Error in test_fetch_single_stock: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }
    finally:
        db.close()
