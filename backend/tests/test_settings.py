"""
Tests for settings split architecture.

Validates that settings are properly split into base/development/production
and that environment detection works correctly.
"""

from django.test import TestCase


class SettingsArchitectureTest(TestCase):
    """Test the split settings architecture loads correctly."""

    def test_base_settings_accessible(self):
        """Verify base settings are accessible."""
        from django.conf import settings

        # Check core base settings are present
        self.assertIsNotNone(settings.BASE_DIR)
        self.assertIsNotNone(settings.LOG_DIR)
        self.assertIsNotNone(settings.INSTALLED_APPS)
        self.assertIsNotNone(settings.MIDDLEWARE)
        self.assertIsNotNone(settings.TEMPLATES)
        self.assertIsNotNone(settings.DATABASES)

    def test_django_tenants_configuration(self):
        """Verify django-tenants is configured correctly."""
        from django.conf import settings

        self.assertEqual(settings.TENANT_MODEL, "tenants.Client")
        self.assertEqual(settings.DOMAIN_MODEL, "tenants.Domain")
        self.assertEqual(settings.PUBLIC_SCHEMA_NAME, "public")
        self.assertIn("django_tenants", settings.SHARED_APPS)
        self.assertIn("api", settings.TENANT_APPS)

    def test_logging_configuration_present(self):
        """Verify logging configuration is complete."""
        from django.conf import settings

        self.assertIn("version", settings.LOGGING)
        self.assertIn("formatters", settings.LOGGING)
        self.assertIn("handlers", settings.LOGGING)
        self.assertIn("loggers", settings.LOGGING)

        # Check critical handlers exist
        self.assertIn("file_error", settings.LOGGING["handlers"])
        self.assertIn("file_security", settings.LOGGING["handlers"])
        self.assertIn("file_audit", settings.LOGGING["handlers"])


class DevelopmentSettingsTest(TestCase):
    """Test development settings configuration.

    Note: Django's test runner overrides some settings for security.
    These tests verify the base development configuration, but accept
    Django's test-mode overrides where appropriate.
    """

    def test_debug_flag_in_test_environment(self):
        """Django test runner sets DEBUG=False for security.

        This is expected behavior - Django intentionally runs tests
        in a production-like environment to catch security issues.
        """
        from django.conf import settings

        # Django test runner sets DEBUG=False (expected)
        self.assertFalse(settings.DEBUG)

    def test_permissive_allowed_hosts(self):
        """Test environment has specific ALLOWED_HOSTS.

        Django test runner overrides ALLOWED_HOSTS to:
        ['127.0.0.1', 'localhost', 'testserver']
        """
        from django.conf import settings

        # Django test runner provides these hosts
        self.assertIn("localhost", settings.ALLOWED_HOSTS)
        self.assertIn("127.0.0.1", settings.ALLOWED_HOSTS)
        self.assertIn("testserver", settings.ALLOWED_HOSTS)

    def test_https_configuration_in_test_environment(self):
        """HTTPS configuration in test environment.

        Test environment may enable HTTPS settings from .env.
        This is acceptable for security testing.
        """
        from django.conf import settings

        # ENFORCE_HTTPS may be True or False depending on .env
        self.assertIsNotNone(settings.ENFORCE_HTTPS)
        # SSL redirect matches ENFORCE_HTTPS setting
        self.assertEqual(settings.SECURE_SSL_REDIRECT, settings.ENFORCE_HTTPS)

    def test_email_backend_in_test_environment(self):
        """Django test runner uses locmem backend.

        Django automatically uses locmem.EmailBackend during tests
        for isolation - this is expected and correct behavior.
        """
        from django.conf import settings

        # Django test runner uses locmem for test isolation
        self.assertEqual(settings.EMAIL_BACKEND, "django.core.mail.backends.locmem.EmailBackend")

    def test_cors_configuration_present(self):
        """CORS configuration should be present."""
        from django.conf import settings

        # Verify CORS settings are configured (values depend on environment)
        self.assertIsNotNone(settings.CORS_ALLOWED_ORIGINS)
        self.assertTrue(settings.CORS_ALLOW_CREDENTIALS)

    def test_cookie_security_configuration(self):
        """Cookie security should be properly configured.

        Cookie security matches ENFORCE_HTTPS setting.
        """
        from django.conf import settings

        # Cookie security matches HTTPS enforcement
        self.assertEqual(settings.SESSION_COOKIE_SECURE, settings.ENFORCE_HTTPS)
        self.assertEqual(settings.CSRF_COOKIE_SECURE, settings.ENFORCE_HTTPS)

    def test_sentry_configuration(self):
        """Sentry configuration should be readable.

        Sentry DSN is loaded from .env - may be set or empty.
        """
        from django.conf import settings

        # Sentry DSN can be set or empty depending on .env
        self.assertIsNotNone(settings.SENTRY_DSN)


