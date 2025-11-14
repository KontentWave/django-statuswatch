"""Auth helpers that proxy to the legacy multi-tenant auth implementation."""

from __future__ import annotations

from api.auth_service import MultiTenantAuthenticationError, MultiTenantAuthService


class TenantAuthService:
    """Wrapper around the existing multi-tenant authentication logic."""

    AuthenticationError = MultiTenantAuthenticationError

    @staticmethod
    def authenticate_user(username: str, password: str, *, tenant_schema: str | None = None):
        return MultiTenantAuthService.authenticate_user(
            username, password, tenant_schema=tenant_schema
        )

    @staticmethod
    def find_all_tenants_for_email(email: str):
        return MultiTenantAuthService.find_all_tenants_for_email(email)

    @staticmethod
    def find_user_in_tenants(username: str, tenant_schema: str | None = None):
        return MultiTenantAuthService.find_user_in_tenants(username, tenant_schema)
