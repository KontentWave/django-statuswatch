"""
Pytest configuration for multi-tenant Django tests.

This conftest.py provides shared fixtures and patches that apply to all tests
in the test suite, ensuring proper handling of multi-tenant database operations.
"""

import logging
import os
import re
import uuid
from pathlib import Path

import psycopg
import pytest
from django.core.cache import cache
from psycopg import sql

try:  # pragma: no cover - dependency availability check
    import pytest_mock  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover - fallback path
    pytest_mock = None
else:  # pragma: no cover - keep lint happy when plugin exists
    pytest_mock = True

if not pytest_mock:
    from unittest import mock

    @pytest.fixture
    def mocker():
        """Lightweight fallback when pytest-mock plugin is unavailable."""

        class _PatchProxy:
            def __init__(self) -> None:
                self._patchers: list[mock._patch] = []  # type: ignore[attr-defined]

            def _start(self, patcher):
                started = patcher.start()
                self._patchers.append(patcher)
                return started

            def __call__(self, target, *args, **kwargs):
                return self._start(mock.patch(target, *args, **kwargs))

            def object(self, target, attribute, *args, **kwargs):
                return self._start(mock.patch.object(target, attribute, *args, **kwargs))

            def stopall(self):
                while self._patchers:
                    self._patchers.pop().stop()

        proxy = _PatchProxy()

        class _Mocker:
            patch = proxy

            @staticmethod
            def Mock(*args, **kwargs):
                return mock.Mock(*args, **kwargs)

        try:
            yield _Mocker()
        finally:
            proxy.stopall()


_worker_db_bootstrapped = False


def _normalize_worker_db_name(base_name: str, worker_id: str) -> str:
    """Return a stable worker DB name without recursive _gw suffixes."""

    # Drop any existing _gwX suffix to avoid dj01_gw0_gw0, etc.
    trimmed = re.sub(r"_gw\d+$", "", base_name)
    return f"{trimmed}_{worker_id}"


def _create_database_if_missing(db_params: dict[str, str], db_name: str) -> None:
    """Create a database if it does not exist; ignore failures to keep tests running."""

    admin_params = {
        "dbname": "postgres",
        "user": db_params.get("USER") or None,
        "password": db_params.get("PASSWORD") or None,
        "host": db_params.get("HOST") or None,
        "port": db_params.get("PORT") or None,
    }
    admin_params = {k: v for k, v in admin_params.items() if v not in (None, "")}

    try:
        with psycopg.connect(**admin_params) as admin_conn:  # type: ignore[arg-type]
            admin_conn.autocommit = True
            with admin_conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                exists = cursor.fetchone()
                if not exists:
                    cursor.execute(f'CREATE DATABASE "{db_name}"')
    except Exception:
        # Keep going even if creation fails; pytest will fall back to the base DB.
        return


def _configure_worker_database(settings):
    """Point each xdist worker at its own database and ensure it exists."""

    global _worker_db_bootstrapped

    if _worker_db_bootstrapped:
        return

    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker_id or worker_id == "master":
        return

    default_db = settings.DATABASES.get("default", {})
    base_name = default_db.get("NAME")
    if not base_name:
        return

    worker_db_name = _normalize_worker_db_name(base_name, worker_id)
    if base_name == worker_db_name:
        return

    _create_database_if_missing(default_db, worker_db_name)

    settings.DATABASES["default"]["NAME"] = worker_db_name
    os.environ["DJANGO_WORKER_DATABASE"] = worker_db_name
    _worker_db_bootstrapped = True


def pytest_configure(config):
    """Configure test environment before tests run."""
    from django.conf import settings

    _configure_worker_database(settings)

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
from django.conf import settings as django_settings  # noqa: E402

_configure_worker_database(django_settings)

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import close_old_connections, connection, transaction  # noqa: E402
from django.db.utils import OperationalError  # noqa: E402
from django_tenants.utils import schema_context  # noqa: E402
from tenants.models import Client, Domain  # noqa: E402


