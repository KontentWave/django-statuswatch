"""
Custom exceptions for StatusWatch API.

Provides standardized error responses without leaking internal details.
"""

from rest_framework.exceptions import APIException


class BaseStatusWatchException(APIException):
    """
    Base exception for all StatusWatch custom exceptions.

    Ensures consistent error response format.
    """

    status_code = 500
    default_detail = "An error occurred. Please try again later."
    default_code = "error"


class TenantCreationError(BaseStatusWatchException):
    """
    Raised when tenant (organization) creation fails.

    This can happen due to database issues, schema conflicts, etc.
    The actual error is logged but not exposed to users.
    """

    status_code = 500
    default_detail = "Failed to create organization. Please try again or contact support."
    default_code = "tenant_creation_failed"


class DuplicateEmailError(BaseStatusWatchException):
    """
    Raised when a user tries to register with an email that already exists.
    """

    status_code = 409
    default_detail = "This email address is already registered."
    default_code = "duplicate_email"


class SchemaConflictError(BaseStatusWatchException):
    """
    Raised when there's a conflict with tenant schema naming.
    """

    status_code = 409
    default_detail = "Organization name is not available. Please choose another."
    default_code = "schema_conflict"


class PaymentProcessingError(BaseStatusWatchException):
    """
    Raised when payment processing fails.

    Sanitizes Stripe errors to prevent leaking sensitive data.
    """

    status_code = 402
    default_detail = "Payment processing failed. Please check your payment method and try again."
    default_code = "payment_failed"


class InvalidPaymentMethodError(BaseStatusWatchException):
    """
    Raised when payment method is invalid or declined.
    """

    status_code = 400
    default_detail = "Payment method is invalid. Please use a different payment method."
    default_code = "invalid_payment_method"


class RateLimitExceededError(BaseStatusWatchException):
    """
    Raised when user exceeds rate limits (in addition to DRF throttling).
    """

    status_code = 429
    default_detail = "Too many requests. Please slow down and try again later."
    default_code = "rate_limit_exceeded"


class ConfigurationError(BaseStatusWatchException):
    """
    Raised when there's a server configuration issue.

    Details are logged but not exposed to users.
    """

    status_code = 500
    default_detail = "Service is temporarily unavailable. Please try again later."
    default_code = "configuration_error"
