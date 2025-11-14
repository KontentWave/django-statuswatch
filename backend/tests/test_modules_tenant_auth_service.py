from __future__ import annotations

import pytest
from api.auth_service import MultiTenantAuthenticationError
from modules.accounts.authentication import TenantAuthService


class TestTenantAuthService:
    def test_authentication_error_alias(self):
        assert TenantAuthService.AuthenticationError is MultiTenantAuthenticationError

    def test_authenticate_user_delegates(self, mocker):
        authenticate = mocker.patch(
            "modules.accounts.authentication.MultiTenantAuthService.authenticate_user",
            return_value={"access": "token"},
        )

        result = TenantAuthService.authenticate_user(
            "user@example.com", "secret", tenant_schema="acme"
        )

        assert result == {"access": "token"}
        authenticate.assert_called_once_with("user@example.com", "secret", tenant_schema="acme")

    def test_find_all_tenants_for_email_delegates(self, mocker):
        finder = mocker.patch(
            "modules.accounts.authentication.MultiTenantAuthService.find_all_tenants_for_email",
            return_value=[{"schema_name": "acme"}],
        )

        result = TenantAuthService.find_all_tenants_for_email("user@example.com")

        assert result == [{"schema_name": "acme"}]
        finder.assert_called_once_with("user@example.com")

    def test_find_user_in_tenants_delegates(self, mocker):
        finder = mocker.patch(
            "modules.accounts.authentication.MultiTenantAuthService.find_user_in_tenants",
            return_value={"schema_name": "acme"},
        )

        result = TenantAuthService.find_user_in_tenants("user@example.com", tenant_schema="acme")

        assert result == {"schema_name": "acme"}
        finder.assert_called_once_with("user@example.com", "acme")

    def test_authenticate_user_propagates_errors(self, mocker):
        authenticate = mocker.patch(
            "modules.accounts.authentication.MultiTenantAuthService.authenticate_user",
            side_effect=MultiTenantAuthenticationError("boom"),
        )

        with pytest.raises(TenantAuthService.AuthenticationError):
            TenantAuthService.authenticate_user("user@example.com", "secret")

        authenticate.assert_called_once_with("user@example.com", "secret", tenant_schema=None)