def _ensure_tenant_auth_tables(schema_name: str) -> None:
    """Ensure the given tenant schema has auth tables before using them.

    Some fixtures create users immediately after tenant creation. If migrations
    have not been applied for that schema yet, auth_user is missing and tests
    error before schema_context can switch. This helper runs migrate_schemas for
    the specific tenant when auth tables are absent.
    """

    from django.core.management import call_command

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_name = 'auth_user'
            )
            """,
            [schema_name],
        )
        has_auth = cursor.fetchone()[0]

    if not has_auth:
        call_command("migrate_schemas", schema_name=schema_name, verbosity=0)


# Store the original BOUND method from connection.ops (not the class method)
# This ensures we have access to 'self' when calling the original method
_original_execute_sql_flush = connection.ops.execute_sql_flush
_worker_schema_bootstrapped = False


def _ensure_connection_ready() -> None:
    """Ensure Django's connection handle is usable before issuing queries."""

    conn = connection

    # pytest-django wraps TestCase-based tests in an atomic transaction.  Closing
    # the connection while django.db thinks it still owns an open transaction
    # puts psycopg into a BAD state that surfaces as "connection is closed".
    if conn.in_atomic_block:
        status = None
        if conn.connection is not None:
            status = getattr(getattr(conn.connection, "pgconn", None), "status", None)

        # If the current transaction has been marked for rollback, clear the flag
        # so future queries can run without tripping TransactionManagementError.
        if conn.needs_rollback:
            transaction.set_rollback(False)

        # psycopg status: 0 == OK. Anything else means we need to roll back the
        # underlying transaction instead of closing the handle.
        if status not in (None, 0):
            try:
                conn._rollback()  # type: ignore[attr-defined]
            except Exception:
                pass
            else:
                transaction.set_rollback(False)

        # If psycopg dropped the socket entirely, re-open it without closing the
        # Django wrapper (which would violate the atomic contract).
        if conn.connection is None or getattr(conn.connection, "closed", False):
            if conn.connection is not None and getattr(conn.connection, "closed", False):
                # Drop the unusable psycopg handle so Django will recreate it.
                try:
                    conn.close_if_unusable_or_obsolete()
                except Exception:
                    conn.connection = None  # pragma: no cover - last-resort guard
        conn.ensure_connection()

        return

    close_old_connections()
    try:
        conn.ensure_connection()
    except OperationalError:
        # Under heavy tenant setup the psycopg handle can get stuck in BAD state.
        conn.close()


def _bootstrap_worker_database_schema() -> None:
    """Run public + tenant migrations and seed test_tenant for worker DBs."""

    global _worker_schema_bootstrapped

    if _worker_schema_bootstrapped:
        return

    from django.core.management import call_command

    connection.set_schema_to_public()
    call_command("migrate_schemas", schema_name="public", verbosity=0)

    tenant, _ = Client.objects.get_or_create(
        schema_name="test_tenant",
        defaults={
            "name": "Test Tenant",
            "paid_until": "2099-12-31",
            "on_trial": False,
        },
    )

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

    call_command("migrate_schemas", schema_name=tenant.schema_name, verbosity=0)
    _ensure_tenant_auth_tables(tenant.schema_name)
    connection.set_schema_to_public()

    _worker_schema_bootstrapped = True


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
    for statement in sql_list:
        stripped_sql = statement.strip()
        if stripped_sql.upper().startswith("TRUNCATE"):
            # Avoid appending CASCADE twice if already present.
            if "CASCADE" not in stripped_sql.upper():
                stripped_sql = re.sub(r";\s*$", " CASCADE;", stripped_sql)
            cascaded_sql_list.append(stripped_sql)
        else:
            cascaded_sql_list.append(statement)

    return _original_execute_sql_flush(cascaded_sql_list, *args, **kwargs)


