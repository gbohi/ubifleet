# Charger Celery au démarrage de Django pour que les tâches @shared_task soient enregistrées
from .celery import app as celery_app

__all__ = ('celery_app',)
