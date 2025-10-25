from django.urls import path

from .views import BillingCheckoutSessionView

urlpatterns = [
    path(
        "create-checkout-session/",
        BillingCheckoutSessionView.as_view(),
        name="billing_create_checkout_session",
    ),
]
