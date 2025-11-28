"""
WSGI config for app project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from modules.core.settings import setup_settings_logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

setup_settings_logging(logger_name="app.settings_loader.wsgi")

application = get_wsgi_application()
