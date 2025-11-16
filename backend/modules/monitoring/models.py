"""Monitoring models shared across legacy apps and modular services."""

from __future__ import annotations

import uuid

from django.db import models


class Endpoint(models.Model):
    """Endpoint monitor definition scoped to a tenant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Client",
        on_delete=models.CASCADE,
        related_name="endpoints",
    )
    name = models.CharField(max_length=120, blank=True)
    url = models.URLField(max_length=500)
    interval_minutes = models.PositiveIntegerField(default=5)
    last_status = models.CharField(max_length=32, default="pending")
    last_checked_at: models.DateTimeField | None = models.DateTimeField(null=True, blank=True)
    last_latency_ms: models.FloatField | None = models.FloatField(null=True, blank=True)
    last_enqueued_at: models.DateTimeField | None = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "monitors"
        ordering = ("url",)
        unique_together = ("tenant", "url")

    def __str__(self) -> str:
        tenant_slug = getattr(self.tenant, "schema_name", "unknown")
        return f"{self.url} ({tenant_slug})"


__all__ = ["Endpoint"]
