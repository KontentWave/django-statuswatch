#!/usr/bin/env python
"""
Cleanup script for leftover test tenant schemas.
Handles the monitors_endpoint table issue by using raw SQL DROP SCHEMA CASCADE.
Date: 2025-01-29 20:00
"""
import os
import sys

import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

from django.db import connection
from tenants.models import Client


def cleanup_test_schemas():
    """Clean up leftover test tenant schemas using SQL CASCADE."""
    test_schemas = ["uniquenametest1", "uniquenametest3"]

    print("=" * 70)
    print("CLEANUP: Leftover Test Tenant Schemas")
    print("=" * 70)

    with connection.cursor() as cursor:
        # Drop schemas
        print("\n📋 Step 1: Drop schemas with CASCADE")
        for schema in test_schemas:
            print(f"  Dropping schema: {schema}")
            try:
                cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE;")
                print(f"    ✓ Dropped schema {schema}")
            except Exception as e:
                print(f"    ⚠️  Error dropping {schema}: {e}")

        # Delete Client records
        print("\n📋 Step 2: Delete Client records")
        try:
            # Use raw SQL to avoid triggering migrations on non-existent schemas
            cursor.execute(
                """
                DELETE FROM tenants_client
                WHERE schema_name IN ('uniquenametest1', 'uniquenametest3');
            """
            )
            rows = cursor.rowcount
            print(f"  ✓ Deleted {rows} Client records")
        except Exception as e:
            print(f"  ⚠️  Error deleting Client records: {e}")

        # Clean up orphaned domains
        print("\n📋 Step 3: Clean up orphaned domains")
        try:
            cursor.execute(
                """
                DELETE FROM tenants_domain
                WHERE tenant_id NOT IN (SELECT id FROM tenants_client);
            """
            )
            rows = cursor.rowcount
            print(f"  ✓ Cleaned up {rows} orphaned domains")
        except Exception as e:
            print(f"  ⚠️  Error cleaning domains: {e}")

        # Verify
        print("\n📋 Step 4: Verify cleanup")
        remaining = Client.objects.filter(schema_name__startswith="uniquenametest")
        if remaining.exists():
            print(f"  ⚠️  Still have {remaining.count()} test tenants:")
            for t in remaining:
                print(f"    - {t.schema_name}: {t.name}")
        else:
            print("  ✓ All test tenants cleaned up successfully")

    print("\n" + "=" * 70)
    print("✅ Cleanup complete!")
    print("=" * 70)


if __name__ == "__main__":
    cleanup_test_schemas()
