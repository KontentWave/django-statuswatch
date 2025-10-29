#!/usr/bin/env python
"""
Manual cleanup of duplicate test tenants
Deletes tenant records from PUBLIC schema only (doesn't touch tenant schemas)
"""

import os
import sys

import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

# ruff: noqa: E402
from django.conf import settings
from django.db import connection
from django_tenants.utils import get_public_schema_name, schema_context
from tenants.models import Client


def manual_delete_duplicates():
    """Manually delete duplicate test tenants using raw SQL."""
    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())

    print("=" * 70)
    print("MANUAL CLEANUP: Duplicate Test Tenants")
    print("=" * 70)
    print()

    # Step 1: Show duplicates
    print("📋 Step 1: Finding duplicate test tenants")
    print("-" * 70)

    with schema_context(public_schema):
        dupes = Client.objects.filter(name="Test Unique Company").order_by("id")

        if not dupes.exists():
            print("✅ No duplicates found - nothing to clean")
            return True

        print(f"Found {dupes.count()} duplicate tenants:")
        for t in dupes:
            print(f'  - ID={t.id}, schema={t.schema_name}, name="{t.name}"')
        print()

    # Step 2: Delete using raw SQL (bypass Django ORM issues)
    print("📋 Step 2: Deleting duplicate tenants (raw SQL)")
    print("-" * 70)

    with connection.cursor() as cursor:
        # Delete domains first (foreign key)
        cursor.execute(
            """
            DELETE FROM public.tenants_domain
            WHERE tenant_id IN (
                SELECT id FROM public.tenants_client
                WHERE name = 'Test Unique Company'
            );
        """
        )
        domains_deleted = cursor.rowcount
        print(f"  ✅ Deleted {domains_deleted} domain records")

        # Delete tenant records
        cursor.execute(
            """
            DELETE FROM public.tenants_client
            WHERE name = 'Test Unique Company';
        """
        )
        tenants_deleted = cursor.rowcount
        print(f"  ✅ Deleted {tenants_deleted} tenant records")

    print()

    # Step 3: Verify
    print("📋 Step 3: Verifying duplicates removed")
    print("-" * 70)

    with schema_context(public_schema):
        remaining = Client.objects.filter(name="Test Unique Company").count()

        if remaining == 0:
            print("  ✅ No duplicates remain - cleanup successful!")
            print()
            return True
        else:
            print(f"  ❌ Still {remaining} duplicates exist")
            print()
            return False


if __name__ == "__main__":
    print()
    success = manual_delete_duplicates()

    if success:
        print("=" * 70)
        print("✅ CLEANUP COMPLETE")
        print("=" * 70)
        print()
        print("Next steps:")
        print("  1. Run: python manage.py migrate tenants")
        print("  2. Run: python tests/test_tenant_uniqueness.py")
        print()
        sys.exit(0)
    else:
        print("=" * 70)
        print("❌ CLEANUP FAILED")
        print("=" * 70)
        print()
        sys.exit(1)
