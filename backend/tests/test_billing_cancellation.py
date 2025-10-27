"""Tests for API-driven subscription cancellation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from api.exceptions import PaymentProcessingError
from django.contrib.auth import get_user_model
from django.test import override_settings
from django_tenants.utils import schema_context
from rest_framework.test import APIClient
from stripe import _error as stripe_error
from tenants.models import Client, SubscriptionStatus

User = get_user_model()


@pytest.fixture
def tenant_user(db):
    with schema_context("test_tenant"):
        user = User.objects.create_user(
            username="cancel.user@example.com",
            email="cancel.user@example.com",
            password="CancelPassw0rd!",
        )

    yield user

    with schema_context("test_tenant"):
        User.objects.filter(id=user.id).delete()


def _authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.defaults["HTTP_HOST"] = "test.localhost"
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db(transaction=True)
@override_settings(STRIPE_SECRET_KEY="sk_test_secret")
def test_cancel_subscription_succeeds(tenant_user):
    tenant = Client.objects.get(schema_name="test_tenant")
    tenant.subscription_status = SubscriptionStatus.PRO
    tenant.stripe_customer_id = "cus_active_123"
    tenant.save(update_fields=["subscription_status", "stripe_customer_id"])

    client = _authenticated_client(tenant_user)

    with (
        patch("payments.views.stripe.Subscription.list") as list_mock,
        patch("payments.views.stripe.Subscription.delete") as delete_mock,
        patch("payments.views.log_audit_event") as audit_mock,
    ):
        list_mock.return_value = SimpleNamespace(data=[{"id": "sub_123", "status": "active"}])
        delete_mock.return_value = MagicMock(id="sub_123", status="canceled")

        response = client.post("/api/billing/cancel/", format="json")

    assert response.status_code == 200
    assert response.json() == {"plan": SubscriptionStatus.FREE}

    tenant.refresh_from_db()
    assert tenant.subscription_status == SubscriptionStatus.FREE

    list_mock.assert_called_once_with(
        customer="cus_active_123",
        status="all",
        limit=5,
    )
    delete_mock.assert_called_once_with("sub_123")
    audit_mock.assert_called_once()


@pytest.mark.django_db(transaction=True)
@override_settings(STRIPE_SECRET_KEY="sk_test_secret")
def test_cancel_subscription_handles_missing_active_subscription(tenant_user):
    tenant = Client.objects.get(schema_name="test_tenant")
    tenant.subscription_status = SubscriptionStatus.PRO
    tenant.stripe_customer_id = "cus_missing_sub"
    tenant.save(update_fields=["subscription_status", "stripe_customer_id"])

    client = _authenticated_client(tenant_user)

    with (
        patch("payments.views.stripe.Subscription.list") as list_mock,
        patch("payments.views.stripe.Subscription.delete") as delete_mock,
    ):
        list_mock.return_value = SimpleNamespace(data=[])

        response = client.post("/api/billing/cancel/", format="json")

    assert response.status_code == 200
    assert response.json() == {"plan": SubscriptionStatus.FREE}

    tenant.refresh_from_db()
    assert tenant.subscription_status == SubscriptionStatus.FREE

    list_mock.assert_called_once()
    delete_mock.assert_not_called()


@pytest.mark.django_db(transaction=True)
@override_settings(STRIPE_SECRET_KEY="sk_test_secret")
def test_cancel_subscription_requires_customer_id(tenant_user):
    tenant = Client.objects.get(schema_name="test_tenant")
    tenant.subscription_status = SubscriptionStatus.PRO
    tenant.stripe_customer_id = None
    tenant.save(update_fields=["subscription_status", "stripe_customer_id"])

    client = _authenticated_client(tenant_user)

    with patch("payments.views.stripe.Subscription.list") as list_mock:
        response = client.post("/api/billing/cancel/", format="json")

    assert response.status_code == 409
    assert "detail" in response.json()
    list_mock.assert_not_called()


@pytest.mark.django_db(transaction=True)
@override_settings(STRIPE_SECRET_KEY="sk_test_secret")
def test_cancel_subscription_surfaces_stripe_errors(tenant_user):
    tenant = Client.objects.get(schema_name="test_tenant")
    tenant.subscription_status = SubscriptionStatus.PRO
    tenant.stripe_customer_id = "cus_active_err"
    tenant.save(update_fields=["subscription_status", "stripe_customer_id"])

    client = _authenticated_client(tenant_user)

    with patch("payments.views.stripe.Subscription.list") as list_mock:
        list_mock.side_effect = stripe_error.APIConnectionError("timeout")
        response = client.post("/api/billing/cancel/", format="json")

    assert response.status_code == PaymentProcessingError.status_code
    data = response.json()
    assert data["detail"] == "Unable to contact the payment processor. Please try again shortly."
