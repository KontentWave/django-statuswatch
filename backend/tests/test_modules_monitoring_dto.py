import pytest
from django.utils import timezone
from django_tenants.utils import schema_context
from modules.monitoring.dto import (
    CreateEndpointPayload,
    EndpointDto,
    build_endpoint_serializer,
    build_list_dto,
)
from monitors.models import Endpoint
from monitors.serializers import EndpointSerializer
from rest_framework.exceptions import ValidationError
from tenants.models import Client


@pytest.mark.django_db
def test_endpoint_dto_matches_serializer_output():
    tenant = Client.objects.get(schema_name="test_tenant")
    with schema_context(tenant.schema_name):
        endpoint = Endpoint.objects.create(
            tenant=tenant,
            name="Health",
            url="https://statuswatch.example/health",
            interval_minutes=5,
            last_status="ok",
        )
        now = timezone.now()
        endpoint.last_checked_at = now
        endpoint.last_enqueued_at = now
        endpoint.last_latency_ms = 123.45
        endpoint.save(
            update_fields=[
                "last_checked_at",
                "last_enqueued_at",
                "last_latency_ms",
                "updated_at",
            ]
        )

        dto = EndpointDto.from_model(endpoint)
        serializer = EndpointSerializer(instance=endpoint)

        assert dto.to_dict() == serializer.data


@pytest.mark.django_db
def test_build_endpoint_serializer_validates_input():
    payload = CreateEndpointPayload(url="https://statuswatch.example/health", interval_minutes=5)
    serializer = build_endpoint_serializer(data=payload.to_dict())

    assert serializer.validated_data["url"] == payload.url


@pytest.mark.django_db
def test_build_endpoint_serializer_rejects_invalid_scheme():
    payload = {"url": "ftp://internal", "interval_minutes": 5}

    with pytest.raises(ValidationError):
        build_endpoint_serializer(data=payload)


@pytest.mark.django_db
def test_build_list_dto_matches_serializer_output():
    tenant = Client.objects.get(schema_name="test_tenant")
    with schema_context(tenant.schema_name):
        endpoints = [
            Endpoint.objects.create(
                tenant=tenant,
                name="API",
                url="https://statuswatch.example/api",
                interval_minutes=3,
                last_status="ok",
            ),
            Endpoint.objects.create(
                tenant=tenant,
                name="Docs",
                url="https://statuswatch.example/docs",
                interval_minutes=10,
                last_status="pending",
            ),
        ]

        list_dto = build_list_dto(
            count=len(endpoints),
            next_url=None,
            previous_url=None,
            endpoints=endpoints,
        )

        serializer = EndpointSerializer(instance=endpoints, many=True)

        assert list_dto.to_dict()["count"] == len(endpoints)
        assert list_dto.to_dict()["results"] == serializer.data
