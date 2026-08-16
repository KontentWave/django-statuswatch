"""
Comprehensive tests for multi-tenant authentication (multi_tenant_auth.py).

Tests cover:
- Single tenant auto-login
- Multiple tenant selection flow
- Tenant-specific login (subdomain)
- Invalid credentials
- Missing credentials
- User not found
- Cross-tenant security

Target Coverage: 80%+ (currently 22%)
"""

import pytest
from api.models import UserProfile
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def public_api_client(db):
    """
    Create API client that simulates access via a public domain.

    This ensures request.tenant is NOT set to a specific tenant (or falls back to public),
    triggering SCENARIO 2 (Centralized Login) in MultiTenantLoginView.

    We use a domain that is NOT mapped to 'test_tenant' (which is mapped to 'testserver').
    Relies on SHOW_PUBLIC_IF_NO_TENANT_FOUND=True to fall back to public schema.
    """
    return APIClient(HTTP_HOST="public.localhost")


@pytest.fixture
def api_client():
    """Create API client for testing."""
    return APIClient()


@pytest.fixture
def user_in_single_tenant(tenant_factory):
    """
    Create a user that exists in ONLY ONE tenant.
    This should trigger auto-login (no tenant selection needed).
    """
    tenant = tenant_factory("Acme Corporation")

    with schema_context(tenant.schema_name):
        user = User.objects.create_user(
            username="alice@acme.com",
            email="alice@acme.com",
            password="SecurePass123!",
            first_name="Alice",
            last_name="Acme",
        )

    return {
        "tenant": tenant,
        "user": user,
        "email": "alice@acme.com",
        "password": "SecurePass123!",
    }


@pytest.fixture
def user_in_multiple_tenants(tenant_factory):
    """
    Create a user with the SAME EMAIL in MULTIPLE tenants.
    This should trigger tenant selection flow.
    """
    tenant1 = tenant_factory("Stark Industries")
    tenant2 = tenant_factory("Wayne Enterprises")

    email = "consultant@example.com"
    password = "MultiTenant123!"

    # Create user in first tenant
    with schema_context(tenant1.schema_name):
        user1 = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name="Tony",
            last_name="Stark",
        )

    # Create user with SAME EMAIL in second tenant
    with schema_context(tenant2.schema_name):
        user2 = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name="Bruce",
            last_name="Wayne",
        )

    return {
        "tenant1": tenant1,
        "tenant2": tenant2,
        "user1": user1,
        "user2": user2,
        "email": email,
        "password": password,
    }


def _mark_profile_verified(user, schema_name):
    """Mark the given user's profile as verified inside the specified schema."""

    with schema_context(schema_name):
        profile, _created = UserProfile.objects.get_or_create(user=user)
        profile.email_verified = True
        profile.email_verification_token = None
        profile.email_verification_sent_at = timezone.now()
        profile.save(
            update_fields=[
                "email_verified",
                "email_verification_token",
                "email_verification_sent_at",
                "updated_at",
            ]
        )


@pytest.fixture
def verified_user_in_single_tenant(user_in_single_tenant):
    """Return single-tenant user data after marking the profile verified."""

    _mark_profile_verified(
        user_in_single_tenant["user"],
        user_in_single_tenant["tenant"].schema_name,
    )
    return user_in_single_tenant


@pytest.fixture
def verified_user_in_multiple_tenants(user_in_multiple_tenants):
    """Return multi-tenant user data after marking both tenant profiles verified."""

    _mark_profile_verified(
        user_in_multiple_tenants["user1"],
        user_in_multiple_tenants["tenant1"].schema_name,
    )
    _mark_profile_verified(
        user_in_multiple_tenants["user2"],
        user_in_multiple_tenants["tenant2"].schema_name,
    )
    return user_in_multiple_tenants


