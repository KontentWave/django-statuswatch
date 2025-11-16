from django.urls import path

from modules.billing.views import (
    BillingCheckoutSessionView,
    BillingPortalSessionView,
    CancelSubscriptionView,
    StripeWebhookView,
    create_checkout_session,
    stripe_config,
)

pay_urlpatterns = [
    path("config/", stripe_config, name="stripe_config"),
    path(
        "create-checkout-session/",
        create_checkout_session,
        name="stripe_create_checkout_session",
    ),
]

billing_urlpatterns = [
    path(
        "create-checkout-session/",
        BillingCheckoutSessionView.as_view(),
        name="billing_create_checkout_session",
    ),
    path(
        "create-portal-session/",
        BillingPortalSessionView.as_view(),
        name="billing_create_portal_session",
    ),
    path(
        "cancel/",
        CancelSubscriptionView.as_view(),
        name="billing_cancel_subscription",
    ),
    path(
        "webhook/",
        StripeWebhookView.as_view(),
        name="billing_webhook",
    ),
]

__all__ = ["pay_urlpatterns", "billing_urlpatterns"]
