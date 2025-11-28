"""Viewsets and endpoints for monitoring functionality."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from modules.monitoring.serializers import EndpointSerializer
from modules.monitoring.service import endpoint_service
from modules.monitoring.tasks import ping_endpoint


class EndpointViewSet(viewsets.ModelViewSet):
    """CRUD operations for tenant-scoped endpoints."""

    serializer_class = EndpointSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return endpoint_service.queryset_for_request(self.request)

    def perform_create(self, serializer):
        endpoint_service.create_endpoint(request=self.request, serializer=serializer)

    def perform_destroy(self, instance):
        endpoint_service.delete_endpoint(request=self.request, endpoint=instance)


__all__ = ["EndpointViewSet", "ping_endpoint"]
