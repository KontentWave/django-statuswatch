import logging
from datetime import datetime, timedelta

import requests
from celery import shared_task
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import schema_context
from tenants.models import Client

from .models import Endpoint

PENDING_REQUEUE_GRACE = timedelta(seconds=settings.PENDING_REQUEUE_GRACE_SECONDS)

logger = logging.getLogger("monitors")
audit_logger = logging.getLogger("monitors.audit")
performance_logger = logging.getLogger("monitors.performance")


def _record_result(endpoint: Endpoint, status: str, latency_ms: float | None) -> None:
    endpoint.last_status = status
    endpoint.last_checked_at = timezone.now()
    endpoint.last_latency_ms = latency_ms
    endpoint.save(update_fields=["last_status", "last_checked_at", "last_latency_ms", "updated_at"])

    logger.info(
        "Endpoint result persisted",
        extra={
            "endpoint_id": str(endpoint.id),
            "status": status,
            "latency_ms": latency_ms,
            "tenant": getattr(endpoint.tenant, "schema_name", "public"),
        },
    )


@shared_task(
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 3},
)
def ping_endpoint(self, endpoint_id: str, tenant_schema: str) -> None:
    """
    Perform an HTTP GET request against the endpoint and persist the result.

    Automatically retries on network errors with exponential backoff.
    After max retries, notifies about permanent failure.
    """

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

            # Check if this is the final retry
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

            # If this is the final retry, notify about permanent failure
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

                # Schedule notification task (non-blocking)
                try:
                    notify_endpoint_failure.delay(
                        endpoint_id,
                        tenant_schema,
                        endpoint.url,
                        str(exc),
                    )
                except Exception as notification_error:
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
            _record_result(endpoint, status, latency_ms)

    connection.set_schema_to_public()  # type: ignore[attr-defined]


@shared_task
def notify_endpoint_failure(
    endpoint_id: str,
    tenant_schema: str,
    url: str,
    error_message: str,
) -> None:
    """
    Notify about permanent endpoint failure after retry exhaustion.

    This is the "dead letter queue" handler for monitoring failures.
    In future, this can send emails, webhooks, or Slack notifications.
    """
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

    # TODO: Implement actual notification mechanisms:
    # - Send email to tenant admin
    # - Send webhook to external monitoring systems
    # - Create incident in incident management system
    # - Update endpoint status to "permanently_failed"

    # For now, just ensure it's logged prominently
    audit_logger.critical(
        "Endpoint requires manual intervention",
        extra={
            "endpoint_id": endpoint_id,
            "tenant": tenant_schema,
            "url": url,
            "error": error_message,
        },
    )


def _is_endpoint_due(endpoint: Endpoint, now: datetime) -> tuple[bool, datetime]:
    """Return whether the endpoint should be enqueued along with the reference timestamp."""

    interval = timedelta(minutes=endpoint.interval_minutes)
    last_checked = endpoint.last_checked_at or endpoint.created_at
    last_enqueued = endpoint.last_enqueued_at

    # Determine if we have recently enqueued a task that might still be pending.
    pending_recently = False
    if last_enqueued is not None:
        baseline = endpoint.last_checked_at or endpoint.created_at
        if baseline is None or last_enqueued >= baseline:
            pending_recently = (now - last_enqueued) < PENDING_REQUEUE_GRACE

    if last_checked is None:
        last_checked = now - interval

    overdue = (now - last_checked) >= interval

    if overdue and not pending_recently:
        reference = endpoint.last_checked_at or endpoint.created_at or now
        return True, reference

    reference = last_enqueued or endpoint.last_checked_at or endpoint.created_at or now
    return False, reference


