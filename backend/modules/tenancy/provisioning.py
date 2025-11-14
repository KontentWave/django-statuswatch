from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from api.exceptions import (
    DuplicateEmailError,
    DuplicateOrganizationNameError,
    SchemaConflictError,
    TenantCreationError,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from django_tenants.utils import get_public_schema_name, schema_context
from tenants.models import Client, Domain

logger = logging.getLogger("modules.tenancy.provisioner")


@dataclass(slots=True)
class TenantDomainService:
    """Create and manage per-tenant domains in a reusable way."""

    logger: logging.Logger = logger

    def ensure_primary_domain(self, tenant: Client, schema_name: str) -> None:
        domain_suffix = getattr(settings, "DEFAULT_TENANT_DOMAIN_SUFFIX", "localhost")
        domain = f"{schema_name}.{domain_suffix}".strip(".")
        try:
            Domain.objects.get_or_create(
                tenant=tenant,
                domain=domain,
                defaults={"is_primary": True},
            )
        except IntegrityError as exc:  # pragma: no cover - re-raised with context
            self.logger.error(
                "Failed to create domain %s for tenant %s", domain, schema_name, exc_info=True
            )
            raise SchemaConflictError(
                "Failed to configure organization domain. Please try a different name."
            ) from exc


@dataclass(slots=True)
class TenantProvisioner:
    """Wraps tenant+owner bootstrap logic so it can be reused across interfaces."""

    detail_message: str = (
        "Registration successful! Please check your email to verify your account before logging in."
    )
    domain_service: TenantDomainService = field(default_factory=TenantDomainService)
    logger: logging.Logger = logger

    def register(self, *, organization_name: str, email: str, password: str) -> dict[str, Any]:
        organization_name = organization_name.strip()
        email = email.lower()

        self.logger.info(
            "Starting tenant registration",
            extra={"email": email, "organization_name": organization_name},
        )

        tenant: Client | None = None
        schema_created = False

        try:
            schema_name = self._build_schema_name(organization_name)
            public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", get_public_schema_name())

            with schema_context(public_schema):
                tenant = Client(schema_name=schema_name, name=organization_name)
                tenant.save()
                schema_created = True

                self.logger.info(
                    "Tenant record saved in public schema",
                    extra={"schema_name": schema_name, "email": email},
                )

                self.domain_service.ensure_primary_domain(tenant, schema_name)

            self.logger.info(
                "Applying tenant schema migrations",
                extra={"schema_name": schema_name, "email": email},
            )

            call_command(
                "migrate_schemas",
                schema_name=schema_name,
                interactive=False,
                verbosity=0,
            )

            self.logger.info(
                "Tenant migrations applied", extra={"schema_name": schema_name, "email": email}
            )

            user = self._create_owner_user(schema_name=schema_name, email=email, password=password)

            self.logger.info(
                "Successfully created tenant and owner user",
                extra={"schema_name": schema_name, "email": email},
            )

            return {
                "detail": self.detail_message,
                "tenant": {
                    "id": tenant.id,
                    "name": tenant.name,
                    "schema_name": tenant.schema_name,
                },
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            }

        except IntegrityError as exc:
            self._cleanup_tenant(tenant, schema_created)
            self._handle_integrity_error(exc)
        except Exception as exc:  # pragma: no cover - surfaced in serializer tests
            self.logger.error(
                "Unexpected error during registration for %s: %s",
                email,
                str(exc),
                exc_info=True,
                extra={"email": email, "organization_name": organization_name},
            )
            self._cleanup_tenant(tenant, schema_created)
            raise TenantCreationError() from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_schema_name(self, organization_name: str) -> str:
        base = slugify(organization_name)
        if not base:
            raise DuplicateOrganizationNameError("Invalid organization name.")

        candidate = base
        suffix = 1
        while Client.objects.filter(schema_name=candidate).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _create_owner_user(self, *, schema_name: str, email: str, password: str):
        UserModel = get_user_model()

        try:
            with schema_context(schema_name):
                with transaction.atomic():
                    user = UserModel.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                    )
                    owner_group, _ = Group.objects.get_or_create(name="Owner")
                    user.groups.add(owner_group)

                    from api.models import UserProfile
                    from api.utils import send_verification_email

                    profile = UserProfile.objects.create(
                        user=user,
                        email_verified=False,
                        email_verification_sent_at=timezone.now(),
                    )

                    send_verification_email(user, profile.email_verification_token)

                    self.logger.info(
                        "Created user profile and sent verification email",
                        extra={"email": email, "schema_name": schema_name},
                    )
                    return user
        except Exception as exc:  # pragma: no cover - re-raised with context
            self.logger.error(
                "Failed to create owner user for schema %s: %s",
                schema_name,
                str(exc),
                exc_info=True,
            )
            raise TenantCreationError() from exc
        return None

    def _cleanup_tenant(self, tenant: Client | None, schema_created: bool) -> None:
        if tenant is not None and schema_created:
            try:
                tenant.delete(force_drop=True)
            except Exception:  # pragma: no cover - best-effort cleanup
                self.logger.exception(
                    "Failed to clean up tenant after provisioning error",
                    extra={"schema_name": getattr(tenant, "schema_name", None)},
                )

    def _handle_integrity_error(self, exc: IntegrityError) -> None:
        error_str = str(exc).lower()
        self.logger.warning("IntegrityError during registration: %s", str(exc))

        if "tenants_client_name" in error_str or ("name" in error_str and "unique" in error_str):
            raise DuplicateOrganizationNameError(
                "This organization name is already taken. Please choose another name."
            ) from exc

        if "email" in error_str or "username" in error_str:
            raise DuplicateEmailError("This email address is already registered.") from exc

        raise TenantCreationError() from exc
