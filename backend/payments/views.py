import logging

import stripe
from api.exceptions import ConfigurationError, InvalidPaymentMethodError, PaymentProcessingError
from api.logging_utils import sanitize_log_value
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from stripe import _error as stripe_error

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def stripe_config(request):
    return Response({"publicKey": settings.STRIPE_PUBLIC_KEY or ""})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
    """
    Create a Stripe Checkout session for payment processing.

    Sanitizes all Stripe errors to prevent API key leakage.
    """
    if not settings.STRIPE_SECRET_KEY:
        logger.error("STRIPE_SECRET_KEY not configured")
        raise ConfigurationError("Payment system is not properly configured.")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    amount = int(request.data.get("amount", 2000))  # cents
    currency = request.data.get("currency", "usd")
    name = request.data.get("name", "Test payment")

    domain = request.build_absolute_uri("/").rstrip("/")
    success_url = f"{domain}/?success=true"
    cancel_url = f"{domain}/?canceled=true"

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": currency,
                        "product_data": {"name": name},
                        "unit_amount": amount,
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return Response({"id": session.id, "url": session.url})

    except stripe_error.CardError as e:
        # Card was declined
        logger.warning(
            sanitize_log_value(f"Stripe card error for user {request.user.id}: {e.user_message}"),
            extra={"stripe_error_code": sanitize_log_value(e.code)},
        )
        raise InvalidPaymentMethodError(
            "Your payment method was declined. Please try a different payment method."
        )

    except stripe_error.InvalidRequestError as e:
        # Invalid parameters
        logger.error(
            sanitize_log_value(f"Stripe invalid request for user {request.user.id}: {str(e)}"),
            exc_info=settings.DEBUG,
            extra={
                "amount": amount,
                "currency": currency,
            },
        )
        raise PaymentProcessingError()

    except stripe_error.AuthenticationError as e:
        # Authentication with Stripe failed
        logger.critical(
            sanitize_log_value(f"Stripe authentication error: {str(e)}"),
            exc_info=settings.DEBUG,
        )
        raise ConfigurationError("Payment system authentication failed.")

    except stripe_error.APIConnectionError as e:
        # Network communication failed
        logger.error(
            sanitize_log_value(f"Stripe API connection error: {str(e)}"),
            exc_info=settings.DEBUG,
        )
        raise PaymentProcessingError(
            "Unable to connect to payment processor. Please try again later."
        )

    except stripe_error.StripeError as e:
        # Generic Stripe error
        logger.error(
            sanitize_log_value(f"Stripe error for user {request.user.id}: {str(e)}"),
            exc_info=settings.DEBUG,
        )
        raise PaymentProcessingError()

    except Exception as e:
        # Non-Stripe error
        logger.error(
            sanitize_log_value(f"Unexpected error in create_checkout_session: {str(e)}"),
            exc_info=settings.DEBUG,
            extra={"user": request.user.id},
        )
        raise PaymentProcessingError()
