#!/bin/sh

# Set the maximum memory limit to 300 MB
ulimit -v $((400 * 1024))

echo "STARTING HTTP SERVER..."
gunicorn main.wsgi:application -t 1800 --bind :5000 --daemon

echo "STARTING CELERY WORKER WITH MEMORY LIMIT..."
celery -A main worker --loglevel=INFO --time-limit=0 --concurrency=1
