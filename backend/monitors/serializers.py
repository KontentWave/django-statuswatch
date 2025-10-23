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