@shared_task(bind=True)
def schedule_endpoint_checks(self) -> int:
    """
    Inspect tenant endpoints and enqueue ping tasks when their interval elapses.

    Uses select_for_update() to prevent race conditions when multiple scheduler
    instances run concurrently.

    Optimized for scale with batch processing and early filtering.
    """

    now = timezone.now()
    scheduled = 0
    skipped_tenants = []
    failed_tenants = []

    # Ensure we start from the public schema before iterating tenants.
    connection.set_schema_to_public()  # type: ignore[attr-defined]
    tenants = Client.objects.exclude(schema_name="public")

    audit_logger.info(
        "Starting endpoint scheduling cycle",
        extra={
            "total_tenants": tenants.count(),
            "timestamp": now.isoformat(),
        },
    )

    # Collect all endpoints to schedule across all tenants
    all_endpoints_to_schedule = []

    for tenant in tenants:
        try:
            # Pre-flight check: Verify tenant schema has required tables
            with schema_context(tenant.schema_name):
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = current_schema()
                        AND table_name = 'monitors_endpoint'
                    )
                """
                )
                table_exists = cursor.fetchone()[0]

                if not table_exists:
                    audit_logger.warning(
                        "Skipping tenant - monitors_endpoint table does not exist",
                        extra={
                            "tenant": tenant.schema_name,
                            "reason": "missing_table",
                            "recommendation": f"Run migrations: python manage.py migrate_schemas --schema={tenant.schema_name}",
                        },
                    )
                    skipped_tenants.append(tenant.schema_name)
                    continue

                # Optimize: Use select_for_update to prevent race conditions
                # Lock endpoints to prevent concurrent scheduler runs from
                # scheduling the same endpoint multiple times
                # NOTE: select_for_update requires a transaction
                with transaction.atomic():
                    endpoints = Endpoint.objects.select_for_update(skip_locked=True).only(
                        "id",
                        "url",
                        "interval_minutes",
                        "last_checked_at",
                        "last_enqueued_at",
                        "created_at",
                        "tenant_id",
                    )  # Don't use iterator() inside transaction - it breaks locking

                    for endpoint in endpoints:
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
                            audit_logger.info(
                                "Endpoint not due",
                                extra={
                                    "tenant": tenant.schema_name,
                                    "endpoint_id": str(endpoint.id),
                                    "reference": reference.isoformat(),
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
                            continue

                        # Update timestamp and collect for scheduling after transaction
                        endpoint.last_enqueued_at = now
                        endpoint.save(update_fields=["last_enqueued_at", "updated_at"])

                        all_endpoints_to_schedule.append(
                            {
                                "id": str(endpoint.id),
                                "url": endpoint.url,
                                "interval_minutes": endpoint.interval_minutes,
                                "reference": reference,
                                "tenant_schema": tenant.schema_name,
                            }
                        )

        except Exception as e:
            # Catch any errors for this tenant and continue with others
            audit_logger.error(
                "Failed to schedule endpoints for tenant",
                extra={
                    "tenant": tenant.schema_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "recommendation": "Check tenant schema integrity and run migrations if needed",
                },
                exc_info=True,
            )
            failed_tenants.append({"schema": tenant.schema_name, "error": str(e)})
            continue  # Skip this tenant, process others

    # All transactions committed and schema contexts exited
    # Now queue tasks outside any database context
    connection.set_schema_to_public()  # type: ignore[attr-defined]

    for endpoint_data in all_endpoints_to_schedule:
        async_result = ping_endpoint.delay(endpoint_data["id"], endpoint_data["tenant_schema"])
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
                "tenant": endpoint_data["tenant_schema"],
                "endpoint_id": endpoint_data["id"],
                "url": endpoint_data["url"],
                "interval_minutes": endpoint_data["interval_minutes"],
                "task_id": getattr(self.request, "id", None),
                "ping_task_id": ping_task_id,
            },
        )

        latency_ms = max(0.0, (now - endpoint_data["reference"]).total_seconds() * 1000)
        performance_logger.info(
            "Endpoint scheduling latency",
            extra={
                "endpoint_id": endpoint_data["id"],
                "url": endpoint_data["url"],
                "latency_ms": latency_ms,
                "tenant": endpoint_data["tenant_schema"],
                "reference": endpoint_data["reference"].isoformat(),
                "scheduled_at": now.isoformat(),
            },
        )

    logger.info(
        "Endpoint scheduler run completed",
        extra={
            "scheduled": scheduled,
            "task_id": getattr(self.request, "id", None),
            "tenant_count": tenants.count(),
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
