#!/bin/sh

# Increase the maximum number of processes available
ulimit -u 4096

echo "STARTING HTTP SERVER..."
python http_server.py &

echo "STARTING CELERY WORKER WITH MEMORY LIMIT..."
python start_celery.py