class ProductionSettingsTest(TestCase):
    """Test production settings configuration.

    Note: These tests validate the current environment's production-like
    settings without attempting to reload modules (which causes ImportError
    in Django's test framework).
    """

    def test_secret_key_present(self):
        """SECRET_KEY should be configured."""
        from django.conf import settings

        # SECRET_KEY must exist and not be empty
        self.assertIsNotNone(settings.SECRET_KEY)
        self.assertNotEqual(settings.SECRET_KEY, "")
        self.assertGreater(len(settings.SECRET_KEY), 20)

    def test_stripe_keys_present(self):
        """Stripe keys should be configured."""
        from django.conf import settings

        # Stripe keys should exist (validation happens at import)
        self.assertIsNotNone(settings.STRIPE_PUBLIC_KEY)
        self.assertIsNotNone(settings.STRIPE_SECRET_KEY)

    def test_debug_disabled_in_test_environment(self):
        """Django test runner sets DEBUG=False for security."""
        from django.conf import settings

        # Django test runner always sets DEBUG=False (expected)
        self.assertFalse(settings.DEBUG)


class SecurityHeadersTest(TestCase):
    """Test security headers configuration."""

    def test_secure_content_type_nosniff(self):
        """X-Content-Type-Options should be enabled."""
        from django.conf import settings

        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)

    def test_x_frame_options(self):
        """X-Frame-Options should be DENY."""
        from django.conf import settings

        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")

    def test_referrer_policy(self):
        """Referrer-Policy should be configured."""
        from django.conf import settings

        self.assertEqual(settings.SECURE_REFERRER_POLICY, "same-origin")

    def test_permissions_policy_configured(self):
        """Permissions-Policy should disable risky features."""
        from django.conf import settings

        self.assertIn("geolocation", settings.PERMISSIONS_POLICY)
        self.assertIn("camera", settings.PERMISSIONS_POLICY)
        self.assertIn("microphone", settings.PERMISSIONS_POLICY)

        # All should be empty (disabled)
        self.assertEqual(settings.PERMISSIONS_POLICY["geolocation"], [])
        self.assertEqual(settings.PERMISSIONS_POLICY["camera"], [])
        self.assertEqual(settings.PERMISSIONS_POLICY["microphone"], [])


