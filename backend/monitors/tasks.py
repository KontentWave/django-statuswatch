import logging
from datetime import datetime, timedelta

import requests
from celery import shared_task
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context
from tenants.models import Client

from .models import Endpoint

logger = logging.getLogger("monitors")
audit_logger = logging.getLogger("monitors.audit")
performance_logger = logging.getLogger("monitors.performance")


def _record_result(endpoint: Endpoint, status: str, latency_ms: float | None) -> None:
    endpoint.last_status = status
    endpoint.last_checked_at = timezone.now()
    endpoint.last_latency_ms = latency_ms
    endpoint.save(update_fields=["last_status", "last_checked_at", "last_latency_ms", "updated_at"])


@shared_task(
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 3},
)
def ping_endpoint(self, endpoint_id: str) -> None:
    """Perform an HTTP GET request against the endpoint and persist the result."""

    try:
        endpoint = Endpoint.objects.select_related("tenant").get(id=endpoint_id)
    except Endpoint.DoesNotExist:
        logger.warning("Endpoint %s no longer exists; skipping", endpoint_id)
        return

    request_id = getattr(self.request, "id", None)
    audit_logger.info(
        "Pinging endpoint",
        extra={
            "endpoint_id": str(endpoint.id),
            "url": endpoint.url,
            "tenant": getattr(endpoint.tenant, "schema_name", "public"),
            "task_id": request_id,
        },
    )

    started_at = timezone.now()
    latency_ms: float | None = None
    status = "error"

    try:
        response = requests.get(endpoint.url, timeout=10)
        latency_ms = (timezone.now() - started_at).total_seconds() * 1000
        response.raise_for_status()
        status = str(response.status_code)
        performance_logger.info(
            "Endpoint ping success",
            extra={
                "endpoint_id": str(endpoint.id),
                "url": endpoint.url,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "task_id": request_id,
            },
        )
    except requests.HTTPError as exc:
        latency_ms = (timezone.now() - started_at).total_seconds() * 1000
        status_code = getattr(exc.response, "status_code", "n/a")
        logger.warning(
            "Endpoint ping returned HTTP error",
            extra={
                "endpoint_id": str(endpoint.id),
                "url": endpoint.url,
                "status_code": status_code,
                "task_id": request_id,
            },
        )
        status = f"error:{status_code}"
    except requests.RequestException as exc:
        latency_ms = (timezone.now() - started_at).total_seconds() * 1000
        logger.error(
            "Endpoint ping failed",
            extra={
                "endpoint_id": str(endpoint.id),
                "url": endpoint.url,
                "error": str(exc),
                "task_id": request_id,
            },
        )
        status = "network-error"
        raise
    finally:
        _record_result(endpoint, status, latency_ms)


def _is_endpoint_due(endpoint: Endpoint, now: datetime) -> tuple[bool, datetime]:
    """Return whether the endpoint should be enqueued along with the reference timestamp."""

    reference_points = [endpoint.last_checked_at, endpoint.last_enqueued_at]
    reference_times = [ts for ts in reference_points if ts is not None]
    reference = max(reference_times) if reference_times else endpoint.created_at
    if reference is None:
        return True, now
    due_delta = now - reference
    required_delta = timedelta(minutes=endpoint.interval_minutes)
    return due_delta >= required_delta, reference


@shared_task(bind=True)
def schedule_endpoint_checks(self) -> int:
    """Inspect tenant endpoints and enqueue ping tasks when their interval elapses."""

    now = timezone.now()
    scheduled = 0

    # Ensure we start from the public schema before iterating tenants.
    connection.set_schema_to_public()
    tenants = Client.objects.exclude(schema_name="public")

    for tenant in tenants:
        with schema_context(tenant.schema_name):
            for endpoint in Endpoint.objects.all():
                audit_logger.debug(
                    "Inspecting endpoint for scheduling",
                    extra={
                        "tenant": tenant.schema_name,
                        "endpoint_id": str(endpoint.id),
                        "last_checked_at": (
                            endpoint.last_checked_at.isoformat()
                            if endpoint.last_checked_at
                            else None
                        ),
                        "last_enqueued_at": (
                            endpoint.last_enqueued_at.isoformat()
                            if endpoint.last_enqueued_at
                            else None
                        ),
                        "interval_minutes": endpoint.interval_minutes,
                    },
                )
                is_due, reference = _is_endpoint_due(endpoint, now)
                if not is_due:
                    audit_logger.debug(
                        "Endpoint not due",
                        extra={
                            "tenant": tenant.schema_name,
                            "endpoint_id": str(endpoint.id),
                            "reference": reference.isoformat(),
                        },
                    )
                    continue

                endpoint.last_enqueued_at = now
                endpoint.save(update_fields=["last_enqueued_at", "updated_at"])

                ping_endpoint.delay(str(endpoint.id))
                scheduled += 1

                audit_logger.info(
                    "Endpoint queued for monitoring",
                    extra={
                        "tenant": tenant.schema_name,
                        "endpoint_id": str(endpoint.id),
                        "url": endpoint.url,
                        "interval_minutes": endpoint.interval_minutes,
                        "task_id": getattr(self.request, "id", None),
                    },
                )

                latency_ms = max(0.0, (now - reference).total_seconds() * 1000)
                performance_logger.info(
                    "Endpoint scheduling latency",
                    extra={
                        "endpoint_id": str(endpoint.id),
                        "url": endpoint.url,
                        "latency_ms": latency_ms,
                        "tenant": tenant.schema_name,
                        "reference": reference.isoformat(),
                        "scheduled_at": now.isoformat(),
                    },
                )

    connection.set_schema_to_public()

    logger.info(
        "Endpoint scheduler run completed",
        extra={
            "scheduled": scheduled,
            "task_id": getattr(self.request, "id", None),
            "tenant_count": tenants.count(),
            "run_at": now.isoformat(),
        },
    )

    return scheduled
