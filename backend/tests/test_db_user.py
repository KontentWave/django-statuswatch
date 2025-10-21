import pytest
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context


@pytest.mark.django_db
def test_user_crud():
    """Test user CRUD operations in tenant schema."""
    User = get_user_model()
    with schema_context("test_tenant"):
        u = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="S3cr3tP@ss123",
        )
        assert User.objects.filter(username="alice").exists()
        assert u.check_password("S3cr3tP@ss123")
