"""
Pytest configuration for multi-tenant Django tests.

This conftest.py provides shared fixtures and patches that apply to all tests
in the test suite, ensuring proper handling of multi-tenant database operations.
"""
import re
import pytest
from django.db import connection
from tenants.models import Client, Domain


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
        if sql.strip().upper().startswith('TRUNCATE'):
            # Add CASCADE before the final semicolon
            cascaded_sql = re.sub(r';\s*$', ' CASCADE;', sql.strip())
            cascaded_sql_list.append(cascaded_sql)
        else:
            cascaded_sql_list.append(sql)
    
    return _original_execute_sql_flush(cascaded_sql_list, *args, **kwargs)


# Apply the CASCADE patch globally at module level
# This ensures it persists for the entire test session
if connection.ops.execute_sql_flush is not _execute_sql_flush_with_cascade:
    connection.ops.execute_sql_flush = _execute_sql_flush_with_cascade


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
    from django_tenants.utils import schema_context
    
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
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = %s 
                    AND table_name IN ('auth_user', 'api_userprofile', 'token_blacklist_outstandingtoken')
                """, [tenant.schema_name])
                existing_tables = {row[0] for row in cursor.fetchall()}
                required_tables = {'auth_user', 'api_userprofile', 'token_blacklist_outstandingtoken'}
                missing_tables = required_tables - existing_tables
        
        if missing_tables:
            # Run migrations for this tenant schema to create missing tables
            print(f"Running migrations for test_tenant (missing: {missing_tables})")
            call_command('migrate_schemas', schema_name=tenant.schema_name, verbosity=0)

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
