"""Legacy shim re-exporting billing views from the modules package."""

from api.audit_log import log_audit_event as _default_log_audit_event
from modules.billing import views as billing_views

BillingCheckoutSessionView = billing_views.BillingCheckoutSessionView
BillingPortalSessionView = billing_views.BillingPortalSessionView
CancelSubscriptionView = billing_views.CancelSubscriptionView
StripeWebhookView = billing_views.StripeWebhookView
create_checkout_session = billing_views.create_checkout_session
stripe_config = billing_views.stripe_config

# Preserve the `payments.views.stripe` import target used throughout tests and legacy code.
stripe = billing_views.stripe
log_audit_event = _default_log_audit_event


def _resolve_log_audit_event():
    return log_audit_event


billing_views.register_log_audit_event_resolver(_resolve_log_audit_event)

__all__ = [
    "BillingCheckoutSessionView",
    "BillingPortalSessionView",
    "CancelSubscriptionView",
    "StripeWebhookView",
    "create_checkout_session",
    "stripe_config",
    "stripe",
    "log_audit_event",
]
