from __future__ import annotations

from contextlib import nullcontext

import pytest
from api.exceptions import (
    DuplicateEmailError,
    DuplicateOrganizationNameError,
    SchemaConflictError,
    TenantCreationError,
)
from django.db import IntegrityError
from django_tenants.utils import get_public_schema_name
from modules.tenancy.provisioning import TenantDomainService, TenantProvisioner


@pytest.mark.django_db
class TestTenantDomainService:
    def test_ensure_primary_domain_creates_domain(self, mocker):
        tenant = mocker.Mock()
        domain = mocker.patch("tenants.models.Domain.objects")
        service = TenantDomainService()

        service.ensure_primary_domain(tenant, "acme")

        domain.get_or_create.assert_called_once()

    def test_ensure_primary_domain_raises_schema_conflict(self, mocker):
        tenant = mocker.Mock()
        domain = mocker.patch("tenants.models.Domain.objects")
        domain.get_or_create.side_effect = IntegrityError("dup")
        service = TenantDomainService()

        with pytest.raises(SchemaConflictError):
            service.ensure_primary_domain(tenant, "acme")


@pytest.mark.django_db
class TestTenantProvisioner:
    def test_register_creates_tenant_schema_and_owner(self, mocker):
        mocker.patch(
            "modules.tenancy.provisioning.TenantProvisioner._build_schema_name",
            return_value="acme",
        )
        owner_user = mocker.Mock(
            id=123,
            email="owner@acme.com",
            username="owner@acme.com",
            first_name="Owner",
            last_name="User",
        )
        mocker.patch(
            "modules.tenancy.provisioning.TenantProvisioner._create_owner_user",
            return_value=owner_user,
        )
        provisioner = TenantProvisioner()
        tenant = mocker.Mock(schema_name="acme", id=321, name="Acme Inc")
        mocker.patch("modules.tenancy.provisioning.call_command")
        mocker.patch("modules.tenancy.provisioning.Client", return_value=tenant)
        domain_service = mocker.patch.object(provisioner, "domain_service")
        schema_context = mocker.patch(
            "modules.tenancy.provisioning.schema_context", return_value=nullcontext()
        )
        public_schema = get_public_schema_name()
        mocker.patch(
            "modules.tenancy.provisioning.get_public_schema_name", return_value=public_schema
        )

        response = provisioner.register(
            organization_name="Acme Inc", email="owner@acme.com", password="pass1234!"
        )

        assert response["detail"] == provisioner.detail_message
        assert response["tenant"] == {
            "id": tenant.id,
            "name": tenant.name,
            "schema_name": tenant.schema_name,
        }
        assert response["user"] == {
            "id": owner_user.id,
            "email": owner_user.email,
            "username": owner_user.username,
            "first_name": owner_user.first_name,
            "last_name": owner_user.last_name,
        }
        schema_context.assert_called_once_with(public_schema)
        tenant.save.assert_called_once()
        domain_service.ensure_primary_domain.assert_called_once_with(tenant, "acme")

    def test_register_handles_integrity_errors(self, mocker):
        mocker.patch(
            "modules.tenancy.provisioning.TenantProvisioner._build_schema_name",
            return_value="acme",
        )
        provisioner = TenantProvisioner()
        tenant = mocker.Mock(
            schema_name="acme",
            save=mocker.Mock(side_effect=IntegrityError("tenants_client_name")),
        )
        mocker.patch("modules.tenancy.provisioning.Client", return_value=tenant)
        mocker.patch("modules.tenancy.provisioning.schema_context", return_value=nullcontext())

        with pytest.raises(DuplicateOrganizationNameError):
            provisioner.register(
                organization_name="Acme", email="owner@acme.com", password="pass1234!"
            )

    def test_build_schema_name_generates_unique_slug(self, mocker):
        provisioner = TenantProvisioner()
        clients = mocker.patch("modules.tenancy.provisioning.Client.objects")
        clients.filter.return_value.exists.side_effect = [True, False]

        slug = provisioner._build_schema_name("Acme Inc")

        assert slug == "acme-inc-1"

    def test_create_owner_user_invokes_profile_and_email(self, mocker):
        provisioner = TenantProvisioner()
        mock_profile = mocker.patch("api.models.UserProfile")
        mock_send_email = mocker.patch("api.utils.send_verification_email")
        mock_group = mocker.patch("modules.tenancy.provisioning.Group.objects.get_or_create")
        mock_group.return_value = (mocker.Mock(), True)
        mock_user_model = mocker.patch("modules.tenancy.provisioning.get_user_model")
        mock_user = mocker.Mock()
        mock_user_model.return_value.objects.create_user.return_value = mock_user
        mock_schema_context = mocker.patch("modules.tenancy.provisioning.schema_context")

        user = provisioner._create_owner_user(
            schema_name="acme", email="owner@acme.com", password="pass"
        )

        mock_schema_context.assert_called_once()
        mock_profile.objects.create.assert_called_once()
        mock_send_email.assert_called_once()
        mock_user.groups.add.assert_called_once()
        assert user is mock_user

    def test_handle_integrity_error_duplicate_name(self):
        provisioner = TenantProvisioner()
        error = IntegrityError("duplicate key value violates unique constraint tenants_client_name")

        with pytest.raises(DuplicateOrganizationNameError):
            provisioner._handle_integrity_error(error)

    def test_handle_integrity_error_duplicate_email(self):
        provisioner = TenantProvisioner()
        error = IntegrityError("duplicate key value violates unique constraint auth_user_email_key")

        with pytest.raises(DuplicateEmailError):
            provisioner._handle_integrity_error(error)

    def test_handle_integrity_error_falls_back_to_generic(self):
        provisioner = TenantProvisioner()
        error = IntegrityError("some other constraint")

        with pytest.raises(TenantCreationError):
            provisioner._handle_integrity_error(error)
