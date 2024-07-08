#!/bin/sh
python3 manage.py collectstatic --noinput
python3 manage.py wait_for_db
python3 manage.py makemigrations
python3 manage.py migrate --noinput
python3 manage.py initadmin
celery -A main worker --loglevel=INFO --time-limit=300
