"""
Tests for Health Check Endpoints (P2-01).

Coverage target: 15% → 90%+
File: api/health.py (136 statements)

This tests the health check, readiness check, and metrics endpoints used by
monitoring systems, load balancers, and Kubernetes orchestration.

Key behaviors tested:
- health_check: Basic database + Redis connectivity
- readiness_check: Deep readiness (database + Redis + Celery + migrations)
- metrics: Application statistics (tenants, endpoints, Celery, activity)
- Error handling for all external service failures
- Proper HTTP status codes (200 OK, 503 Service Unavailable)
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from django.test import RequestFactory, override_settings
from rest_framework import status
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def api_client():
    """API client for making requests."""
    return APIClient()


@pytest.fixture
def request_factory():
    """Django RequestFactory for creating HttpRequest objects."""
    return RequestFactory()


@pytest.fixture
def mock_celery_app():
    """Mock Celery app with inspector."""
    with patch("app.celery.celery_app") as mock_app:
        # Mock connection
        mock_conn = Mock()
        mock_app.connection.return_value = mock_conn
        mock_conn.ensure_connection = Mock()

        # Mock inspector
        mock_inspector = Mock()
        mock_app.control.inspect.return_value = mock_inspector
        mock_inspector.active.return_value = {"worker1": [{"id": "task1"}]}
        mock_inspector.scheduled.return_value = {"worker1": []}
        mock_inspector.registered.return_value = {
            "worker1": ["monitors.tasks.ping_endpoint", "celery.ping"]
        }

        yield mock_app


class TestHealthCheck:
    """Test suite for health_check endpoint."""

    def test_health_check_all_services_healthy_returns_200(self, request_factory, mock_celery_app):
        """
        Test health check returns 200 OK when all services are healthy.

        Verifies:
        - GET /api/health/ (Note: URL must be configured in urls.py)
        - Returns 200 OK
        - Response contains 'status': 'healthy'
        - Database check passes
        - Redis check passes
        - Timestamp is present
        """
        with patch("django.db.connection.cursor") as mock_cursor:
            cursor_mock = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor_mock
            cursor_mock.execute = Mock()

            # Direct function call (since URL routing not in api/urls.py yet)
            from api.health import health_check

            request = request_factory.get("/health/")
            response = health_check(request)

            assert response.status_code == status.HTTP_200_OK
            assert response.data["status"] == "healthy"
            assert response.data["database"] == "ok"
            assert response.data["redis"] == "ok"
            assert "timestamp" in response.data

    def test_health_check_database_down_returns_503(self, request_factory, mock_celery_app):
        """
        Test health check returns 503 when database is down.

        Verifies:
        - Database failure sets status to 'unhealthy'
        - Returns HTTP 503 Service Unavailable
        - Redis still checked (graceful degradation)
        """
        with patch("django.db.connection.cursor") as mock_cursor:
            # Simulate database failure
            mock_cursor.side_effect = Exception("Database connection failed")

            from api.health import health_check

            request = request_factory.get("/health/")
            response = health_check(request)

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert response.data["status"] == "unhealthy"
            assert response.data["database"] == "error"
            assert response.data["redis"] == "ok"  # Redis still works

    def test_health_check_redis_down_returns_503(self, request_factory):
        """
        Test health check returns 503 when Redis/Celery broker is down.

        Verifies:
        - Redis failure sets status to 'unhealthy'
        - Returns HTTP 503 Service Unavailable
        - Database still checked (graceful degradation)
        """
        with patch("django.db.connection.cursor") as mock_cursor:
            cursor_mock = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor_mock
            cursor_mock.execute = Mock()

            with patch("app.celery.celery_app") as mock_app:
                # Simulate Redis connection failure
                mock_app.connection.return_value.ensure_connection.side_effect = Exception(
                    "Redis connection refused"
                )

                from api.health import health_check

                request = request_factory.get("/health/")
                response = health_check(request)

                assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                assert response.data["status"] == "unhealthy"
                assert response.data["database"] == "ok"  # Database still works
                assert response.data["redis"] == "error"

    def test_health_check_all_services_down_returns_503(self, request_factory):
        """
        Test health check returns 503 when all services are down.

        Verifies:
        - Multiple failures handled gracefully
        - Status reflects overall unhealthy state
        """
        with patch("django.db.connection.cursor") as mock_cursor:
            mock_cursor.side_effect = Exception("Database down")

            with patch("app.celery.celery_app") as mock_app:
                mock_app.connection.return_value.ensure_connection.side_effect = Exception(
                    "Redis down"
                )

                from api.health import health_check

                request = request_factory.get("/health/")
                response = health_check(request)

                assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                assert response.data["status"] == "unhealthy"
                assert response.data["database"] == "error"
                assert response.data["redis"] == "error"


class TestReadinessCheck:
    """Test suite for readiness_check endpoint."""

    def test_readiness_check_all_ready_returns_200(self, request_factory, mock_celery_app):
        """
        Test readiness check returns 200 when all systems are ready.

        Verifies:
        - Database connectivity
        - Redis connectivity
        - Celery workers responding
        - No pending migrations
        - Returns HTTP 200 OK
        """
        with patch("django.db.connection.cursor") as mock_cursor:
            cursor_mock = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor_mock
            cursor_mock.execute = Mock()

            with patch("django.db.migrations.executor.MigrationExecutor") as mock_exec:
                mock_instance = Mock()
                mock_exec.return_value = mock_instance
                mock_instance.migration_plan.return_value = []  # No pending migrations

                from api.health import readiness_check

                request = request_factory.get("/health/")
                response = readiness_check(request)

                assert response.status_code == status.HTTP_200_OK
                assert response.data["status"] == "ready"
                assert response.data["database"] == "ok"
                assert response.data["redis"] == "ok"
                assert "1 active" in response.data["celery_workers"]
                assert response.data["migrations"] == "up to date"

    def test_readiness_check_database_down_returns_503(self, request_factory, mock_celery_app):
        """
        Test readiness check returns 503 when database is down.
        """
        with patch("django.db.connection.cursor") as mock_cursor:
            mock_cursor.side_effect = Exception("Database unavailable")

            from api.health import readiness_check

            request = request_factory.get("/health/")
            response = readiness_check(request)

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert response.data["status"] == "not_ready"
            assert response.data["database"] == "error"

    def test_readiness_check_redis_down_returns_503(self, request_factory):
        """
        Test readiness check returns 503 when Redis is down.
        """
        with patch("django.db.connection.cursor") as mock_cursor:
            cursor_mock = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor_mock
            cursor_mock.execute = Mock()

            with patch("app.celery.celery_app") as mock_app:
                mock_app.connection.return_value.ensure_connection.side_effect = Exception(
                    "Redis timeout"
                )

                from api.health import readiness_check

                request = request_factory.get("/health/")
                response = readiness_check(request)

                assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                assert response.data["status"] == "not_ready"
                assert response.data["redis"] == "error"

    def test_readiness_check_no_celery_workers_returns_503(self, request_factory):
        """
        Test readiness check returns 503 when no Celery workers are active.

        Verifies:
        - Detects absence of workers
        - Sets status to 'not_ready'
        """
        with patch("django.db.connection.cursor") as mock_cursor:
            cursor_mock = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor_mock
            cursor_mock.execute = Mock()

            with patch("app.celery.celery_app") as mock_app:
                mock_app.connection.return_value.ensure_connection = Mock()
                mock_inspector = Mock()
                mock_app.control.inspect.return_value = mock_inspector
                mock_inspector.active.return_value = None  # No workers

                from api.health import readiness_check

                request = request_factory.get("/health/")
                response = readiness_check(request)

                assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                assert response.data["status"] == "not_ready"
                assert response.data["celery_workers"] == "no active workers"

    def test_readiness_check_celery_inspection_fails_returns_503(self, request_factory):
        """
        Test readiness check returns 503 when Celery inspection fails.
        """
        with patch("django.db.connection.cursor") as mock_cursor:
            cursor_mock = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor_mock
            cursor_mock.execute = Mock()

            with patch("app.celery.celery_app") as mock_app:
                mock_app.connection.return_value.ensure_connection = Mock()
                mock_app.control.inspect.side_effect = Exception("Celery timeout")

                from api.health import readiness_check

                request = request_factory.get("/health/")
                response = readiness_check(request)

                assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                assert response.data["status"] == "not_ready"
                assert response.data["celery_workers"] == "error"

    def test_readiness_check_unapplied_migrations_returns_503(
        self, request_factory, mock_celery_app
    ):
        """
        Test readiness check returns 503 when migrations are pending.

        Verifies:
        - Detects unapplied migrations
        - Reports count of pending migrations
        """
        with patch("django.db.connection.cursor") as mock_cursor:
            cursor_mock = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor_mock
            cursor_mock.execute = Mock()

            with patch("django.db.migrations.executor.MigrationExecutor") as mock_exec:
                mock_instance = Mock()
                mock_exec.return_value = mock_instance
                # Simulate 3 pending migrations
                mock_instance.migration_plan.return_value = [
                    Mock(),
                    Mock(),
                    Mock(),
                ]

                from api.health import readiness_check

                request = request_factory.get("/health/")
                response = readiness_check(request)

                assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                assert response.data["status"] == "not_ready"
                assert "3 unapplied" in response.data["migrations"]

    def test_readiness_check_migration_check_fails_returns_503(
        self, request_factory, mock_celery_app
    ):
        """
        Test readiness check handles migration check failure gracefully.
        """
        with patch("django.db.connection.cursor") as mock_cursor:
            cursor_mock = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor_mock
            cursor_mock.execute = Mock()

            with patch("django.db.migrations.executor.MigrationExecutor") as mock_exec:
                mock_exec.side_effect = Exception("Migration executor failed")

                from api.health import readiness_check

                request = request_factory.get("/health/")
                response = readiness_check(request)

                assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                assert response.data["status"] == "not_ready"
                assert response.data["migrations"] == "error"


class TestMetrics:
    """Test suite for metrics endpoint."""

    def test_metrics_returns_all_statistics_successfully(self, request_factory):
        """
        Test metrics endpoint returns complete application statistics.

        Verifies:
        - Environment information
        - Tenant counts
        - Endpoint statistics
        - Celery worker information
        - Recent activity stats
        - Returns HTTP 200 OK (always, even with errors)
        """
        with patch("django_tenants.utils.get_tenant_model") as mock_get_model:
            mock_tenant_model = Mock()
            mock_get_model.return_value = mock_tenant_model

            # Mock tenant queryset
            mock_tenant1 = Mock()
            mock_tenant1.schema_name = "tenant1"
            mock_tenant2 = Mock()
            mock_tenant2.schema_name = "tenant2"

            # Create a mock queryset that supports both count() and iteration
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 2
            mock_queryset.__iter__.return_value = iter([mock_tenant1, mock_tenant2])
            mock_tenant_model.objects.exclude.return_value = mock_queryset

            with patch("monitors.models.Endpoint") as mock_endpoint:
                # Mock endpoint queries per tenant
                mock_qs = Mock()
                mock_qs.count.return_value = 5
                mock_qs.exclude.return_value.count.return_value = 4
                mock_qs.filter.return_value.count.return_value = 3
                mock_qs.filter.return_value = mock_qs  # For chaining
                mock_endpoint.objects.all.return_value = mock_qs

                with patch("django_tenants.utils.schema_context"):
                    with patch("app.celery.celery_app") as mock_app:
                        mock_inspector = Mock()
                        mock_app.control.inspect.return_value = mock_inspector
                        mock_inspector.active.return_value = {"worker1": [{"id": "task1"}]}
                        mock_inspector.scheduled.return_value = {"worker1": []}
                        mock_inspector.registered.return_value = {
                            "worker1": [
                                "monitors.tasks.ping",
                                "monitors.tasks.schedule",
                                "celery.ping",
                            ]
                        }

                        with override_settings(DEBUG=False):
                            from api.health import metrics

                            request = request_factory.get("/health/")
                            response = metrics(request)

                            assert response.status_code == status.HTTP_200_OK
                            assert "timestamp" in response.data
                            assert response.data["debug"] is False
                            assert response.data["tenants"]["total"] == 2
                            # 2 tenants × 5 endpoints each = 10 total
                            assert response.data["endpoints"]["total"] == 10
                            assert response.data["celery"]["workers"] == 1
                            assert "activity" in response.data

    def test_metrics_handles_tenant_fetch_failure_gracefully(self, request_factory):
        """
        Test metrics endpoint handles tenant fetch failure gracefully.

        Verifies:
        - Still returns 200 OK
        - Tenant section contains error details
        """
        with patch("django_tenants.utils.get_tenant_model") as mock_get_model:
            # Mock model but make objects.exclude() fail
            mock_tenant_model = Mock()
            mock_get_model.return_value = mock_tenant_model
            mock_tenant_model.objects.exclude.side_effect = Exception("Tenant query unavailable")

            with patch("app.celery.celery_app") as mock_app:
                mock_inspector = Mock()
                mock_app.control.inspect.return_value = mock_inspector
                mock_inspector.active.return_value = {}
                mock_inspector.scheduled.return_value = {}
                mock_inspector.registered.return_value = {}

                from api.health import metrics

                request = request_factory.get("/health/")
                response = metrics(request)

                assert response.status_code == status.HTTP_200_OK
                assert "error" in response.data["tenants"]
                assert "Tenant query unavailable" in response.data["tenants"]["error"]

    def test_metrics_handles_endpoint_fetch_failure_gracefully(self, request_factory):
        """
        Test metrics endpoint handles endpoint fetch failure gracefully.
        """
        with patch("django_tenants.utils.get_tenant_model") as mock_get_model:
            mock_tenant_model = Mock()
            mock_get_model.return_value = mock_tenant_model
            mock_tenant_model.objects.exclude.return_value.count.return_value = 1
            mock_tenant_model.objects.exclude.return_value = [Mock()]

            with patch("monitors.models.Endpoint") as mock_endpoint:
                mock_endpoint.objects.all.side_effect = Exception("Endpoint query failed")

                with patch("django_tenants.utils.schema_context"):
                    with patch("app.celery.celery_app") as mock_app:
                        mock_inspector = Mock()
                        mock_app.control.inspect.return_value = mock_inspector
                        mock_inspector.active.return_value = {}
                        mock_inspector.scheduled.return_value = {}
                        mock_inspector.registered.return_value = {}

                        from api.health import metrics

                        request = request_factory.get("/health/")
                        response = metrics(request)

                        assert response.status_code == status.HTTP_200_OK
                        assert "error" in response.data["endpoints"]

    def test_metrics_handles_celery_fetch_failure_gracefully(self, request_factory):
        """
        Test metrics endpoint handles Celery stats fetch failure gracefully.
        """
        with patch("django_tenants.utils.get_tenant_model") as mock_get_model:
            mock_tenant_model = Mock()
            mock_get_model.return_value = mock_tenant_model
            mock_tenant_model.objects.exclude.return_value.count.return_value = 0
            mock_tenant_model.objects.exclude.return_value = []

            with patch("app.celery.celery_app") as mock_app:
                mock_app.control.inspect.side_effect = Exception("Celery unavailable")

                from api.health import metrics

                request = request_factory.get("/health/")
                response = metrics(request)

                assert response.status_code == status.HTTP_200_OK
                assert "error" in response.data["celery"]
                assert "Celery unavailable" in response.data["celery"]["error"]

    def test_metrics_handles_activity_fetch_failure_gracefully(self, request_factory):
        """
        Test metrics endpoint handles activity stats fetch failure gracefully.
        """
        with patch("django_tenants.utils.get_tenant_model") as mock_get_model:
            mock_tenant_model = Mock()
            mock_get_model.return_value = mock_tenant_model
            mock_tenant_model.objects.exclude.return_value.count.return_value = 1

            # Make tenant iteration succeed but activity query fail
            mock_tenant = Mock()
            mock_tenant.schema_name = "test_tenant"
            mock_tenant_model.objects.exclude.return_value = [mock_tenant]

            with patch("monitors.models.Endpoint") as mock_endpoint:
                mock_qs = Mock()
                mock_qs.count.return_value = 0
                mock_qs.exclude.return_value.count.return_value = 0
                mock_qs.filter.return_value.count.return_value = 0
                # First call for endpoint stats succeeds, second call for activity fails
                mock_endpoint.objects.all.return_value = mock_qs
                mock_endpoint.objects.filter.side_effect = Exception("Activity query timeout")

                with patch("django_tenants.utils.schema_context"):
                    with patch("app.celery.celery_app") as mock_app:
                        mock_inspector = Mock()
                        mock_app.control.inspect.return_value = mock_inspector
                        mock_inspector.active.return_value = {}
                        mock_inspector.scheduled.return_value = {}
                        mock_inspector.registered.return_value = {}

                        from api.health import metrics

                        request = request_factory.get("/health/")
                        response = metrics(request)

                        assert response.status_code == status.HTTP_200_OK
                        assert "error" in response.data["activity"]

    @override_settings(SENTRY_ENVIRONMENT="staging")
    def test_metrics_includes_sentry_environment_when_configured(self, request_factory):
        """
        Test metrics includes Sentry environment when configured.
        """
        with patch("django_tenants.utils.get_tenant_model") as mock_get_model:
            mock_tenant_model = Mock()
            mock_get_model.return_value = mock_tenant_model
            mock_tenant_model.objects.exclude.return_value.count.return_value = 0
            mock_tenant_model.objects.exclude.return_value = []

            with patch("app.celery.celery_app") as mock_app:
                mock_inspector = Mock()
                mock_app.control.inspect.return_value = mock_inspector
                mock_inspector.active.return_value = {}
                mock_inspector.scheduled.return_value = {}
                mock_inspector.registered.return_value = {}

                from api.health import metrics

                request = request_factory.get("/health/")
                response = metrics(request)

                assert response.status_code == status.HTTP_200_OK
                assert response.data["environment"] == "staging"

    def test_metrics_defaults_to_unknown_environment_when_not_configured(self, request_factory):
        """
        Test metrics defaults to 'unknown' when SENTRY_ENVIRONMENT not set.
        """
        with patch("django_tenants.utils.get_tenant_model") as mock_get_model:
            mock_tenant_model = Mock()
            mock_get_model.return_value = mock_tenant_model
            mock_tenant_model.objects.exclude.return_value.count.return_value = 0
            mock_tenant_model.objects.exclude.return_value = []

            with patch("app.celery.celery_app") as mock_app:
                mock_inspector = Mock()
                mock_app.control.inspect.return_value = mock_inspector
                mock_inspector.active.return_value = {}
                mock_inspector.scheduled.return_value = {}
                mock_inspector.registered.return_value = {}

                from api.health import metrics

                request = request_factory.get("/health/")
                response = metrics(request)

                assert response.status_code == status.HTTP_200_OK
                assert response.data["environment"] == "unknown"
