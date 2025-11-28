"""Monitoring services encapsulating Endpoint CRUD workflows."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from tenants.models import SubscriptionStatus

from .models import Endpoint
from .tasks import ping_endpoint

logger = logging.getLogger("monitors")
audit_logger = logging.getLogger("monitors.audit")
subscription_logger = logging.getLogger("subscriptions.feature_gating")


class EndpointService:
    """Business logic for creating, listing, and deleting monitored endpoints."""

    def queryset_for_request(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Endpoint.objects.none()
        return Endpoint.objects.filter(tenant=tenant).select_related("tenant").order_by("url")

    def create_endpoint(self, *, request, serializer) -> Endpoint:
        tenant = getattr(request, "tenant", None)
        self._enforce_plan_limits(request, tenant)

        with transaction.atomic():
            endpoint = serializer.save(tenant=tenant)

            audit_logger.info(
                "Endpoint created",
                extra=self._audit_payload(
                    tenant_schema=getattr(tenant, "schema_name", "public"),
                    endpoint=endpoint,
                    user_id=getattr(request.user, "id", None),
                ),
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
            try:
                ping_endpoint.delay(str(endpoint.id), tenant_schema)
            except Exception as exc:  # noqa: BLE001
                from django.conf import settings  # Local import to avoid settings at module load

                if settings.CELERY_TASK_ALWAYS_EAGER:
                    logger.warning(
                        "Failed to schedule endpoint ping in eager mode (development)",
                        extra={
                            "endpoint_id": str(endpoint.id),
                            "error": str(exc),
                            "note": "Expected in development without Celery worker",
                        },
                    )
                else:
                    logger.error(
                        "Failed to schedule endpoint ping",
                        extra={
                            "endpoint_id": str(endpoint.id),
                            "error": str(exc),
                        },
                    )
                    raise

        return endpoint

    def delete_endpoint(self, *, request, endpoint: Endpoint) -> None:
        audit_logger.info(
            "Endpoint deleted",
            extra=self._audit_payload(
                tenant_schema=getattr(endpoint.tenant, "schema_name", "public"),
                endpoint=endpoint,
                user_id=getattr(request.user, "id", None),
            ),
        )
        endpoint.delete()

    def _enforce_plan_limits(self, request, tenant) -> None:
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
                        "user_id": getattr(request.user, "id", None),
                        "existing_endpoints": existing_count,
                        "limit": 3,
                    },
                )
                raise PermissionDenied("Your 3-endpoint limit reached. Please upgrade to Pro.")

    @staticmethod
    def _audit_payload(*, tenant_schema: str, endpoint: Endpoint, user_id: Any) -> dict[str, Any]:
        return {
            "tenant": tenant_schema,
            "endpoint_id": str(endpoint.id),
            "url": endpoint.url,
            "user_id": user_id,
        }


endpoint_service = EndpointService()

__all__ = ["EndpointService", "endpoint_service"]
