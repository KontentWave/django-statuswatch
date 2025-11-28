"""Billing services that orchestrate Stripe calls and tenant updates."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import stripe
from tenants.models import Client, SubscriptionStatus


@dataclass(slots=True, frozen=True)
class BillingCheckoutSessionResult:
    """Outcome of the subscription checkout service call."""

    url: str
    session_id: str | None
    customer_id: str | None
    customer_origin: str
    metadata: dict[str, str]


@dataclass(slots=True, frozen=True)
class BillingPortalSessionResult:
    """Outcome of the billing portal session creation."""

    url: str
    session_id: str | None


@dataclass(slots=True, frozen=True)
class BillingCancellationResult:
    """Information about a subscription cancellation attempt."""

    plan: SubscriptionStatus
    previous_status: SubscriptionStatus
    new_status: SubscriptionStatus
    subscription_id: str | None
    remote_status: str | None
    remote_cancelled: bool
    customer_id: str | None


@dataclass(slots=True, frozen=True)
class BillingWebhookResult:
    """Structured outcome of processing a Stripe webhook event."""

    handled: bool
    status: str
    tenant_schema: str | None
    event_type: str
    event_id: str | None
    session_id: str | None
    subscription_id: str | None
    previous_status: SubscriptionStatus | None
    new_status: SubscriptionStatus | None
    customer_id: str | None


def create_subscription_checkout_session(
    *,
    stripe_secret_key: str,
    tenant: Client,
    user: Any,
    plan: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    stripe_api: Any | None = None,
) -> BillingCheckoutSessionResult:
    """Create or reuse a Stripe customer and start a subscription checkout session."""

    stripe_client = stripe_api or stripe
    stripe_client.api_key = stripe_secret_key

    tenant_schema = getattr(tenant, "schema_name", "public")
    tenant_customer_id = getattr(tenant, "stripe_customer_id", "") or ""
    customer_origin = "existing"
    customer_id = tenant_customer_id

    user_email = getattr(user, "email", None) or ""
    user_id = getattr(user, "id", None)

    if not customer_id:
        search_result = stripe_client.Customer.list(email=user_email, limit=1)
        if search_result and getattr(search_result, "data", None):
            customer = search_result.data[0]
            customer_id = getattr(customer, "id", "")
            customer_origin = "reused"

        if not customer_id:
            full_name = getattr(user, "get_full_name", lambda: "")() or (
                getattr(user, "username", "") or user_email
            )
            customer = stripe_client.Customer.create(
                email=user_email,
                name=full_name,
                metadata={
                    "tenant_schema": tenant_schema,
                    "user_id": str(user_id) if user_id is not None else "",
                },
            )
            customer_id = getattr(customer, "id", "")
            customer_origin = "created"

        if customer_id:
            tenant.stripe_customer_id = customer_id
            tenant.save(update_fields=["stripe_customer_id"])

    metadata = {
        "tenant_schema": tenant_schema,
        "user_id": str(user_id) if user_id is not None else "",
        "plan": plan,
    }

    checkout_payload: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "metadata": metadata,
        "success_url": success_url,
        "cancel_url": cancel_url,
    }

    if customer_id:
        checkout_payload["customer"] = customer_id
    else:
        checkout_payload["customer_creation"] = "always"
        checkout_payload["customer_email"] = user_email
        customer_origin = "email_only"

    session = stripe_client.checkout.Session.create(**checkout_payload)

    return BillingCheckoutSessionResult(
        url=getattr(session, "url", ""),
        session_id=getattr(session, "id", None),
        customer_id=customer_id,
        customer_origin=customer_origin,
        metadata=metadata,
    )


def create_billing_portal_session(
    *,
    stripe_secret_key: str,
    customer_id: str,
    return_url: str,
    stripe_api: Any | None = None,
) -> BillingPortalSessionResult:
    """Create a Stripe billing portal session for an existing customer."""

    stripe_client = stripe_api or stripe
    stripe_client.api_key = stripe_secret_key
    session = stripe_client.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return BillingPortalSessionResult(
        url=getattr(session, "url", ""),
        session_id=getattr(session, "id", None),
    )


def cancel_active_subscription(
    *,
    stripe_secret_key: str,
    tenant: Client,
    cancelable_statuses: Iterable[str],
    new_status: SubscriptionStatus = SubscriptionStatus.FREE,
    stripe_api: Any | None = None,
) -> BillingCancellationResult:
    """Cancel the tenant's active Stripe subscription if one exists."""

    stripe_client = stripe_api or stripe
    stripe_client.api_key = stripe_secret_key
    tenant_customer_id = getattr(tenant, "stripe_customer_id", "") or ""

    subscription_list = stripe_client.Subscription.list(
        customer=tenant_customer_id,
        status="all",
        limit=5,
    )

    cancelable = set(cancelable_statuses)
    subscription_to_cancel = None
    if subscription_list and getattr(subscription_list, "data", None):
        for item in subscription_list.data:
            status_value = (item or {}).get("status")
            if status_value in cancelable:
                subscription_to_cancel = item
                break

    remote_cancelled = False
    subscription_id = None
    remote_status = None

    if subscription_to_cancel is not None:
        subscription_id = subscription_to_cancel.get("id")
        remote_status = subscription_to_cancel.get("status")
        if subscription_id:
            stripe_client.Subscription.delete(subscription_id)
            remote_cancelled = True

    previous_status = tenant.subscription_status
    if previous_status != new_status:
        tenant.subscription_status = new_status
        tenant.save(update_fields=["subscription_status"])

    return BillingCancellationResult(
        plan=new_status,
        previous_status=previous_status,
        new_status=new_status,
        subscription_id=subscription_id,
        remote_status=remote_status,
        remote_cancelled=remote_cancelled,
        customer_id=tenant_customer_id or None,
    )


