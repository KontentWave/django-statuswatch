"""Monitoring scheduling helpers shared by Celery tasks and future services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import schema_context
from monitors.models import Endpoint
from tenants.models import Client

PENDING_REQUEUE_GRACE = timedelta(seconds=settings.PENDING_REQUEUE_GRACE_SECONDS)


@dataclass(slots=True, frozen=True)
class ScheduledEndpoint:
    """Captured endpoint metadata used to enqueue ping tasks."""

    id: str
    url: str
    interval_minutes: int
    reference: datetime
    tenant_schema: str


def record_result(endpoint: Endpoint, status: str, latency_ms: float | None) -> None:
    """Persist ping results while keeping a consistent log contract."""

    endpoint.last_status = status
    endpoint.last_checked_at = timezone.now()
    endpoint.last_latency_ms = latency_ms
    endpoint.save(update_fields=["last_status", "last_checked_at", "last_latency_ms", "updated_at"])


def collect_due_endpoints(
    now: datetime,
    *,
    audit_logger,
) -> tuple[list[ScheduledEndpoint], list[str], list[dict[str, str]], int]:
    """Inspect every tenant and return the endpoints that should be enqueued."""

    connection.set_schema_to_public()  # type: ignore[attr-defined]
    tenants = Client.objects.exclude(schema_name="public")

    audit_logger.info(
        "Starting endpoint scheduling cycle",
        extra={
            "total_tenants": tenants.count(),
            "timestamp": now.isoformat(),
        },
    )

    scheduled: list[ScheduledEndpoint] = []
    skipped_tenants: list[str] = []
    failed_tenants: list[dict[str, str]] = []

    for tenant in tenants:
        try:
            with schema_context(tenant.schema_name):
                if not _tenant_table_exists():
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

                with transaction.atomic():
                    endpoints = Endpoint.objects.select_for_update(skip_locked=True).only(
                        "id",
                        "url",
                        "interval_minutes",
                        "last_checked_at",
                        "last_enqueued_at",
                        "created_at",
                        "tenant_id",
                    )

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

                        endpoint.last_enqueued_at = now
                        endpoint.save(update_fields=["last_enqueued_at", "updated_at"])

                        scheduled.append(
                            ScheduledEndpoint(
                                id=str(endpoint.id),
                                url=endpoint.url,
                                interval_minutes=endpoint.interval_minutes,
                                reference=reference,
                                tenant_schema=tenant.schema_name,
                            )
                        )

        except Exception as exc:  # noqa: BLE001
            audit_logger.error(
                "Failed to schedule endpoints for tenant",
                extra={
                    "tenant": tenant.schema_name,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "recommendation": "Check tenant schema integrity and run migrations if needed",
                },
                exc_info=True,
            )
            failed_tenants.append({"schema": tenant.schema_name, "error": str(exc)})
            continue

    connection.set_schema_to_public()  # type: ignore[attr-defined]
    return scheduled, skipped_tenants, failed_tenants, tenants.count()


def _tenant_table_exists() -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = current_schema()
                AND table_name = 'monitors_endpoint'
            )
        """
        )
        exists = cursor.fetchone()
    return bool(exists and exists[0])


def _is_endpoint_due(endpoint: Endpoint, now: datetime) -> tuple[bool, datetime]:
    interval = timedelta(minutes=endpoint.interval_minutes)
    last_checked = endpoint.last_checked_at or endpoint.created_at
    last_enqueued = endpoint.last_enqueued_at

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


__all__ = [
    "ScheduledEndpoint",
    "collect_due_endpoints",
    "record_result",
]
