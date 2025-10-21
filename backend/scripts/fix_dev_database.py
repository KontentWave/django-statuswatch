#!/usr/bin/env python3
"""
Fix development database after test runs.

This script:
1. Removes test_tenant (created by tests)
2. Ensures public tenant exists with localhost domain
3. Creates acme tenant for development with proper domains
"""
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

import django
django.setup()

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.utils import schema_context
from tenants.models import Client, Domain

User = get_user_model()


def main():
    print("=" * 60)
    print("Fixing Development Database")
    print("=" * 60)
    
    # 1. Remove test_tenant if it exists
    test_tenant = Client.objects.filter(schema_name="test_tenant").first()
    if test_tenant:
        print("\n[1/5] Removing test_tenant (created by tests)...")
        # Remove domains first
        Domain.objects.filter(tenant=test_tenant).delete()
        # Drop schema
        with connection.cursor() as cursor:
            cursor.execute(f"DROP SCHEMA IF EXISTS test_tenant CASCADE")
        # Delete tenant record
        test_tenant.delete()
        print("✓ test_tenant removed")
    else:
        print("\n[1/5] test_tenant not found (OK)")
    
    # 2. Ensure public tenant exists
    print("\n[2/5] Ensuring public tenant exists...")
    public_tenant, created = Client.objects.get_or_create(
        schema_name="public",
        defaults={"name": "Public Tenant"}
    )
    if created:
        public_tenant.auto_create_schema = False
        public_tenant.save()
        print("✓ Created public tenant")
    else:
        print("✓ Public tenant exists")
    
    # 3. Ensure localhost domain for public tenant
    print("\n[3/5] Ensuring localhost domain...")
    localhost_domain, created = Domain.objects.get_or_create(
        domain="localhost",
        defaults={"tenant": public_tenant, "is_primary": True}
    )
    if created:
        print("✓ Created localhost → public")
    else:
        print(f"✓ localhost → {localhost_domain.tenant.schema_name}")
    
    # 4. Create acme tenant for development
    print("\n[4/5] Creating acme tenant...")
    acme_tenant = Client.objects.filter(schema_name="acme").first()
    if acme_tenant is None:
        acme_tenant = Client(
            schema_name="acme",
            name="Acme Corporation",
            paid_until="2099-12-31",
            on_trial=False,
        )
        acme_tenant.save()
        print("✓ Created acme tenant (migrations ran automatically)")
        
        # Create domains for acme
        Domain.objects.create(
            tenant=acme_tenant,
            domain="acme.localhost",
            is_primary=True
        )
        print("✓ Created acme.localhost → acme (primary)")
        
        Domain.objects.create(
            tenant=acme_tenant,
            domain="acme.django-01.local",
            is_primary=False
        )
        print("✓ Created acme.django-01.local → acme")
    else:
        print("✓ acme tenant already exists")
        # Ensure domains exist
        Domain.objects.get_or_create(
            domain="acme.localhost",
            defaults={"tenant": acme_tenant, "is_primary": True}
        )
        Domain.objects.get_or_create(
            domain="acme.django-01.local",
            defaults={"tenant": acme_tenant, "is_primary": False}
        )
        print("✓ acme domains verified")
    
    # 5. Create test user in acme tenant
    print("\n[5/5] Creating test user in acme tenant...")
    with schema_context("acme"):
        user, created = User.objects.get_or_create(
            username="jwt",
            defaults={"email": "jwt@example.com", "is_active": True}
        )
        user.set_password("JwtP@ss123456")
        user.save()
        if created:
            print("✓ Created user 'jwt' in acme tenant")
        else:
            print("✓ Updated user 'jwt' in acme tenant")
    
    print("\n" + "=" * 60)
    print("✅ Development database fixed!")
    print("=" * 60)
    print("\nCurrent setup:")
    print(f"  Tenants: {list(Client.objects.values_list('schema_name', flat=True))}")
    print(f"  Domains: {list(Domain.objects.values_list('domain', 'tenant__schema_name'))}")
    print("\nYou can now:")
    print("  1. Start backend: python manage.py runserver")
    print("  2. Access at: http://acme.localhost:8000")
    print("  3. Login with: jwt / JwtP@ss123456")
    print()


if __name__ == "__main__":
    main()
