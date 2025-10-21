"""
Tests for JWT-based login authentication.

Following TDD approach for Feature 2: User Authentication (Login/Logout).

Note: CASCADE patch for database teardown and shared fixtures are defined
in conftest.py and apply automatically to all tests.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils.text import slugify
from django_tenants.utils import schema_context
from tenants.models import Client, Domain

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


@pytest.fixture
def stark_industries_tenant(db):
    """Create Stark Industries tenant with tony@stark.com user."""
    import uuid

    # Ensure we're operating on the public schema before mutating tenant metadata
    connection.set_schema_to_public()
    Client.objects.filter(schema_name__startswith="stark-industries").delete()

    # Create tenant with unique schema/domain per test to avoid collisions
    unique_suffix = uuid.uuid4().hex[:8]
    schema_name = slugify(f"Stark Industries {unique_suffix}")
    tenant = Client(schema_name=schema_name, name=f"Stark Industries {unique_suffix}")
    tenant.save()

    tenant_domain = f"{schema_name}.localhost"
    Domain.objects.create(
        tenant=tenant,
        domain=tenant_domain,
        is_primary=True,
    )

    username = f"tony-{unique_suffix}@stark.com"

    with schema_context(schema_name):
        user = User.objects.create_user(
            username=username,
            email="tony@stark.com",
            password="JarvisIsMyP@ssw0rd",
        )
        from django.contrib.auth.models import Group

        owner_group, _ = Group.objects.get_or_create(name="Owner")
        user.groups.add(owner_group)

    fixture_data = {
        "tenant": tenant,
        "user": user,
        "schema": schema_name,
        "domain": tenant_domain,
        "username": username,
        "email": "tony@stark.com",
        "password": "JarvisIsMyP@ssw0rd",
    }

    yield fixture_data

    # Cleanup: remove tokens/users and drop tenant schema to keep DB clean between tests
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    connection.set_schema_to_public()

    with schema_context(schema_name):
        BlacklistedToken.objects.all().delete()
        OutstandingToken.objects.all().delete()

    connection.set_schema_to_public()
    tenant.delete(force_drop=True)


def _post_json(client, url, payload, http_host="testserver"):
    """Helper to POST JSON data with optional HTTP_HOST header for tenant routing."""
    return client.post(
        url, data=json.dumps(payload), content_type="application/json", HTTP_HOST=http_host
    )


def test_login_with_valid_credentials_returns_jwt_tokens(client, stark_industries_tenant):
    """
    GIVEN a registered user exists in a tenant
    WHEN the user posts valid credentials to /api/auth/token/
    THEN the API returns 200 with access and refresh JWT tokens
    """
    payload = {
        "username": stark_industries_tenant["username"],
        "password": stark_industries_tenant["password"],
    }

    # Route request to tenant via HTTP_HOST
    tenant_host = stark_industries_tenant["domain"]
    print(f"Using HTTP_HOST: {tenant_host}")
    response = _post_json(client, "/api/auth/token/", payload, http_host=tenant_host)

    # Debug: print response details if not 200
    if response.status_code != 200:
        # Provide minimal debug info if the test fails
        current_tenant = getattr(connection, "tenant", None)
        tenant_name = getattr(current_tenant, "schema_name", "<none>")
        raise AssertionError(
            f"Expected 200, got {response.status_code}. Tenant: {tenant_name}. Body: {response.content.decode()}"
        )

    assert response.status_code == 200
    data = response.json()
    assert "access" in data
    assert "refresh" in data
    assert isinstance(data["access"], str)
    assert isinstance(data["refresh"], str)
    assert len(data["access"]) > 20  # JWT tokens are long strings


def test_login_with_invalid_password_returns_401(client, stark_industries_tenant):
    """
    GIVEN a registered user exists
    WHEN the user posts incorrect password
    THEN the API returns 401 with error detail
    """
    payload = {
        "username": stark_industries_tenant["username"],
        "password": "wrongpassword",
    }

    tenant_host = stark_industries_tenant["domain"]
    response = _post_json(client, "/api/auth/token/", payload, http_host=tenant_host)

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    # Simple JWT returns "No active account found with the given credentials"
    assert "credentials" in data["detail"].lower() or "account" in data["detail"].lower()


def test_login_with_nonexistent_user_returns_401(client):
    """
    GIVEN no user exists with the given email
    WHEN attempting to log in
    THEN the API returns 401 (no user enumeration)
    """
    payload = {
        "username": "nonexistent@example.com",
        "password": "anypassword",
    }

    response = _post_json(client, "/api/auth/token/", payload)

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


def test_refresh_token_returns_new_access_token(client, stark_industries_tenant):
    """
    GIVEN a user has obtained a refresh token
    WHEN the refresh token is posted to /api/auth/token/refresh/
    THEN the API returns 200 with a new access token
    """
    tenant_host = stark_industries_tenant["domain"]

    # First, log in to get refresh token
    login_payload = {
        "username": stark_industries_tenant["username"],
        "password": stark_industries_tenant["password"],
    }
    login_response = _post_json(client, "/api/auth/token/", login_payload, http_host=tenant_host)
    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh"]

    # Now use refresh token to get new access token
    refresh_payload = {"refresh": refresh_token}
    refresh_response = _post_json(
        client, "/api/auth/token/refresh/", refresh_payload, http_host=tenant_host
    )

    assert refresh_response.status_code == 200
    data = refresh_response.json()
    assert "access" in data
    assert isinstance(data["access"], str)
    assert len(data["access"]) > 20


def test_invalid_refresh_token_returns_401(client):
    """
    GIVEN an invalid or expired refresh token
    WHEN posted to /api/auth/token/refresh/
    THEN the API returns 401
    """
    payload = {"refresh": "invalid.token.here"}

    response = _post_json(client, "/api/auth/token/refresh/", payload)

    assert response.status_code == 401
