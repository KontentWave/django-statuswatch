"""Tests for Stripe webhook endpoint handling subscription updates."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from stripe import _error as stripe_error
from tenants.models import Client


@pytest.fixture
def tenant(db) -> Client:
    client = Client.objects.filter(schema_name="test_tenant").first()
    assert client is not None, "test_tenant fixture should provision default tenant"
    return client


def _post_webhook(payload: dict[str, Any], signature: str = "whsec_test"):
    client = APIClient()
    response = client.post(
        "/api/billing/webhook/",
        data=payload,
        format="json",
        HTTP_STRIPE_SIGNATURE=signature,
    )
    return response


@pytest.mark.django_db(transaction=True)
@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
@patch("payments.views.stripe.Webhook.construct_event")
def test_checkout_session_completed_promotes_tenant(mock_construct_event, tenant):
    payload = {
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"tenant_schema": tenant.schema_name}}},
    }
    mock_construct_event.return_value = payload

    response = _post_webhook(payload)

    assert response.status_code == 200
    tenant.refresh_from_db()
    assert tenant.subscription_status == "pro"


@pytest.mark.django_db(transaction=True)
@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
@patch("payments.views.stripe.Webhook.construct_event")
def test_invoice_paid_promotes_tenant(mock_construct_event, tenant):
    payload = {
        "type": "invoice.paid",
        "data": {"object": {"metadata": {"tenant_schema": tenant.schema_name}}},
    }
    mock_construct_event.return_value = payload

    response = _post_webhook(payload)

    assert response.status_code == 200
    tenant.refresh_from_db()
    assert tenant.subscription_status == "pro"


@pytest.mark.django_db(transaction=True)
@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
@patch("payments.views.stripe.Webhook.construct_event")
def test_subscription_deleted_marks_tenant_cancelled(mock_construct_event, tenant):
    payload = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"metadata": {"tenant_schema": tenant.schema_name}}},
    }
    mock_construct_event.return_value = payload

    tenant.subscription_status = "pro"
    tenant.save()

    response = _post_webhook(payload)

    assert response.status_code == 200
    tenant.refresh_from_db()
    assert tenant.subscription_status == "canceled"


@pytest.mark.django_db(transaction=True)
@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
@patch("payments.views.stripe.Webhook.construct_event")
def test_invalid_signature_returns_400(mock_construct_event, tenant):
    mock_construct_event.side_effect = stripe_error.SignatureVerificationError(
        "bad signature", "payload"
    )

    response = _post_webhook({"type": "invoice.paid"}, signature="invalid")

    assert response.status_code == 400
    tenant.refresh_from_db()
    assert tenant.subscription_status == "free"


@pytest.mark.django_db(transaction=True)
@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
@patch("payments.views.stripe.Webhook.construct_event")
def test_unknown_event_returns_202_and_noop(mock_construct_event, tenant):
    payload = {
        "type": "random.event",
        "data": {"object": {"metadata": {"tenant_schema": tenant.schema_name}}},
    }
    mock_construct_event.return_value = payload

    response = _post_webhook(payload)

    assert response.status_code == 202
    tenant.refresh_from_db()
    assert tenant.subscription_status == "free"
