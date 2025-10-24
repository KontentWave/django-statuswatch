#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Ensure the project root (which contains the "app" package) is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context


def main():
    U = get_user_model()
    with schema_context("acme"):
        email = "jwt@example.com"
        u, created = U.objects.get_or_create(
            username=email,
            defaults={"email": email, "is_active": True},
        )
        u.set_password("JwtP@ss123456")  # Meets complexity requirements
        u.save()
        print("OK:", "created" if created else "updated", "user 'jwt' in acme")


if __name__ == "__main__":
    main()
