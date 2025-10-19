import pytest
from django.contrib.auth import get_user_model

@pytest.mark.django_db
def test_user_crud():
    User = get_user_model()
    u = User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="S3cr3tP@ss123",
    )
    assert User.objects.filter(username="alice").exists()
    assert u.check_password("S3cr3tP@ss123")
