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
        Validate URL to prevent SSRF attacks:
        1. Only allow http/https schemes
        2. Block private IP ranges (RFC 1918, loopback, link-local)
        3. Prevent access to internal services
        """
        # Parse and validate URL
        try:
            parsed = urlparse(value)
        except Exception:
            raise serializers.ValidationError("Invalid URL format.")

        # Only allow http and https schemes
        if parsed.scheme not in ("http", "https"):
            raise serializers.ValidationError("Only HTTP and HTTPS protocols are supported.")

        # Validate hostname exists
        if not parsed.hostname:
            raise serializers.ValidationError("URL must include a hostname.")

        # Block private IP addresses
        try:
            # Try to parse as IP address
            addr = ip_address(parsed.hostname)

            # Define private ranges
            private_ranges = [
                ip_network("10.0.0.0/8"),  # RFC 1918
                ip_network("172.16.0.0/12"),  # RFC 1918
                ip_network("192.168.0.0/16"),  # RFC 1918
                ip_network("127.0.0.0/8"),  # Loopback
                ip_network("169.254.0.0/16"),  # Link-local
                ip_network("::1/128"),  # IPv6 loopback
                ip_network("fe80::/10"),  # IPv6 link-local
                ip_network("fc00::/7"),  # IPv6 unique local
            ]

            # Check if IP is in any private range
            for private_range in private_ranges:
                if addr in private_range:
                    raise serializers.ValidationError(
                        "Cannot monitor private IP addresses or internal services."
                    )

        except ValueError:
            # Not an IP address, it's a hostname - this is OK
            # Note: We could add DNS resolution checks here, but that adds latency
            # and complexity. Better to handle in the ping task.
            pass

        return value
