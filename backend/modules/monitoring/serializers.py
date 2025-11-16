"""Monitoring serializers shared across legacy endpoints and modular services."""

from __future__ import annotations

from ipaddress import ip_address, ip_network
from urllib.parse import urlparse

from rest_framework import serializers

from .models import Endpoint


class EndpointSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = Endpoint
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "name",
            "url",
            "interval_minutes",
            "last_status",
            "last_checked_at",
            "last_enqueued_at",
            "last_latency_ms",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "tenant",
            "tenant_name",
            "last_status",
            "last_checked_at",
            "last_enqueued_at",
            "last_latency_ms",
            "created_at",
            "updated_at",
        )

    def validate_interval_minutes(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError("Interval must be at least 1 minute.")
        if value > 24 * 60:
            raise serializers.ValidationError("Interval cannot exceed 24 hours.")
        return value

    def validate_url(self, value: str) -> str:
        """
        Validate URL to prevent SSRF attacks by enforcing scheme/hostname rules and
        blocking private IP ranges.
        """

        try:
            parsed = urlparse(value)
        except Exception:  # noqa: BLE001 - serializer raises ValidationError below
            raise serializers.ValidationError("Invalid URL format.") from None

        if parsed.scheme not in ("http", "https"):
            raise serializers.ValidationError("Only HTTP and HTTPS protocols are supported.")

        if not parsed.hostname:
            raise serializers.ValidationError("URL must include a hostname.")

        try:
            addr = ip_address(parsed.hostname)
            private_ranges = [
                ip_network("10.0.0.0/8"),
                ip_network("172.16.0.0/12"),
                ip_network("192.168.0.0/16"),
                ip_network("127.0.0.0/8"),
                ip_network("169.254.0.0/16"),
                ip_network("::1/128"),
                ip_network("fe80::/10"),
                ip_network("fc00::/7"),
            ]
            for private_range in private_ranges:
                if addr in private_range:
                    raise serializers.ValidationError(
                        "Cannot monitor private IP addresses or internal services."
                    )
        except ValueError:
            pass

        return value


__all__ = ["EndpointSerializer"]
