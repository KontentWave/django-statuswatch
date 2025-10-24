import logging
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from tenants.models import Client

from ..models import Endpoint

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "test_endpoints_api.log"

LOGGER = logging.getLogger("monitors.tests.endpoints_api")
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False
for handler in list(LOGGER.handlers):
    if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == LOG_FILE:
        LOGGER.removeHandler(handler)
        handler.close()

file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
LOGGER.addHandler(file_handler)


def _log_response(label: str, response) -> None:
    try:
        payload = response.json()
    except Exception:
        payload = response.content.decode("utf-8", errors="replace")
    LOGGER.info("%s status=%s payload=%s", label, response.status_code, payload)


@pytest.fixture(autouse=True)
def allow_all_hosts(settings):
    settings.ALLOWED_HOSTS = ["*"]


@pytest.fixture
def auth_client_factory():
    user_model = get_user_model()

    def _create(tenant: Client, email: str | None = None):
        user_email = email or f"owner@{tenant.schema_name}.example.com"
        with schema_context(tenant.schema_name):
            user = user_model.objects.create_user(
                username=user_email,
                email=user_email,
                password="StrongPass123!",
            )
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

        client = APIClient()
        client.defaults["HTTP_HOST"] = f"{tenant.schema_name}.localhost"
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        LOGGER.info("Issued access token for tenant=%s user=%s", tenant.schema_name, user_email)

        return client, user

    return _create


@pytest.fixture
def capture_ping_calls(monkeypatch):
    captured: list[tuple[str, str]] = []

    def fake_delay(endpoint_id: str, tenant_schema: str) -> None:
        captured.append((endpoint_id, tenant_schema))
        LOGGER.info(
            "Captured ping enqueue endpoint_id=%s tenant=%s",
            endpoint_id,
            tenant_schema,
        )

    monkeypatch.setattr("monitors.views.ping_endpoint.delay", fake_delay)
    return captured


@pytest.mark.django_db(transaction=True)
def test_endpoint_list_requires_authentication(tenant_factory):
    tenant = tenant_factory()
    LOGGER.info("Using tenant schema=%s for unauthenticated list", tenant.schema_name)

    client = APIClient()
    client.defaults["HTTP_HOST"] = f"{tenant.schema_name}.localhost"

    LOGGER.info("Requesting endpoint list without auth for tenant=%s", tenant.schema_name)
    response = client.get("/api/endpoints/")

    _log_response("Unauthenticated endpoint list", response)
    assert response.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_create_endpoint_triggers_ping_and_lists_result(
    tenant_factory, auth_client_factory, capture_ping_calls
):
    tenant = tenant_factory()
    LOGGER.info("Using tenant schema=%s for create/list", tenant.schema_name)
    client, _ = auth_client_factory(tenant)

    payload = {"url": "https://tenant-a.example.com/health", "interval_minutes": 5}
    LOGGER.info("Creating endpoint payload=%s", payload)
    response = client.post("/api/endpoints/", payload, format="json")

    _log_response("Create endpoint", response)
    assert response.status_code == 201
    endpoint_id = response.json()["id"]
    assert capture_ping_calls == [(endpoint_id, tenant.schema_name)]

    LOGGER.info("Listing endpoints after create")
    list_response = client.get("/api/endpoints/")
    _log_response("List endpoints after create", list_response)
    assert list_response.status_code == 200

    data = list_response.json()
    assert data["count"] == 1
    result = data["results"][0]
    assert result["url"] == payload["url"]
    assert result["interval_minutes"] == payload["interval_minutes"]
    assert result["last_status"] == "pending"
    assert result["last_enqueued_at"] is not None


@pytest.mark.django_db(transaction=True)
def test_delete_endpoint_removes_record(tenant_factory, auth_client_factory, capture_ping_calls):
    tenant = tenant_factory()
    LOGGER.info("Using tenant schema=%s for delete flow", tenant.schema_name)
    client, _ = auth_client_factory(tenant)

    payload = {"url": "https://tenant-delete.example.com/status", "interval_minutes": 10}
    LOGGER.info("Creating endpoint to delete payload=%s", payload)
    create_response = client.post("/api/endpoints/", payload, format="json")
    _log_response("Create endpoint for delete", create_response)
    endpoint_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/endpoints/{endpoint_id}/")
    _log_response("Delete endpoint", delete_response)
    assert delete_response.status_code == 204

    list_response = client.get("/api/endpoints/")
    _log_response("List endpoints after delete", list_response)
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 0

    with schema_context(tenant.schema_name):
        assert Endpoint.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_endpoints_are_isolated_per_tenant(tenant_factory, auth_client_factory, monkeypatch):
    tenant_a = tenant_factory("Tenant A")
    tenant_b = tenant_factory("Tenant B")
    LOGGER.info(
        "Using tenants schema_a=%s schema_b=%s for isolation test",
        tenant_a.schema_name,
        tenant_b.schema_name,
    )

    client_a, _ = auth_client_factory(tenant_a, email="owner-a@example.com")
    client_b, _ = auth_client_factory(tenant_b, email="owner-b@example.com")

    monkeypatch.setattr(
        "monitors.views.ping_endpoint.delay", lambda endpoint_id, tenant_schema: None
    )

    LOGGER.info("Creating endpoint for tenant_a schema=%s", tenant_a.schema_name)
    client_a.post(
        "/api/endpoints/",
        {"url": "https://tenant-a.example.com/health", "interval_minutes": 5},
        format="json",
    )
    LOGGER.info("Creating endpoint for tenant_b schema=%s", tenant_b.schema_name)
    client_b.post(
        "/api/endpoints/",
        {"url": "https://tenant-b.example.com/health", "interval_minutes": 5},
        format="json",
    )

    LOGGER.info("Listing endpoints for tenant_a schema=%s", tenant_a.schema_name)
    list_a = client_a.get("/api/endpoints/")
    _log_response("Tenant A list", list_a)
    LOGGER.info("Listing endpoints for tenant_b schema=%s", tenant_b.schema_name)
    list_b = client_b.get("/api/endpoints/")
    _log_response("Tenant B list", list_b)

    urls_a = {entry["url"] for entry in list_a.json()["results"]}
    urls_b = {entry["url"] for entry in list_b.json()["results"]}

    assert urls_a == {"https://tenant-a.example.com/health"}
    assert urls_b == {"https://tenant-b.example.com/health"}
