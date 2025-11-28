"""
ASGI config for app project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from modules.core.settings import setup_settings_logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

setup_settings_logging(logger_name="app.settings_loader.asgi")

application = get_asgi_application()
