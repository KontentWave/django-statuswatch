"""
Pytest configuration for multi-tenant Django tests.

This conftest.py provides shared fixtures and patches that apply to all tests
in the test suite, ensuring proper handling of multi-tenant database operations.
"""

import logging
import re
import uuid
from pathlib import Path

import pytest


def pytest_configure(config):
    """Configure test environment before tests run."""
    from django.conf import settings

    # Fix database connection pooling for tests
    # CONN_MAX_AGE causes connection pool exhaustion in test suites
    # Set to 0 to close connections immediately after each test
    if hasattr(settings, "DATABASES"):
        for db_config in settings.DATABASES.values():
            db_config["CONN_MAX_AGE"] = 0
            db_config["CONN_HEALTH_CHECKS"] = False

    # Ensure STATIC_ROOT exists so Django/Whitenoise stop warning during tests.
    static_root = getattr(settings, "STATIC_ROOT", None)
    if static_root:
        Path(static_root).mkdir(parents=True, exist_ok=True)


# Delay Django imports until after pytest setup
from django.db import connection  # noqa: E402
from django_tenants.utils import schema_context  # noqa: E402
from tenants.models import Client, Domain  # noqa: E402

# Store the original BOUND method from connection.ops (not the class method)
# This ensures we have access to 'self' when calling the original method
_original_execute_sql_flush = connection.ops.execute_sql_flush


def _execute_sql_flush_with_cascade(sql_list, *args, **kwargs):
    """
    Wrapper for execute_sql_flush that adds CASCADE to TRUNCATE statements.

    In multi-tenant setups with django-tenants, tenant schemas often have
    foreign key constraints referencing tables in the public schema
    (e.g., auth_permission -> django_content_type).

    Standard TRUNCATE fails without CASCADE when these cross-schema
    references exist. This wrapper automatically adds CASCADE to all
    TRUNCATE statements to handle test database cleanup properly.
    """
    connection.set_schema_to_public()

    cascaded_sql_list = []
    for sql in sql_list:
        stripped_sql = sql.strip()
        if stripped_sql.upper().startswith("TRUNCATE"):
            # Avoid appending CASCADE twice if already present.
            if "CASCADE" not in stripped_sql.upper():
                stripped_sql = re.sub(r";\s*$", " CASCADE;", stripped_sql)
            cascaded_sql_list.append(stripped_sql)
        else:
            cascaded_sql_list.append(sql)

    return _original_execute_sql_flush(cascaded_sql_list, *args, **kwargs)


# Apply the CASCADE patch globally at module level
# This ensures it persists for the entire test session
if connection.ops.execute_sql_flush is not _execute_sql_flush_with_cascade:
    connection.ops.execute_sql_flush = _execute_sql_flush_with_cascade


