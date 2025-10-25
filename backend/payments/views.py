import logging

import stripe
from api.exceptions import ConfigurationError, InvalidPaymentMethodError, PaymentProcessingError
from api.logging_utils import sanitize_log_value
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from stripe import _error as stripe_error

logger = logging.getLogger(__name__)
checkout_logger = logging.getLogger("payments.checkout")
billing_logger = logging.getLogger("payments.billing")


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


class BillingCheckoutSessionView(APIView):
    """Create Stripe Checkout session for subscription upgrades."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not settings.STRIPE_SECRET_KEY:
            billing_logger.error(
                "STRIPE_SECRET_KEY not configured",
                extra={
                    "event": "billing_checkout",
                    "status": "error",
                    "reason": "missing_secret",
                    "plan": sanitize_log_value(request.data.get("plan", "")),
                    "user_id": request.user.id,
                },
            )
            raise ConfigurationError("Payment system is not properly configured.")

        plan = str(request.data.get("plan", "pro")).lower()
        plan_price_map = {"pro": settings.STRIPE_PRO_PRICE_ID}
        price_id = plan_price_map.get(plan)

        sanitized_plan = sanitize_log_value(plan)
        log_context_base = {
            "event": "billing_checkout",
            "plan": sanitized_plan,
            "user_id": request.user.id,
        }

        if price_id is None:
            billing_logger.warning(
                "Received checkout request for unknown plan",
                extra={
                    **log_context_base,
                    "status": "error",
                    "reason": "unknown_plan",
                },
            )
            return Response(
                {"detail": f"The plan '{plan}' is not available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not price_id:
            billing_logger.error(
                "Stripe price ID not configured for plan",
                extra={
                    **log_context_base,
                    "status": "error",
                    "reason": "missing_price_id",
                },
            )
            raise ConfigurationError("Subscription plan is temporarily unavailable.")

        stripe.api_key = settings.STRIPE_SECRET_KEY

        tenant = getattr(request, "tenant", None)
        tenant_schema = getattr(tenant, "schema_name", "public")
        base_frontend_url = settings.FRONTEND_URL.rstrip("/")
        success_url = f"{base_frontend_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_frontend_url}/billing/cancel"

        sanitized_tenant = sanitize_log_value(tenant_schema)

        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                line_items=[{"price": price_id, "quantity": 1}],
                customer_email=request.user.email,
                metadata={
                    "tenant_schema": tenant_schema,
                    "user_id": str(request.user.id),
                    "plan": plan,
                },
                success_url=success_url,
                cancel_url=cancel_url,
            )

            sanitized_session_id = sanitize_log_value(getattr(session, "id", ""))

            log_context = {
                **log_context_base,
                "tenant_schema": sanitized_tenant,
                "session_id": sanitized_session_id,
                "checkout_mode": "subscription",
                "status": "success",
            }
            billing_logger.info(
                "Created Stripe checkout session | tenant=%s plan=%s user_id=%s session_id=%s",
                log_context["tenant_schema"],
                log_context["plan"],
                log_context["user_id"],
                log_context["session_id"],
                extra=log_context,
            )
            checkout_logger.info(
                "Created Stripe checkout session | tenant=%s plan=%s user_id=%s session_id=%s",
                log_context["tenant_schema"],
                log_context["plan"],
                log_context["user_id"],
                log_context["session_id"],
                extra=log_context,
            )

            return Response({"url": session.url}, status=status.HTTP_201_CREATED)

        except stripe_error.CardError as e:
            sanitized_message = sanitize_log_value(
                f"Stripe card error for user {request.user.id}: {e.user_message}"
            )
            extra_payload = {
                **log_context_base,
                "status": "error",
                "error_type": "card_error",
                "stripe_error_code": sanitize_log_value(e.code),
            }
            billing_logger.warning(sanitized_message, extra=extra_payload)
            checkout_logger.warning(sanitized_message, extra=extra_payload)
            raise InvalidPaymentMethodError(
                "Your payment method was declined. Please try a different payment method."
            )

        except stripe_error.InvalidRequestError as e:
            sanitized_message = sanitize_log_value(
                f"Stripe invalid request for user {request.user.id}: {str(e)}"
            )
            extra_payload = {
                **log_context_base,
                "status": "error",
                "error_type": "invalid_request",
            }
            billing_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra=extra_payload,
            )
            checkout_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra=extra_payload,
            )
            raise PaymentProcessingError()

        except stripe_error.AuthenticationError as e:
            sanitized_message = sanitize_log_value(f"Stripe authentication error: {str(e)}")
            extra_payload = {
                **log_context_base,
                "status": "error",
                "error_type": "auth_error",
            }
            billing_logger.critical(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra=extra_payload,
            )
            checkout_logger.critical(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra=extra_payload,
            )
            raise ConfigurationError("Payment system authentication failed.")

        except stripe_error.APIConnectionError as e:
            sanitized_message = sanitize_log_value(f"Stripe API connection error: {str(e)}")
            extra_payload = {
                **log_context_base,
                "status": "error",
                "error_type": "api_connection",
            }
            billing_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra=extra_payload,
            )
            checkout_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra=extra_payload,
            )
            raise PaymentProcessingError(
                "Unable to connect to payment processor. Please try again later."
            )

        except stripe_error.StripeError as e:
            sanitized_message = sanitize_log_value(
                f"Stripe error for user {request.user.id}: {str(e)}"
            )
            extra_payload = {
                **log_context_base,
                "status": "error",
                "error_type": "generic_stripe",
            }
            billing_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra=extra_payload,
            )
            checkout_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra=extra_payload,
            )
            raise PaymentProcessingError()

        except Exception as e:  # noqa: BLE001
            sanitized_message = sanitize_log_value(
                f"Unexpected error in billing checkout session: {str(e)}"
            )
            extra_payload = {
                **log_context_base,
                "tenant_schema": sanitized_tenant,
                "status": "error",
                "error_type": "unexpected",
            }
            billing_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra=extra_payload,
            )
            checkout_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra=extra_payload,
            )
            raise PaymentProcessingError()
