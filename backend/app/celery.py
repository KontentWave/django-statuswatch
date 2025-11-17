import os

from celery import Celery
from modules.core.settings import setup_settings_logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

setup_settings_logging(logger_name="app.settings_loader.celery")

celery_app = Celery("app")
celery_app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover tasks from all installed Django apps
# Use lambda to ensure INSTALLED_APPS is loaded after Django setup
celery_app.autodiscover_tasks(
    lambda: __import__("django.conf", fromlist=["settings"]).settings.INSTALLED_APPS
)