@pytest.fixture(scope="session", autouse=True)
def cleanup_all_test_schemas(django_db_setup, django_db_blocker):
    """
    Clean ALL test schemas before test session starts.

    Handles orphaned schemas (schemas without tenant records) that persist
    from previous test runs and cause unique constraint violations.

    This runs once at the start of the test session and ensures a clean slate.
    """
    with django_db_blocker.unblock():
        connection.set_schema_to_public()

        # First, delete any test tenant records with force_drop
        test_patterns = ["testuniqueorg", "uniquenametest", "diagnostic", "test-org"]
        for pattern in test_patterns:
            test_tenants = Client.objects.filter(schema_name__icontains=pattern)
            for tenant in test_tenants:
                try:
                    tenant.delete(force_drop=True)
                except Exception:
                    pass  # Ignore errors - schema might already be gone

        # Then, drop any orphaned test schemas (schemas without tenant records)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE (schema_name LIKE 'testuniqueorg%'
                       OR schema_name LIKE 'uniquenametest%'
                       OR schema_name LIKE 'diagnostic%'
                       OR schema_name LIKE 'test-org%'
                       OR schema_name LIKE 'test_org%')
                AND schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            """
            )
            orphaned_schemas = [row[0] for row in cursor.fetchall()]

        for schema in orphaned_schemas:
            try:
                with connection.cursor() as cursor:
                    # Use quotes for schemas with hyphens
                    cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            except Exception:
                pass  # Ignore errors - schema might not exist

    yield
    # No teardown - let pytest handle normal cleanup


@pytest.fixture(scope="session", autouse=True)
def apply_cascade_patch():
    """
    Session-scoped fixture that ensures CASCADE patch is applied for all tests.

    This fixture runs once at the start of the test session and ensures the
    execute_sql_flush method is patched before any tests run.
    """
    # Patch is already applied at module level, but this fixture ensures
    # pytest knows about it and documents the dependency
    connection.ops.execute_sql_flush = _execute_sql_flush_with_cascade
    yield
    # Don't restore - keep patch active for entire session


@pytest.fixture(autouse=True)
def ensure_public_domain(db):
    """
    Ensure public tenant exists and testserver domain points to test_tenant.

    Many tests use testserver domain. Since we now use test_tenant for all
    user operations, testserver should point to test_tenant, not public.
    """
    # Ensure public tenant exists (needed for django-tenants infrastructure)
    public_tenant = Client.objects.filter(schema_name="public").first()
    if public_tenant is None:
        public_tenant = Client(schema_name="public", name="Public Tenant")
        public_tenant.auto_create_schema = False
        public_tenant.save()

    # Don't create domains here to avoid fixture-order races. Tenant domains
    # are created/ensured by `ensure_test_tenant` below which runs migrations
    # and sets up tenant domains reliably.


@pytest.fixture(autouse=True)
def ensure_test_tenant(db):
    """
    Ensure a default test tenant exists for all tests.

    Creates a tenant named 'test_tenant' with 'test.localhost' domain
    and runs migrations to create all necessary tables.

    This allows TestCase-based tests to create users in the tenant schema
    using schema_context() without explicit tenant setup in setUp() methods.

    IMPORTANT: This fixture does NOT change the active schema.
    Tests remain in the public schema by default. Use schema_context()
    or TenantClient to switch to tenant schemas when needed.
    """
    from django.core.management import call_command

    # Ensure we're in public schema to create tenants
    connection.set_schema_to_public()

    # Check if tenant already exists
    tenant = Client.objects.filter(schema_name="test_tenant").first()

    if tenant is None:
        # Create tenant - this will auto-create schema and run migrations
        tenant = Client(
            schema_name="test_tenant",
            name="Test Tenant",
            paid_until="2099-12-31",
            on_trial=False,
        )
        # auto_create_schema=True is the default, which runs migrations
        tenant.save()

        # Create primary domain
        Domain.objects.create(
            tenant=tenant,
            domain="test.localhost",
            is_primary=True,
        )
        # Also create a 'testserver' alias domain used by many APITestCase tests.
        Domain.objects.get_or_create(
            tenant=tenant,
            domain="testserver",
            defaults={"is_primary": False},
        )
    else:
        # Tenant exists - verify all required tables exist
        with schema_context(tenant.schema_name):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_name IN ('auth_user', 'api_userprofile', 'token_blacklist_outstandingtoken')
                """,
                    [tenant.schema_name],
                )
                existing_tables = {row[0] for row in cursor.fetchall()}
                required_tables = {
                    "auth_user",
                    "api_userprofile",
                    "token_blacklist_outstandingtoken",
                }
                missing_tables = required_tables - existing_tables

        if missing_tables:
            # Run migrations for this tenant schema to create missing tables
            print(f"Running migrations for test_tenant (missing: {missing_tables})")
            call_command("migrate_schemas", schema_name=tenant.schema_name, verbosity=0)

        # Ensure both domains exist for the tenant: the primary test.localhost
        # and an alias 'testserver' used by APITestCase client host resolution.
        Domain.objects.get_or_create(
            tenant=tenant,
            domain="test.localhost",
            defaults={"is_primary": True},
        )
        Domain.objects.get_or_create(
            tenant=tenant,
            domain="testserver",
            defaults={"is_primary": False},
        )

    # Stay in public schema (don't switch to tenant schema)
    connection.set_schema_to_public()
    return tenant


@pytest.fixture(autouse=True)
def reset_schema_between_tests(db, ensure_test_tenant):
    """
    Ensure each test starts and ends with the public schema selected.

    Multi-tenant tests often switch schemas during execution. This fixture
    ensures we always return to the public schema after each test to prevent
    cross-test contamination. Tests that need tenant schemas should use
    TenantClient or schema_context() explicitly.
    """
    # Start in public schema
    connection.set_schema_to_public()
    yield
    # Return to public schema for next test
    connection.set_schema_to_public()


@pytest.fixture(autouse=True, scope="function")
def cleanup_jwt_tokens(db):
    """
    Clean up JWT token blacklist tables after each test to prevent table bloat.

    After ~70 tests with JWT operations, token_blacklist tables can have hundreds
    of rows causing PostgreSQL table locks and test hangs. This fixture truncates
    the tables after each test to prevent resource exhaustion.
    """
    yield
    # Clean up after test
    try:
        with schema_context("test_tenant"):
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE token_blacklist_blacklistedtoken CASCADE")
                cursor.execute("TRUNCATE TABLE token_blacklist_outstandingtoken CASCADE")
    except Exception:
        # Ignore errors if tables don't exist yet
        pass
    finally:
        connection.set_schema_to_public()


@pytest.fixture
def tenant_factory(db):
    """Create disposable tenants for tests that need isolated schemas."""

    created: list[Client] = []

    def _create(name: str | None = None) -> Client:
        # Generate unique name to avoid violating Feature 7's unique constraint on Client.name
        if name is None:
            name = f"Test Tenant {uuid.uuid4().hex[:8]}"

        schema_name = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}"
        tenant = Client(
            schema_name=schema_name,
            name=name,
            paid_until="2099-12-31",
            on_trial=False,
        )
        tenant.save()

        Domain.objects.create(
            tenant=tenant,
            domain=f"{schema_name}.localhost",
            is_primary=True,
        )

        created.append(tenant)
        return tenant

    yield _create

    connection.set_schema_to_public()
    for tenant in created:
        try:
            tenant.delete()
        except Exception:
            # If the tenant cleanup fails we ignore it to keep tests resilient.
            pass


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Log failing test details to the Django error logger for debugging."""

    outcome = yield
    report = outcome.get_result()

    if not report.failed:
        return

    logger = logging.getLogger("django")
    longrepr = getattr(report, "longreprtext", None)
    detail = longrepr if isinstance(longrepr, str) else str(report.longrepr)
    logger.error(
        "Pytest failure | phase=%s | nodeid=%s\n%s",
        report.when,
        report.nodeid,
        detail,
    )
