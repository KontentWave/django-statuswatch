"""
Tests for the /api/auth/me/ endpoint (CurrentUserView).

Validates that authenticated users can retrieve their profile information,
including groups, and that unauthenticated requests are rejected.
"""

import time
from datetime import datetime

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import override_settings
from django_tenants.utils import schema_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from tenants.models import Client, Domain

User = get_user_model()


@pytest.fixture
def stark_industries_tenant(db):
    """
    Create a unique tenant for each test with guaranteed cleanup.

    Creates tenant with unique schema name to avoid collisions between tests.
    Ensures tenant is deleted even if test fails.

    Note: CASCADE patch for teardown is handled globally in conftest.py
    """
    # Generate unique schema name with timestamp
    timestamp = str(int(time.time() * 1000))
    schema_name = f"stark-industries-{timestamp}"

    tenant = Client(schema_name=schema_name, name="Stark Industries Test")
    tenant.save()

    Domain.objects.create(
        tenant=tenant,
        domain=f"{schema_name}.localhost",
        is_primary=True,
    )

    yield tenant

    # Cleanup: delete tenant and its schema
    try:
        connection.set_schema_to_public()
        tenant.delete()
    except Exception as e:
        print(f"Warning: Failed to delete tenant {schema_name}: {e}")


@pytest.fixture
def test_user_with_groups(stark_industries_tenant):
    """
    Create a test user with Owner and custom groups in the tenant schema.

    Returns:
        tuple: (user, access_token) for authenticated requests
    """
    with schema_context(stark_industries_tenant.schema_name):
        user = User.objects.create_user(
            username="tony@starkindustries.com",
            email="tony@starkindustries.com",
            password="IronManRules123!",
            first_name="Tony",
            last_name="Stark",
        )

        # Add user to Owner and a custom group
        owner_group, _ = Group.objects.get_or_create(name="Owner")
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        user.groups.add(owner_group, admin_group)

        # Generate JWT access token
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return user, access_token


@override_settings(ALLOWED_HOSTS=["*"])
@pytest.mark.django_db(transaction=True)
def test_me_endpoint_requires_authentication(stark_industries_tenant):
    """
    Test that /api/auth/me/ returns 401 when no JWT is provided.
    """
    client = APIClient()
    client.defaults["HTTP_HOST"] = f"{stark_industries_tenant.schema_name}.localhost"

    response = client.get("/api/auth/me/")

    assert response.status_code == 401
    assert "detail" in response.json()


@override_settings(ALLOWED_HOSTS=["*"])
@pytest.mark.django_db(transaction=True)
def test_me_endpoint_returns_user_data(stark_industries_tenant, test_user_with_groups):
    """
    Test that /api/auth/me/ returns correct user data with valid JWT.
    """
    user, access_token = test_user_with_groups

    client = APIClient()
    client.defaults["HTTP_HOST"] = f"{stark_industries_tenant.schema_name}.localhost"
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    response = client.get("/api/auth/me/")

    assert response.status_code == 200
    data = response.json()

    # Verify core user fields
    assert data["id"] == user.id
    assert data["username"] == "tony@starkindustries.com"
    assert data["email"] == "tony@starkindustries.com"
    assert data["first_name"] == "Tony"
    assert data["last_name"] == "Stark"
    assert data["is_staff"] is False

    # Verify date_joined is present and valid ISO format
    assert "date_joined" in data
    date_joined = datetime.fromisoformat(data["date_joined"].replace("Z", "+00:00"))
    assert isinstance(date_joined, datetime)

    # Verify groups are included
    assert "groups" in data
    assert isinstance(data["groups"], list)
    assert "Owner" in data["groups"]
    assert "Admin" in data["groups"]
    assert len(data["groups"]) == 2


@override_settings(ALLOWED_HOSTS=["*"])
@pytest.mark.django_db(transaction=True)
def test_me_endpoint_with_invalid_token(stark_industries_tenant):
    """
    Test that /api/auth/me/ returns 401 with an invalid JWT.
    """
    client = APIClient()
    client.defaults["HTTP_HOST"] = f"{stark_industries_tenant.schema_name}.localhost"
    client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.here")

    response = client.get("/api/auth/me/")

    assert response.status_code == 401
    assert "detail" in response.json()


@override_settings(ALLOWED_HOSTS=["*"])
@pytest.mark.django_db(transaction=True)
def test_me_endpoint_user_without_groups(stark_industries_tenant):
    """
    Test that /api/auth/me/ returns empty groups list for users without groups.
    """
    with schema_context(stark_industries_tenant.schema_name):
        user = User.objects.create_user(
            username="pepper@starkindustries.com",
            email="pepper@starkindustries.com",
            password="PepperPotts123!",
            first_name="Pepper",
            last_name="Potts",
        )
        # Don't add any groups

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

    client = APIClient()
    client.defaults["HTTP_HOST"] = f"{stark_industries_tenant.schema_name}.localhost"
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    response = client.get("/api/auth/me/")

    assert response.status_code == 200
    data = response.json()

    assert data["username"] == "pepper@starkindustries.com"
    assert data["groups"] == []


@override_settings(ALLOWED_HOSTS=["*"])
@pytest.mark.django_db(transaction=True)
def test_me_endpoint_staff_user(stark_industries_tenant):
    """
    Test that /api/auth/me/ correctly returns is_staff=True for staff users.
    """
    with schema_context(stark_industries_tenant.schema_name):
        user = User.objects.create_user(
            username="jarvis@starkindustries.com",
            email="jarvis@starkindustries.com",
            password="JustARatherVeryIntelligentSystem123!",
            is_staff=True,
        )

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

    client = APIClient()
    client.defaults["HTTP_HOST"] = f"{stark_industries_tenant.schema_name}.localhost"
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    response = client.get("/api/auth/me/")

    assert response.status_code == 200
    data = response.json()

    assert data["username"] == "jarvis@starkindustries.com"
    assert data["is_staff"] is True
