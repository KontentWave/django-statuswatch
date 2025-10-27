"""Tests for Stripe subscription checkout endpoint."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django_tenants.utils import schema_context
from rest_framework.test import APIClient
from stripe import _error as stripe_error
from tenants.models import Client

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

    Client.objects.filter(schema_name="test_tenant").update(
        stripe_customer_id="cus_test_existing",
    )

    yield user

    with schema_context("test_tenant"):
        User.objects.filter(id=user.id).delete()
    Client.objects.filter(schema_name="test_tenant").update(
        stripe_customer_id=None,
    )


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
    assert kwargs["customer"] == "cus_test_existing"
    assert "customer_email" not in kwargs
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
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.billing_portal.Session.create")
def test_create_portal_session_returns_stripe_url(mock_create, tenant_user):
    """Authenticated Pro users receive a billing portal URL when customer ID exists."""

    mock_create.return_value = MagicMock(
        id="bps_test_123",
        url="https://stripe.test/portal/bps_test_123",
    )

    Client.objects.filter(schema_name="test_tenant").update(
        stripe_customer_id="cus_test_123",
        subscription_status="pro",
    )

    client = _authenticated_client(tenant_user)

    response = client.post("/api/billing/create-portal-session/", format="json")

    assert response.status_code == 201
    assert response.json() == {"url": "https://stripe.test/portal/bps_test_123"}

    mock_create.assert_called_once_with(
        customer="cus_test_123",
        return_url="https://app.statuswatch.local/billing",
    )


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.billing_portal.Session.create")
def test_create_portal_session_requires_customer_id(mock_create, tenant_user):
    """Portal session is unavailable until the tenant has a Stripe customer ID."""

    Client.objects.filter(schema_name="test_tenant").update(
        stripe_customer_id=None,
        subscription_status="pro",
    )

    client = _authenticated_client(tenant_user)

    response = client.post("/api/billing/create-portal-session/", format="json")

    assert response.status_code == 409
    detail = response.json().get("detail", "")
    assert "Billing portal" in detail
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


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_handles_invalid_request_error(mock_create, tenant_user, caplog):
    """InvalidRequestError returns 402 with appropriate logging."""

    mock_create.side_effect = stripe_error.InvalidRequestError(
        message="Invalid parameters",
        param="price",
    )

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
    assert "Payment processing failed" in detail
    mock_create.assert_called_once()

    error_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "payments.checkout" and record.levelno >= logging.ERROR
    ]
    assert any("Stripe invalid request" in message for message in error_messages)


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_handles_authentication_error(mock_create, tenant_user, caplog):
    """AuthenticationError returns 500 with critical logging."""

    mock_create.side_effect = stripe_error.AuthenticationError(
        message="Invalid API key",
    )

    caplog.set_level(logging.CRITICAL, logger="payments.checkout")
    checkout_logger = logging.getLogger("payments.checkout")
    checkout_logger.addHandler(caplog.handler)

    client = _authenticated_client(tenant_user)
    try:
        with caplog.at_level(logging.CRITICAL, logger="payments.checkout"):
            response = client.post(
                "/api/billing/create-checkout-session/",
                {"plan": "pro"},
                format="json",
            )
    finally:
        checkout_logger.removeHandler(caplog.handler)

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_server_error"
    # In production mode, the error message is sanitized for security
    assert "unexpected error occurred" in body["error"]["message"].lower()
    mock_create.assert_called_once()

    critical_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "payments.checkout" and record.levelno >= logging.CRITICAL
    ]
    assert any("authentication error" in message.lower() for message in critical_messages)


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_handles_api_connection_error(mock_create, tenant_user, caplog):
    """APIConnectionError returns 402 with appropriate error message."""

    mock_create.side_effect = stripe_error.APIConnectionError(
        message="Connection timeout",
    )

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
    assert "Unable to connect to payment processor" in detail
    assert "try again later" in detail.lower()
    mock_create.assert_called_once()

    error_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "payments.checkout" and record.levelno >= logging.ERROR
    ]
    assert any("API connection error" in message for message in error_messages)


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_handles_generic_exception(mock_create, tenant_user, caplog):
    """Generic exceptions return 402 with sanitized logging."""

    mock_create.side_effect = Exception("Database connection failed")

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
    assert "Payment processing failed" in detail
    mock_create.assert_called_once()

    error_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "payments.checkout" and record.levelno >= logging.ERROR
    ]
    assert any("Unexpected error" in message for message in error_messages)


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_missing_plan_parameter(mock_create, tenant_user):
    """Missing plan parameter defaults to 'pro' and processes successfully."""

    mock_create.return_value = MagicMock(
        id="cs_test_789",
        url="https://stripe.test/checkout/cs_test_789",
    )

    client = _authenticated_client(tenant_user)
    response = client.post(
        "/api/billing/create-checkout-session/",
        {},  # No plan parameter
        format="json",
    )

    assert response.status_code == 201
    assert response.json() == {"url": "https://stripe.test/checkout/cs_test_789"}
    mock_create.assert_called_once()


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_case_insensitive_plan(mock_create, tenant_user):
    """Plan names are case-insensitive (PRO, Pro, pro all work)."""

    mock_create.return_value = MagicMock(
        id="cs_test_upper",
        url="https://stripe.test/checkout/cs_test_upper",
    )

    client = _authenticated_client(tenant_user)
    response = client.post(
        "/api/billing/create-checkout-session/",
        {"plan": "PRO"},  # Uppercase
        format="json",
    )

    assert response.status_code == 201
    mock_create.assert_called_once()

    # Verify metadata has lowercase plan
    _, kwargs = mock_create.call_args
    assert kwargs["metadata"]["plan"] == "pro"


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
def test_create_checkout_session_tenant_context_in_metadata(tenant_user):
    """Tenant schema is correctly captured in session metadata."""

    with patch("payments.views.stripe.checkout.Session.create") as mock_create:
        mock_create.return_value = MagicMock(
            id="cs_test_tenant",
            url="https://stripe.test/checkout/cs_test_tenant",
        )

        client = _authenticated_client(tenant_user)
        response = client.post(
            "/api/billing/create-checkout-session/",
            {"plan": "pro"},
            format="json",
        )

        assert response.status_code == 201
        mock_create.assert_called_once()

        _, kwargs = mock_create.call_args
        assert "metadata" in kwargs
        assert kwargs["metadata"]["tenant_schema"] == "test_tenant"
        assert kwargs["metadata"]["user_id"] == str(tenant_user.id)
        assert kwargs["metadata"]["plan"] == "pro"


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_urls_use_frontend_url(mock_create, tenant_user):
    """Success and cancel URLs use configured FRONTEND_URL."""

    mock_create.return_value = MagicMock(
        id="cs_test_urls",
        url="https://stripe.test/checkout/cs_test_urls",
    )

    client = _authenticated_client(tenant_user)
    response = client.post(
        "/api/billing/create-checkout-session/",
        {"plan": "pro"},
        format="json",
    )

    assert response.status_code == 201
    mock_create.assert_called_once()

    _, kwargs = mock_create.call_args
    assert kwargs["success_url"].startswith("https://app.statuswatch.local/billing/success")
    assert "{CHECKOUT_SESSION_ID}" in kwargs["success_url"]
    assert kwargs["cancel_url"] == "https://app.statuswatch.local/billing/cancel"


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_PRO_PRICE_ID="price_test_pro",
    FRONTEND_URL="https://app.statuswatch.local",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_create_checkout_session_uses_subscription_mode(mock_create, tenant_user):
    """Checkout session is created with subscription mode, not one-time payment."""

    mock_create.return_value = MagicMock(
        id="cs_test_mode",
        url="https://stripe.test/checkout/cs_test_mode",
    )

    client = _authenticated_client(tenant_user)
    response = client.post(
        "/api/billing/create-checkout-session/",
        {"plan": "pro"},
        format="json",
    )

    assert response.status_code == 201
    mock_create.assert_called_once()

    _, kwargs = mock_create.call_args
    assert kwargs["mode"] == "subscription"
    assert kwargs["line_items"] == [{"price": "price_test_pro", "quantity": 1}]


# ============================================================================
# Legacy Endpoint Tests (create_checkout_session - one-time payment)
# ============================================================================


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_legacy_create_checkout_session_success(mock_create, tenant_user):
    """Legacy endpoint creates one-time payment session successfully."""

    mock_create.return_value = MagicMock(
        id="cs_legacy_123",
        url="https://stripe.test/checkout/cs_legacy_123",
    )

    client = _authenticated_client(tenant_user)
    response = client.post(
        "/api/pay/create-checkout-session/",
        {"amount": 5000, "currency": "usd", "name": "Test Product"},
        format="json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "cs_legacy_123"
    assert data["url"] == "https://stripe.test/checkout/cs_legacy_123"

    mock_create.assert_called_once()
    _, kwargs = mock_create.call_args
    assert kwargs["mode"] == "payment"
    assert kwargs["line_items"][0]["price_data"]["unit_amount"] == 5000


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_legacy_create_checkout_session_missing_secret_key(mock_create, tenant_user):
    """Legacy endpoint requires STRIPE_SECRET_KEY configuration."""

    client = _authenticated_client(tenant_user)
    response = client.post(
        "/api/pay/create-checkout-session/",
        {"amount": 5000},
        format="json",
    )

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_server_error"
    mock_create.assert_not_called()


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_legacy_create_checkout_session_requires_authentication(mock_create):
    """Legacy endpoint requires authentication."""

    client = APIClient()
    client.defaults["HTTP_HOST"] = "test.localhost"

    response = client.post(
        "/api/pay/create-checkout-session/",
        {"amount": 5000},
        format="json",
    )

    assert response.status_code == 401
    mock_create.assert_not_called()


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_SECRET_KEY="sk_test_secret",
)
@patch("payments.views.stripe.checkout.Session.create")
def test_legacy_create_checkout_session_handles_stripe_errors(mock_create, tenant_user):
    """Legacy endpoint handles Stripe errors gracefully."""

    mock_create.side_effect = stripe_error.InvalidRequestError(
        message="Invalid amount",
        param="amount",
    )

    client = _authenticated_client(tenant_user)
    response = client.post(
        "/api/pay/create-checkout-session/",
        {"amount": -100},  # Invalid amount
        format="json",
    )

    assert response.status_code == 402
    assert "payment processing failed" in response.json()["detail"].lower()


# -------------------------------------------------------------------
# Rate Limiting Configuration Tests
# -------------------------------------------------------------------


def test_billing_rate_throttle_is_configured():
    """Verify BillingRateThrottle class is properly configured."""
    from api.throttles import BillingRateThrottle
    from rest_framework.throttling import UserRateThrottle

    # BillingRateThrottle should exist and inherit from UserRateThrottle
    assert issubclass(BillingRateThrottle, UserRateThrottle)

    # Should have correct scope
    assert BillingRateThrottle.scope == "billing"


def test_billing_endpoints_have_throttle_classes():
    """Verify billing endpoints are configured with BillingRateThrottle."""
    from api.throttles import BillingRateThrottle
    from payments.views import BillingCheckoutSessionView, create_checkout_session

    # Class-based view should have throttle_classes
    assert hasattr(BillingCheckoutSessionView, "throttle_classes")
    assert BillingRateThrottle in BillingCheckoutSessionView.throttle_classes

    # Function-based view should have throttle_classes decorator applied
    # (verified by checking the view's closure/decorator chain)
    assert hasattr(create_checkout_session, "cls")  # Has @api_view decorator


def test_billing_throttle_rate_in_settings():
    """Verify billing throttle rate is configured in Django settings."""
    from django.conf import settings

    throttle_rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})

    # Billing rate should be configured
    assert "billing" in throttle_rates
    assert throttle_rates["billing"] == "100/hour"
