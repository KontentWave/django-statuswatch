"""
Middleware to allow HTTP access to internal endpoints.

This middleware exempts specific internal endpoints (like Caddy's on-demand TLS
validation) from HTTPS redirect while keeping HTTPS enforcement for all other routes.
"""

import logging

logger = logging.getLogger(__name__)


class InternalEndpointMiddleware:
    """
    Allow HTTP access to internal endpoints without HTTPS redirect.

    This middleware must be placed BEFORE SecurityMiddleware in MIDDLEWARE settings
    to prevent SECURE_SSL_REDIRECT from redirecting internal endpoints.

    Internal endpoints (HTTP allowed):
    - /api/internal/validate-domain/ (Caddy on-demand TLS validation)
    - /health/live/ (Health checks)
    - /metrics/ (Monitoring - if unauthenticated)
    """

    # Paths that should allow HTTP access
    HTTP_ALLOWED_PATHS = [
        "/api/internal/validate-domain/",
        "/health/",
        "/health/live/",
        "/health/ready/",
        "/healthz",
        "/metrics/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if this is an internal endpoint that should allow HTTP
        if self._is_internal_endpoint(request.path):
            # Mark request to skip HTTPS redirect in SecurityMiddleware
            request._skip_secure_redirect = True

            logger.debug(
                f"Internal endpoint accessed via HTTP: {request.path}",
                extra={
                    "path": request.path,
                    "method": request.method,
                    "remote_addr": request.META.get("REMOTE_ADDR"),
                    "http_allowed": True,
                },
            )

        response = self.get_response(request)
        return response

    def _is_internal_endpoint(self, path):
        """Check if path is an internal endpoint that allows HTTP."""
        return any(path.startswith(allowed_path) for allowed_path in self.HTTP_ALLOWED_PATHS)
