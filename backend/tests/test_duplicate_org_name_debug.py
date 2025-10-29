#!/usr/bin/env python
"""
Debug version of duplicate organization name test with extensive logging.

This version logs everything to help diagnose cleanup issues.
"""

import json
import os
import sys
from datetime import datetime

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

# ruff: noqa: E402
from api.exceptions import DuplicateOrganizationNameError
from api.serializers import RegistrationSerializer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.utils import get_public_schema_name, schema_context
from tenants.models import Client

User = get_user_model()

# Create log file
LOG_FILE = "backend/logs/test_duplicate_org_debug.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


def log(message, level="INFO"):
    """Log message to both console and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)
    with open(LOG_FILE, "a") as f:
        f.write(log_entry + "\n")


def get_all_schemas():
    """Get list of all schemas in database."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            ORDER BY schema_name
        """
        )
        return [row[0] for row in cursor.fetchall()]


def get_all_tenants():
    """Get list of all tenant records."""
    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())
    with schema_context(public_schema):
        return list(Client.objects.all().values("id", "schema_name", "name"))


def cleanup_test_data():
    """Remove test tenants from previous runs with extensive logging."""
    log("=" * 70, "INFO")
    log("CLEANUP: Starting test data cleanup", "INFO")
    log("=" * 70, "INFO")

    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())
    log(f"Public schema: {public_schema}", "DEBUG")

    # Log database state BEFORE cleanup
    log("Database state BEFORE cleanup:", "INFO")
    all_tenants = get_all_tenants()
    log(f"  Total tenants: {len(all_tenants)}", "INFO")
    for t in all_tenants:
        log(f"    - {t['schema_name']:20s} | {t['name']}", "DEBUG")

    all_schemas = get_all_schemas()
    log(f"  Total schemas: {len(all_schemas)}", "INFO")
    test_schemas = [s for s in all_schemas if s.startswith(("testuniqueorg", "uniquenametest"))]
    log(f"  Test schemas: {len(test_schemas)}", "INFO")
    for s in test_schemas:
        log(f"    - {s}", "DEBUG")

    with schema_context(public_schema):
        # Find test tenants
        test_tenants = Client.objects.filter(
            name__in=["TestUniqueOrg", "TestUniqueOrg2"]
        ) | Client.objects.filter(schema_name__startswith="testuniqueorg")

        test_tenant_list = list(test_tenants.values("id", "schema_name", "name"))
        log(f"Found {len(test_tenant_list)} test tenants to delete", "INFO")

        for tenant_data in test_tenant_list:
            log(
                f"  - {tenant_data['schema_name']} (id={tenant_data['id']}, name={tenant_data['name']})",
                "DEBUG",
            )

        # Delete each tenant
        for tenant in test_tenants:
            log(f"Deleting tenant: {tenant.schema_name} (id={tenant.id})", "INFO")

            # Check if schema exists before delete
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                    [tenant.schema_name],
                )
                schema_exists_before = cursor.fetchone() is not None
                log(f"  Schema exists before delete: {schema_exists_before}", "DEBUG")

            # Try delete with force_drop=False first
            try:
                log("  Attempting delete with force_drop=False...", "DEBUG")
                tenant.delete(force_drop=False)
                log("  ✅ Tenant record deleted (force_drop=False)", "INFO")
            except Exception as e:
                log(f"  ❌ Delete failed (force_drop=False): {type(e).__name__}: {e}", "ERROR")
                # Try with force_drop=True
                try:
                    log("  Attempting delete with force_drop=True...", "DEBUG")
                    tenant.delete(force_drop=True)
                    log("  ✅ Tenant record deleted (force_drop=True)", "INFO")
                except Exception as e2:
                    log(f"  ❌ Delete failed (force_drop=True): {type(e2).__name__}: {e2}", "ERROR")

            # Check if schema exists after delete
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                    [tenant.schema_name],
                )
                schema_exists_after = cursor.fetchone() is not None
                log(f"  Schema exists after delete: {schema_exists_after}", "DEBUG")

                if schema_exists_before and schema_exists_after:
                    log("  ⚠️  Schema NOT dropped - attempting manual DROP SCHEMA", "WARNING")
                    try:
                        cursor.execute(f"DROP SCHEMA IF EXISTS {tenant.schema_name} CASCADE")
                        log(f"  ✅ Manually dropped schema {tenant.schema_name}", "INFO")
                    except Exception as e:
                        log(f"  ❌ Manual schema drop failed: {e}", "ERROR")

    # Log database state AFTER cleanup
    log("Database state AFTER cleanup:", "INFO")
    all_tenants = get_all_tenants()
    log(f"  Total tenants: {len(all_tenants)}", "INFO")
    for t in all_tenants:
        log(f"    - {t['schema_name']:20s} | {t['name']}", "DEBUG")

    all_schemas = get_all_schemas()
    test_schemas = [s for s in all_schemas if s.startswith(("testuniqueorg", "uniquenametest"))]
    log(f"  Test schemas remaining: {len(test_schemas)}", "INFO")
    for s in test_schemas:
        log(f"    - {s}", "WARNING")

    log("CLEANUP: Complete", "INFO")
    log("=" * 70, "INFO")


def main():
    """Main test function with detailed logging."""
    log("\n" + "=" * 70, "INFO")
    log("TEST: Duplicate Organization Name Error Handling (DEBUG VERSION)", "INFO")
    log("=" * 70, "INFO")
    log(f"Log file: {os.path.abspath(LOG_FILE)}", "INFO")
    log("", "INFO")

    # Cleanup first
    log("📋 Step 1: Cleanup previous test data", "INFO")
    cleanup_test_data()
    log("", "INFO")

    # Now run the actual test
    log("📋 Step 2: Create first organization", "INFO")
    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())

    with schema_context(public_schema):
        data1 = {
            "email": "user1@test.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "organization_name": "TestUniqueOrg",
        }
        log(f"  Data: {json.dumps(data1, indent=2)}", "DEBUG")

        serializer1 = RegistrationSerializer(data=data1)
        if serializer1.is_valid():
            user1, tenant1 = serializer1.save()
            log(f"  ✅ First org created: {tenant1.name} (schema: {tenant1.schema_name})", "INFO")
        else:
            log(f"  ❌ First org creation failed: {serializer1.errors}", "ERROR")
            return False

    log("", "INFO")
    log("📋 Step 3: Attempt to create duplicate organization", "INFO")

    with schema_context(public_schema):
        data2 = {
            "email": "user2@test.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "organization_name": "TestUniqueOrg",  # Same name!
        }
        log(f"  Data: {json.dumps(data2, indent=2)}", "DEBUG")

        serializer2 = RegistrationSerializer(data=data2)
        try:
            if serializer2.is_valid():
                user2, tenant2 = serializer2.save()
                log("  ❌ TEST FAILED: Duplicate org was allowed!", "ERROR")
                log(f"     Created: {tenant2.name} (schema: {tenant2.schema_name})", "ERROR")
                return False
            else:
                log(f"  Validation errors: {serializer2.errors}", "DEBUG")
                if "organization_name" in serializer2.errors:
                    error_detail = serializer2.errors["organization_name"][0]
                    log(f"  ✅ Duplicate rejected with validation error: {error_detail}", "INFO")
                    return True
                else:
                    log(f"  ❌ Wrong error field: {serializer2.errors}", "ERROR")
                    return False
        except DuplicateOrganizationNameError as e:
            log(f"  ✅ Duplicate rejected with exception: {e}", "INFO")
            return True
        except Exception as e:
            log(f"  ❌ Unexpected exception: {type(e).__name__}: {e}", "ERROR")
            return False

    log("", "INFO")
    log("📋 Step 4: Final cleanup", "INFO")
    cleanup_test_data()

    log("", "INFO")
    log("=" * 70, "INFO")
    log("TEST COMPLETE", "INFO")
    log("=" * 70, "INFO")


if __name__ == "__main__":
    # Clear log file
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    success = main()
    sys.exit(0 if success else 1)
