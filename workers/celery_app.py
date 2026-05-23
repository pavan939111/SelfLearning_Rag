import os
from celery import Celery
from kombu import Queue, Exchange
from config import get_config

config = get_config()

# Ensure REDIS_URL uses SSL (rediss://) and injects password for Upstash
redis_url = config.redis_url
password = config.redis_password

if redis_url and 'upstash' in redis_url.lower():
    # Inject password if not already present
    if password and f":{password}@" not in redis_url:
        if redis_url.startswith("redis://"):
            redis_url = redis_url.replace("redis://", f"redis://default:{password}@", 1)
        elif redis_url.startswith("rediss://"):
            redis_url = redis_url.replace("rediss://", f"rediss://default:{password}@", 1)
            
    if redis_url.startswith('redis://'):
        redis_url = redis_url.replace('redis://', 'rediss://', 1)
        
    if 'ssl_cert_reqs' not in redis_url:
        if '?' not in redis_url:
            redis_url += '?ssl_cert_reqs=CERT_NONE'
        else:
            redis_url += '&ssl_cert_reqs=CERT_NONE'

celery_app = Celery(
    "failurerag",
    broker=redis_url,
    backend=redis_url
)

# Configure Celery
celery_app.conf.update(
    broker_use_ssl={'ssl_cert_reqs': None},
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    worker_concurrency=2,
    broker_connection_retry_on_startup=True,
    
    # Define three priority queues
    task_queues=(
        Queue('high_priority', Exchange('high_priority'), routing_key='high_priority'),
        Queue('medium_priority', Exchange('medium_priority'), routing_key='medium_priority'),
        Queue('low_priority', Exchange('low_priority'), routing_key='low_priority'),
    ),
    
    # Task routing
    task_routes={
        'repair.*': {'queue': 'high_priority'},
        'ingest.*': {'queue': 'medium_priority'},
        'analysis.*': {'queue': 'low_priority'},
    }
)

@celery_app.task(name="test.ping")
def ping():
    return "pong"
