import logging
from datetime import timedelta

import pytest
from django.utils import timezone
from django_tenants.utils import schema_context
from monitors.models import Endpoint
from monitors.tasks import PENDING_REQUEUE_GRACE, schedule_endpoint_checks


@pytest.fixture(autouse=True)
def _set_caplog_default_level(caplog):
    # Attach the capture handler directly because these loggers do not propagate to root.
    target_loggers = [
        logging.getLogger("monitors"),
        logging.getLogger("monitors.audit"),
        logging.getLogger("monitors.performance"),
    ]

    caplog.handler.setLevel(logging.DEBUG)

    for logger in target_loggers:
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)

    caplog.clear()
    yield
    caplog.clear()

    for logger in target_loggers:
        logger.removeHandler(caplog.handler)


@pytest.mark.django_db(transaction=True)
def test_scheduler_enqueues_due_endpoints(tenant_factory, caplog, monkeypatch):
    tenant = tenant_factory("Scheduler Tenant")

    overdue = timezone.now() - timedelta(minutes=10)

    with schema_context(tenant.schema_name):
        endpoint = Endpoint.objects.create(
            tenant=tenant,
            name="API Health",
            url="https://scheduler.example.com/health",
            interval_minutes=5,
            last_status="ok",
            last_checked_at=overdue,
            last_enqueued_at=overdue,
        )

    captured: list[tuple[str, str]] = []

    class DummyResult:
        def __init__(self, endpoint_id: str, tenant_schema: str) -> None:
            self.id = f"test-{tenant_schema}-{endpoint_id}"

    def record_call(endpoint_id: str, tenant_schema: str) -> DummyResult:
        captured.append((endpoint_id, tenant_schema))
        return DummyResult(endpoint_id, tenant_schema)

    monkeypatch.setattr("monitors.tasks.ping_endpoint.delay", record_call)

    caplog.clear()

    schedule_endpoint_checks()

    assert captured == [(str(endpoint.id), tenant.schema_name)]

    with schema_context(tenant.schema_name):
        endpoint.refresh_from_db()
        assert endpoint.last_enqueued_at is not None
        assert endpoint.last_enqueued_at > overdue

    audit_logs = [
        record.getMessage() for record in caplog.records if record.name == "monitors.audit"
    ]
    performance_logs = [
        record.getMessage() for record in caplog.records if record.name == "monitors.performance"
    ]

    assert any("Endpoint queued" in message or "queued" in message for message in audit_logs)
    assert any("scheduling latency" in message for message in performance_logs)


@pytest.mark.django_db(transaction=True)
def test_scheduler_skips_recent_endpoints(tenant_factory, monkeypatch):
    tenant = tenant_factory("Scheduler Idle Tenant")

    recent = timezone.now()

    with schema_context(tenant.schema_name):
        Endpoint.objects.create(
            tenant=tenant,
            name="Recent API",
            url="https://scheduler.example.com/recent",
            interval_minutes=30,
            last_status="ok",
            last_checked_at=recent,
            last_enqueued_at=recent,
        )

    captured: list[tuple[str, str]] = []

    class DummyResult:
        def __init__(self, endpoint_id: str, tenant_schema: str) -> None:
            self.id = f"test-{tenant_schema}-{endpoint_id}"

    def record_call(endpoint_id: str, tenant_schema: str) -> DummyResult:
        captured.append((endpoint_id, tenant_schema))
        return DummyResult(endpoint_id, tenant_schema)

    monkeypatch.setattr("monitors.tasks.ping_endpoint.delay", record_call)

    schedule_endpoint_checks()

    assert captured == []


@pytest.mark.django_db(transaction=True)
def test_scheduler_requeues_after_pending_grace(tenant_factory, monkeypatch):
    tenant = tenant_factory("Scheduler Grace Tenant")

    overdue = timezone.now() - timedelta(minutes=10)
    recent_enqueue = timezone.now() - timedelta(seconds=10)

    with schema_context(tenant.schema_name):
        endpoint = Endpoint.objects.create(
            tenant=tenant,
            name="Grace API",
            url="https://scheduler.example.com/grace",
            interval_minutes=5,
            last_status="ok",
            last_checked_at=overdue,
            last_enqueued_at=recent_enqueue,
        )

    captured: list[tuple[str, str]] = []

    class DummyResult:
        def __init__(self, endpoint_id: str, tenant_schema: str) -> None:
            self.id = f"test-{tenant_schema}-{endpoint_id}"

    def record_call(endpoint_id: str, tenant_schema: str) -> DummyResult:
        captured.append((endpoint_id, tenant_schema))
        return DummyResult(endpoint_id, tenant_schema)

    monkeypatch.setattr("monitors.tasks.ping_endpoint.delay", record_call)

    schedule_endpoint_checks()

    assert captured == []  # Still within grace window; no duplicate enqueue

    with schema_context(tenant.schema_name):
        endpoint.last_enqueued_at = timezone.now() - PENDING_REQUEUE_GRACE - timedelta(seconds=5)
        endpoint.save(update_fields=["last_enqueued_at", "updated_at"])

    schedule_endpoint_checks()

    assert captured == [(str(endpoint.id), tenant.schema_name)]
