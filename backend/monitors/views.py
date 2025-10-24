import logging

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Endpoint
from .serializers import EndpointSerializer
from .tasks import ping_endpoint

logger = logging.getLogger("monitors")
audit_logger = logging.getLogger("monitors.audit")


class EndpointViewSet(viewsets.ModelViewSet):
    """CRUD operations for tenant-scoped endpoints."""

    serializer_class = EndpointSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Endpoint.objects.none()
        return Endpoint.objects.filter(tenant=tenant).order_by("url")

    def perform_create(self, serializer):
        tenant = getattr(self.request, "tenant", None)
        endpoint = serializer.save(tenant=tenant)

        audit_logger.info(
            "Endpoint created",
            extra={
                "tenant": getattr(tenant, "schema_name", "public"),
                "endpoint_id": str(endpoint.id),
                "url": endpoint.url,
                "user_id": getattr(self.request.user, "id", None),
            },
        )

        logger.info(
            "Scheduling endpoint ping",
            extra={
                "endpoint_id": str(endpoint.id),
                "url": endpoint.url,
            },
        )

        endpoint.last_enqueued_at = timezone.now()
        endpoint.save(update_fields=["last_enqueued_at", "updated_at"])
        tenant_schema = getattr(tenant, "schema_name", "public")
        ping_endpoint.delay(str(endpoint.id), tenant_schema)

    def perform_destroy(self, instance):
        audit_logger.info(
            "Endpoint deleted",
            extra={
                "tenant": getattr(instance.tenant, "schema_name", "public"),
                "endpoint_id": str(instance.id),
                "url": instance.url,
                "user_id": getattr(self.request.user, "id", None),
            },
        )
        instance.delete()
