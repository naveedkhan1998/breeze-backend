#!/bin/sh

echo "STARTING HTTP SERVER..."
python3 http_server.py &

echo "STARTING CELERY WORKER..."
celery -A main worker --loglevel=INFO --time-limit=0
