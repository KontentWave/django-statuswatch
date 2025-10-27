from django.urls import path

from .views import (
    BillingCheckoutSessionView,
    BillingPortalSessionView,
    CancelSubscriptionView,
    StripeWebhookView,
)

urlpatterns = [
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
