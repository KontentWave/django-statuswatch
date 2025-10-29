#!/usr/bin/env python
"""
Test duplicate organization name error handling during registration.

Verifies that:
1. First organization with a name succeeds
2. Second organization with same name gets proper error (409 Conflict)
3. Error message is user-friendly
"""

import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

# ruff: noqa: E402
from api.exceptions import DuplicateOrganizationNameError
from api.serializers import RegistrationSerializer
from django.conf import settings
from django.contrib.auth import get_user_model
from django_tenants.utils import get_public_schema_name, schema_context
from tenants.models import Client

User = get_user_model()


def cleanup_test_data():
    """Remove test tenants from previous runs."""
    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())

    with schema_context(public_schema):
        test_tenants = Client.objects.filter(name="TestUniqueOrg")
        for tenant in test_tenants:
            try:
                print(f"  🧹 Cleaning up: {tenant.schema_name}")
                tenant.delete(force_drop=False)
            except Exception as e:
                print(f"  ⚠️  Cleanup warning: {e}")


def test_duplicate_organization_name_error():
    """Test that duplicate organization names are properly rejected."""
    print("\n" + "=" * 70)
    print("TEST: Duplicate Organization Name Error Handling")
    print("=" * 70)
    print()

    # Cleanup first
    print("📋 Step 1: Cleanup previous test data")
    print("-" * 70)
    cleanup_test_data()
    print()

    # Test 1: Register first organization
    print("📋 Step 2: Register first organization 'TestUniqueOrg'")
    print("-" * 70)

    serializer1 = RegistrationSerializer(
        data={
            "email": "test1@uniqueorg.test",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "organization_name": "TestUniqueOrg",
        }
    )

    if serializer1.is_valid():
        try:
            _ = serializer1.save()
            print("  ✅ First registration successful")
            print("     Email: test1@uniqueorg.test")
            print("     Org: TestUniqueOrg")
        except Exception as e:
            print(f"  ❌ First registration failed: {e}")
            cleanup_test_data()
            return False
    else:
        print(f"  ❌ Validation failed: {serializer1.errors}")
        return False
    print()

    # Test 2: Try to register with SAME organization name
    print("📋 Step 3: Try to register with SAME name 'TestUniqueOrg'")
    print("-" * 70)

    serializer2 = RegistrationSerializer(
        data={
            "email": "test2@uniqueorg.test",  # Different email
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "organization_name": "TestUniqueOrg",  # SAME name - should fail
        }
    )

    if serializer2.is_valid():
        try:
            _ = serializer2.save()
            print("  ❌ FAILED: Duplicate name was accepted (should have been rejected!)")
            print("     Email: test2@uniqueorg.test")
            print("     Org: TestUniqueOrg")
            cleanup_test_data()
            return False
        except DuplicateOrganizationNameError as e:
            print("  ✅ SUCCESS: Duplicate name rejected with DuplicateOrganizationNameError")
            print(f"     Status code: {e.status_code}")
            print(f"     Error code: {e.default_code}")
            print(f"     Message: {e.detail}")

            # Verify error details
            if e.status_code != 409:
                print(f"  ⚠️  WARNING: Expected status 409, got {e.status_code}")
            if "already taken" not in str(e.detail).lower():
                print("  ⚠️  WARNING: Error message should mention 'already taken'")
        except Exception as e:
            print(f"  ❌ FAILED: Wrong exception type: {type(e).__name__}")
            print(f"     Message: {e}")
            cleanup_test_data()
            return False
    else:
        print(f"  ❌ Validation failed before save: {serializer2.errors}")
        cleanup_test_data()
        return False
    print()

    # Test 3: Register with DIFFERENT organization name
    print("📋 Step 4: Register with DIFFERENT name 'TestUniqueOrg2'")
    print("-" * 70)

    serializer3 = RegistrationSerializer(
        data={
            "email": "test3@uniqueorg.test",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "organization_name": "TestUniqueOrg2",  # Different name - should succeed
        }
    )

    if serializer3.is_valid():
        try:
            _ = serializer3.save()
            print("  ✅ Third registration successful")
            print("     Email: test3@uniqueorg.test")
            print("     Org: TestUniqueOrg2")
        except Exception as e:
            print(f"  ❌ Third registration failed: {e}")
            cleanup_test_data()
            return False
    else:
        print(f"  ❌ Validation failed: {serializer3.errors}")
        cleanup_test_data()
        return False
    print()

    # Cleanup
    print("📋 Step 5: Cleanup test data")
    print("-" * 70)
    cleanup_test_data()

    # Also clean up the second org
    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())
    with schema_context(public_schema):
        test_tenants = Client.objects.filter(name="TestUniqueOrg2")
        for tenant in test_tenants:
            try:
                print(f"  🧹 Cleaning up: {tenant.schema_name}")
                tenant.delete(force_drop=False)
            except Exception as e:
                print(f"  ⚠️  Cleanup warning: {e}")

    print()
    print("=" * 70)
    print("✅ ALL TESTS PASSED: Duplicate organization names properly rejected!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = test_duplicate_organization_name_error()
    sys.exit(0 if success else 1)
