import logging
from datetime import timedelta

import pytest
from django.utils import timezone
from django_tenants.utils import schema_context

from ..models import Endpoint
from ..tasks import schedule_endpoint_checks


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

    captured: list[str] = []
    monkeypatch.setattr(
        "monitors.tasks.ping_endpoint.delay", lambda endpoint_id: captured.append(endpoint_id)
    )

    caplog.clear()

    schedule_endpoint_checks()

    assert captured == [str(endpoint.id)]

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

    captured: list[str] = []
    monkeypatch.setattr(
        "monitors.tasks.ping_endpoint.delay", lambda endpoint_id: captured.append(endpoint_id)
    )

    schedule_endpoint_checks()

    assert captured == []
