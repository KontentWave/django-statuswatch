"""Health check and metrics endpoints for monitoring and observability."""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.logging_utils import sanitize_log_value

logger = logging.getLogger("api.health")


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    Lightweight health check endpoint for load balancers and monitoring.

    Returns 200 OK if the application is healthy, 503 Service Unavailable otherwise.
    """
    logger.info(
        "Health check invoked",
        extra={
            "remote_addr": request.META.get("REMOTE_ADDR", "unknown"),
            "path": request.path,
        },
    )

    checks = {
        "status": "healthy",
        "timestamp": timezone.now().isoformat(),
    }

    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        logger.error(f"Health check database failure: {e}")
        checks["database"] = "error"
        checks["status"] = "unhealthy"

    # Check Redis connectivity (via Celery broker)
    try:
        from app.celery import celery_app

        celery_app.connection().ensure_connection(max_retries=1)
        checks["redis"] = "ok"
    except Exception as e:
        logger.error(f"Health check Redis failure: {e}")
        checks["redis"] = "error"
        checks["status"] = "unhealthy"

    http_status = (
        status.HTTP_200_OK if checks["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    logger.info(
        "Health check completed",
        extra={
            "status_code": http_status,
            "result": sanitize_log_value(checks),
        },
    )

    return Response(checks, status=http_status)


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness_check(request):
    """
    Readiness check for Kubernetes/orchestration systems.

    Returns 200 if the app is ready to serve traffic, 503 otherwise.
    More thorough than health_check - includes migrations, Celery workers, etc.
    """
    logger.info(
        "Readiness check invoked",
        extra={
            "remote_addr": request.META.get("REMOTE_ADDR", "unknown"),
            "path": request.path,
        },
    )

    checks = {
        "status": "ready",
        "timestamp": timezone.now().isoformat(),
    }

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        logger.error(f"Readiness check database failure: {e}")
        checks["database"] = "error"
        checks["status"] = "not_ready"

    # Check Redis
    try:
        from app.celery import celery_app

        celery_app.connection().ensure_connection(max_retries=1)
        checks["redis"] = "ok"
    except Exception as e:
        logger.error(f"Readiness check Redis failure: {e}")
        checks["redis"] = "error"
        checks["status"] = "not_ready"

    # Check Celery workers (are any workers responding?)
    try:
        from app.celery import celery_app

        inspector = celery_app.control.inspect(timeout=1.0)
        active_workers = inspector.active()
        if active_workers:
            checks["celery_workers"] = f"{len(active_workers)} active"
        else:
            checks["celery_workers"] = "no active workers"
            checks["status"] = "not_ready"
    except Exception as e:
        logger.error(f"Readiness check Celery failure: {e}")
        checks["celery_workers"] = "error"
        checks["status"] = "not_ready"

    # Check migrations (are there unapplied migrations?)
    try:
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            checks["migrations"] = f"{len(plan)} unapplied"
            checks["status"] = "not_ready"
        else:
            checks["migrations"] = "up to date"
    except Exception as e:
        logger.error(f"Readiness check migrations failure: {e}")
        checks["migrations"] = "error"
        checks["status"] = "not_ready"

    http_status = (
        status.HTTP_200_OK if checks["status"] == "ready" else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    logger.info(
        "Readiness check completed",
        extra={
            "status_code": http_status,
            "result": sanitize_log_value(checks),
        },
    )

    return Response(checks, status=http_status)


@api_view(["GET"])
@permission_classes([AllowAny])
def metrics(request):
    """
    Basic metrics endpoint for monitoring dashboards.

    Provides statistics about the application state.
    """
    from monitors.models import Endpoint

    logger.info(
        "Metrics snapshot requested",
        extra={
            "remote_addr": request.META.get("REMOTE_ADDR", "unknown"),
            "path": request.path,
        },
    )

    metrics_data = {
        "timestamp": timezone.now().isoformat(),
        "environment": (
            settings.SENTRY_ENVIRONMENT if hasattr(settings, "SENTRY_ENVIRONMENT") else "unknown"
        ),
        "debug": settings.DEBUG,
    }

    # Tenant statistics
    try:
        from django_tenants.utils import get_tenant_model

        Tenant = get_tenant_model()
        tenant_count = Tenant.objects.exclude(schema_name="public").count()
        metrics_data["tenants"] = {
            "total": tenant_count,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch tenant metrics: {e}")
        metrics_data["tenants"] = {"error": str(e)}  # Endpoint statistics (across all tenants)
    try:
        total_endpoints = 0
        active_endpoints = 0
        healthy_endpoints = 0

        # Iterate through tenants to get aggregate stats
        from django_tenants.utils import get_tenant_model

        Tenant = get_tenant_model()
        for tenant in Tenant.objects.exclude(schema_name="public"):
            from django_tenants.utils import schema_context

            with schema_context(tenant.schema_name):
                tenant_endpoints = Endpoint.objects.all()
                total_endpoints += tenant_endpoints.count()
                # Count endpoints that have been checked (not pending)
                active_endpoints += tenant_endpoints.exclude(last_status="pending").count()
                healthy_endpoints += tenant_endpoints.filter(last_status="success").count()

        metrics_data["endpoints"] = {
            "total": total_endpoints,
            "active": active_endpoints,
            "healthy": healthy_endpoints,
            "unhealthy": active_endpoints - healthy_endpoints if active_endpoints > 0 else 0,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch endpoint metrics: {e}")
        metrics_data["endpoints"] = {"error": str(e)}

    # Celery statistics
    try:
        from app.celery import celery_app

        inspector = celery_app.control.inspect(timeout=1.0)

        # Get active tasks
        active = inspector.active()
        active_count = sum(len(tasks) for tasks in (active or {}).values())

        # Get scheduled tasks
        scheduled = inspector.scheduled()
        scheduled_count = sum(len(tasks) for tasks in (scheduled or {}).values())

        # Get registered tasks
        registered = inspector.registered()
        registered_tasks = []
        if registered:
            for _worker, tasks in registered.items():
                registered_tasks.extend([t for t in tasks if not t.startswith("celery.")])

        metrics_data["celery"] = {
            "workers": len(active or {}),
            "active_tasks": active_count,
            "scheduled_tasks": scheduled_count,
            "registered_tasks": len(set(registered_tasks)),
        }
    except Exception as e:
        logger.warning(f"Failed to fetch Celery metrics: {e}")
        metrics_data["celery"] = {"error": str(e)}

    # Recent check statistics (last hour)
    try:
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_checks = 0
        from django_tenants.utils import get_tenant_model

        Tenant = get_tenant_model()
        for tenant in Tenant.objects.exclude(schema_name="public"):
            from django_tenants.utils import schema_context

            with schema_context(tenant.schema_name):
                recent_checks += Endpoint.objects.filter(last_checked_at__gte=one_hour_ago).count()

        metrics_data["activity"] = {
            "checks_last_hour": recent_checks,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch activity metrics: {e}")
        metrics_data["activity"] = {"error": str(e)}

    logger.info(
        "Metrics snapshot completed",
        extra={"result": sanitize_log_value(metrics_data)},
    )

    return Response(metrics_data)
