"""UbiFleet — Celery Configuration"""

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('ubifleet')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Tâches périodiques (Celery Beat)
app.conf.beat_schedule = {
    'check-all-alerts-daily': {
        'task': 'apps.alertes.tasks.run_all_checks',
        'schedule': crontab(hour=7, minute=0),
    },
    'check-assurances-monday': {
        'task': 'apps.alertes.tasks.check_assurance_alerts',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),
    },
}
