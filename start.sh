#!/bin/sh

echo "STARTING GUNICORN SERVER..."
gunicorn main.wsgi:application -t 1800 --bind :5000 --daemon
celery -A main worker --loglevel=INFO --time-limit=0
