import pytest
from django.conf import settings
from django.urls import reverse

_admin_enabled = "django.contrib.admin" in settings.INSTALLED_APPS

pytestmark = pytest.mark.skipif(
    not _admin_enabled, reason="admin not in INSTALLED_APPS"
)

def test_admin_index_route_smoke(client):
    url = reverse("admin:index")
    resp = client.get(url)
    # Anonymous users usually get a redirect to login; 200 also fine for custom skins
    assert resp.status_code in {200, 301, 302, 401, 403}
