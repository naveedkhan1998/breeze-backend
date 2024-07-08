#!/bin/sh


# Set the maximum memory limit to 300 MB
ulimit -v $((300 * 1024))

echo "STARTING HTTP SERVER..."
python3 http_server.py 

echo "STARTING CELERY WORKER WITH MEMORY LIMIT..."
celery -A main worker --loglevel=INFO --time-limit=0 --concurrency=1
