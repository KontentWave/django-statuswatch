"""Celery tasks for monitoring, exposed under legacy `monitors.tasks` names."""

from __future__ import annotations

import logging

import requests
from celery import shared_task
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context
from monitors.models import Endpoint

from .scheduler import collect_due_endpoints, record_result

logger = logging.getLogger("monitors")
audit_logger = logging.getLogger("monitors.audit")
performance_logger = logging.getLogger("monitors.performance")


@shared_task(
    name="monitors.tasks.ping_endpoint",
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 3},
)
def ping_endpoint(self, endpoint_id: str, tenant_schema: str) -> None:
    """Perform an HTTP GET request against the endpoint and persist the result."""

    connection.set_schema_to_public()  # type: ignore[attr-defined]
    with schema_context(tenant_schema):
        try:
            endpoint = Endpoint.objects.select_related("tenant").get(id=endpoint_id)
        except Endpoint.DoesNotExist:
            logger.warning(
                "Endpoint %s no longer exists in tenant %s; skipping",
                endpoint_id,
                tenant_schema,
            )
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
            logger.info(
                "Issuing ping request",
                extra={
                    "endpoint_id": str(endpoint.id),
                    "url": endpoint.url,
                    "tenant": getattr(endpoint.tenant, "schema_name", "public"),
                    "task_id": request_id,
                },
            )
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
            current_retries = self.request.retries
            max_retries = self.max_retries

            logger.error(
                "Endpoint ping failed",
                extra={
                    "endpoint_id": str(endpoint.id),
                    "url": endpoint.url,
                    "error": str(exc),
                    "task_id": request_id,
                    "retry_count": current_retries,
                    "max_retries": max_retries,
                },
            )

            if current_retries >= max_retries:
                logger.critical(
                    "Endpoint permanently unreachable after max retries",
                    extra={
                        "endpoint_id": str(endpoint.id),
                        "url": endpoint.url,
                        "tenant": tenant_schema,
                        "error": str(exc),
                        "retry_count": current_retries,
                    },
                )
                try:
                    notify_endpoint_failure.delay(
                        endpoint_id,
                        tenant_schema,
                        endpoint.url,
                        str(exc),
                    )
                except Exception as notification_error:  # noqa: BLE001
                    logger.error(
                        "Failed to schedule failure notification",
                        extra={
                            "endpoint_id": str(endpoint.id),
                            "error": str(notification_error),
                        },
                    )

            status = "network-error"
            raise
        finally:
            record_result(endpoint, status, latency_ms)

    connection.set_schema_to_public()  # type: ignore[attr-defined]


@shared_task(name="monitors.tasks.notify_endpoint_failure")
def notify_endpoint_failure(
    endpoint_id: str,
    tenant_schema: str,
    url: str,
    error_message: str,
) -> None:
    """Notify about permanent endpoint failure after retry exhaustion."""

    logger.error(
        "DEAD LETTER QUEUE: Endpoint monitoring permanently failed",
        extra={
            "endpoint_id": endpoint_id,
            "tenant": tenant_schema,
            "url": url,
            "error": error_message,
            "timestamp": timezone.now().isoformat(),
        },
    )

    audit_logger.critical(
        "Endpoint requires manual intervention",
        extra={
            "endpoint_id": endpoint_id,
            "tenant": tenant_schema,
            "url": url,
            "error": error_message,
        },
    )


@shared_task(bind=True, name="monitors.tasks.schedule_endpoint_checks")
def schedule_endpoint_checks(self) -> int:
    """Inspect tenant endpoints and enqueue ping tasks when their interval elapses."""

    now = timezone.now()
    scheduled_payloads, skipped_tenants, failed_tenants, tenant_count = collect_due_endpoints(
        now,
        audit_logger=audit_logger,
    )

    scheduled = 0
    for endpoint_data in scheduled_payloads:
        async_result = ping_endpoint.delay(endpoint_data.id, endpoint_data.tenant_schema)
        scheduled += 1

        ping_task_id = getattr(async_result, "id", None)
        if ping_task_id is not None:
            ping_task_id = str(ping_task_id)

        log_message = (
            f"Endpoint queued for monitoring (ping_task_id={ping_task_id})"
            if ping_task_id
            else "Endpoint queued for monitoring"
        )

        audit_logger.info(
            log_message,
            extra={
                "tenant": endpoint_data.tenant_schema,
                "endpoint_id": endpoint_data.id,
                "url": endpoint_data.url,
                "interval_minutes": endpoint_data.interval_minutes,
                "task_id": getattr(self.request, "id", None),
                "ping_task_id": ping_task_id,
            },
        )

        latency_ms = max(0.0, (now - endpoint_data.reference).total_seconds() * 1000)
        performance_logger.info(
            "Endpoint scheduling latency",
            extra={
                "endpoint_id": endpoint_data.id,
                "url": endpoint_data.url,
                "latency_ms": latency_ms,
                "tenant": endpoint_data.tenant_schema,
                "reference": endpoint_data.reference.isoformat(),
                "scheduled_at": now.isoformat(),
            },
        )

    logger.info(
        "Endpoint scheduler run completed",
        extra={
            "scheduled": scheduled,
            "task_id": getattr(self.request, "id", None),
            "tenant_count": tenant_count,
            "skipped_tenants": len(skipped_tenants),
            "failed_tenants": len(failed_tenants),
            "run_at": now.isoformat(),
        },
    )

    if skipped_tenants:
        audit_logger.warning(
            "Some tenants were skipped due to missing tables",
            extra={
                "skipped_count": len(skipped_tenants),
                "skipped_schemas": skipped_tenants,
            },
        )

    if failed_tenants:
        audit_logger.error(
            "Some tenants failed during scheduling",
            extra={
                "failed_count": len(failed_tenants),
                "failures": failed_tenants,
            },
        )

    return scheduled


__all__ = [
    "notify_endpoint_failure",
    "ping_endpoint",
    "schedule_endpoint_checks",
]
