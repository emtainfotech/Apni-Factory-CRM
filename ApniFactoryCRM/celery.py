import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ApniFactoryCRM.settings')

app = Celery('ApniFactoryCRM')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


from celery.schedules import crontab

app.conf.beat_schedule = {
    'send-morning-dashboard-report-6am': {
        'task': 'core.tasks.send_morning_dashboard_report',
        'schedule': crontab(hour=6, minute=0),
    },
    'send-evening-dashboard-report-8pm': {
        'task': 'core.tasks.send_evening_dashboard_report',
        'schedule': crontab(hour=20, minute=0),
    },
}
app.conf.timezone = 'Asia/Kolkata'
