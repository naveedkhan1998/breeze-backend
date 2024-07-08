#!/bin/sh


# echo "STARTING HTTP SERVER..."
# python http_server.py &

echo "STARTING CELERY WORKER WITH MEMORY LIMIT..."
python3 start_celery.py
