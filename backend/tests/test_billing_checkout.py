"""Tests for Stripe subscription checkout endpoint."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django_tenants.utils import schema_context
from rest_framework.test import APIClient
from stripe import _error as stripe_error

User = get_user_model()


@pytest.fixture
def tenant_user(db):
    """Create a user inside the default test tenant schema."""

    with schema_context("test_tenant"):
        user = User.objects.create_user(
            username="jane.doe@example.com",
            email="jane.doe@example.com",
            password="SafePassw0rd!",
        )

    yield user

    with schema_context("test_tenant"):
        User.objects.filter(id=user.id).delete()


def _authenticated_client(user: User) -> APIClient:
    """Return an API client authenticated as the given user."""

    client = APIClient()
    client.defaults["HTTP_HOST"] = "test.localhost"
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_returns_stripe_url(mock_create, tenant_user, caplog):
    """Authenticated users receive a Stripe Checkout URL for the Pro plan."""

    mock_create.return_value = MagicMock(
        id="cs_test_123",
        url="https://stripe.test/checkout/cs_test_123",
    )

    caplog.set_level(logging.INFO, logger="payments.checkout")
    checkout_logger = logging.getLogger("payments.checkout")
    checkout_logger.addHandler(caplog.handler)

    client = _authenticated_client(tenant_user)
    try:
        with caplog.at_level(logging.INFO, logger="payments.checkout"):
            response = client.post(
                "/api/billing/create-checkout-session/",
                {"plan": "pro"},
                format="json",
            )
    finally:
        checkout_logger.removeHandler(caplog.handler)

    assert response.status_code == 201
    assert response.json() == {"url": "https://stripe.test/checkout/cs_test_123"}

    mock_create.assert_called_once()
    _, kwargs = mock_create.call_args

    assert kwargs["mode"] == "subscription"
    assert kwargs["line_items"] == [{"price": "price_test_pro", "quantity": 1}]
    assert kwargs["customer_email"] == "jane.doe@example.com"
    assert kwargs["metadata"]["tenant_schema"] == "test_tenant"
    assert kwargs["metadata"]["user_id"] == str(tenant_user.id)
    assert kwargs["success_url"] == (
        "https://app.statuswatch.local/billing/success?session_id={CHECKOUT_SESSION_ID}"
    )
    assert kwargs["cancel_url"] == "https://app.statuswatch.local/billing/cancel"

    checkout_records = [record for record in caplog.records if record.name == "payments.checkout"]
    log_messages = [record.getMessage() for record in checkout_records]

    assert any("Created Stripe checkout session" in message for message in log_messages)
    assert any("tenant=test_tenant" in message for message in log_messages)
    assert any("session_id=cs_test_123" in message for message in log_messages)

    structured_records = [
        record
        for record in checkout_records
        if "Created Stripe checkout session" in record.getMessage()
    ]
    assert structured_records, "No structured payments.checkout log record was captured"
    structured_record = structured_records[-1]

    assert structured_record.tenant_schema == "test_tenant"
    assert structured_record.plan == "pro"
    assert structured_record.user_id == tenant_user.id
    assert structured_record.session_id == "cs_test_123"
    assert structured_record.checkout_mode == "subscription"


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_validates_plan(mock_create, tenant_user):
    """Unknown plans should produce a 400 response without calling Stripe."""

    client = _authenticated_client(tenant_user)
    response = client.post(
        "/api/billing/create-checkout-session/",
        {"plan": "enterprise"},
        format="json",
    )

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "enterprise" in data["detail"]
    mock_create.assert_not_called()


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_requires_authentication(mock_create):
    """Unauthenticated requests should be rejected with 401."""

    client = APIClient()
    client.defaults["HTTP_HOST"] = "test.localhost"

    response = client.post(
        "/api/billing/create-checkout-session/",
        {"plan": "pro"},
        format="json",
    )

    assert response.status_code == 401
    mock_create.assert_not_called()


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_missing_price_configuration(mock_create, tenant_user):
    """Missing price configuration yields a configuration error."""

    client = _authenticated_client(tenant_user)
    response = client.post(
        "/api/billing/create-checkout-session/",
        {"plan": "pro"},
        format="json",
    )

    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert isinstance(data["error"], dict)
    assert "message" in data["error"]
    mock_create.assert_not_called()


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_requires_secret_key(mock_create, tenant_user):
    """Configuration error is raised if the Stripe secret key is missing."""

    client = _authenticated_client(tenant_user)

    response = client.post(
        "/api/billing/create-checkout-session/",
        {"plan": "pro"},
        format="json",
    )

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_server_error"
    assert "Please try again" in body["error"]["message"]
    mock_create.assert_not_called()


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_handles_card_error(mock_create, tenant_user, caplog):
    """Card declines surface as a 400 with sanitized logging."""

    mock_create.side_effect = stripe_error.CardError(
        message="Card declined",
        param="",
        code="card_declined",
    )

    caplog.set_level(logging.WARNING, logger="payments.checkout")
    checkout_logger = logging.getLogger("payments.checkout")
    checkout_logger.addHandler(caplog.handler)

    client = _authenticated_client(tenant_user)
    try:
        with caplog.at_level(logging.WARNING, logger="payments.checkout"):
            response = client.post(
                "/api/billing/create-checkout-session/",
                {"plan": "pro"},
                format="json",
            )
    finally:
        checkout_logger.removeHandler(caplog.handler)

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Your payment method was declined. Please try a different payment method."
    )
    mock_create.assert_called_once()

    warning_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "payments.checkout" and record.levelno == logging.WARNING
    ]
    assert any("Stripe card error" in message for message in warning_messages)
    warning_records = [
        record
        for record in caplog.records
        if record.name == "payments.checkout" and record.levelno == logging.WARNING
    ]
    assert warning_records[-1].stripe_error_code == "card_declined"


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_handles_stripe_error(mock_create, tenant_user, caplog):
    """Generic Stripe failures return a 402 response and log context."""

    mock_create.side_effect = stripe_error.StripeError("stripe boom")

    caplog.set_level(logging.ERROR, logger="payments.checkout")
    checkout_logger = logging.getLogger("payments.checkout")
    checkout_logger.addHandler(caplog.handler)

    client = _authenticated_client(tenant_user)
    try:
        with caplog.at_level(logging.ERROR, logger="payments.checkout"):
            response = client.post(
                "/api/billing/create-checkout-session/",
                {"plan": "pro"},
                format="json",
            )
    finally:
        checkout_logger.removeHandler(caplog.handler)

    assert response.status_code == 402
    detail = response.json()["detail"]
    assert detail.startswith("Payment processing failed. Please check your payment method")
    assert detail.endswith("try again.")
    mock_create.assert_called_once()

    error_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "payments.checkout" and record.levelno >= logging.ERROR
    ]
    assert any("Stripe error" in message for message in error_messages)
    error_records = [
        record
        for record in caplog.records
        if record.name == "payments.checkout" and record.levelno >= logging.ERROR
    ]
    assert any("stripe boom" in record.getMessage() for record in error_records)