class TestMultiTenantLogin:
    """Test multi-tenant login scenarios."""

    def test_login_with_missing_username_returns_400(self, api_client):
        """Should reject login attempt with missing username."""
        response = api_client.post(
            "/api/auth/login/",
            {"password": "somepassword"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "required" in response.data["error"].lower()

    def test_login_with_missing_password_returns_400(self, api_client):
        """Should reject login attempt with missing password."""
        response = api_client.post(
            "/api/auth/login/",
            {"username": "user@example.com"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "required" in response.data["error"].lower()

    def test_login_with_nonexistent_user_returns_401(self, api_client):
        """Should reject login for user that doesn't exist in any tenant."""
        response = api_client.post(
            "/api/auth/login/",
            {
                "username": "nonexistent@example.com",
                "password": "WrongPassword123!",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data
        assert "credentials" in response.data["error"].lower()

    def test_login_with_wrong_password_returns_401(self, api_client, user_in_single_tenant):
        """Should reject login with incorrect password."""
        response = api_client.post(
            "/api/auth/login/",
            {
                "username": user_in_single_tenant["email"],
                "password": "WrongPassword123!",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data

    def test_user_in_single_tenant_auto_login(self, public_api_client, user_in_single_tenant):
        """
        Unverified users are blocked even when only one tenant match exists.
        """
        response = public_api_client.post(
            "/api/auth/login/",
            {
                "username": user_in_single_tenant["email"],
                "password": user_in_single_tenant["password"],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        error = response.data.get("error", {})
        assert error.get("code") == "email_unverified"
        assert "verify" in error.get("message", "").lower()

    def test_user_in_single_tenant_auto_login_when_verified(
        self, public_api_client, verified_user_in_single_tenant
    ):
        """Verified users with a single tenant receive tokens automatically."""

        response = public_api_client.post(
            "/api/auth/login/",
            {
                "username": verified_user_in_single_tenant["email"],
                "password": verified_user_in_single_tenant["password"],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify JWT tokens returned
        assert "access" in response.data
        assert "refresh" in response.data
        assert isinstance(response.data["access"], str)
        assert isinstance(response.data["refresh"], str)
        assert len(response.data["access"]) > 100  # JWT tokens are long

        # Verify tenant info returned
        assert (
            response.data["tenant_schema"] == verified_user_in_single_tenant["tenant"].schema_name
        )
        assert response.data["tenant_name"] == verified_user_in_single_tenant["tenant"].name
        assert "tenant_domain" in response.data

        # Verify user info returned
        assert "user" in response.data
        user_data = response.data["user"]
        assert user_data["id"] == verified_user_in_single_tenant["user"].id
        assert user_data["email"] == verified_user_in_single_tenant["email"]
        assert user_data["username"] == verified_user_in_single_tenant["email"]
        assert user_data["first_name"] == "Alice"
        assert user_data["last_name"] == "Acme"

        # Should NOT return tenant selection (no "multiple_tenants" field)
        assert "multiple_tenants" not in response.data
        assert "tenants" not in response.data

    def test_user_in_multiple_tenants_returns_selection(
        self, public_api_client, user_in_multiple_tenants
    ):
        """
        When user exists in MULTIPLE tenants, should return tenant list for selection.

        Uses public_api_client to simulate centralized login (SCENARIO 2).
        Expected: 200 OK with tenant options (no JWT tokens yet).
        """
        response = public_api_client.post(
            "/api/auth/login/",
            {
                "username": user_in_multiple_tenants["email"],
                "password": user_in_multiple_tenants["password"],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        # Should return tenant selection flag
        assert response.data["multiple_tenants"] is True

        # Should return list of tenant options
        assert "tenants" in response.data
        assert len(response.data["tenants"]) == 2

        # Verify tenant options structure
        tenant_options = response.data["tenants"]
        tenant_schemas = {t["tenant_schema"] for t in tenant_options}
        assert user_in_multiple_tenants["tenant1"].schema_name in tenant_schemas
        assert user_in_multiple_tenants["tenant2"].schema_name in tenant_schemas

        # Each option should have required fields
        for tenant_option in tenant_options:
            assert "tenant_schema" in tenant_option
            assert "tenant_name" in tenant_option
            assert "tenant_id" in tenant_option

        # Should include helpful message
        assert "message" in response.data
        assert "select" in response.data["message"].lower()

        # Should NOT return JWT tokens yet (user hasn't selected tenant)
        assert "access" not in response.data
        assert "refresh" not in response.data
        assert "user" not in response.data

    def test_tenant_selection_with_valid_tenant(self, api_client, user_in_multiple_tenants):
        """
        Unverified users are blocked even after selecting a valid tenant.
        """
        # Select the first tenant
        selected_schema = user_in_multiple_tenants["tenant1"].schema_name

        response = api_client.post(
            "/api/auth/login/",
            {
                "username": user_in_multiple_tenants["email"],
                "password": user_in_multiple_tenants["password"],
                "tenant_schema": selected_schema,  # User's selection
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        error = response.data.get("error", {})
        assert error.get("code") == "email_unverified"
        assert "verify" in error.get("message", "").lower()

    def test_tenant_selection_with_valid_tenant_when_verified(
        self, api_client, verified_user_in_multiple_tenants
    ):
        """Verified users obtain tokens after selecting a tenant."""

        selected_schema = verified_user_in_multiple_tenants["tenant1"].schema_name

        response = api_client.post(
            "/api/auth/login/",
            {
                "username": verified_user_in_multiple_tenants["email"],
                "password": verified_user_in_multiple_tenants["password"],
                "tenant_schema": selected_schema,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["tenant_schema"] == selected_schema
        assert response.data["tenant_name"] == verified_user_in_multiple_tenants["tenant1"].name
        assert "multiple_tenants" not in response.data
        assert "tenants" not in response.data

    def test_tenant_selection_with_invalid_tenant_returns_401(
        self, api_client, user_in_multiple_tenants
    ):
        """
        User tries to select a tenant they don't belong to.

        Expected: 401 Unauthorized (security violation).
        """
        response = api_client.post(
            "/api/auth/login/",
            {
                "username": user_in_multiple_tenants["email"],
                "password": user_in_multiple_tenants["password"],
                "tenant_schema": "nonexistent_tenant",  # Invalid tenant
            },
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data

    def test_login_from_tenant_subdomain(self, api_client, user_in_single_tenant):
        """
        Tenant-specific login is blocked until the email is verified.
        """
        tenant = user_in_single_tenant["tenant"]

        # Simulate request from tenant subdomain by setting tenant on request
        # In real scenario, TenantMiddleware sets this based on Host header
        # For testing, we can pass tenant_schema to force tenant-specific login
        response = api_client.post(
            "/api/auth/login/",
            {
                "username": user_in_single_tenant["email"],
                "password": user_in_single_tenant["password"],
                "tenant_schema": tenant.schema_name,  # Subdomain context
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        error = response.data.get("error", {})
        assert error.get("code") == "email_unverified"
        assert "verify" in error.get("message", "").lower()

    def test_login_from_tenant_subdomain_when_verified(
        self, api_client, verified_user_in_single_tenant
    ):
        """Verified tenant-specific logins succeed and return tokens."""

        tenant = verified_user_in_single_tenant["tenant"]

        response = api_client.post(
            "/api/auth/login/",
            {
                "username": verified_user_in_single_tenant["email"],
                "password": verified_user_in_single_tenant["password"],
                "tenant_schema": tenant.schema_name,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["tenant_schema"] == tenant.schema_name
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_from_wrong_tenant_subdomain_returns_401(
        self, api_client, user_in_multiple_tenants, tenant_factory
    ):
        """
        User tries to login from tenant subdomain they don't belong to.

        Expected: 401 Unauthorized (user doesn't exist in this tenant).
        """
        # Create a third tenant that the user is NOT part of
        wrong_tenant = tenant_factory("Wrong Company")

        response = api_client.post(
            "/api/auth/login/",
            {
                "username": user_in_multiple_tenants["email"],
                "password": user_in_multiple_tenants["password"],
                "tenant_schema": wrong_tenant.schema_name,  # User not in this tenant
            },
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data

    def test_centralized_login_searches_all_tenants(self, public_api_client, user_in_single_tenant):
        """
        Centralized login locates the user but blocks until verification.
        """
        # Don't specify tenant_schema - this simulates centralized login
        response = public_api_client.post(
            "/api/auth/login/",
            {
                "username": user_in_single_tenant["email"],
                "password": user_in_single_tenant["password"],
                # No tenant_schema - centralized mode
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        error = response.data.get("error", {})
        assert error.get("code") == "email_unverified"

    def test_centralized_login_searches_all_tenants_when_verified(
        self, public_api_client, verified_user_in_single_tenant
    ):
        """Centralized login succeeds once the email address is verified."""

        response = public_api_client.post(
            "/api/auth/login/",
            {
                "username": verified_user_in_single_tenant["email"],
                "password": verified_user_in_single_tenant["password"],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response.data["tenant_schema"] == verified_user_in_single_tenant["tenant"].schema_name
        )
        assert "access" in response.data


class TestMultiTenantLoginEdgeCases:
    """Test edge cases and error handling."""

    def test_inactive_user_cannot_login(self, api_client, tenant_factory):
        """Inactive users should not be able to login."""
        tenant = tenant_factory("Test Corp")

        with schema_context(tenant.schema_name):
            User.objects.create_user(
                username="inactive@test.com",
                email="inactive@test.com",
                password="TestPass123!",
                is_active=False,  # Inactive user
            )

        response = api_client.post(
            "/api/auth/login/",
            {
                "username": "inactive@test.com",
                "password": "TestPass123!",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data

    def test_response_does_not_leak_password(self, api_client, user_in_single_tenant):
        """Verify password is never in response (security check)."""
        response = api_client.post(
            "/api/auth/login/",
            {
                "username": user_in_single_tenant["email"],
                "password": user_in_single_tenant["password"],
            },
            format="json",
        )

        # Convert entire response to string and check for password
        response_str = str(response.data).lower()
        assert user_in_single_tenant["password"].lower() not in response_str
        assert "password" not in response.data

    def test_response_includes_tenant_domain_when_verified(
        self, public_api_client, verified_user_in_single_tenant
    ):
        """Successful centralized responses include tenant domain for redirects."""

        response = public_api_client.post(
            "/api/auth/login/",
            {
                "username": verified_user_in_single_tenant["email"],
                "password": verified_user_in_single_tenant["password"],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "tenant_domain" in response.data

        # Should be a valid domain format
        domain = response.data["tenant_domain"]
        assert isinstance(domain, str)
        assert len(domain) > 0
        # Should contain .localhost for dev environment
        assert ".localhost" in domain or "localhost" in domain
