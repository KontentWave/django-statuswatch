"""
Custom SecurityMiddleware with support for internal endpoint exemptions.

Extends Django's SecurityMiddleware to skip HTTPS redirect for internal endpoints
marked by InternalEndpointMiddleware.
"""

from django.middleware.security import SecurityMiddleware as DjangoSecurityMiddleware


class CustomSecurityMiddleware(DjangoSecurityMiddleware):
    """
    Extended SecurityMiddleware that respects _skip_secure_redirect flag.

    This allows InternalEndpointMiddleware to exempt specific paths from
    HTTPS redirect while maintaining SECURE_SSL_REDIRECT=True for all other paths.
    """

    def process_request(self, request):
        # Check if this request should skip HTTPS redirect
        if getattr(request, "_skip_secure_redirect", False):
            # Temporarily disable SSL redirect for this request only
            original_redirect = self.redirect
            self.redirect = False
            try:
                return super().process_request(request)
            finally:
                self.redirect = original_redirect

        # Normal security processing for all other requests
        return super().process_request(request)
