import hashlib
import json
import logging
from urllib.parse import urlsplit

import stripe
from api.audit_log import AuditEvent, log_audit_event
from api.exceptions import ConfigurationError, InvalidPaymentMethodError, PaymentProcessingError
from api.logging_utils import sanitize_log_value
from api.throttles import BillingRateThrottle
from django.conf import settings
from django.core.exceptions import DisallowedHost
from modules.billing import (
    BillingCancelResponseDto,
    BillingCheckoutResponseDto,
    BillingPortalResponseDto,
    cancel_active_subscription,
    create_billing_portal_session,
    create_subscription_checkout_session,
    dispatch_billing_webhook_event,
)
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from stripe import _error as stripe_error
from tenants.models import SubscriptionStatus

logger = logging.getLogger(__name__)
checkout_logger = logging.getLogger("payments.checkout")
billing_logger = logging.getLogger("payments.billing")
frontend_resolver_logger = logging.getLogger("payments.frontend_resolver")
webhook_logger = logging.getLogger("payments.webhooks")
subscription_logger = logging.getLogger("payments.subscriptions")
webhook_debug_logger = logging.getLogger("payments.webhooks.debug")
cancellation_logger = logging.getLogger("payments.cancellations")
subscription_state_logger = logging.getLogger("payments.subscription_state")
webhook_signature_logger = logging.getLogger("payments.webhooks.signature")


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def stripe_config(request):
    return Response({"publicKey": settings.STRIPE_PUBLIC_KEY or ""})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([BillingRateThrottle])
