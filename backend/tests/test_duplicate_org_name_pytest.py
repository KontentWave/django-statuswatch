"""
Test duplicate organization name error handling during registration.

Pytest version with proper fixtures and cleanup.
"""

import pytest
from api.exceptions import DuplicateOrganizationNameError
from api.serializers import RegistrationSerializer
from django.conf import settings
from django_tenants.utils import get_public_schema_name, schema_context
from tenants.models import Client


@pytest.fixture(autouse=True)
def cleanup_test_tenants(db):
    """
    Automatically cleanup test tenants before and after each test.
    autouse=True means this runs for every test in this file.
    """
    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())

    def _cleanup():
        with schema_context(public_schema):
            # Clean up any TestUniqueOrg tenants (by name and by schema pattern)
            test_tenants = Client.objects.filter(
                name__in=["TestUniqueOrg", "TestUniqueOrg2"]
            ) | Client.objects.filter(schema_name__istartswith="testuniqueorg")

            for tenant in test_tenants:
                try:
                    # Use force_drop=True to drop schema along with tenant record
                    tenant.delete(force_drop=True)
                except Exception:
                    pass  # Ignore cleanup errors - schema might not exist

    # Cleanup before test
    _cleanup()

    # Run the test
    yield

    # Cleanup after test
    _cleanup()


@pytest.mark.django_db(transaction=True)
def test_first_organization_registration_succeeds():
    """First registration with unique name should succeed."""
    serializer = RegistrationSerializer(
        data={
            "email": "test1@uniqueorg.test",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "organization_name": "TestUniqueOrg",
        }
    )

    assert serializer.is_valid(), f"Validation failed: {serializer.errors}"

    result = serializer.save()

    # RegistrationSerializer.save() returns {"detail": "message"}
    assert "detail" in result
    assert isinstance(result["detail"], str)

    # Verify tenant was created
    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())
    with schema_context(public_schema):
        tenant = Client.objects.get(name="TestUniqueOrg")
        assert tenant is not None
        assert tenant.name == "TestUniqueOrg"


@pytest.mark.django_db(transaction=True)
def test_duplicate_organization_name_rejected():
    """Duplicate name should return 409 Conflict."""
    # First registration
    serializer1 = RegistrationSerializer(
        data={
            "email": "user1@dupetest.test",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "organization_name": "TestUniqueOrg",
        }
    )
    assert serializer1.is_valid()
    serializer1.save()

    # Second registration with SAME name but DIFFERENT email
    serializer2 = RegistrationSerializer(
        data={
            "email": "user2@dupetest.test",  # Different email
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "organization_name": "TestUniqueOrg",  # SAME name - should fail
        }
    )

    assert serializer2.is_valid()

    # Should raise DuplicateOrganizationNameError
    with pytest.raises(DuplicateOrganizationNameError) as exc_info:
        serializer2.save()

    # Verify error details
    assert exc_info.value.status_code == 409
    assert exc_info.value.default_code == "duplicate_organization_name"
    assert "already taken" in str(exc_info.value.detail).lower()


@pytest.mark.django_db(transaction=True)
def test_different_organization_name_succeeds():
    """Registration with different name should succeed."""
    # First registration
    serializer1 = RegistrationSerializer(
        data={
            "email": "user1@differentorg.test",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "organization_name": "TestUniqueOrg",
        }
    )
    assert serializer1.is_valid()
    result1 = serializer1.save()
    assert "detail" in result1

    # Second registration with DIFFERENT name and DIFFERENT email
    serializer2 = RegistrationSerializer(
        data={
            "email": "user2@differentorg.test",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "organization_name": "TestUniqueOrg2",  # Different name - should succeed
        }
    )

    assert serializer2.is_valid()
    result2 = serializer2.save()

    assert "detail" in result2
    assert isinstance(result2["detail"], str)

    # Verify both tenants exist
    public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())
    with schema_context(public_schema):
        tenant1 = Client.objects.get(name="TestUniqueOrg")
        tenant2 = Client.objects.get(name="TestUniqueOrg2")
        assert tenant1.id != tenant2.id
