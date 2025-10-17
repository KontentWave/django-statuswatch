# tests/test_admin_url.py
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db  # allow DB if anything touches it

def test_admin_index_route_smoke(client, settings):
    # Skip tenant resolution for this simple smoke test
    settings.MIDDLEWARE = [
        m for m in settings.MIDDLEWARE
        if m != "django_tenants.middleware.main.TenantMainMiddleware"
    ]

    resp = client.get(reverse("admin:index"))
    # unauthenticated users usually get redirected to login
    assert resp.status_code in (200, 302)
