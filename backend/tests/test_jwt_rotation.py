"""
Tests for P1-05: JWT Token Rotation and Blacklisting.

Tests cover:
- Token lifetime configuration (15 min access, 7 day refresh)
- Token refresh with rotation (new refresh token issued)
- Token blacklisting on logout
- Blacklisted tokens cannot be reused
- Access token expiration
"""

from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django_tenants.utils import schema_context
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(db):
    """Create a test user with a strong password in the test_tenant schema."""
    with schema_context("test_tenant"):
        user = User.objects.create_user(
            username="tokentest",
            password="TokenTest@123456",
            email="token@example.com",
        )
    return user


@pytest.mark.django_db
class TestJWTTokenLifetime:
    """Test JWT token lifetime configuration."""

    def test_access_token_lifetime_is_15_minutes(self):
        """Access tokens should expire after 15 minutes."""
        assert settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] == timedelta(minutes=15)

    def test_refresh_token_lifetime_is_7_days(self):
        """Refresh tokens should expire after 7 days."""
        assert settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] == timedelta(days=7)

    def test_token_rotation_enabled(self):
        """Token rotation should be enabled."""
        assert settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"] is True

    def test_blacklist_after_rotation_enabled(self):
        """Blacklisting after rotation should be enabled."""
        assert settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"] is True


