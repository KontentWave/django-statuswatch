"""
Request/Response Logging Middleware for StatusWatch.

Logs all API requests and responses with timing, user context, and tenant information.
"""

import logging
import time

from api.logging_utils import sanitize_log_value
from django.utils.deprecation import MiddlewareMixin

request_logger = logging.getLogger("api.requests")


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Log all API requests and responses with timing information.

    Logs include:
    - Request method, path, query parameters
    - User ID and tenant context
    - IP address and user agent
    - Response status code and size
    - Request duration in milliseconds

    All sensitive data is sanitized before logging.
    """

    def process_request(self, request):
        """Log incoming request and start timer."""
        request._start_time = time.time()

        # Log incoming request
        request_logger.info(
            "Incoming request",
            extra={
                "request_id": getattr(request, "id", None),
                "method": request.method,
                "path": sanitize_log_value(request.path),
                "query_params": sanitize_log_value(dict(request.GET)),
                "ip_address": self._get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "user_id": getattr(request.user, "id", None) if hasattr(request, "user") else None,
                "tenant": (
                    getattr(request.tenant, "schema_name", None)
                    if hasattr(request, "tenant")
                    else None
                ),
            },
        )

    def process_response(self, request, response):
        """Log response with timing information."""
        # Calculate request duration
        if hasattr(request, "_start_time"):
            duration_ms = (time.time() - request._start_time) * 1000
        else:
            duration_ms = 0

        # Determine log level based on status code
        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO

        # Log response
        request_logger.log(
            log_level,
            "Request completed",
            extra={
                "request_id": getattr(request, "id", None),
                "method": request.method,
                "path": sanitize_log_value(request.path),
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "response_size_bytes": len(response.content) if hasattr(response, "content") else 0,
                "user_id": getattr(request.user, "id", None) if hasattr(request, "user") else None,
            },
        )

        return response

    @staticmethod
    def _get_client_ip(request):
        """Extract client IP address from request, handling proxies."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Get first IP in chain (original client)
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


class RequestIDMiddleware(MiddlewareMixin):
    """
    Generate unique request ID for tracking requests across systems.

    The request ID is:
    - Added to the request object as `request.id`
    - Included in response headers as `X-Request-ID`
    - Available for logging and error tracking
    """

    def process_request(self, request):
        """Generate and attach unique request ID."""
        import uuid

        request.id = str(uuid.uuid4())

    def process_response(self, request, response):
        """Add request ID to response headers."""
        if hasattr(request, "id"):
            response["X-Request-ID"] = request.id
        return response