def dispatch_billing_webhook_event(
    event: dict,
    *,
    client_model: type[Client] = Client,
) -> BillingWebhookResult:
    """Update tenant subscription state based on a Stripe webhook event."""

    event_type = event.get("type", "unknown")
    event_id = event.get("id")
    session_id = _extract_session_id(event)
    tenant_schema = _extract_tenant_schema(event)
    customer_id = _extract_customer_id(event)
    subscription_id = _extract_subscription_id(event)

    if not tenant_schema:
        return BillingWebhookResult(
            handled=False,
            status="missing_metadata",
            tenant_schema=None,
            event_type=event_type,
            event_id=event_id,
            session_id=session_id,
            subscription_id=subscription_id,
            previous_status=None,
            new_status=None,
            customer_id=customer_id,
        )

    tenant = client_model.objects.filter(schema_name=tenant_schema).first()
    if tenant is None:
        return BillingWebhookResult(
            handled=False,
            status="tenant_not_found",
            tenant_schema=tenant_schema,
            event_type=event_type,
            event_id=event_id,
            session_id=session_id,
            subscription_id=subscription_id,
            previous_status=None,
            new_status=None,
            customer_id=customer_id,
        )

    target_status = _resolve_webhook_status(event_type)
    if target_status is None:
        return BillingWebhookResult(
            handled=False,
            status="ignored",
            tenant_schema=tenant_schema,
            event_type=event_type,
            event_id=event_id,
            session_id=session_id,
            subscription_id=subscription_id,
            previous_status=None,
            new_status=None,
            customer_id=customer_id,
        )

    previous_status = tenant.subscription_status
    updated_fields = ["subscription_status"]
    tenant.subscription_status = target_status

    if customer_id and tenant.stripe_customer_id != customer_id:
        tenant.stripe_customer_id = customer_id
        updated_fields.append("stripe_customer_id")

    tenant.save(update_fields=updated_fields)

    return BillingWebhookResult(
        handled=True,
        status="updated",
        tenant_schema=tenant_schema,
        event_type=event_type,
        event_id=event_id,
        session_id=session_id,
        subscription_id=subscription_id,
        previous_status=previous_status,
        new_status=target_status,
        customer_id=customer_id,
    )


def _extract_tenant_schema(event: dict) -> str | None:
    data_object = event.get("data", {}).get("object", {}) or {}
    metadata = data_object.get("metadata") or {}
    tenant_schema = metadata.get("tenant_schema") or metadata.get("tenant")
    return tenant_schema


def _extract_customer_id(event: dict) -> str | None:
    data_object = event.get("data", {}).get("object", {}) or {}
    customer = data_object.get("customer")
    if isinstance(customer, str) and customer.strip():
        return customer
    return None


def _extract_session_id(event: dict) -> str | None:
    return event.get("data", {}).get("object", {}).get("id")


def _extract_subscription_id(event: dict) -> str | None:
    return event.get("data", {}).get("object", {}).get("id")


def _resolve_webhook_status(event_type: str) -> SubscriptionStatus | None:
    if event_type in {"checkout.session.completed", "invoice.paid"}:
        return SubscriptionStatus.PRO
    if event_type == "customer.subscription.deleted":
        return SubscriptionStatus.FREE
    return None


__all__ = [
    "BillingCancellationResult",
    "BillingCheckoutSessionResult",
    "BillingPortalSessionResult",
    "BillingWebhookResult",
    "cancel_active_subscription",
    "create_billing_portal_session",
    "create_subscription_checkout_session",
    "dispatch_billing_webhook_event",
]
