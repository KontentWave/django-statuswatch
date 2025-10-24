import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
celery_app = Celery("app")
celery_app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover tasks from all installed Django apps
# Use lambda to ensure INSTALLED_APPS is loaded after Django setup
celery_app.autodiscover_tasks(
    lambda: __import__("django.conf", fromlist=["settings"]).settings.INSTALLED_APPS
)
