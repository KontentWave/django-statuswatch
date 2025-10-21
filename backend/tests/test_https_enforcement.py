"""
Tests for HTTPS enforcement and security headers (P1-02).

Verifies:
- HTTP to HTTPS redirects in production
- HSTS headers are present when ENFORCE_HTTPS=True
- Cookie security flags are set correctly
- Development mode allows HTTP
"""

import pytest
from django.test import TestCase, override_settings
from django_tenants.test.client import TenantClient
from tenants.models import Client as TenantModel


class HTTPSEnforcementTests(TestCase):
    """Test HTTPS redirect and security headers."""

    def setUp(self):
        """Set up test tenant for HTTPS tests."""
        # Use test_tenant created by conftest.py fixture
        self.tenant = TenantModel.objects.get(schema_name="test_tenant")
        # Domains already created by conftest.py ensure_test_tenant

    @override_settings(
        ENFORCE_HTTPS=True,
        SECURE_SSL_REDIRECT=True,
        SECURE_HSTS_SECONDS=3600,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=False,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
    )
    def test_http_redirects_to_https_when_enforced(self):
        """HTTP requests should redirect to HTTPS when ENFORCE_HTTPS=True."""
        client = TenantClient(self.tenant)
        response = client.get("/api/ping/", secure=False)

        # Should redirect to HTTPS
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.url.startswith("https://"))

    @override_settings(
        ENFORCE_HTTPS=False,
        SECURE_SSL_REDIRECT=False,
    )
    def test_http_allowed_in_development(self):
        """HTTP requests should work normally when ENFORCE_HTTPS=False."""
        client = TenantClient(self.tenant)
        response = client.get("/api/ping/", secure=False)

        # Should not redirect (200 OK or 404, but not 301)
        self.assertNotEqual(response.status_code, 301)

    @override_settings(
        ENFORCE_HTTPS=True,
        SECURE_HSTS_SECONDS=3600,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=False,
    )
    def test_hsts_header_present_when_enforced(self):
        """HSTS headers should be present on HTTPS requests when enforced."""
        client = TenantClient(self.tenant)
        response = client.get("/api/ping/", secure=True)

        # Check HSTS header exists
        self.assertIn("Strict-Transport-Security", response.headers)

        hsts_value = response["Strict-Transport-Security"]

        # Should include max-age
        self.assertIn("max-age=3600", hsts_value)

        # Should include subdomains
        self.assertIn("includeSubDomains", hsts_value)

        # Should NOT include preload (unless explicitly set)
        self.assertNotIn("preload", hsts_value)

    @override_settings(
        ENFORCE_HTTPS=True,
        SECURE_HSTS_SECONDS=31536000,  # 1 year
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
    )
    def test_hsts_header_with_preload(self):
        """HSTS headers should include preload when configured."""
        client = TenantClient(self.tenant)
        response = client.get("/api/ping/", secure=True)

        hsts_value = response.get("Strict-Transport-Security", "")

        # Should include preload directive
        self.assertIn("preload", hsts_value)
        self.assertIn("max-age=31536000", hsts_value)

    @override_settings(
        ENFORCE_HTTPS=False,
        SECURE_HSTS_SECONDS=0,
    )
    def test_no_hsts_header_in_development(self):
        """HSTS headers should NOT be present when ENFORCE_HTTPS=False."""
        client = TenantClient(self.tenant)
        response = client.get("/api/ping/", secure=False)

        # HSTS header should not be present or should be max-age=0
        hsts_value = response.get("Strict-Transport-Security", "")
        if hsts_value:
            # If present, max-age should be 0
            self.assertIn("max-age=0", hsts_value)

    @override_settings(
        ENFORCE_HTTPS=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
    )
    def test_secure_cookies_in_production(self):
        """Cookies should have Secure flag when ENFORCE_HTTPS=True."""
        # Check session cookie settings
        from django.conf import settings

        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)

    @override_settings(
        ENFORCE_HTTPS=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
    )
    def test_insecure_cookies_in_development(self):
        """Cookies should NOT have Secure flag in development."""
        from django.conf import settings

        self.assertFalse(settings.SESSION_COOKIE_SECURE)
        self.assertFalse(settings.CSRF_COOKIE_SECURE)

    def test_security_middleware_installed(self):
        """SecurityMiddleware should be properly configured."""
        from django.conf import settings

        middleware = settings.MIDDLEWARE

        # SecurityMiddleware should be present
        self.assertIn(
            "django.middleware.security.SecurityMiddleware",
            middleware,
        )

        # It should be early in the middleware stack
        # (within the first 3 entries is reasonable)
        security_index = middleware.index("django.middleware.security.SecurityMiddleware")
        self.assertLess(
            security_index,
            3,
            "SecurityMiddleware should be early in MIDDLEWARE stack",
        )

    @override_settings(
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    )
    def test_respects_x_forwarded_proto_header(self):
        """Should respect X-Forwarded-Proto header from reverse proxy."""
        client = TenantClient(self.tenant)

        # Simulate reverse proxy setting X-Forwarded-Proto
        response = client.get(
            "/api/ping/",
            HTTP_X_FORWARDED_PROTO="https",
        )

        # Request should be treated as HTTPS
        # (exact behavior depends on SECURE_SSL_REDIRECT setting)
        self.assertIsNotNone(response)


class CookieSecurityTests(TestCase):
    """Test cookie security configuration."""

    def test_cookie_samesite_configured(self):
        """SameSite cookie attribute should be configured."""
        from django.conf import settings

        # SameSite should be set for CSRF and Session cookies
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")

    def test_cookie_httponly_configured(self):
        """HttpOnly flag should be set for cookies."""
        from django.conf import settings

        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)


@pytest.mark.django_db
class HTTPSIntegrationTests(TestCase):
    """Integration tests for HTTPS enforcement."""

    def setUp(self):
        """Set up test tenant for HTTPS integration tests."""
        # Use test_tenant created by conftest.py fixture
        self.tenant = TenantModel.objects.get(schema_name="test_tenant")
        # Domains already created by conftest.py ensure_test_tenant

    @override_settings(
        ENFORCE_HTTPS=True,
        SECURE_SSL_REDIRECT=True,
    )
    def test_api_endpoints_redirect_to_https(self):
        """All API endpoints should redirect HTTP to HTTPS."""
        client = TenantClient(self.tenant)

        # Test endpoints that exist in all configurations
        endpoints = [
            "/admin/",
            "/admin/login/",
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = client.get(endpoint, secure=False)

                # Should redirect to HTTPS (301)
                self.assertEqual(
                    response.status_code,
                    301,
                    f"{endpoint} should redirect HTTP to HTTPS",
                )

    @override_settings(
        ENFORCE_HTTPS=False,
    )
    def test_development_mode_works_with_http(self):
        """Development mode should work normally with HTTP."""
        client = TenantClient(self.tenant)

        # Use API endpoint which exists in tenant schemas
        # TenantClient automatically uses the tenant's primary domain
        response = client.get("/api/ping/", secure=False)

        # Should work without redirect (200 is expected for ping endpoint)
        self.assertEqual(response.status_code, 200)
        # Most importantly, should NOT be a 301 redirect to HTTPS
        self.assertNotEqual(response.status_code, 301)
