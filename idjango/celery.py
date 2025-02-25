import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'idjango.settings')

app = Celery('idjango')
app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
