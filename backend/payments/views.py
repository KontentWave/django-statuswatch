import logging

import stripe
from api.exceptions import ConfigurationError, InvalidPaymentMethodError, PaymentProcessingError
from api.logging_utils import sanitize_log_value
from api.throttles import BillingRateThrottle
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from stripe import _error as stripe_error
from tenants.models import Client, SubscriptionStatus

logger = logging.getLogger(__name__)
checkout_logger = logging.getLogger("payments.checkout")
billing_logger = logging.getLogger("payments.billing")
webhook_logger = logging.getLogger("payments.webhooks")
subscription_logger = logging.getLogger("payments.subscriptions")


@api_view(["GET"])
@permission_classes([AllowAny])
def stripe_config(request):
    return Response({"publicKey": settings.STRIPE_PUBLIC_KEY or ""})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([BillingRateThrottle])
def create_checkout_session(request):
    """
    Create a Stripe Checkout session for payment processing.

    Sanitizes all Stripe errors to prevent API key leakage.
    Rate limited to prevent billing abuse.
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
        ) from e

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
        raise PaymentProcessingError() from e

    except stripe_error.AuthenticationError as e:
        # Authentication with Stripe failed
        logger.critical(
            sanitize_log_value(f"Stripe authentication error: {str(e)}"),
            exc_info=settings.DEBUG,
        )
        raise ConfigurationError("Payment system authentication failed.") from e

    except stripe_error.APIConnectionError as e:
        # Network communication failed
        logger.error(
            sanitize_log_value(f"Stripe API connection error: {str(e)}"),
            exc_info=settings.DEBUG,
        )
        raise PaymentProcessingError(
            "Unable to connect to payment processor. Please try again later."
        ) from e

    except stripe_error.StripeError as e:
        # Generic Stripe error
        logger.error(
            sanitize_log_value(f"Stripe error for user {request.user.id}: {str(e)}"),
            exc_info=settings.DEBUG,
        )
        raise PaymentProcessingError() from e

    except Exception as e:
        # Non-Stripe error
        logger.error(
            sanitize_log_value(f"Unexpected error in create_checkout_session: {str(e)}"),
            exc_info=settings.DEBUG,
            extra={"user": request.user.id},
        )
        raise PaymentProcessingError() from e


class BillingCheckoutSessionView(APIView):
    """
    Create Stripe Checkout session for subscription upgrades.

    Rate limited to prevent billing abuse and duplicate transactions.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]

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
            ) from e

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
            raise PaymentProcessingError() from e

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
            raise ConfigurationError("Payment system authentication failed.") from e

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
            ) from e

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
            raise PaymentProcessingError() from e

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
            raise PaymentProcessingError() from e


