import pytest
from tenants.models import Client, Domain


@pytest.mark.django_db
def test_test_tenant_bootstrap_creates_expected_domains(ensure_test_tenant):
    tenant = Client.objects.get(schema_name=ensure_test_tenant.schema_name)

    assert tenant.name == "Test Tenant"
    assert list(
        Domain.objects.filter(tenant=tenant).order_by("domain").values_list("domain", "is_primary")
    ) == [
        ("test.localhost", True),
        ("testserver", False),
    ]
