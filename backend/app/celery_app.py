"""
Celery application configuration for StockAnalyzer automatic data fetching

This module configures Celery for background task processing including:
- Price data fetching (hourly for high-priority stocks)
- News and metadata fetching
- Pattern detection
- Priority recalculation
"""
from celery import Celery
from celery.schedules import crontab
import os

# Create Celery app
celery_app = Celery(
    'stockanalyzer',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    include=[
        'app.tasks.fetcher_tasks',
        'app.tasks.processor_tasks',
        'app.tasks.maintenance_tasks',
        'app.tasks.analysis_tasks',
    ]
)

# ============================================
# CELERY CONFIGURATION
# ============================================
celery_app.conf.update(
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    # Timezone (US market timezone)
    timezone='America/New_York',
    enable_utc=True,

    # Task routing (different queues for different task types)
    task_routes={
        'app.tasks.fetcher_tasks.*': {'queue': 'fetcher'},
        'app.tasks.processor_tasks.*': {'queue': 'processor'},
        'app.tasks.maintenance_tasks.*': {'queue': 'maintenance'},
        # analysis_tasks -> processor (CPU-bound). Without this, analysis tasks fall
        # into the default 'celery' queue, which the worker does NOT consume (it only
        # listens on fetcher/processor/maintenance), so scheduled + batch analysis
        # never executed — the whole analysis pipeline was silently dead via Celery.
        'app.tasks.analysis_tasks.*': {'queue': 'processor'},
    },

    # Priority system (0-10, higher = more urgent)
    task_queue_max_priority=10,
    task_default_priority=5,

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time (better for rate limiting)
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (prevent memory leaks)

    # Task execution
    task_acks_late=True,  # Acknowledge task after completion, not before
    task_reject_on_worker_lost=True,  # Re-queue if worker dies

    # Task time limits — safety net so a runaway task can't hang a worker forever.
    # 30-min hard cap is well above any legitimate batch (the medium-priority sweep
    # of ~189 stocks takes ~10 min) but catches truly stuck tasks.
    task_soft_time_limit=1800,
    task_time_limit=1860,

    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,

    # Result backend settings
    result_expires=3600,  # Task results expire after 1 hour

    # H2 (audit): the task_annotations rate-limits referenced non-existent task
    # names (fetch_stock_prices / fetch_stock_news / fetch_stock_metadata) so they
    # never applied — dead config. Removed. Polygon's Stocks Starter tier is
    # effectively unlimited, so per-task rate limiting isn't needed; if a real
    # limit is wanted later, point keys at the actual tasks
    # (fetch_high/medium/low_priority_stocks, fetch_*_priority_news).
)