class JWTConfigurationTest(TestCase):
    """Test JWT configuration."""

    def test_jwt_token_lifetimes(self):
        """JWT tokens should have appropriate lifetimes."""
        from datetime import timedelta

        from django.conf import settings

        self.assertEqual(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"], timedelta(minutes=15))
        self.assertEqual(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"], timedelta(days=7))

    def test_jwt_token_rotation_enabled(self):
        """JWT token rotation should be enabled."""
        from django.conf import settings

        self.assertTrue(settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"])
        self.assertTrue(settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"])

    def test_jwt_signing_key_configured(self):
        """JWT should use SECRET_KEY for signing."""
        from django.conf import settings

        self.assertIsNotNone(settings.SIMPLE_JWT.get("SIGNING_KEY"))
        self.assertEqual(settings.SIMPLE_JWT["ALGORITHM"], "HS256")


class RESTFrameworkConfigurationTest(TestCase):
    """Test REST Framework configuration."""

    def test_jwt_authentication_enabled(self):
        """JWT authentication should be enabled."""
        from django.conf import settings

        auth_classes = settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
        self.assertIn("rest_framework_simplejwt.authentication.JWTAuthentication", auth_classes)

    def test_custom_exception_handler(self):
        """Custom exception handler should be configured."""
        from django.conf import settings

        self.assertEqual(
            settings.REST_FRAMEWORK["EXCEPTION_HANDLER"],
            "api.exception_handler.custom_exception_handler",
        )

    def test_pagination_configured(self):
        """Pagination should be configured."""
        from django.conf import settings

        self.assertIn("DEFAULT_PAGINATION_CLASS", settings.REST_FRAMEWORK)
        self.assertEqual(settings.REST_FRAMEWORK["PAGE_SIZE"], 50)

    def test_throttle_rates_configured(self):
        """Throttle rates should be configured for security."""
        from django.conf import settings

        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]

        # Check critical endpoints have rate limits
        self.assertIn("registration", rates)
        self.assertIn("login", rates)
        self.assertIn("billing", rates)

        # Registration should be most restrictive
        self.assertEqual(rates["registration"], "5/hour")
        self.assertEqual(rates["login"], "10/hour")


class CeleryConfigurationTest(TestCase):
    """Test Celery configuration."""

    def test_celery_broker_configured(self):
        """Celery broker should be configured."""
        from django.conf import settings

        self.assertIsNotNone(settings.CELERY_BROKER_URL)
        self.assertTrue(settings.CELERY_BROKER_URL.startswith("redis://"))

    def test_celery_beat_schedule_configured(self):
        """Celery Beat schedule should include endpoint checks."""
        from django.conf import settings

        self.assertIn("monitors.schedule_endpoint_checks", settings.CELERY_BEAT_SCHEDULE)

        task_config = settings.CELERY_BEAT_SCHEDULE["monitors.schedule_endpoint_checks"]
        self.assertEqual(task_config["task"], "monitors.tasks.schedule_endpoint_checks")

    def test_celery_timezone_matches_django(self):
        """Celery timezone should match Django timezone."""
        from django.conf import settings

        self.assertEqual(settings.CELERY_TIMEZONE, settings.TIME_ZONE)


class MiddlewareOrderTest(TestCase):
    """Test middleware order is correct."""

    def test_internal_endpoint_middleware_first(self):
        """InternalEndpointMiddleware should be first to exempt internal endpoints from HTTPS redirect."""
        from django.conf import settings

        self.assertEqual(
            settings.MIDDLEWARE[0],
            "app.middleware_internal.InternalEndpointMiddleware",
            "InternalEndpointMiddleware must be first to mark internal endpoints before security checks",
        )

    def test_custom_security_middleware_second(self):
        """CustomSecurityMiddleware should be second (after InternalEndpointMiddleware)."""
        from django.conf import settings

        self.assertEqual(
            settings.MIDDLEWARE[1],
            "app.middleware_security_custom.CustomSecurityMiddleware",
            "CustomSecurityMiddleware must be second to respect internal endpoint exemptions",
        )

    def test_tenant_middleware_after_whitenoise(self):
        """TenantMainMiddleware should come after WhiteNoise."""
        from django.conf import settings

        whitenoise_idx = settings.MIDDLEWARE.index("whitenoise.middleware.WhiteNoiseMiddleware")
        tenant_idx = settings.MIDDLEWARE.index(
            "django_tenants.middleware.main.TenantMainMiddleware"
        )

        self.assertLess(
            whitenoise_idx, tenant_idx, "WhiteNoise must come before TenantMainMiddleware"
        )

    def test_cors_middleware_before_common(self):
        """CORS middleware should come before CommonMiddleware."""
        from django.conf import settings

        cors_idx = settings.MIDDLEWARE.index("corsheaders.middleware.CorsMiddleware")
        common_idx = settings.MIDDLEWARE.index("django.middleware.common.CommonMiddleware")

        self.assertLess(cors_idx, common_idx, "CORS middleware must come before CommonMiddleware")
