"""Legacy shim re-exporting monitoring serializers under the original app path."""

from modules.monitoring.serializers import EndpointSerializer

__all__ = ["EndpointSerializer"]
