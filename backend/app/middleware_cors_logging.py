"""
CORS Logging Middleware

Logs all CORS-related request/response headers to help debug multi-tenant subdomain access.
Writes to: backend/logs/cors_debug.log

This middleware should be placed AFTER CorsMiddleware in MIDDLEWARE setting.
"""

import logging
import re
from collections.abc import Callable
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, HttpResponse

# Configure CORS debug logger
LOGS_DIR = Path(settings.BASE_DIR) / "logs"
LOGS_DIR.mkdir(exist_ok=True)

cors_logger = logging.getLogger("cors_debug")
cors_logger.setLevel(logging.DEBUG)

# File handler for CORS logs
cors_log_file = LOGS_DIR / "cors_debug.log"
file_handler = logging.FileHandler(cors_log_file)
file_handler.setLevel(logging.DEBUG)

# Detailed formatter
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(formatter)
cors_logger.addHandler(file_handler)
cors_logger.propagate = False  # Don't propagate to root logger


class CorsLoggingMiddleware:
    """
    Middleware to log CORS-related headers for debugging multi-tenant subdomain access.

    Logs:
    - Origin header from request
    - Host header from request
    - Whether origin matches allowed patterns
    - CORS response headers added by django-cors-headers

    This helps diagnose issues where frontend calls from tenant subdomains
    (e.g., http://acme.localhost:5173) are blocked by CORS.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

        # Get CORS config for validation
        self.allowed_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
        self.allowed_regexes = getattr(settings, "CORS_ALLOWED_ORIGIN_REGEXES", [])
        self.allow_all = getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False)

        cors_logger.info("=" * 80)
        cors_logger.info("CORS Logging Middleware initialized")
        cors_logger.info(f"CORS_ALLOW_ALL_ORIGINS: {self.allow_all}")
        cors_logger.info(f"CORS_ALLOWED_ORIGINS: {self.allowed_origins}")
        cors_logger.info(f"CORS_ALLOWED_ORIGIN_REGEXES: {self.allowed_regexes}")
        cors_logger.info("=" * 80)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Extract key headers
        origin = request.headers.get("Origin", None)
        host = request.headers.get("Host", None)
        referer = request.headers.get("Referer", None)
        method = request.method
        path = request.path

        # Log API requests (even without Origin header - Vite proxy may strip it)
        is_api_request = path.startswith("/api/")

        if origin:
            # CORS request with Origin header
            origin_allowed = self._check_origin_allowed(origin)

            cors_logger.debug(
                f"[CORS REQUEST] {method} {path} | "
                f"Origin: {origin} | "
                f"Host: {host} | "
                f"Allowed: {origin_allowed}"
            )

            if not origin_allowed:
                cors_logger.warning(
                    f"[CORS BLOCKED?] Origin '{origin}' may not match allowed patterns. "
                    f"Request: {method} {path}"
                )
        elif is_api_request:
            # API request without Origin (likely proxied)
            cors_logger.debug(
                f"[PROXY REQUEST] {method} {path} | "
                f"Host: {host} | "
                f"Referer: {referer} | "
                f"No Origin header (likely Vite proxy)"
            )

        # Process request
        response = self.get_response(request)

        # Log CORS response headers if present
        if origin:
            cors_headers = {
                key: value
                for key, value in response.items()
                if key.lower().startswith("access-control-")
            }

            if cors_headers:
                cors_logger.debug(
                    f"[CORS RESPONSE] {method} {path} | "
                    f"Status: {response.status_code} | "
                    f"Headers: {cors_headers}"
                )
            else:
                cors_logger.warning(
                    f"[CORS NO HEADERS] {method} {path} | "
                    f"Status: {response.status_code} | "
                    f"Origin: {origin} | "
                    f"No CORS headers in response - possible misconfiguration"
                )
        elif is_api_request:
            # Log proxy response status
            cors_logger.debug(
                f"[PROXY RESPONSE] {method} {path} | "
                f"Status: {response.status_code} | "
                f"Host: {host}"
            )

        return response

    def _check_origin_allowed(self, origin: str) -> bool:
        """
        Check if origin matches allowed origins or regex patterns.

        Args:
            origin: Origin header value (e.g., "http://acme.localhost:5173")

        Returns:
            True if origin is allowed, False otherwise
        """
        if self.allow_all:
            return True

        # Check exact matches
        if origin in self.allowed_origins:
            return True

        # Check regex patterns
        for pattern in self.allowed_regexes:
            try:
                if re.match(pattern, origin):
                    return True
            except re.error as e:
                cors_logger.error(f"Invalid regex pattern '{pattern}': {e}")

        return False