def _build_raw_db_params() -> dict[str, str]:
    """Return psycopg-friendly params for the current Django connection."""

    settings_dict = connection.settings_dict
    params = {
        "dbname": settings_dict.get("NAME"),
        "user": settings_dict.get("USER") or None,
        "password": settings_dict.get("PASSWORD") or None,
        "host": settings_dict.get("HOST") or None,
        "port": settings_dict.get("PORT") or None,
    }
    return {key: value for key, value in params.items() if value not in (None, "")}


def _cleanup_tenant_tables(schema_name: str) -> None:
    """Truncate tenant tables (tokens, auth) using a dedicated psycopg connection."""

    params = _build_raw_db_params()
    if not params:
        return

    try:
        with psycopg.connect(**params) as raw_conn:  # type: ignore[arg-type]
            raw_conn.autocommit = True
            with raw_conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SET search_path TO {};").format(sql.Identifier(schema_name))
                )
                # Clean up tokens first (dependencies)
                cursor.execute("TRUNCATE TABLE token_blacklist_blacklistedtoken CASCADE")
                cursor.execute("TRUNCATE TABLE token_blacklist_outstandingtoken CASCADE")
                # Clean up users (auth_user) which might persist if transaction=True
                cursor.execute("TRUNCATE TABLE auth_user CASCADE")
    except Exception:
        # Fixture cleanup should never fail the test suite; swallow any driver errors.
        pass


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
def bootstrap_test_tenant(
    django_db_setup,
    django_db_blocker,
    cleanup_all_test_schemas,
):
    """Create the shared test tenant once per session outside test transactions."""

    from django.core.management import call_command

    with django_db_blocker.unblock():
        _ensure_connection_ready()
        _bootstrap_worker_database_schema()

        connection.set_schema_to_public()

        tenant, _ = Client.objects.get_or_create(
            schema_name="test_tenant",
            defaults={
                "name": "Test Tenant",
                "paid_until": "2099-12-31",
                "on_trial": False,
            },
        )

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

        call_command("migrate_schemas", schema_name=tenant.schema_name, verbosity=0)
        connection.set_schema_to_public()

    yield tenant.schema_name


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


@pytest.fixture(scope="session", autouse=True)
def ensure_public_domain(
    django_db_setup,
    django_db_blocker,
):
    """Ensure the public tenant exists once per session outside test transactions."""

    with django_db_blocker.unblock():
        _ensure_connection_ready()
        connection.set_schema_to_public()

        public_tenant = Client.objects.filter(schema_name="public").first()
        if public_tenant is None:
            public_tenant = Client(schema_name="public", name="Public Tenant")
            public_tenant.auto_create_schema = False
            public_tenant.save()

        # Ensure public.localhost domain exists so requests to it route to public schema
        if not Domain.objects.filter(domain="public.localhost").exists():
            Domain.objects.create(domain="public.localhost", tenant=public_tenant, is_primary=True)

        connection.set_schema_to_public()

    yield


@pytest.fixture(scope="session", autouse=True)
def ensure_test_tenant_session(
    django_db_setup,
    django_db_blocker,
    bootstrap_test_tenant,
):
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
    with django_db_blocker.unblock():
        _ensure_connection_ready()
        connection.set_schema_to_public()

        tenant = Client.objects.filter(schema_name="test_tenant").first()
        if tenant is None:
            raise AssertionError("Expected bootstrap_test_tenant to provision test_tenant")

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

        _ensure_tenant_auth_tables(tenant.schema_name)

        connection.set_schema_to_public()
        yield tenant


