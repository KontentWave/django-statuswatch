from django.urls import path
from .views import stripe_config, create_checkout_session

urlpatterns = [
    path("config/", stripe_config, name="stripe_config"),
    path("create-checkout-session/", create_checkout_session, name="stripe_create_checkout_session"),
]
