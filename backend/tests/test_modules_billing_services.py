"""Unit tests for modules.billing.services."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from modules.billing.services import (
    BillingWebhookResult,
    cancel_active_subscription,
    create_billing_portal_session,
    create_subscription_checkout_session,
    dispatch_billing_webhook_event,
)
from tenants.models import SubscriptionStatus


class TenantStub:
    def __init__(self, schema_name: str = "acme", stripe_customer_id: str | None = None):
        self.schema_name = schema_name
        self.stripe_customer_id = stripe_customer_id
        self.subscription_status = SubscriptionStatus.FREE
        self.saved_fields: list[list[str]] = []

    def save(self, update_fields: list[str] | None = None):
        self.saved_fields.append(update_fields or [])


class StripeStub:
    def __init__(self):
        self.api_key: str | None = None
        self.customer_list_calls: list[dict] = []
        self.customer_create_calls: list[dict] = []
        self.checkout_calls: list[dict] = []
        self.portal_calls: list[dict] = []
        self.subscription_list_calls: list[dict] = []
        self.subscription_delete_calls: list[dict] = []

        self.Customer = SimpleNamespace(
            list=self._customer_list,
            create=self._customer_create,
        )
        self.checkout = SimpleNamespace(Session=SimpleNamespace(create=self._checkout_create))
        self.billing_portal = SimpleNamespace(Session=SimpleNamespace(create=self._portal_create))
        self.Subscription = SimpleNamespace(
            list=self._subscription_list,
            delete=self._subscription_delete,
        )

        self._customer_list_response = SimpleNamespace(data=[])
        self._customer_create_response = SimpleNamespace(id="cus_new")
        self._checkout_response = SimpleNamespace(id="cs_test", url="https://stripe/session")
        self._portal_response = SimpleNamespace(id="bps_test", url="https://stripe/portal")
        self._subscription_list_response = SimpleNamespace(data=[])

    # Stripe customer helpers
    def _customer_list(self, **kwargs):
        self.customer_list_calls.append(kwargs)
        return self._customer_list_response

    def _customer_create(self, **kwargs):
        self.customer_create_calls.append(kwargs)
        return self._customer_create_response

    # Checkout helpers
    def _checkout_create(self, **kwargs):
        self.checkout_calls.append(kwargs)
        return self._checkout_response

    # Portal helpers
    def _portal_create(self, **kwargs):
        self.portal_calls.append(kwargs)
        return self._portal_response

    # Subscription helpers
    def _subscription_list(self, **kwargs):
        self.subscription_list_calls.append(kwargs)
        return self._subscription_list_response

    def _subscription_delete(self, subscription_id):
        self.subscription_delete_calls.append(subscription_id)
        return SimpleNamespace(id=subscription_id, status="canceled")


@pytest.mark.django_db
def test_create_subscription_checkout_session_creates_customer_and_session():
    tenant = TenantStub(schema_name="acme")
    stripe_stub = StripeStub()
    user = SimpleNamespace(id=1, email="owner@example.com", username="owner")

    result = create_subscription_checkout_session(
        stripe_secret_key="sk_test",
        tenant=tenant,
        user=user,
        plan="pro",
        price_id="price_pro",
        success_url="https://app/billing/success",
        cancel_url="https://app/billing/cancel",
        stripe_api=stripe_stub,
    )

    assert result.url == "https://stripe/session"
    assert result.session_id == "cs_test"
    assert result.customer_origin in {"created", "email_only"}
    assert stripe_stub.api_key == "sk_test"
    assert stripe_stub.checkout_calls[-1]["metadata"]["plan"] == "pro"
    assert tenant.stripe_customer_id == "cus_new"
    assert tenant.saved_fields == [["stripe_customer_id"]]


@pytest.mark.django_db
def test_create_billing_portal_session_uses_existing_customer():
    stripe_stub = StripeStub()

    result = create_billing_portal_session(
        stripe_secret_key="sk_test",
        customer_id="cus_existing",
        return_url="https://app/billing",
        stripe_api=stripe_stub,
    )

    assert result.url == "https://stripe/portal"
    assert stripe_stub.portal_calls[-1]["customer"] == "cus_existing"
    assert stripe_stub.portal_calls[-1]["return_url"] == "https://app/billing"


@pytest.mark.django_db
def test_cancel_active_subscription_updates_status_and_deletes_remote():
    tenant = TenantStub(schema_name="acme", stripe_customer_id="cus_active")
    tenant.subscription_status = SubscriptionStatus.PRO
    stripe_stub = StripeStub()
    stripe_stub._subscription_list_response = SimpleNamespace(
        data=[{"id": "sub_123", "status": "active"}]
    )

    result = cancel_active_subscription(
        stripe_secret_key="sk_test",
        tenant=tenant,
        cancelable_statuses={"active"},
        stripe_api=stripe_stub,
    )

    assert result.subscription_id == "sub_123"
    assert result.remote_cancelled is True
    assert tenant.subscription_status == SubscriptionStatus.FREE
    assert stripe_stub.subscription_delete_calls == ["sub_123"]


class FakeClientManager:
    def __init__(self, tenant: TenantStub | None):
        self._tenant = tenant

    def filter(self, schema_name: str):
        tenant = self._tenant if self._tenant and self._tenant.schema_name == schema_name else None
        return SimpleNamespace(first=lambda: tenant)


class FakeClientModel:
    def __init__(self, tenant: TenantStub | None):
        self.objects = FakeClientManager(tenant)


def test_dispatch_billing_webhook_event_promotes_tenant():
    tenant = TenantStub(schema_name="acme")
    client_model = FakeClientModel(tenant)
    event = {
        "id": "evt_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_123",
                "metadata": {"tenant_schema": "acme"},
                "customer": "cus_123",
            }
        },
    }

    result = dispatch_billing_webhook_event(event, client_model=client_model)

    assert isinstance(result, BillingWebhookResult)
    assert result.handled is True
    assert result.new_status == SubscriptionStatus.PRO
    assert tenant.subscription_status == SubscriptionStatus.PRO
    assert tenant.stripe_customer_id == "cus_123"
