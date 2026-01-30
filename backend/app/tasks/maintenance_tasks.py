"""
Maintenance tasks for system health and optimization

These tasks run during off-hours to:
- Recalculate stock priorities
- Clean up old logs and data
- Generate statistics and reports
"""
from app.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)

# ============================================
# MAINTENANCE TASKS
# ============================================

@celery_app.task
def recalculate_all_priorities():
    """
    Recalculate priority scores for all stocks (daily at 3 AM)

    This determines which stocks are high/medium/low priority
    based on volume, patterns, volatility, etc.
    """
    from app.db.database import SessionLocal
    from app.services.priority_calculator import PriorityCalculator

    logger.info("🔄 Starting priority recalculation for all stocks")

    db = SessionLocal()
    try:
        calculator = PriorityCalculator(db)
        result = calculator.recalculate_all_priorities()

        logger.info(f"✅ Priority recalculation complete:")
        logger.info(f"   High priority: {result['high_priority']} stocks")
        logger.info(f"   Medium priority: {result['medium_priority']} stocks")
        logger.info(f"   Low priority: {result['low_priority']} stocks")
        logger.info(f"   Errors: {result['errors']} stocks")

        return result

    except Exception as e:
        logger.error(f"❌ Error in recalculate_all_priorities: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }
    finally:
        db.close()

@celery_app.task
def cleanup_old_news_articles():
    """
    Clean up old news articles (daily at 2 AM)

    Removes news articles older than 14 days to maintain database performance
    """
    from app.db.database import SessionLocal
    from app.models.news import News
    from datetime import datetime, timedelta

    logger.info("🗑️ Starting news article cleanup (14-day retention)")

    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=14)

        # Delete old articles
        deleted_count = db.query(News)\
            .filter(News.published_utc < cutoff_date)\
            .delete()

        db.commit()

        logger.info(f"✅ News cleanup complete: Deleted {deleted_count} articles older than 14 days")

        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error in cleanup_old_news_articles: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }
    finally:
        db.close()

@celery_app.task
def cleanup_old_task_logs():
    """
    Clean up old task execution logs (daily at 2 AM)

    Removes task logs older than 30 days to prevent database bloat

    TODO: Implement after task tracking tables are created
    """
    logger.info("cleanup_old_task_logs - Not yet implemented")
    return {'status': 'placeholder', 'message': 'Task log cleanup not yet implemented'}