@pytest.fixture(autouse=True)
def ensure_test_tenant(db, ensure_test_tenant_session):
    """
    Ensure test_tenant exists for every test, recreating it if flushed.
    """
    _ensure_connection_ready()
    connection.set_schema_to_public()

    # Check if the tenant still exists (it might have been flushed by TransactionTestCase)
    if not Client.objects.filter(schema_name="test_tenant").exists():
        # Re-create the tenant and domains
        tenant, _ = Client.objects.get_or_create(
            schema_name="test_tenant",
            defaults={
                "name": "Test Tenant",
                "paid_until": "2099-12-31",
                "on_trial": False,
            },
        )
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
        # We don't need to re-run migrations because schemas (DDL) are not flushed,
        # only the rows in the public schema (Client/Domain tables) are flushed.

        # Update the session object to match the new DB row
        ensure_test_tenant_session.id = tenant.id
        ensure_test_tenant_session.refresh_from_db()

    return ensure_test_tenant_session


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
    _ensure_connection_ready()
    connection.set_schema_to_public()


@pytest.fixture(autouse=True)
def isolate_rate_limiting(settings, request):
    """Disable throttling for ordinary tests and clear cached throttle state."""

    if request.node.fspath.basename != "test_rate_limiting.py":
        settings.API_RATE_LIMITING_ENABLED = False

    cache.clear()
    yield
    cache.clear()

    # Return to public schema for next test.
    _ensure_connection_ready()
    connection.set_schema_to_public()


@pytest.fixture(autouse=True, scope="function")
def cleanup_jwt_tokens(db, ensure_test_tenant, request):
    """
    Clean up JWT token blacklist tables after each test to prevent table bloat.

    After ~70 tests with JWT operations, token_blacklist tables can have hundreds
    of rows causing PostgreSQL table locks and test hangs. This fixture truncates
    the tables after each test to prevent resource exhaustion.
    """
    schema_name = ensure_test_tenant.schema_name
    yield

    # Skip explicit truncation for standard tests (transaction=False) to avoid deadlocks.
    # Standard tests run in a transaction that is rolled back, so cleanup is automatic.
    # Attempting to TRUNCATE from a separate connection while the test transaction is open
    # causes a deadlock.
    django_db_mark = request.node.get_closest_marker("django_db")
    if django_db_mark:
        transaction = django_db_mark.kwargs.get("transaction", False)
        if not transaction:
            return

    _cleanup_tenant_tables(schema_name)
    _ensure_connection_ready()
    connection.set_schema_to_public()


@pytest.fixture
def tenant_factory(db):
    """Create disposable tenants with migrated auth tables for isolation.

    We run `migrate_schemas` the first time a tenant schema is created to ensure
    auth tables exist before any fixtures touch `User` or `UserProfile`, which
    prevents `relation "auth_user" does not exist` errors when a schema_context
    is entered immediately after tenant creation.
    """

    # Cache tenants by name to avoid repeated schema creation/migrations.
    cache: dict[str, Client] = {}
    created: list[Client] = []
    migrated: set[str] = set()

    def _create(name: str | None = None) -> Client:
        from api.models import UserProfile

        User = get_user_model()

        # Generate stable key when name is provided to enable reuse across tests.
        cache_key = name or "__anon__"  # anonymous requests still get unique schemas

        if cache_key in cache and name is not None:
            tenant = cache[cache_key]
        else:
            # Generate unique schema name to satisfy unique constraint on Client.name
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

            Domain.objects.get_or_create(
                tenant=tenant,
                domain=f"{schema_name}.localhost",
                defaults={"is_primary": True},
            )

            created.append(tenant)
            if name is not None:
                cache[cache_key] = tenant

        # Ensure the tenant schema has auth tables before any user creation.
        if tenant.schema_name not in migrated:
            _ensure_tenant_auth_tables(tenant.schema_name)
            migrated.add(tenant.schema_name)

        # Clean per-tenant auth tables to avoid cross-test contamination when reusing tenants.
        with schema_context(tenant.schema_name):
            User.objects.all().delete()
            UserProfile.objects.all().delete()

        return tenant

    yield _create

    _ensure_connection_ready()
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
