import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from tenants.models import SubscriptionStatus

from .models import Endpoint
from .serializers import EndpointSerializer
from .tasks import ping_endpoint

logger = logging.getLogger("monitors")
audit_logger = logging.getLogger("monitors.audit")
subscription_logger = logging.getLogger("subscriptions.feature_gating")


class EndpointViewSet(viewsets.ModelViewSet):
    """CRUD operations for tenant-scoped endpoints."""

    serializer_class = EndpointSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get tenant-scoped endpoints with optimized query.
        Uses select_related('tenant') to avoid N+1 query problem.
        """
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Endpoint.objects.none()
        return Endpoint.objects.filter(tenant=tenant).select_related("tenant").order_by("url")

    def perform_create(self, serializer):
        """
        Create endpoint and schedule initial ping atomically.
        Using transaction.atomic() ensures:
        1. Endpoint is only saved if task scheduling succeeds
        2. No orphaned records if Celery connection fails
        3. Database consistency maintained
        """
        tenant = getattr(self.request, "tenant", None)

        if (
            tenant
            and getattr(tenant, "subscription_status", SubscriptionStatus.FREE)
            == SubscriptionStatus.FREE
        ):
            existing_count = Endpoint.objects.filter(tenant=tenant).count()
            if existing_count >= 3:
                subscription_logger.info(
                    "Free plan endpoint limit reached",
                    extra={
                        "tenant": getattr(tenant, "schema_name", "public"),
                        "user_id": getattr(self.request.user, "id", None),
                        "existing_endpoints": existing_count,
                        "limit": 3,
                    },
                )
                raise PermissionDenied("Your 3-endpoint limit reached. Please upgrade to Pro.")

        with transaction.atomic():
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

            # Update last_enqueued_at timestamp
            endpoint.last_enqueued_at = timezone.now()
            endpoint.save(update_fields=["last_enqueued_at", "updated_at"])

            # Schedule initial ping task (inside transaction)
            # In development (eager mode), tasks may fail due to schema switching
            tenant_schema = getattr(tenant, "schema_name", "public")
            try:
                ping_endpoint.delay(str(endpoint.id), tenant_schema)
            except Exception as e:
                # If task scheduling fails in development, log but don't rollback
                # In production with real Celery worker, this will propagate and rollback
                from django.conf import settings

                if settings.CELERY_TASK_ALWAYS_EAGER:
                    logger.warning(
                        "Failed to schedule endpoint ping in eager mode (development)",
                        extra={
                            "endpoint_id": str(endpoint.id),
                            "error": str(e),
                            "note": "This is expected in development without Celery worker",
                        },
                    )
                else:
                    # Production: re-raise to rollback transaction
                    logger.error(
                        "Failed to schedule endpoint ping",
                        extra={
                            "endpoint_id": str(endpoint.id),
                            "error": str(e),
                        },
                    )
                    raise

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