# ============================================
# CELERY BEAT SCHEDULE (Periodic Tasks)
# ============================================
celery_app.conf.beat_schedule = {
    # ────────────────────────────────────────
    # PRICE DATA FETCHING
    # ────────────────────────────────────────

    # High-priority stocks: Every hour during market hours (9 AM - 4 PM ET)
    'fetch-high-priority-stocks-hourly': {
        'task': 'app.tasks.fetcher_tasks.fetch_high_priority_stocks',
        'schedule': crontab(minute=0, hour='9-16'),  # Every hour, 9 AM - 4 PM
        'options': {'queue': 'fetcher', 'priority': 10}
    },

    # Medium-priority stocks: Every 4 hours
    'fetch-medium-priority-stocks-4hourly': {
        'task': 'app.tasks.fetcher_tasks.fetch_medium_priority_stocks',
        'schedule': crontab(minute=0, hour='*/4'),  # 12 AM, 4 AM, 8 AM, 12 PM, 4 PM, 8 PM
        'options': {'queue': 'fetcher', 'priority': 5}
    },

    # Low-priority stocks: Daily at 5 PM (after market close)
    'fetch-low-priority-stocks-daily': {
        'task': 'app.tasks.fetcher_tasks.fetch_low_priority_stocks',
        'schedule': crontab(minute=0, hour=17),  # 5:00 PM ET
        'options': {'queue': 'fetcher', 'priority': 3}
    },

    # ────────────────────────────────────────
    # NEWS & SENTIMENT
    # ────────────────────────────────────────

    # High-priority news: Every 2 hours
    'fetch-high-priority-news': {
        'task': 'app.tasks.fetcher_tasks.fetch_high_priority_news',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
        'options': {'queue': 'fetcher', 'priority': 7}
    },

    # Medium-priority news: Every 8 hours
    'fetch-medium-priority-news': {
        'task': 'app.tasks.fetcher_tasks.fetch_medium_priority_news',
        'schedule': crontab(minute=0, hour='*/8'),  # 12 AM, 8 AM, 4 PM
        'options': {'queue': 'fetcher', 'priority': 4}
    },

    # ────────────────────────────────────────
    # METADATA (Weekly batches)
    # ────────────────────────────────────────

    # Dividends: Weekly on Sunday
    'fetch-dividends-weekly': {
        'task': 'app.tasks.fetcher_tasks.fetch_dividends_batch',
        'schedule': crontab(minute=0, hour=0, day_of_week=0),  # Sunday 12:00 AM
        'options': {'queue': 'fetcher', 'priority': 3}
    },

    # Splits: Weekly on Monday
    'fetch-splits-weekly': {
        'task': 'app.tasks.fetcher_tasks.fetch_splits_batch',
        'schedule': crontab(minute=0, hour=0, day_of_week=1),  # Monday 12:00 AM
        'options': {'queue': 'fetcher', 'priority': 3}
    },

    # Short Interest: Weekly on Tuesday
    'fetch-short-interest-weekly': {
        'task': 'app.tasks.fetcher_tasks.fetch_short_interest_batch',
        'schedule': crontab(minute=0, hour=0, day_of_week=2),  # Tuesday 12:00 AM
        'options': {'queue': 'fetcher', 'priority': 3}
    },

    # ────────────────────────────────────────
    # MARKET STATUS
    # ────────────────────────────────────────

    # Market status: Every hour (lightweight, global check)
    'check-market-status-hourly': {
        'task': 'app.tasks.fetcher_tasks.fetch_market_status',
        'schedule': crontab(minute=0),  # Every hour on the hour
        'options': {'queue': 'fetcher', 'priority': 8}
    },

    # ────────────────────────────────────────
    # PATTERN DETECTION
    # ────────────────────────────────────────

    # High-priority pattern detection: 15 minutes after hourly price fetch
    'detect-patterns-high-priority': {
        'task': 'app.tasks.processor_tasks.detect_patterns_high_priority',
        'schedule': crontab(minute=15, hour='9-16'),  # 9:15 AM - 4:15 PM (15 min after price)
        'options': {'queue': 'processor', 'priority': 7}
    },

    # Medium-priority pattern detection: After 4-hour price fetch
    'detect-patterns-medium-priority': {
        'task': 'app.tasks.processor_tasks.detect_patterns_medium_priority',
        'schedule': crontab(minute=30, hour='*/4'),  # 30 min after price fetch
        'options': {'queue': 'processor', 'priority': 5}
    },

    # Low-priority pattern detection: Daily at 6 PM
    'detect-patterns-low-priority': {
        'task': 'app.tasks.processor_tasks.detect_patterns_low_priority',
        'schedule': crontab(minute=0, hour=18),  # 6:00 PM ET
        'options': {'queue': 'processor', 'priority': 3}
    },

    # ────────────────────────────────────────
    # MAINTENANCE TASKS
    # ────────────────────────────────────────

    # Recalculate stock priorities: Daily at 3 AM
    'recalculate-priorities-daily': {
        'task': 'app.tasks.maintenance_tasks.recalculate_all_priorities',
        'schedule': crontab(minute=0, hour=3),  # 3:00 AM ET
        'options': {'queue': 'maintenance', 'priority': 9}
    },

    # Cleanup old news articles: Daily at 2 AM
    'cleanup-old-news-daily': {
        'task': 'app.tasks.maintenance_tasks.cleanup_old_news_articles',
        'schedule': crontab(minute=0, hour=2),  # 2:00 AM ET (14-day retention)
        'options': {'queue': 'maintenance', 'priority': 2}
    },

    # Cleanup old task logs: Daily at 2 AM
    'cleanup-old-tasks-daily': {
        'task': 'app.tasks.maintenance_tasks.cleanup_old_task_logs',
        'schedule': crontab(minute=30, hour=2),  # 2:30 AM ET (after news cleanup)
        'options': {'queue': 'maintenance', 'priority': 1}
    },
}

# ============================================
# CELERY SIGNALS (for monitoring/logging)
# ============================================
from celery.signals import task_prerun, task_postrun, task_failure, task_retry

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Log task start"""
    print(f"[TASK START] {task.name} [{task_id}]")

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, retval=None, **extra):
    """Log task completion"""
    print(f"[TASK SUCCESS] {task.name} [{task_id}]")

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, **extra):
    """Log task failure"""
    print(f"[TASK FAILURE] {sender.name} [{task_id}] - Error: {exception}")

@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, **extra):
    """Log task retry"""
    print(f"[TASK RETRY] {sender.name} [{task_id}] - Reason: {reason}")

# ============================================
# DEBUG TASK (for testing Celery setup)
# ============================================
@celery_app.task(bind=True)
def debug_task(self):
    """
    Debug task to verify Celery is working

    Usage:
        from app.celery_app import debug_task
        result = debug_task.delay()
        print(result.get())
    """
    print(f'Request: {self.request!r}')
    return {
        'status': 'ok',
        'task_id': self.request.id,
        'message': 'Celery is working!'
    }
