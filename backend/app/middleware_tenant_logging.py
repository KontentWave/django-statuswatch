"""
Middleware to log django-tenants schema selection for debugging.
"""

import logging

logger = logging.getLogger("tenant.routing")


class TenantRoutingLoggingMiddleware:
    """
    Log which tenant schema is selected by django-tenants.

    This middleware should be placed AFTER TenantMainMiddleware
    so we can see which tenant was selected (or if we're in PUBLIC schema).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get tenant info (set by TenantMainMiddleware)
        host = request.get_host()

        # Check if tenant was set
        tenant_name = "UNKNOWN"
        schema_name = "UNKNOWN"

        if hasattr(request, "tenant"):
            tenant = request.tenant
            if hasattr(tenant, "name"):
                tenant_name = tenant.name
            if hasattr(tenant, "schema_name"):
                schema_name = tenant.schema_name

        # Log the routing decision
        logger.info(
            f"[TENANT ROUTING] Host: {host} → Schema: {schema_name} (Tenant: {tenant_name})"
        )

        # Also log to console for immediate visibility
        print(f"🔍 [TENANT ROUTING] Host: {host} → Schema: {schema_name} (Tenant: {tenant_name})")

        response = self.get_response(request)
        return response