class StripeWebhookView(APIView):
    """Receive Stripe webhook events and synchronize tenant subscription state."""

    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    def post(self, request):
        secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        if not secret:
            webhook_logger.error(
                "Stripe webhook secret not configured",
                extra={"event": "stripe_webhook", "status": "error", "reason": "missing_secret"},
            )
            raise ConfigurationError("Webhook secret is not configured.")

        payload = request.body
        signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            event = stripe.Webhook.construct_event(payload, signature, secret)
        except ValueError as exc:  # invalid payload
            webhook_logger.warning(
                "Stripe webhook payload could not be parsed",
                extra={"event": "stripe_webhook", "status": "invalid_payload", "error": str(exc)},
            )
            return Response({"detail": "Invalid payload."}, status=status.HTTP_400_BAD_REQUEST)
        except stripe_error.SignatureVerificationError as exc:
            webhook_logger.warning(
                "Stripe webhook signature verification failed",
                extra={
                    "event": "stripe_webhook",
                    "status": "invalid_signature",
                    "error": sanitize_log_value(str(exc)),
                },
            )
            return Response({"detail": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            webhook_logger.error(
                "Unexpected error constructing Stripe webhook event",
                extra={
                    "event": "stripe_webhook",
                    "status": "error",
                    "error": sanitize_log_value(str(exc)),
                },
                exc_info=settings.DEBUG,
            )
            return Response(
                {"detail": "Webhook processing failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self._handle_event(event)

    def _handle_event(self, event: dict):
        event_type = event.get("type", "unknown")
        event_id = event.get("id")
        tenant_schema = self._extract_tenant_schema(event)
        sanitized_schema = sanitize_log_value(tenant_schema or "")
        session_id = event.get("data", {}).get("object", {}).get("id")
        sanitized_session_id = sanitize_log_value(session_id or "")
        sanitized_event_id = sanitize_log_value(event_id or "")

        subscription_logger.info(
            "Processing Stripe webhook event",
            extra={
                "event": "stripe_webhook",
                "event_type": event_type,
                "event_id": sanitized_event_id,
                "tenant_schema": sanitized_schema,
                "session_id": sanitized_session_id,
                "status": "received",
            },
        )

        if tenant_schema is None:
            webhook_logger.warning(
                "Stripe webhook missing tenant metadata",
                extra={"event": "stripe_webhook", "status": "ignored", "event_type": event_type},
            )
            return Response(status=status.HTTP_202_ACCEPTED)

        tenant = Client.objects.filter(schema_name=tenant_schema).first()
        if tenant is None:
            webhook_logger.warning(
                "Stripe webhook tenant not found",
                extra={
                    "event": "stripe_webhook",
                    "status": "ignored",
                    "event_type": event_type,
                    "tenant_schema": sanitized_schema,
                },
            )
            return Response(status=status.HTTP_202_ACCEPTED)

        if event_type in {"checkout.session.completed", "invoice.paid"}:
            return self._update_subscription(
                tenant,
                SubscriptionStatus.PRO,
                event_type,
                event_id=event_id,
                session_id=session_id,
            )

        if event_type == "customer.subscription.deleted":
            return self._update_subscription(
                tenant,
                SubscriptionStatus.CANCELED,
                event_type,
                event_id=event_id,
                session_id=session_id,
            )

        webhook_logger.info(
            "Stripe webhook event ignored",
            extra={
                "event": "stripe_webhook",
                "status": "ignored",
                "event_type": event_type,
                "tenant_schema": sanitized_schema,
            },
        )
        return Response(status=status.HTTP_202_ACCEPTED)

    @staticmethod
    def _extract_tenant_schema(event: dict) -> str | None:
        data_object = event.get("data", {}).get("object", {}) or {}
        metadata = data_object.get("metadata") or {}
        tenant_schema = metadata.get("tenant_schema") or metadata.get("tenant")
        return tenant_schema

    def _update_subscription(
        self,
        tenant: Client,
        new_status: SubscriptionStatus,
        event_type: str,
        event_id: str | None = None,
        session_id: str | None = None,
    ) -> Response:
        previous_status = tenant.subscription_status
        tenant.subscription_status = new_status
        tenant.save(update_fields=["subscription_status"])

        sanitized_event_id = sanitize_log_value(event_id or "")
        sanitized_session_id = sanitize_log_value(session_id or "")
        sanitized_schema = sanitize_log_value(tenant.schema_name)

        subscription_logger.info(
            "Subscription status updated",
            extra={
                "event": "subscription_update",
                "event_type": event_type,
                "event_id": sanitized_event_id,
                "session_id": sanitized_session_id,
                "tenant_schema": sanitized_schema,
                "previous_status": previous_status,
                "new_status": new_status,
            },
        )

        webhook_logger.info(
            "Stripe webhook updated subscription status",
            extra={
                "event": "stripe_webhook",
                "status": "updated",
                "event_type": event_type,
                "tenant_schema": sanitized_schema,
                "previous_status": previous_status,
                "new_status": new_status,
                "event_id": sanitized_event_id,
                "session_id": sanitized_session_id,
            },
        )

        return Response(status=status.HTTP_200_OK)
