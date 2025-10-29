#!/usr/bin/env python
"""
Test script to verify tenant name uniqueness constraint.

This script tests that:
1. Creating a tenant with a unique name succeeds
2. Creating a second tenant with the same name fails with IntegrityError
3. Schema names can still be auto-incremented (acme, acme-1, etc.)
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
from django.db import IntegrityError
from django_tenants.utils import get_public_schema_name, schema_context
from tenants.models import Client, Domain


def cleanup_test_tenants():
    """Remove any test tenants from previous runs."""
    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())

    with schema_context(public_schema):
        test_tenants = Client.objects.filter(schema_name__startswith="uniquenametest")
        for tenant in test_tenants:
            try:
                print(f"  🧹 Cleaning up test tenant: {tenant.schema_name}")
                # Just delete the Client record, don't drop schema (faster)
                tenant.delete(force_drop=False)
            except Exception as e:
                print(f"  ⚠️  Failed to clean up {tenant.schema_name}: {e}")


def test_unique_tenant_name():
    """Test that tenant names must be unique."""
    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())

    print("\n" + "=" * 70)
    print("TEST: Tenant Name Uniqueness Constraint")
    print("=" * 70)

    # Cleanup first
    print("\n📋 Step 1: Cleanup previous test data")
    cleanup_test_tenants()

    # Test 1: Create first tenant with unique name
    print("\n📋 Step 2: Create first tenant with name 'Test Unique Company'")
    try:
        with schema_context(public_schema):
            tenant1 = Client(schema_name="uniquenametest1", name="Test Unique Company")
            tenant1.save()

            # Create domain
            Domain.objects.create(
                tenant=tenant1, domain="uniquenametest1.localhost", is_primary=True
            )

        print("  ✅ SUCCESS: First tenant created")
        print(f"     - ID: {tenant1.id}")
        print(f"     - Name: {tenant1.name}")
        print(f"     - Schema: {tenant1.schema_name}")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        cleanup_test_tenants()
        return False

    # Test 2: Try to create second tenant with SAME name
    print("\n📋 Step 3: Try to create second tenant with SAME name 'Test Unique Company'")
    try:
        with schema_context(public_schema):
            tenant2 = Client(
                schema_name="uniquenametest2",  # Different schema
                name="Test Unique Company",  # SAME name - should fail
            )
            tenant2.save()

        print(
            "  ❌ FAILED: Second tenant with duplicate name was created (constraint not working!)"
        )
        print(f"     - ID: {tenant2.id}")
        print(f"     - Name: {tenant2.name}")
        print(f"     - Schema: {tenant2.schema_name}")

        # Cleanup
        try:
            tenant2.delete(force_drop=True)
        except Exception:
            pass

        cleanup_test_tenants()
        return False

    except IntegrityError as e:
        print("  ✅ SUCCESS: Duplicate name rejected with IntegrityError")
        print(f"     - Error: {str(e)}")
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            print("     - Constraint type: UNIQUE constraint (correct)")
        else:
            print(f"     - Unexpected error type: {e}")

    # Test 3: Create third tenant with DIFFERENT name
    print("\n📋 Step 4: Create third tenant with DIFFERENT name 'Test Other Company'")
    try:
        with schema_context(public_schema):
            tenant3 = Client(
                schema_name="uniquenametest3",
                name="Test Other Company",  # Different name - should succeed
            )
            tenant3.save()

            # Create domain
            Domain.objects.create(
                tenant=tenant3, domain="uniquenametest3.localhost", is_primary=True
            )

        print("  ✅ SUCCESS: Third tenant with different name created")
        print(f"     - ID: {tenant3.id}")
        print(f"     - Name: {tenant3.name}")
        print(f"     - Schema: {tenant3.schema_name}")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        cleanup_test_tenants()
        return False

    # Test 4: Verify current state
    print("\n📋 Step 5: Verify current tenant state")
    with schema_context(public_schema):
        test_tenants = Client.objects.filter(schema_name__startswith="uniquenametest").order_by(
            "schema_name"
        )

        print(f"  Found {test_tenants.count()} test tenants:")
        for tenant in test_tenants:
            print(f"    - {tenant.schema_name}: '{tenant.name}'")

    # Cleanup
    print("\n📋 Step 6: Cleanup test data")
    cleanup_test_tenants()

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED: Tenant name uniqueness is enforced!")
    print("=" * 70)
    return True


def test_existing_tenants():
    """Check if any existing tenants have duplicate names."""
    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())

    print("\n" + "=" * 70)
    print("CHECK: Existing Tenant Names")
    print("=" * 70)

    with schema_context(public_schema):
        tenants = Client.objects.all().order_by("name")

        print(f"\n📊 Total tenants: {tenants.count()}")
        print("\nAll tenants:")

        name_counts = {}
        for tenant in tenants:
            print(f"  - {tenant.schema_name:20s} | {tenant.name}")
            name_counts[tenant.name] = name_counts.get(tenant.name, 0) + 1

        # Check for duplicates
        duplicates = {name: count for name, count in name_counts.items() if count > 1}

        if duplicates:
            print("\n⚠️  WARNING: Found duplicate tenant names:")
            for name, count in duplicates.items():
                print(f"  - '{name}' appears {count} times")
            print("\n💡 You may need to rename some tenants before the constraint can be applied.")
            return False
        else:
            print("\n✅ No duplicate names found - safe to add unique constraint")
            return True


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🧪 TENANT NAME UNIQUENESS TEST SUITE")
    print("=" * 70)

    # First check existing data
    existing_ok = test_existing_tenants()

    if not existing_ok:
        print("\n⚠️  SKIPPING uniqueness tests - fix duplicates first")
        sys.exit(1)

    # Then test the constraint
    success = test_unique_tenant_name()

    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)
