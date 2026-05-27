#!/bin/bash
# Start Celery worker in background
celery -A workers.celery_app worker \
  --loglevel=info \
  -Q high_priority,medium_priority,low_priority \
  --detach \
  --logfile=/tmp/celery.log \
  --pidfile=/tmp/celery.pid

# Start FastAPI (foreground — Render needs this)
uvicorn api.main:app \
  --host 0.0.0.0 \
  --port $PORT \
  --workers 1
