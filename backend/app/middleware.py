"""
Custom middleware for StatusWatch.

Includes:
- SecurityHeadersMiddleware: Apply additional security headers (P1-03)
"""

from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Apply additional security headers not covered by Django's SecurityMiddleware.

    Headers applied:
    - Permissions-Policy: Control browser features
    - Content-Security-Policy: Prevent XSS attacks

    Note: Django's SecurityMiddleware already applies:
    - X-Frame-Options
    - X-Content-Type-Options
    - Strict-Transport-Security (HSTS)
    - Referrer-Policy
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Apply Permissions-Policy
        if hasattr(settings, "PERMISSIONS_POLICY"):
            policy_parts = []
            for feature, allowed_origins in settings.PERMISSIONS_POLICY.items():
                if allowed_origins:
                    origins = " ".join(
                        f'"{origin}"' if origin != "*" else origin for origin in allowed_origins
                    )
                    policy_parts.append(f"{feature}=({origins})")
                else:
                    policy_parts.append(f"{feature}=()")

            if policy_parts:
                response["Permissions-Policy"] = ", ".join(policy_parts)

        # Apply Content-Security-Policy
        if hasattr(settings, "CSP_DEFAULT_SRC"):
            csp_directives = []

            # Build CSP directives from settings
            csp_mapping = {
                "default-src": "CSP_DEFAULT_SRC",
                "script-src": "CSP_SCRIPT_SRC",
                "style-src": "CSP_STYLE_SRC",
                "font-src": "CSP_FONT_SRC",
                "img-src": "CSP_IMG_SRC",
                "connect-src": "CSP_CONNECT_SRC",
                "frame-ancestors": "CSP_FRAME_ANCESTORS",
                "base-uri": "CSP_BASE_URI",
                "form-action": "CSP_FORM_ACTION",
            }

            for directive, setting_name in csp_mapping.items():
                if hasattr(settings, setting_name):
                    sources = getattr(settings, setting_name)
                    if sources:
                        csp_directives.append(f"{directive} {' '.join(sources)}")

            if csp_directives:
                response["Content-Security-Policy"] = "; ".join(csp_directives)

        return response
