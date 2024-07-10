import os
from datetime import timedelta

from celery import Celery

# Set the default Django settings module for the 'celery' program.
from celery.schedules import crontab
from datetime import timedelta
from main import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

app = Celery('main', include=[])

app.conf.beat_schedule = {
    'candle_making_job':{
        'task':'candle_maker',
        'schedule':1,
        'relative':True
    },
    'websocket_connect':{
        'task':'websocket_start',
        'schedule':crontab(minute=30, hour=3, day_of_week='1-5'),
        'relative':True
    },
}



CELERY_TIMEZONE = 'Asia/Kolkata'
# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.conf.broker_connection_retry_on_startup = True
app.config_from_object('django.conf:settings')
#CELERY_BROKER_URL = 'amqp://guest:guest@rabbitmq3:5672/'
# Load task modules from all registered Django apps.
app.autodiscover_tasks(lambda:settings.INSTALLED_APPS)
BROKER_CONNECTION_RETRY = True
BROKER_CONNECTION_MAX_RETRIES = 0
BROKER_CONNECTION_TIMEOUT = 10120