@pytest.mark.django_db
class TestTokenObtain:
    """Test obtaining JWT tokens via login."""

    def test_obtain_token_pair_success(self, api_client, test_user):
        """Should return access and refresh tokens on valid login."""
        url = reverse("token_obtain_pair")
        response = api_client.post(
            url,
            {"username": "tokentest", "password": "TokenTest@123456"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

        # Tokens should be non-empty strings
        assert isinstance(response.data["access"], str)
        assert isinstance(response.data["refresh"], str)
        assert len(response.data["access"]) > 50
        assert len(response.data["refresh"]) > 50

    def test_obtain_token_invalid_credentials(self, api_client, test_user):
        """Should reject invalid credentials."""
        url = reverse("token_obtain_pair")
        response = api_client.post(
            url,
            {"username": "tokentest", "password": "WrongPassword"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "access" not in response.data
        assert "refresh" not in response.data


@pytest.mark.django_db
class TestTokenRefresh:
    """Test JWT token refresh with rotation."""

    def test_refresh_token_returns_new_access_token(self, api_client, test_user):
        """Should return a new access token when refreshing."""
        # Get initial tokens
        url_obtain = reverse("token_obtain_pair")
        response = api_client.post(
            url_obtain,
            {"username": "tokentest", "password": "TokenTest@123456"},
            format="json",
        )
        initial_access = response.data["access"]
        refresh_token = response.data["refresh"]

        # Refresh the token
        url_refresh = reverse("token_refresh")
        response = api_client.post(url_refresh, {"refresh": refresh_token}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

        # New access token should be different
        new_access = response.data["access"]
        assert new_access != initial_access

    def test_refresh_token_rotation_returns_new_refresh_token(self, api_client, test_user):
        """Should return a new refresh token when ROTATE_REFRESH_TOKENS is enabled."""
        # Get initial tokens
        url_obtain = reverse("token_obtain_pair")
        response = api_client.post(
            url_obtain,
            {"username": "tokentest", "password": "TokenTest@123456"},
            format="json",
        )
        old_refresh = response.data["refresh"]

        # Refresh the token
        url_refresh = reverse("token_refresh")
        response = api_client.post(url_refresh, {"refresh": old_refresh}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "refresh" in response.data

        # New refresh token should be different
        new_refresh = response.data["refresh"]
        assert new_refresh != old_refresh

    def test_old_refresh_token_blacklisted_after_rotation(self, api_client, test_user):
        """Old refresh token should be blacklisted after rotation."""
        # Get initial tokens
        url_obtain = reverse("token_obtain_pair")
        response = api_client.post(
            url_obtain,
            {"username": "tokentest", "password": "TokenTest@123456"},
            format="json",
        )
        old_refresh = response.data["refresh"]

        # Refresh the token (this should blacklist the old one)
        url_refresh = reverse("token_refresh")
        response = api_client.post(url_refresh, {"refresh": old_refresh}, format="json")
        assert response.status_code == status.HTTP_200_OK

        # Try to use the old refresh token again - should fail
        response = api_client.post(url_refresh, {"refresh": old_refresh}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "blacklisted" in str(response.data).lower()

    def test_refresh_with_invalid_token(self, api_client):
        """Should reject invalid refresh tokens."""
        url_refresh = reverse("token_refresh")
        response = api_client.post(url_refresh, {"refresh": "invalid.token.here"}, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTokenBlacklist:
    """Test JWT token blacklisting on logout."""

    def test_logout_blacklists_refresh_token(self, api_client, test_user):
        """Logout should blacklist the refresh token."""
        # Get tokens
        url_obtain = reverse("token_obtain_pair")
        response = api_client.post(
            url_obtain,
            {"username": "tokentest", "password": "TokenTest@123456"},
            format="json",
        )
        access_token = response.data["access"]
        refresh_token = response.data["refresh"]

        # Logout
        url_logout = reverse("api-logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = api_client.post(url_logout, {"refresh": refresh_token}, format="json")

        assert response.status_code == status.HTTP_205_RESET_CONTENT
        assert "success" in response.data["detail"].lower()

    def test_blacklisted_token_cannot_be_used(self, api_client, test_user):
        """Blacklisted refresh token should be rejected."""
        # Get tokens
        url_obtain = reverse("token_obtain_pair")
        response = api_client.post(
            url_obtain,
            {"username": "tokentest", "password": "TokenTest@123456"},
            format="json",
        )
        access_token = response.data["access"]
        refresh_token = response.data["refresh"]

        # Logout (blacklist the token)
        url_logout = reverse("api-logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = api_client.post(url_logout, {"refresh": refresh_token}, format="json")
        assert response.status_code == status.HTTP_205_RESET_CONTENT

        # Try to refresh with blacklisted token
        url_refresh = reverse("token_refresh")
        api_client.credentials()  # Clear auth header
        response = api_client.post(url_refresh, {"refresh": refresh_token}, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "blacklisted" in str(response.data).lower()

    def test_logout_requires_authentication(self, api_client):
        """Logout endpoint should require authentication."""
        url_logout = reverse("api-logout")
        response = api_client.post(url_logout, {"refresh": "some.token.here"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_requires_refresh_token(self, api_client, test_user):
        """Logout should require a refresh token in the request body."""
        # Get tokens
        url_obtain = reverse("token_obtain_pair")
        response = api_client.post(
            url_obtain,
            {"username": "tokentest", "password": "TokenTest@123456"},
            format="json",
        )
        access_token = response.data["access"]

        # Try to logout without providing refresh token
        url_logout = reverse("api-logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = api_client.post(url_logout, {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "required" in str(response.data).lower()

    def test_logout_with_invalid_token(self, api_client, test_user):
        """Logout should handle invalid refresh tokens gracefully."""
        # Get valid access token
        url_obtain = reverse("token_obtain_pair")
        response = api_client.post(
            url_obtain,
            {"username": "tokentest", "password": "TokenTest@123456"},
            format="json",
        )
        access_token = response.data["access"]

        # Try to logout with invalid refresh token
        url_logout = reverse("api-logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = api_client.post(url_logout, {"refresh": "invalid.token.here"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid" in str(response.data).lower()


@pytest.mark.django_db
class TestTokenBlacklistModels:
    """Test that token blacklist models work correctly."""

    def test_outstanding_token_created_on_login(self, api_client, test_user):
        """Outstanding token should be created when user logs in."""
        with schema_context("test_tenant"):
            initial_count = OutstandingToken.objects.count()

        url_obtain = reverse("token_obtain_pair")
        api_client.post(
            url_obtain,
            {"username": "tokentest", "password": "TokenTest@123456"},
            format="json",
        )

        # Should have created an outstanding token
        with schema_context("test_tenant"):
            assert OutstandingToken.objects.count() > initial_count

    def test_blacklisted_token_created_on_logout(self, api_client, test_user):
        """Blacklisted token should be created when user logs out."""
        # Get tokens
        url_obtain = reverse("token_obtain_pair")
        response = api_client.post(
            url_obtain,
            {"username": "tokentest", "password": "TokenTest@123456"},
            format="json",
        )
        access_token = response.data["access"]
        refresh_token = response.data["refresh"]

        with schema_context("test_tenant"):
            initial_blacklist_count = BlacklistedToken.objects.count()

        # Logout
        url_logout = reverse("api-logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        api_client.post(url_logout, {"refresh": refresh_token}, format="json")

        # Should have created a blacklisted token
        with schema_context("test_tenant"):
            assert BlacklistedToken.objects.count() > initial_blacklist_count
