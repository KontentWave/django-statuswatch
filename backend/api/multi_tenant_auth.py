"""
MULTI-TENANT AUTHENTICATION VIEW

This view handles centralized login for all tenants.
It's designed to work from the public schema (localhost).

Endpoint: POST /api/auth/login/
Request: {"username": "user@example.com", "password": "password123"}
Response: {
    "access": "jwt_access_token",
    "refresh": "jwt_refresh_token",
    "tenant_schema": "marcepokus",
    "tenant_name": "MarcePokus",
    "tenant_domain": "marcepokus.localhost",
    "user": {
        "id": 1,
        "username": "marcel@cores.sk",
        "email": "marcel@cores.sk",
        "first_name": "Marcel",
        "last_name": "Pokus"
    }
}

The frontend should:
1. Store the JWT tokens
2. Redirect to: http://{tenant_domain}:5173/dashboard
"""

import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth_service import MultiTenantAuthenticationError, MultiTenantAuthService

logger = logging.getLogger("api.auth")


class MultiTenantLoginView(APIView):
    """
    Centralized login endpoint that works across all tenant schemas.

    This endpoint:
    1. Searches all tenant schemas to find the user
    2. Authenticates the user in their tenant schema
    3. Returns JWT tokens + tenant information for frontend redirect

    Endpoint: POST /api/auth/login/
    Request: {"username": "user@example.com", "password": "password123"}
    Response: {
        "access": "jwt_access_token",
        "refresh": "jwt_refresh_token",
        "tenant_schema": "marcepokus",
        "tenant_name": "MarcePokus",
        "tenant_domain": "marcepokus.localhost",
        "user": {"id": 1, "username": "marcel@cores.sk", "email": "marcel@cores.sk"}
    }
    """

    # Disable authentication completely - this is a login endpoint (no user yet!)
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Handle multi-tenant login request with smart tenant detection.

        Scenarios:
        1. Login from tenant subdomain (e.g., acme.localhost:5173/login)
           → Search ONLY that tenant's schema

        2. Login from centralized hub (localhost:5173/login)
           → Search all tenants
           → If found in ONE tenant: auto-login
           → If found in MULTIPLE tenants: return tenant list for selection

        3. Login with tenant_schema specified
           → Use that specific tenant (tenant selection flow)
        """

        username = request.data.get("username")
        password = request.data.get("password")
        tenant_schema = request.data.get("tenant_schema")  # Optional: for tenant selection

        # Log the attempt (without password)
        logger.info(
            f"[MULTI-TENANT-LOGIN] Login attempt from IP: {request.META.get('REMOTE_ADDR')}, "
            f"username: {username}, tenant_schema: {tenant_schema or 'auto-detect'}"
        )

        # Validate input
        if not username or not password:
            logger.warning(
                f"[MULTI-TENANT-LOGIN] Missing credentials in request from "
                f"IP: {request.META.get('REMOTE_ADDR')}"
            )
            return Response(
                {"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get current tenant from request (if accessing from tenant subdomain)
            current_tenant = getattr(request, "tenant", None)
            current_schema = (
                getattr(current_tenant, "schema_name", "public") if current_tenant else "public"
            )

            logger.info(
                f"[MULTI-TENANT-LOGIN] Current schema: {current_schema}, "
                f"Tenant specified: {tenant_schema or 'None'}"
            )

            # SCENARIO 1: Tenant-specific login (subdomain or explicit selection)
            if tenant_schema or (current_schema != "public"):
                # Use specified tenant or current tenant
                target_schema = tenant_schema or current_schema

                logger.info(
                    f"[MULTI-TENANT-LOGIN] Tenant-specific login for schema: {target_schema}"
                )

                # Authenticate using the multi-tenant service
                auth_data = MultiTenantAuthService.authenticate_user(username, password)

                # Verify the user was found in the correct tenant
                if auth_data["tenant_schema"] != target_schema:
                    logger.warning(
                        f"[MULTI-TENANT-LOGIN] User found in different tenant: "
                        f"expected {target_schema}, got {auth_data['tenant_schema']}"
                    )
                    return Response(
                        {"error": "Invalid credentials for this organization"},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )

                logger.info(
                    f"[MULTI-TENANT-LOGIN] ✓ Login successful for user '{username}' "
                    f"in tenant '{auth_data['tenant_name']}'"
                )

                return Response(auth_data, status=status.HTTP_200_OK)

            # SCENARIO 2: Centralized login - auto-detect tenant
            logger.info(
                f"[MULTI-TENANT-LOGIN] Centralized login - searching all tenants for: {username}"
            )

            # Find all tenants that have this email
            matches = MultiTenantAuthService.find_all_tenants_for_email(username)

            if not matches:
                logger.warning(f"[MULTI-TENANT-LOGIN] No user found with email: {username}")
                return Response(
                    {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
                )

            if len(matches) == 1:
                # SINGLE MATCH: Auto-login
                logger.info(
                    f"[MULTI-TENANT-LOGIN] Single tenant match - auto-login to: "
                    f"{matches[0]['tenant_name']}"
                )

                # Authenticate with the single matched tenant
                auth_data = MultiTenantAuthService.authenticate_user(username, password)

                logger.info(
                    f"[MULTI-TENANT-LOGIN] ✓ Login successful for user '{username}' "
                    f"in tenant '{auth_data['tenant_name']}'"
                )

                return Response(auth_data, status=status.HTTP_200_OK)

            else:
                # MULTIPLE MATCHES: Return tenant list for user to select
                logger.info(
                    f"[MULTI-TENANT-LOGIN] Multiple tenant matches ({len(matches)}) - "
                    f"requesting tenant selection"
                )

                # Don't authenticate yet - just return the tenant options
                tenant_options = [
                    {
                        "tenant_schema": match["schema_name"],
                        "tenant_name": match["tenant_name"],
                        "tenant_id": match["tenant_id"],
                    }
                    for match in matches
                ]

                return Response(
                    {
                        "multiple_tenants": True,
                        "tenants": tenant_options,
                        "message": "Multiple organizations found. Please select one.",
                    },
                    status=status.HTTP_200_OK,
                )

        except MultiTenantAuthenticationError as e:
            logger.warning(f"[MULTI-TENANT-LOGIN] ✗ Login failed for user '{username}': {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        except Exception as e:
            logger.error(
                f"[MULTI-TENANT-LOGIN] ✗ Unexpected error during login for user '{username}': {e}",
                exc_info=True,
            )
            return Response(
                {"error": "An unexpected error occurred during authentication"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
