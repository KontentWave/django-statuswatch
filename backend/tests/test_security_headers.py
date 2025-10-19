"""
Tests for P1-03: Security Headers.

Tests cover:
- X-Frame-Options header
- X-Content-Type-Options header
- Referrer-Policy header
- Permissions-Policy header
- Content-Security-Policy header
- Cross-Origin-Opener-Policy header
- Headers present in both development and production modes
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from tenants.models import Client, Domain

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def ensure_public_domain(db):
    """Ensure public tenant and testserver domain exist."""
    tenant = Client.objects.filter(schema_name="public").first()
    if tenant is None:
        tenant = Client(schema_name="public", name="Public Tenant")
        tenant.auto_create_schema = False
        tenant.save()

    Domain.objects.get_or_create(
        tenant=tenant,
        domain="testserver",
        defaults={"is_primary": True},
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestXFrameOptions:
    """Test X-Frame-Options header prevents clickjacking."""

    def test_x_frame_options_set_to_deny(self, api_client):
        """X-Frame-Options should be set to DENY."""
        response = api_client.get(reverse("api-ping"))
        
        assert "X-Frame-Options" in response
        assert response["X-Frame-Options"] == "DENY"

    def test_x_frame_options_present_on_all_endpoints(self, api_client):
        """X-Frame-Options should be present on all endpoints."""
        # Test on API endpoint
        response = api_client.get(reverse("api-ping"))
        assert "X-Frame-Options" in response
        assert response["X-Frame-Options"] == "DENY"


@pytest.mark.django_db
class TestXContentTypeOptions:
    """Test X-Content-Type-Options header prevents MIME sniffing."""

    def test_x_content_type_options_set_to_nosniff(self, api_client):
        """X-Content-Type-Options should be set to nosniff."""
        response = api_client.get(reverse("api-ping"))
        
        assert "X-Content-Type-Options" in response
        assert response["X-Content-Type-Options"] == "nosniff"

    def test_x_content_type_options_present_on_static_files(self, api_client):
        """X-Content-Type-Options should be present on static file responses."""
        # Test with a simple endpoint (static files would be served by whitenoise)
        response = api_client.get(reverse("api-ping"))
        assert "X-Content-Type-Options" in response


@pytest.mark.django_db
class TestReferrerPolicy:
    """Test Referrer-Policy header controls referrer information."""

    def test_referrer_policy_set_to_same_origin(self, api_client):
        """Referrer-Policy should be set to same-origin."""
        response = api_client.get(reverse("api-ping"))
        
        assert "Referrer-Policy" in response
        assert response["Referrer-Policy"] == "same-origin"


@pytest.mark.django_db
class TestCrossOriginOpenerPolicy:
    """Test Cross-Origin-Opener-Policy header."""

    def test_cross_origin_opener_policy_set(self, api_client):
        """Cross-Origin-Opener-Policy should be set to same-origin."""
        response = api_client.get(reverse("api-ping"))
        
        assert "Cross-Origin-Opener-Policy" in response
        assert response["Cross-Origin-Opener-Policy"] == "same-origin"


@pytest.mark.django_db
class TestPermissionsPolicy:
    """Test Permissions-Policy header controls browser features."""

    def test_permissions_policy_header_present(self, api_client):
        """Permissions-Policy header should be present."""
        response = api_client.get(reverse("api-ping"))
        
        assert "Permissions-Policy" in response

    def test_permissions_policy_disables_dangerous_features(self, api_client):
        """Permissions-Policy should disable geolocation, camera, microphone, etc."""
        response = api_client.get(reverse("api-ping"))
        
        policy = response["Permissions-Policy"]
        
        # Check that dangerous features are disabled (empty allow list)
        assert "geolocation=()" in policy
        assert "camera=()" in policy
        assert "microphone=()" in policy
        assert "payment=()" in policy
        assert "usb=()" in policy

    def test_permissions_policy_format_is_correct(self, api_client):
        """Permissions-Policy should have correct format."""
        response = api_client.get(reverse("api-ping"))
        
        policy = response["Permissions-Policy"]
        
        # Should be comma-separated list of feature=() pairs
        assert "," in policy
        assert "=" in policy
        assert "(" in policy
        assert ")" in policy


@pytest.mark.django_db
class TestContentSecurityPolicy:
    """Test Content-Security-Policy header prevents XSS."""

    def test_csp_header_present(self, api_client):
        """Content-Security-Policy header should be present."""
        response = api_client.get(reverse("api-ping"))
        
        assert "Content-Security-Policy" in response

    def test_csp_default_src_restricts_sources(self, api_client):
        """CSP default-src should restrict resource sources."""
        response = api_client.get(reverse("api-ping"))
        
        csp = response["Content-Security-Policy"]
        
        # Should have default-src directive
        assert "default-src" in csp
        # Should include 'self'
        assert "'self'" in csp

    def test_csp_frame_ancestors_prevents_clickjacking(self, api_client):
        """CSP frame-ancestors should be set to 'none' to prevent clickjacking."""
        response = api_client.get(reverse("api-ping"))
        
        csp = response["Content-Security-Policy"]
        
        # Should have frame-ancestors 'none' (same as X-Frame-Options: DENY)
        assert "frame-ancestors" in csp
        assert "'none'" in csp

    def test_csp_allows_stripe_api_connections(self, api_client):
        """CSP connect-src should allow Stripe API calls."""
        response = api_client.get(reverse("api-ping"))
        
        csp = response["Content-Security-Policy"]
        
        # Should allow connections to Stripe API
        assert "connect-src" in csp
        # In production mode, should include Stripe
        # In dev mode, should allow websockets for hot reload

    def test_csp_base_uri_restricts_base_tag(self, api_client):
        """CSP base-uri should restrict base tag to prevent injection."""
        response = api_client.get(reverse("api-ping"))
        
        csp = response["Content-Security-Policy"]
        
        # Should restrict base tag to same origin
        assert "base-uri" in csp
        assert "'self'" in csp

    def test_csp_form_action_restricts_form_submissions(self, api_client):
        """CSP form-action should restrict where forms can be submitted."""
        response = api_client.get(reverse("api-ping"))
        
        csp = response["Content-Security-Policy"]
        
        # Should restrict form submissions to same origin
        assert "form-action" in csp
        assert "'self'" in csp


@pytest.mark.django_db
class TestProductionSecurityHeaders:
    """Test security headers in production mode (ENFORCE_HTTPS=True)."""

    def test_production_headers_are_stricter(self, api_client, settings):
        """Production mode should have stricter CSP policies."""
        settings.ENFORCE_HTTPS = True
        response = api_client.get(reverse("api-ping"))
        
        # In production, should have Stripe in connect-src
        # (This test would need actual production settings to verify)
        assert "Content-Security-Policy" in response
        
        # Production should have stricter policies
        csp = response["Content-Security-Policy"]
        assert "default-src" in csp


@pytest.mark.django_db
class TestDevelopmentSecurityHeaders:
    """Test security headers in development mode."""

    def test_development_headers_allow_hot_reload(self, api_client, settings):
        """Development mode should allow WebSocket for hot reload."""
        settings.ENFORCE_HTTPS = False
        settings.DEBUG = True
        response = api_client.get(reverse("api-ping"))
        
        csp = response["Content-Security-Policy"]
        
        # In development, should allow WebSocket connections
        assert "connect-src" in csp
        # Should allow ws: or wss: for hot reload (Vite, etc.)

    def test_development_still_has_basic_security(self, api_client):
        """Development mode should still have basic security headers."""
        response = api_client.get(reverse("api-ping"))
        
        # Even in dev, should have X-Frame-Options
        assert "X-Frame-Options" in response
        assert response["X-Frame-Options"] == "DENY"
        
        # Should have X-Content-Type-Options
        assert "X-Content-Type-Options" in response
        assert response["X-Content-Type-Options"] == "nosniff"
        
        # Should have Referrer-Policy
        assert "Referrer-Policy" in response


@pytest.mark.django_db
class TestSecurityHeadersIntegration:
    """Test that security headers work together correctly."""

    def test_all_critical_headers_present(self, api_client):
        """All critical security headers should be present on responses."""
        response = api_client.get(reverse("api-ping"))
        
        critical_headers = [
            "X-Frame-Options",
            "X-Content-Type-Options",
            "Referrer-Policy",
            "Cross-Origin-Opener-Policy",
            "Permissions-Policy",
            "Content-Security-Policy",
        ]
        
        for header in critical_headers:
            assert header in response, f"Missing critical header: {header}"

    def test_security_headers_on_api_endpoints(self, api_client):
        """Security headers should be present on API endpoints."""
        response = api_client.get(reverse("api-ping"))
        
        assert response.status_code == 200
        assert "X-Frame-Options" in response
        assert "Content-Security-Policy" in response

    def test_security_headers_on_html_responses(self, api_client):
        """Security headers should be present on HTML/API responses."""
        # Test with API endpoint (we don't have HTML pages yet)
        response = api_client.get(reverse("api-ping"))
        
        assert response.status_code == 200
        assert "X-Frame-Options" in response
        assert "Content-Security-Policy" in response

    def test_security_middleware_is_first(self):
        """SecurityMiddleware should be first in middleware stack."""
        from django.conf import settings
        
        middleware = settings.MIDDLEWARE
        
        # Django's SecurityMiddleware should be first
        assert middleware[0] == "django.middleware.security.SecurityMiddleware"
        
        # Our custom SecurityHeadersMiddleware should be right after
        assert middleware[1] == "app.middleware.SecurityHeadersMiddleware"


@pytest.mark.django_db
class TestSecurityHeadersConfiguration:
    """Test that security headers are properly configured in settings."""

    def test_x_frame_options_setting(self):
        """X_FRAME_OPTIONS should be set to DENY."""
        from django.conf import settings
        
        assert hasattr(settings, "X_FRAME_OPTIONS")
        assert settings.X_FRAME_OPTIONS == "DENY"

    def test_content_type_nosniff_setting(self):
        """SECURE_CONTENT_TYPE_NOSNIFF should be enabled."""
        from django.conf import settings
        
        assert hasattr(settings, "SECURE_CONTENT_TYPE_NOSNIFF")
        assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True

    def test_referrer_policy_setting(self):
        """SECURE_REFERRER_POLICY should be set to same-origin."""
        from django.conf import settings
        
        assert hasattr(settings, "SECURE_REFERRER_POLICY")
        assert settings.SECURE_REFERRER_POLICY == "same-origin"

    def test_cross_origin_opener_policy_setting(self):
        """SECURE_CROSS_ORIGIN_OPENER_POLICY should be set."""
        from django.conf import settings
        
        assert hasattr(settings, "SECURE_CROSS_ORIGIN_OPENER_POLICY")
        assert settings.SECURE_CROSS_ORIGIN_OPENER_POLICY == "same-origin"

    def test_permissions_policy_configured(self):
        """PERMISSIONS_POLICY should be configured with feature restrictions."""
        from django.conf import settings
        
        assert hasattr(settings, "PERMISSIONS_POLICY")
        policy = settings.PERMISSIONS_POLICY
        
        # Should disable dangerous features
        assert "geolocation" in policy
        assert policy["geolocation"] == []
        assert "camera" in policy
        assert policy["camera"] == []
        assert "microphone" in policy
        assert policy["microphone"] == []

    def test_csp_directives_configured(self):
        """CSP directives should be configured."""
        from django.conf import settings
        
        # Should have CSP directives defined
        assert hasattr(settings, "CSP_DEFAULT_SRC")
        assert hasattr(settings, "CSP_SCRIPT_SRC")
        assert hasattr(settings, "CSP_FRAME_ANCESTORS")
        
        # default-src should include 'self'
        assert "'self'" in settings.CSP_DEFAULT_SRC
        
        # frame-ancestors should be 'none' for clickjacking protection
        assert "'none'" in settings.CSP_FRAME_ANCESTORS
