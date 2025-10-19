"""
Tests for API rate limiting and throttling.

Ensures that rate limits protect against spam and abuse.
"""

import json
import pytest
from django.urls import reverse
from django.core.cache import cache
from rest_framework.test import APIClient

from tenants.models import Client, Domain

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def ensure_public_domain(db):
    """Ensure public tenant and domain exist for tests."""
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
    """Clear throttle cache before and after each test to prevent interference."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    """Create API client for testing."""
    return APIClient()


def test_registration_rate_limit_blocks_excessive_requests(api_client, settings):
    """
    Test that registration endpoint blocks requests after rate limit is exceeded.
    
    Default limit: 5 requests per hour per IP.
    """
    # Set a very strict limit for testing
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["registration"] = "3/min"
    
    url = reverse("api-register")
    payload = lambda i: {
        "organization_name": f"Test Org {i}",
        "email": f"test{i}@example.com",
        "password": "TestP@ss123456",
        "password_confirm": "TestP@ss123456",
    }
    
    # First 3 requests should succeed
    for i in range(3):
        response = api_client.post(
            url,
            data=json.dumps(payload(i)),
            content_type="application/json"
        )
        assert response.status_code in (201, 400), f"Request {i+1} should succeed or fail validation"
    
    # 4th request should be throttled
    response = api_client.post(
        url,
        data=json.dumps(payload(99)),
        content_type="application/json"
    )
    assert response.status_code == 429, "Request should be throttled"
    assert "throttled" in response.json().get("detail", "").lower()


def test_registration_rate_limit_returns_proper_error_message(api_client, settings):
    """
    Test that throttled requests return proper 429 status and error message.
    
    Note: The error message format may vary depending on DRF version,
    but it should always contain "throttled" and return 429 status.
    """
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["registration"] = "1/min"
    
    url = reverse("api-register")
    payload = {
        "organization_name": "Test Org",
        "email": "test@example.com",
        "password": "TestP@ss123456",
        "password_confirm": "TestP@ss123456",
    }
    
    # First request succeeds or fails validation
    api_client.post(url, data=json.dumps(payload), content_type="application/json")
    
    # Second request is throttled
    response = api_client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json"
    )
    
    assert response.status_code == 429
    response_data = response.json()
    assert "detail" in response_data
    assert "throttled" in response_data["detail"].lower()


def test_burst_rate_limit_protects_against_rapid_requests(api_client, settings):
    """
    Test that burst rate limit prevents rapid-fire requests.
    
    Default: 20 requests per minute.
    """
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["burst"] = "5/min"
    
    url = reverse("api-register")
    payload = lambda i: {
        "organization_name": f"Burst Test {i}",
        "email": f"burst{i}@example.com",
        "password": "TestP@ss123456",
        "password_confirm": "TestP@ss123456",
    }
    
    # Fire requests rapidly
    throttled_count = 0
    for i in range(10):
        response = api_client.post(
            url,
            data=json.dumps(payload(i)),
            content_type="application/json"
        )
        if response.status_code == 429:
            throttled_count += 1
    
    # At least some requests should be throttled
    assert throttled_count > 0, "Burst protection should throttle some requests"


def test_different_ips_have_independent_rate_limits(settings):
    """
    Test that rate limits are tracked per IP address.
    """
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["registration"] = "2/min"
    
    url = reverse("api-register")
    payload = lambda i: {
        "organization_name": f"IP Test {i}",
        "email": f"iptest{i}@example.com",
        "password": "TestP@ss123456",
        "password_confirm": "TestP@ss123456",
    }
    
    # Client 1 (IP: 192.168.1.1)
    client1 = APIClient()
    for i in range(2):
        response = client1.post(
            url,
            data=json.dumps(payload(i)),
            content_type="application/json",
            REMOTE_ADDR="192.168.1.1"
        )
        assert response.status_code in (201, 400)
    
    # Client 1's 3rd request should be throttled
    response = client1.post(
        url,
        data=json.dumps(payload(99)),
        content_type="application/json",
        REMOTE_ADDR="192.168.1.1"
    )
    assert response.status_code == 429
    
    # Client 2 (different IP) should still work
    client2 = APIClient()
    response = client2.post(
        url,
        data=json.dumps(payload(100)),
        content_type="application/json",
        REMOTE_ADDR="192.168.1.2"
    )
    assert response.status_code in (201, 400), "Different IP should have independent limit"
