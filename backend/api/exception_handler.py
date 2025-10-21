"""
Custom exception handler for Django REST Framework.

Sanitizes error responses to prevent information leakage while maintaining
useful debugging information in logs.
"""

import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .logging_utils import sanitize_log_value

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that sanitizes error messages.

    - In DEBUG mode: Shows detailed errors for development
    - In production: Returns generic messages, logs details
    - Sanitizes Stripe errors to prevent API key leakage
    - Prevents SQL query exposure from database errors

    Args:
        exc: The exception instance
        context: Dict with view, request, args, kwargs

    Returns:
        Response object with sanitized error message
    """
    # Get the standard DRF error response
    response = drf_exception_handler(exc, context)

    # If DRF didn't handle it, we need to
    if response is None:
        response = handle_generic_exception(exc, context)

    # Log the actual error for debugging
    log_exception(exc, context, response)

    # Sanitize the response in production
    if not settings.DEBUG and response is not None:
        response = sanitize_error_response(response, exc)

    return response


def handle_generic_exception(exc, context):
    """
    Handle exceptions that DRF doesn't handle by default.

    This includes Python exceptions, database errors, etc.
    """
    # Get request info for logging
    request = context.get("request")
    view = context.get("view")

    # Log the unhandled exception
    message = sanitize_log_value(
        f"Unhandled exception in {view.__class__.__name__ if view else 'unknown'}: {exc}"
    )
    logger.error(
        message,
        exc_info=settings.DEBUG,
        extra={
            "request_path": sanitize_log_value(request.path if request else None),
            "request_method": request.method if request else None,
            "exception_type": type(exc).__name__,
        },
    )

    # Return generic error response
    return Response(
        {
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred. Please try again later.",
            }
        },
        status=500,
    )


def sanitize_error_response(response, exc):
    """
    Sanitize error response to prevent information leakage.

    Removes:
    - Stack traces
    - File paths
    - SQL queries
    - API keys
    - Internal implementation details
    """
    if not response.data:
        return response

    # Check for Stripe errors
    if "stripe" in str(type(exc)).lower() or "stripe" in str(exc).lower():
        response.data = {
            "error": {
                "code": "payment_error",
                "message": "Payment processing failed. Please try again or contact support.",
            }
        }
        return response

    # Sanitize database errors
    if any(keyword in str(exc).lower() for keyword in ["sql", "database", "relation", "table"]):
        response.data = {
            "error": {
                "code": "database_error",
                "message": "A database error occurred. Please try again later.",
            }
        }
        return response

    # Keep validation errors (they're safe to show)
    if isinstance(exc, exceptions.ValidationError):
        # Validation errors are already sanitized by DRF
        return response

    # Keep throttling errors (they're safe to show)
    if isinstance(exc, exceptions.Throttled):
        return response

    # Keep authentication/permission errors (they're safe to show)
    if isinstance(
        exc,
        (
            exceptions.AuthenticationFailed,
            exceptions.NotAuthenticated,
            exceptions.PermissionDenied,
            PermissionDenied,
        ),
    ):
        return response

    # Keep 404 errors (they're safe to show)
    if isinstance(exc, (exceptions.NotFound, Http404)):
        return response

    # For everything else, return generic error
    if response.status_code >= 500:
        response.data = {
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred. Please try again later.",
            }
        }

    return response


def log_exception(exc, context, response):
    """
    Log exception details for debugging.

    Logs at different levels based on error type:
    - 5xx errors: ERROR level
    - 4xx errors: WARNING level
    - Throttling: INFO level
    """
    request = context.get("request")
    view = context.get("view")

    # Determine log level
    if response and response.status_code >= 500:
        log_level = logging.ERROR
    elif isinstance(exc, exceptions.Throttled):
        log_level = logging.INFO
    else:
        log_level = logging.WARNING

    # Build log message
    view_name = view.__class__.__name__ if view else "Unknown"
    request_path = request.path if request else "Unknown"
    request_method = request.method if request else "Unknown"

    message = sanitize_log_value(f"{type(exc).__name__} in {view_name}: {exc}")
    extra = {
        "exception_type": type(exc).__name__,
        "request_path": sanitize_log_value(request_path),
        "request_method": request_method,
        "status_code": response.status_code if response else None,
        "user": sanitize_log_value(
            str(request.user) if request and hasattr(request, "user") else "Anonymous"
        ),
    }

    logger.log(
        log_level,
        message,
        exc_info=settings.DEBUG and log_level == logging.ERROR,
        extra=extra,
    )
