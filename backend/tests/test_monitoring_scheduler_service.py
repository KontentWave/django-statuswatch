"""Deterministic unit tests for the monitoring scheduler helpers."""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context
from modules.monitoring import scheduler as monitoring_scheduler
from modules.monitoring.scheduler import _is_endpoint_due, collect_due_endpoints, record_result
from monitors.models import Endpoint
from tenants.models import Client


@pytest.mark.django_db(transaction=True)
def test_is_endpoint_due_flags_overdue_endpoint(tenant_factory):
    tenant = tenant_factory("Scheduler Service Tenant")

    overdue = timezone.now() - timedelta(minutes=10)

    with schema_context(tenant.schema_name):
        endpoint = Endpoint.objects.create(
            tenant=tenant,
            name="API Health",
            url="https://scheduler.example.com/health",
            interval_minutes=2,
            last_status="ok",
            last_checked_at=overdue,
            last_enqueued_at=None,
        )

    is_due, reference = _is_endpoint_due(endpoint, timezone.now())

    assert is_due is True
    assert reference == overdue


@pytest.mark.django_db(transaction=True)
def test_is_endpoint_due_respects_pending_grace(tenant_factory):
    tenant = tenant_factory("Scheduler Grace Tenant")

    overdue = timezone.now() - timedelta(minutes=10)
    recent_enqueue = timezone.now() - timedelta(seconds=5)

    with schema_context(tenant.schema_name):
        endpoint = Endpoint.objects.create(
            tenant=tenant,
            name="Grace API",
            url="https://scheduler.example.com/grace",
            interval_minutes=2,
            last_status="ok",
            last_checked_at=overdue,
            last_enqueued_at=recent_enqueue,
        )

    is_due, _ = _is_endpoint_due(endpoint, timezone.now())

    assert is_due is False


@pytest.mark.django_db(transaction=True)
def test_record_result_updates_endpoint_fields(tenant_factory):
    tenant = tenant_factory("Scheduler Result Tenant")

    with schema_context(tenant.schema_name):
        endpoint = Endpoint.objects.create(
            tenant=tenant,
            name="Result API",
            url="https://scheduler.example.com/result",
            interval_minutes=5,
            last_status="unknown",
        )

        record_result(endpoint, status="200", latency_ms=123.45)

    with schema_context(tenant.schema_name):
        endpoint.refresh_from_db()
        assert endpoint.last_status == "200"
        assert endpoint.last_latency_ms == pytest.approx(123.45)
        assert endpoint.last_checked_at is not None


@pytest.mark.django_db(transaction=True)
def test_collect_due_endpoints_handles_scheduled_skipped_and_failed_tenants(
    tenant_factory, monkeypatch
):
    active_tenant = tenant_factory("Scheduler Active Tenant")
    skip_tenant = tenant_factory("Scheduler Skip Tenant")
    failing_tenant = tenant_factory("Scheduler Failing Tenant")

    with schema_context(active_tenant.schema_name):
        overdue = timezone.now() - timedelta(minutes=10)
        due_endpoint = Endpoint.objects.create(
            tenant=active_tenant,
            name="Scheduler Target",
            url="https://scheduler.example.com/target",
            interval_minutes=5,
            last_status="ok",
            last_checked_at=overdue,
            last_enqueued_at=None,
        )
        Endpoint.objects.create(
            tenant=active_tenant,
            name="Scheduler Fresh",
            url="https://scheduler.example.com/fresh",
            interval_minutes=60,
            last_status="ok",
            last_checked_at=timezone.now(),
            last_enqueued_at=timezone.now(),
        )

    skip_schema = skip_tenant.schema_name
    failing_schema = failing_tenant.schema_name

    original_table_exists = monitoring_scheduler._tenant_table_exists

    def fake_table_exists():
        if connection.schema_name == skip_schema:
            return False
        return original_table_exists()

    monkeypatch.setattr(monitoring_scheduler, "_tenant_table_exists", fake_table_exists)

    original_select_for_update = monitoring_scheduler.Endpoint.objects.select_for_update

    def fake_select_for_update(*args, **kwargs):
        queryset = original_select_for_update(*args, **kwargs)
        if connection.schema_name == failing_schema:
            raise RuntimeError("scheduler failure")
        return queryset

    monkeypatch.setattr(
        monitoring_scheduler.Endpoint.objects,
        "select_for_update",
        fake_select_for_update,
    )

    existing_tenants = Client.objects.exclude(schema_name="public").count()

    now = timezone.now()
    audit_logger = logging.getLogger("monitors.audit")
    scheduled, skipped, failed, tenant_count = collect_due_endpoints(now, audit_logger=audit_logger)

    assert tenant_count == existing_tenants
    assert skipped == [skip_schema]
    assert failed == [{"schema": failing_schema, "error": "scheduler failure"}]

    scheduled_ids = {payload.id for payload in scheduled}
    assert scheduled_ids == {str(due_endpoint.id)}

    payload = scheduled[0]
    assert payload.tenant_schema == active_tenant.schema_name
    assert payload.interval_minutes == 5
    assert payload.reference <= now


@pytest.mark.django_db(transaction=True)
def test_collect_due_endpoints_updates_last_enqueued(tenant_factory):
    tenant = tenant_factory("Scheduler Enqueue Tenant")

    overdue = timezone.now() - timedelta(minutes=10)

    with schema_context(tenant.schema_name):
        endpoint = Endpoint.objects.create(
            tenant=tenant,
            name="Scheduler Update",
            url="https://scheduler.example.com/update",
            interval_minutes=5,
            last_status="ok",
            last_checked_at=overdue,
            last_enqueued_at=overdue,
        )

    audit_logger = logging.getLogger("monitors.audit")
    collect_due_endpoints(timezone.now(), audit_logger=audit_logger)

    with schema_context(tenant.schema_name):
        endpoint.refresh_from_db()
        assert endpoint.last_enqueued_at is not None
        assert endpoint.last_enqueued_at > overdue
