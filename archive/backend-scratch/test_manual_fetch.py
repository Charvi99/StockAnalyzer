"""Manually test fetcher task by sending it directly to the queue"""
import redis
import json

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=False)

# Create a Celery task message
task_id = 'test-manual-fetch-001'
task_message = {
    'task': 'app.tasks.fetcher_tasks.fetch_high_priority_stocks',
    'id': task_id,
    'args': [],
    'kwargs': {},
    'retries': 0
}

# Encode as JSON and wrap in Celery format
body = json.dumps(task_message).encode('utf-8')
headers = {}
properties = {
    'body_encoding': 'base64',
    'delivery_info': {'exchange': 'fetcher', 'routing_key': 'fetcher'},
    'delivery_mode': 2,
    'delivery_tag': task_id
}

# Create the full message
message = [
    body,
    headers,
    properties,
    {}
]

# Push to fetcher queue
queue_name = 'fetcher'
r.lpush(queue_name, json.dumps(message))

print(f"✅ Task pushed to '{queue_name}' queue")
print(f"Task ID: {task_id}")
print(f"Check worker logs for execution")