def create_checkout_session(request):
    """
    Create a Stripe Checkout session for payment processing.

    Sanitizes all Stripe errors to prevent API key leakage.
    Rate limited to prevent billing abuse.
    Allows anonymous users to test checkout (demo purposes).
    """
    if not settings.STRIPE_SECRET_KEY:
        logger.error("STRIPE_SECRET_KEY not configured")
        raise ConfigurationError("Payment system is not properly configured.")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    amount = int(request.data.get("amount", 2000))  # cents
    currency = request.data.get("currency", "usd")
    name = request.data.get("name", "Test payment")

    base_frontend_url, frontend_source = _resolve_frontend_base_url(request)

    logger.info(
        "Resolved checkout redirect base URL",
        extra={
            "event": "checkout_redirect_base_resolved",
            "base_frontend_url": base_frontend_url,
            "source": frontend_source,
            "request_host": request.get_host(),
        },
    )

    success_url = f"{base_frontend_url}/?success=true"
    cancel_url = f"{base_frontend_url}/?canceled=true"

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
        user_id = request.user.id if request.user.is_authenticated else "anonymous"
        logger.warning(
            sanitize_log_value(f"Stripe card error for user {user_id}: {e.user_message}"),
            extra={"stripe_error_code": sanitize_log_value(e.code)},
        )
        raise InvalidPaymentMethodError(
            "Your payment method was declined. Please try a different payment method."
        ) from e

    except stripe_error.InvalidRequestError as e:
        # Invalid parameters
        user_id = request.user.id if request.user.is_authenticated else "anonymous"
        logger.error(
            sanitize_log_value(f"Stripe invalid request for user {user_id}: {str(e)}"),
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
        user_id = request.user.id if request.user.is_authenticated else "anonymous"
        logger.error(
            sanitize_log_value(f"Stripe error for user {user_id}: {str(e)}"),
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
            dto = BillingCheckoutResponseDto(detail=f"The plan '{plan}' is not available.")
            return Response(dto.to_dict(), status=status.HTTP_400_BAD_REQUEST)

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

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            billing_logger.error(
                "Tenant context missing during checkout",
                extra={
                    **log_context_base,
                    "status": "error",
                    "reason": "missing_tenant",
                },
            )
            raise ConfigurationError("Tenant context is not available for this request.")
        tenant_schema = getattr(tenant, "schema_name", "public")
        tenant_customer_id = getattr(tenant, "stripe_customer_id", "") or ""
        sanitized_tenant = sanitize_log_value(tenant_schema)
        sanitized_customer = sanitize_log_value(tenant_customer_id)

        base_frontend_url, frontend_source = _resolve_frontend_base_url(request, tenant)

        success_url = f"{base_frontend_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_frontend_url}/billing/cancel"
        try:
            checkout_result = create_subscription_checkout_session(
                stripe_secret_key=settings.STRIPE_SECRET_KEY,
                tenant=tenant,
                user=request.user,
                plan=plan,
                price_id=price_id,
                success_url=success_url,
                cancel_url=cancel_url,
                stripe_api=stripe,
            )

            sanitized_customer = sanitize_log_value(checkout_result.customer_id or "")
            sanitized_session_id = sanitize_log_value(checkout_result.session_id or "")

            if checkout_result.customer_id and checkout_result.customer_id != tenant_customer_id:
                sync_context = {
                    **log_context_base,
                    "tenant_schema": sanitized_tenant,
                    "customer_id": sanitized_customer,
                    "customer_origin": checkout_result.customer_origin,
                    "status": "customer_ready",
                }
                billing_logger.info(
                    "Synchronized Stripe customer for tenant | tenant=%s customer_id=%s origin=%s",
                    sanitized_tenant,
                    sanitized_customer,
                    checkout_result.customer_origin,
                    extra=sync_context,
                )

            log_context = {
                **log_context_base,
                "tenant_schema": sanitized_tenant,
                "session_id": sanitized_session_id,
                "checkout_mode": "subscription",
                "customer_id": sanitized_customer,
                "customer_origin": checkout_result.customer_origin,
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

            dto = BillingCheckoutResponseDto(url=checkout_result.url)
            return Response(dto.to_dict(), status=status.HTTP_201_CREATED)

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


class BillingPortalSessionView(APIView):
    """Create a Stripe Billing Portal session so tenants can manage subscriptions."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]

    def post(self, request):
        if not settings.STRIPE_SECRET_KEY:
            billing_logger.error(
                "STRIPE_SECRET_KEY not configured",
                extra={
                    "event": "billing_portal",
                    "status": "error",
                    "reason": "missing_secret",
                    "user_id": request.user.id,
                },
            )
            raise ConfigurationError("Payment system is not properly configured.")

        tenant = getattr(request, "tenant", None)
        tenant_schema = getattr(tenant, "schema_name", "public")
        tenant_customer_id = getattr(tenant, "stripe_customer_id", "") or ""

        sanitized_schema = sanitize_log_value(tenant_schema)
        sanitized_customer = sanitize_log_value(tenant_customer_id)
        log_context = {
            "event": "billing_portal",
            "tenant_schema": sanitized_schema,
            "user_id": request.user.id,
            "customer_id": sanitized_customer,
        }

        if not tenant_customer_id:
            billing_logger.warning(
                "Tenant missing Stripe customer ID for billing portal",
                extra={**log_context, "status": "error", "reason": "missing_customer"},
            )
            dto = BillingPortalResponseDto(
                detail=(
                    "Billing portal is not available yet. Please try again shortly or contact support."
                )
            )
            return Response(dto.to_dict(), status=status.HTTP_409_CONFLICT)

        base_frontend_url, frontend_source = _resolve_frontend_base_url(request, tenant)
        return_url = f"{base_frontend_url}/billing"

        try:
            request_host = request.get_host()
        except DisallowedHost:
            request_host = request.META.get("HTTP_HOST", "")

        sanitized_base = sanitize_log_value(base_frontend_url)
        sanitized_return = sanitize_log_value(return_url)
        sanitized_host = sanitize_log_value(request_host)

        billing_logger.info(
            "[STRIPE-PORTAL] Creating billing portal with return URL | base=%s return_url=%s source=%s",
            sanitized_base,
            sanitized_return,
            frontend_source,
            extra={
                **log_context,
                "status": "preflight",
                "base_frontend_url": sanitized_base,
                "return_url": sanitized_return,
                "resolution_source": frontend_source,
                "request_host": sanitized_host,
            },
        )

        try:
            billing_logger.info(
                "Creating Stripe billing portal session",
                extra={
                    **log_context,
                    "status": "start",
                    "base_frontend_url": sanitized_base,
                    "return_url": sanitized_return,
                    "resolution_source": frontend_source,
                },
            )
            portal_result = create_billing_portal_session(
                stripe_secret_key=settings.STRIPE_SECRET_KEY,
                customer_id=tenant_customer_id,
                return_url=return_url,
            )

            sanitized_session = sanitize_log_value(portal_result.session_id or "")
            success_context = {
                **log_context,
                "status": "success",
                "session_id": sanitized_session,
                "base_frontend_url": sanitized_base,
                "return_url": sanitized_return,
                "resolution_source": frontend_source,
            }
            billing_logger.info(
                "Created Stripe billing portal session | tenant=%s user_id=%s session_id=%s",
                success_context["tenant_schema"],
                success_context["user_id"],
                success_context["session_id"],
                extra=success_context,
            )
            dto = BillingPortalResponseDto(url=portal_result.url)
            return Response(dto.to_dict(), status=status.HTTP_201_CREATED)

        except stripe_error.InvalidRequestError as e:
            sanitized_message = sanitize_log_value(
                f"Stripe invalid request while creating portal session: {str(e)}"
            )
            billing_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra={**log_context, "status": "error", "error_type": "invalid_request"},
            )
            raise PaymentProcessingError() from e

        except stripe_error.AuthenticationError as e:
            sanitized_message = sanitize_log_value(
                f"Stripe authentication error while creating portal session: {str(e)}"
            )
            billing_logger.critical(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra={**log_context, "status": "error", "error_type": "auth_error"},
            )
            raise ConfigurationError("Payment system authentication failed.") from e

        except stripe_error.APIConnectionError as e:
            sanitized_message = sanitize_log_value(
                f"Stripe API connection error while creating portal session: {str(e)}"
            )
            billing_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra={**log_context, "status": "error", "error_type": "api_connection"},
            )
            raise PaymentProcessingError(
                "Unable to connect to payment processor. Please try again later."
            ) from e

        except stripe_error.StripeError as e:
            sanitized_message = sanitize_log_value(
                f"Stripe error while creating portal session: {str(e)}"
            )
            billing_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra={**log_context, "status": "error", "error_type": "generic_stripe"},
            )
            raise PaymentProcessingError() from e

        except Exception as e:  # noqa: BLE001
            sanitized_message = sanitize_log_value(
                f"Unexpected error creating billing portal session: {str(e)}"
            )
            billing_logger.error(
                sanitized_message,
                exc_info=settings.DEBUG,
                extra={**log_context, "status": "error", "error_type": "unexpected"},
            )
            raise PaymentProcessingError() from e


class CancelSubscriptionView(APIView):
    """Cancel the active Stripe subscription and revert the tenant to the free plan."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [BillingRateThrottle]
    CANCELABLE_STATUSES = {"trialing", "active", "past_due", "unpaid"}

    def post(self, request):
        if not settings.STRIPE_SECRET_KEY:
            cancellation_logger.error(
                "STRIPE_SECRET_KEY not configured",
                extra={
                    "event": "billing_cancellation",
                    "status": "error",
                    "reason": "missing_secret",
                    "user_id": getattr(request.user, "id", None),
                },
            )
            raise ConfigurationError("Payment system is not properly configured.")

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            cancellation_logger.error(
                "Tenant context missing during cancellation",
                extra={
                    "event": "billing_cancellation",
                    "status": "error",
                    "reason": "missing_tenant",
                    "user_id": getattr(request.user, "id", None),
                },
            )
            raise ConfigurationError("Tenant context is not available for this request.")

        tenant_schema = getattr(tenant, "schema_name", "public")
        tenant_customer_id = getattr(tenant, "stripe_customer_id", "") or ""
        sanitized_schema = sanitize_log_value(tenant_schema)
        sanitized_customer = sanitize_log_value(tenant_customer_id)
        user_id = getattr(request.user, "id", None)
        log_context = {
            "event": "billing_cancellation",
            "tenant_schema": sanitized_schema,
            "user_id": user_id,
            "customer_id": sanitized_customer,
        }

        if not tenant_customer_id:
            cancellation_logger.warning(
                "Tenant missing Stripe customer ID for cancellation",
                extra={**log_context, "status": "error", "reason": "missing_customer"},
            )
            dto = BillingCancelResponseDto(
                detail=(
                    "We could not locate an active subscription for this workspace. "
                    "Please try again after refreshing the page."
                )
            )
            return Response(dto.to_dict(), status=status.HTTP_409_CONFLICT)

        cancellation_logger.info(
            "Attempting to cancel Stripe subscription",
            extra={**log_context, "status": "start"},
        )

        try:
            cancel_result = cancel_active_subscription(
                stripe_secret_key=settings.STRIPE_SECRET_KEY,
                tenant=tenant,
                cancelable_statuses=self.CANCELABLE_STATUSES,
                stripe_api=stripe,
            )
        except stripe_error.APIConnectionError as exc:
            sanitized_error = sanitize_log_value(str(exc))
            cancellation_logger.error(
                "Stripe API connection error while cancelling subscription",
                extra={**log_context, "status": "error", "error": sanitized_error},
                exc_info=settings.DEBUG,
            )
            raise PaymentProcessingError(
                "Unable to contact the payment processor. Please try again shortly."
            ) from exc
        except stripe_error.InvalidRequestError as exc:
            sanitized_error = sanitize_log_value(str(exc))
            cancellation_logger.error(
                "Stripe invalid request while cancelling subscription",
                extra={**log_context, "status": "error", "error": sanitized_error},
                exc_info=settings.DEBUG,
            )
            raise PaymentProcessingError() from exc
        except stripe_error.StripeError as exc:
            sanitized_error = sanitize_log_value(str(exc))
            cancellation_logger.error(
                "Stripe error while cancelling subscription",
                extra={**log_context, "status": "error", "error": sanitized_error},
                exc_info=settings.DEBUG,
            )
            raise PaymentProcessingError(
                "Payment processor reported an error while cancelling the subscription."
            ) from exc
        except Exception as exc:  # noqa: BLE001
            cancellation_logger.error(
                "Unexpected error while cancelling subscription",
                extra={**log_context, "status": "error", "error": sanitize_log_value(str(exc))},
                exc_info=settings.DEBUG,
            )
            raise PaymentProcessingError() from exc

        sanitized_subscription_id = sanitize_log_value(cancel_result.subscription_id or "")

        if cancel_result.subscription_id:
            cancellation_logger.info(
                "Cancelling Stripe subscription",
                extra={
                    **log_context,
                    "status": "processing",
                    "subscription_id": sanitized_subscription_id,
                    "subscription_status": sanitize_log_value(cancel_result.remote_status or ""),
                },
            )
        subscription_logger.info(
            "Subscription status updated via cancellation API",
            extra={
                "event": "subscription_update",
                "event_type": "api.billing.cancel",
                "tenant_schema": sanitized_schema,
                "previous_status": cancel_result.previous_status,
                "new_status": SubscriptionStatus.FREE,
                "subscription_id": sanitized_subscription_id,
                "customer_id": sanitized_customer,
                "status": "updated",
            },
        )

        cancellation_logger.info(
            "Tenant downgraded to free plan",
            extra={
                **log_context,
                "status": "success",
                "subscription_id": sanitized_subscription_id,
                "previous_status": sanitize_log_value(cancel_result.previous_status),
                "new_status": SubscriptionStatus.FREE,
            },
        )

        log_audit_event(
            event=AuditEvent.SUBSCRIPTION_CANCELLED,
            user_id=user_id,
            user_email=getattr(request.user, "email", None),
            tenant_schema=tenant_schema,
            details={
                "origin": "api",
                "previous_status": cancel_result.previous_status,
                "subscription_id": cancel_result.subscription_id,
                "customer_id": tenant_customer_id,
            },
        )

        if not cancel_result.remote_cancelled and cancel_result.subscription_id is None:
            cancellation_logger.info(
                "No cancelable Stripe subscription found",
                extra={**log_context, "status": "skipped"},
            )

        dto = BillingCancelResponseDto(plan=SubscriptionStatus.FREE)
        return Response(dto.to_dict(), status=status.HTTP_200_OK)


def _resolve_frontend_base_url(request, tenant=None) -> tuple[str, str]:
    """Resolve the SPA base URL used for Stripe redirects."""

    configured_url = getattr(settings, "FRONTEND_URL", "") or ""
    parsed_config = urlsplit(configured_url) if configured_url else None

    configured_scheme = parsed_config.scheme if parsed_config else None
    configured_hostname = parsed_config.hostname if parsed_config else None
    configured_port = parsed_config.port if parsed_config else None

    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
    scheme = configured_scheme or (
        "https" if request.is_secure() or forwarded_proto == "https" else request.scheme or "https"
    )

    try:
        request_host = request.get_host()
    except DisallowedHost:
        request_host = request.META.get("HTTP_HOST", "") or (configured_hostname or "")
    host_only = (
        request_host.split(":", 1)[0] if request_host else (configured_hostname or "localhost")
    )

    def build_url(host: str, port: int | None = None) -> str:
        if port and port not in (80, 443):
            return f"{scheme}://{host}:{port}".rstrip("/")
        return f"{scheme}://{host}".rstrip("/")

    tenant_schema = getattr(tenant, "schema_name", "public") if tenant else "public"

    if tenant and tenant_schema != "public":
        tenant_domains = getattr(tenant, "domains", None)
        if tenant_domains is not None:
            domain_records = list(tenant_domains.order_by("id"))
            best_choice: tuple | None = None
            best_rank: tuple[int, int, int, int, int] | None = None
            candidate_rows: list[dict[str, object]] = []

            for record in domain_records:
                domain_value = record.domain or ""
                host_part, port_fragment = (
                    domain_value.split(":", 1) if ":" in domain_value else (domain_value, None)
                )
                try:
                    domain_port = int(port_fragment) if port_fragment else None
                except ValueError:
                    domain_port = None

                if configured_port is not None:
                    port_penalty = 0 if domain_port == configured_port else 1
                else:
                    port_penalty = 0 if domain_port is None else 1

                host_match_penalty = 0 if host_part == host_only else 1
                suffix_penalty = (
                    0 if configured_hostname and host_part.endswith(configured_hostname) else 1
                )
                primary_penalty = 0 if getattr(record, "is_primary", False) else 1
                record_id = getattr(record, "id", 0) or 0
                rank = (
                    port_penalty,
                    host_match_penalty,
                    suffix_penalty,
                    primary_penalty,
                    record_id,
                )

                candidate_rows.append(
                    {
                        "domain": sanitize_log_value(domain_value),
                        "host": sanitize_log_value(host_part),
                        "port": domain_port,
                        "is_primary": getattr(record, "is_primary", False),
                        "rank": rank,
                        "matches_request_host": host_part == host_only,
                        "matches_configured_suffix": bool(
                            configured_hostname and host_part.endswith(configured_hostname)
                        ),
                    }
                )

                if best_rank is None or rank < best_rank:
                    best_rank = rank
                    best_choice = (record, host_part, domain_port)

            if best_choice is not None:
                selected_record, selected_host, selected_port = best_choice
                port_value = selected_port if selected_port is not None else configured_port

                resolution_flags = []
                if configured_port is not None:
                    if selected_port == configured_port:
                        resolution_flags.append(f"port_match:{configured_port}")
                    else:
                        resolution_flags.append("port_configured_fallback")
                elif selected_port is None:
                    resolution_flags.append("portless_match")
                else:
                    resolution_flags.append(f"port_from_domain:{selected_port}")

                if selected_host == host_only:
                    resolution_flags.append("request_host_match")
                elif configured_hostname and selected_host.endswith(configured_hostname):
                    resolution_flags.append("configured_hostname_suffix")

                if getattr(selected_record, "is_primary", False):
                    resolution_flags.append("primary_domain")

                resolution_source = "tenant_domain"
                if resolution_flags:
                    resolution_source = f"{resolution_source}[{','.join(resolution_flags)}]"

                sanitized_schema = sanitize_log_value(tenant_schema)
                sanitized_request_host = sanitize_log_value(request_host)
                sanitized_configured = sanitize_log_value(configured_url)
                sanitized_selected = sanitize_log_value(selected_record.domain)

                frontend_resolver_logger.info(
                    "Resolved tenant frontend base URL",
                    extra={
                        "tenant_schema": sanitized_schema,
                        "request_host": sanitized_request_host,
                        "configured_url": sanitized_configured,
                        "selected_domain": sanitized_selected,
                        "selected_port": selected_port,
                        "configured_port": configured_port,
                        "resolution_source": resolution_source,
                        "candidates": sanitize_log_value(candidate_rows),
                    },
                )

                return build_url(selected_host, port_value), resolution_source

        if configured_port is not None:
            return build_url(host_only, configured_port), "request_host_with_configured_port"

        return build_url(host_only), "request_host"

    if configured_url:
        hostname = configured_hostname or host_only
        return build_url(hostname, configured_port), "configured"

    return build_url(host_only), "request_host"


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

        raw_payload = ""
        try:
            raw_payload = payload.decode("utf-8")
        except (AttributeError, UnicodeDecodeError):
            raw_payload = str(payload)

        # Record webhook signature diagnostics to a dedicated log file without leaking payload data.
        if isinstance(payload, bytes | bytearray):
            payload_bytes = bytes(payload)
        else:
            payload_bytes = str(payload).encode("utf-8", "replace")
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()

        signature_log = {
            "event": "stripe_webhook_signature",
            "status": "received",
            "signature": sanitize_log_value(signature),
            "payload_sha256": payload_sha256,
            "content_length": len(payload_bytes),
            "remote_addr": sanitize_log_value(request.META.get("REMOTE_ADDR", "")),
            "request_id": sanitize_log_value(request.META.get("HTTP_X_REQUEST_ID", "")),
            "user_agent": sanitize_log_value(request.META.get("HTTP_USER_AGENT", "")),
            "forwarded_for": sanitize_log_value(request.META.get("HTTP_X_FORWARDED_FOR", "")),
        }
        webhook_signature_logger.info(json.dumps(signature_log, separators=(",", ":")))

        webhook_debug_logger.debug(
            "Received Stripe webhook payload",
            extra={
                "event": "stripe_webhook_raw",
                "payload": sanitize_log_value(raw_payload),
                "signature": sanitize_log_value(signature),
            },
        )

        try:
            event = stripe.Webhook.construct_event(payload, signature, secret)
            verified_log = {
                **signature_log,
                "status": "verified",
                "event_id": sanitize_log_value(event.get("id")),
                "event_type": event.get("type", "unknown"),
            }
            webhook_signature_logger.info(json.dumps(verified_log, separators=(",", ":")))
        except ValueError as exc:  # invalid payload
            invalid_payload_log = {
                **signature_log,
                "status": "invalid_payload",
                "error": sanitize_log_value(str(exc)),
            }
            webhook_signature_logger.info(json.dumps(invalid_payload_log, separators=(",", ":")))
            webhook_logger.warning(
                "Stripe webhook payload could not be parsed",
                extra={"event": "stripe_webhook", "status": "invalid_payload", "error": str(exc)},
            )
            return Response({"detail": "Invalid payload."}, status=status.HTTP_400_BAD_REQUEST)
        except stripe_error.SignatureVerificationError as exc:
            failure_log = {
                **signature_log,
                "status": "invalid_signature",
                "error": sanitize_log_value(str(exc)),
            }
            webhook_signature_logger.info(json.dumps(failure_log, separators=(",", ":")))
            webhook_logger.warning(
                "Stripe webhook signature verification failed",
                extra={
                    "event": "stripe_webhook",
                    "status": "invalid_signature",
                    "error": sanitize_log_value(str(exc)),
                },
            )
            webhook_debug_logger.debug(
                "Signature verification failure details",
                extra={
                    "event": "stripe_webhook_signature_failure",
                    "error": sanitize_log_value(str(exc)),
                    "raw_signature": sanitize_log_value(signature),
                    "payload": sanitize_log_value(raw_payload),
                },
            )
            return Response({"detail": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            unexpected_log = {
                **signature_log,
                "status": "error",
                "error": sanitize_log_value(str(exc)),
            }
            webhook_signature_logger.error(json.dumps(unexpected_log, separators=(",", ":")))
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
        session_id = event.get("data", {}).get("object", {}).get("id")
        metadata = event.get("data", {}).get("object", {}).get("metadata", {}) or {}
        tenant_schema = metadata.get("tenant_schema") or metadata.get("tenant")
        customer_id = event.get("data", {}).get("object", {}).get("customer")
        if not isinstance(customer_id, str) or not customer_id.strip():
            customer_id = None

        sanitized_event_id = sanitize_log_value(event_id or "")
        sanitized_session_id = sanitize_log_value(session_id or "")
        sanitized_customer = sanitize_log_value(customer_id or "")
        sanitized_schema = sanitize_log_value(tenant_schema or "")

        subscription_logger.info(
            "Processing Stripe webhook event",
            extra={
                "event": "stripe_webhook",
                "event_type": event_type,
                "event_id": sanitized_event_id,
                "tenant_schema": sanitized_schema,
                "session_id": sanitized_session_id,
                "status": "received",
                "customer_id": sanitized_customer,
            },
        )

        result = dispatch_billing_webhook_event(event)

        sanitized_event_id = sanitize_log_value(result.event_id or event_id or "")
        sanitized_session_id = sanitize_log_value(result.session_id or session_id or "")
        sanitized_customer = sanitize_log_value(result.customer_id or customer_id or "")
        sanitized_schema = sanitize_log_value(result.tenant_schema or tenant_schema or "")

        if result.status == "missing_metadata":
            webhook_logger.warning(
                "Stripe webhook missing tenant metadata",
                extra={"event": "stripe_webhook", "status": "ignored", "event_type": event_type},
            )
            return Response(status=status.HTTP_202_ACCEPTED)

        if result.status == "tenant_not_found":
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

        if result.status == "ignored":
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

        if not result.handled:
            webhook_logger.error(
                "Stripe webhook processing failed",
                extra={
                    "event": "stripe_webhook",
                    "status": result.status,
                    "event_type": event_type,
                    "tenant_schema": sanitized_schema,
                },
            )
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        subscription_logger.info(
            "Subscription status updated",
            extra={
                "event": "subscription_update",
                "event_type": event_type,
                "event_id": sanitized_event_id,
                "session_id": sanitized_session_id,
                "tenant_schema": sanitized_schema,
                "previous_status": result.previous_status,
                "new_status": result.new_status,
                "customer_id": sanitized_customer,
            },
        )

        webhook_logger.info(
            "Stripe webhook updated subscription status",
            extra={
                "event": "stripe_webhook",
                "status": "updated",
                "event_type": event_type,
                "tenant_schema": sanitized_schema,
                "previous_status": result.previous_status,
                "new_status": result.new_status,
                "event_id": sanitized_event_id,
                "session_id": sanitized_session_id,
                "customer_id": sanitized_customer,
            },
        )

        state_payload = {
            "event_type": event_type,
            "event_id": sanitized_event_id,
            "session_id": sanitized_session_id,
            "tenant_schema": sanitized_schema,
            "previous_status": sanitize_log_value(result.previous_status),
            "new_status": sanitize_log_value(result.new_status),
            "customer_id": sanitized_customer,
        }
        subscription_state_logger.info(json.dumps(state_payload, separators=(",", ":")))

        if (
            result.new_status == SubscriptionStatus.PRO
            and result.previous_status != SubscriptionStatus.PRO
        ):
            log_audit_event(
                event=AuditEvent.SUBSCRIPTION_CREATED,
                tenant_schema=result.tenant_schema or tenant_schema or "",
                user_id=None,
                details={
                    "origin": "webhook",
                    "event_type": event_type,
                    "event_id": result.event_id,
                    "customer_id": result.customer_id,
                },
            )

        if event_type == "customer.subscription.deleted":
            log_audit_event(
                event=AuditEvent.SUBSCRIPTION_CANCELLED,
                tenant_schema=result.tenant_schema or tenant_schema or "",
                user_id=None,
                details={
                    "origin": "webhook",
                    "event_type": event_type,
                    "event_id": result.event_id,
                    "customer_id": result.customer_id,
                },
            )
            cancellation_logger.info(
                "Stripe subscription cancelled via webhook",
                extra={
                    "event": "billing_cancellation",
                    "status": "success",
                    "tenant_schema": sanitized_schema,
                    "event_id": sanitized_event_id,
                    "customer_id": sanitized_customer,
                },
            )

        return Response(status=status.HTTP_200_OK)
