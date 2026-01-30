"""Manually trigger hourly high-priority fetch to debug"""
from app.celery_app import celery_app

# Trigger the fetch task manually
result = celery_app.send_task('app.tasks.fetcher_tasks.fetch_high_priority_stocks')
print(f"Task triggered: {result.id}")
print(f"Task state: {result.state}")
print(f"Waiting for result...")

try:
    # Wait up to 60 seconds for the task to complete
    output = result.get(timeout=60)
    print(f"Task completed successfully!")
    print(f"Result: {output}")
except Exception as e:
    print(f"Task failed or timed out: {e}")
