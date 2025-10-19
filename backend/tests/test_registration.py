import json

import pytest
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django_tenants.utils import schema_context
from django.core.cache import cache

from tenants.models import Client, Domain

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def ensure_public_domain(db):
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


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Clear throttle cache before and after each test to prevent rate limit interference."""
    cache.clear()
    yield
    cache.clear()


def _post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def test_register_creates_tenant_and_owner_user(client):
    payload = {
        "organization_name": "Stark Industries",
        "email": "tony@stark.com",
        "password": "JarvisIsMyP@ssw0rd",
        "password_confirm": "JarvisIsMyP@ssw0rd",
    }

    response = _post_json(client, "/api/auth/register/", payload)

    assert response.status_code == 201
    body = response.json()
    assert body["detail"].lower().startswith("registration successful")

    tenant = Client.objects.get(name="Stark Industries")
    expected_schema_name = slugify("Stark Industries")
    assert tenant.schema_name == expected_schema_name

    with schema_context(expected_schema_name):
        user = get_user_model().objects.get(email="tony@stark.com")
        assert user.check_password("JarvisIsMyP@ssw0rd")
        assert user.groups.filter(name="Owner").exists()


@pytest.mark.parametrize(
    "payload,expected_error_field",
    [
        (
            {
                "organization_name": "Wayne Enterprises",
                "email": "bruce@wayne.com",
                "password": "IAmBatman123",
                "password_confirm": "different",
            },
            "password_confirm",
        ),
        (
            {
                "organization_name": "",
                "email": "not-an-email",
                "password": "short",
                "password_confirm": "short",
            },
            "organization_name",
        ),
    ],
)

def test_register_validation_errors_return_400(client, payload, expected_error_field):
    response = _post_json(client, "/api/auth/register/", payload)

    assert response.status_code == 400
    errors = response.json().get("errors", {})
    assert expected_error_field in errors
