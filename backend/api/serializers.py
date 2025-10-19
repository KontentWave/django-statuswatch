from __future__ import annotations

import logging
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from django.utils.text import slugify
from rest_framework import serializers

from tenants.models import Client, Domain
from api.exceptions import (
    TenantCreationError,
    DuplicateEmailError,
    SchemaConflictError,
)

logger = logging.getLogger(__name__)


class RegistrationSerializer(serializers.Serializer):
    organization_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    default_detail_message = (
        "Registration successful! Please check your email to verify your account before logging in."
    )

    def validate_organization_name(self, value: str) -> str:
        slug = slugify(value)
        if not slug:
            raise serializers.ValidationError("Organization name must contain letters or numbers.")
        return value

    def validate_password(self, value: str) -> str:
        """
        Validate password against Django's password validators.
        
        This includes our custom validators:
        - Minimum 12 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        - At least one special character
        - Not too similar to user attributes
        - Not a common password
        """
        # Run Django's password validation
        # Note: We don't have a user object yet, so we pass None
        # UserAttributeSimilarityValidator will be checked again during user creation
        validate_password(value, user=None)
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data: dict) -> dict:
        organization_name: str = validated_data["organization_name"].strip()
        email: str = validated_data["email"].lower()
        password: str = validated_data["password"]

        try:
            with transaction.atomic():
                schema_name = self._build_schema_name(organization_name)
                
                tenant = Client(schema_name=schema_name, name=organization_name)
                tenant.save()  # auto-creates the schema via django-tenants

                self._create_domain(tenant, schema_name)
                self._create_owner_user(schema_name, email, password)

                logger.info(
                    f"Successfully created tenant '{schema_name}' with owner {email}",
                    extra={'schema_name': schema_name, 'email': email}
                )
                
                return {"detail": self.default_detail_message}
        
        except IntegrityError as e:
            # Database constraint violation (e.g., duplicate email in tenant)
            logger.warning(
                f"IntegrityError during registration for {email}: {str(e)}",
                extra={'email': email, 'organization_name': organization_name}
            )
            if 'email' in str(e).lower() or 'username' in str(e).lower():
                raise DuplicateEmailError(
                    "This email address is already registered."
                )
            raise TenantCreationError()
        
        except Exception as e:
            # Any other error during tenant creation
            logger.error(
                f"Unexpected error during registration for {email}: {str(e)}",
                exc_info=True,
                extra={'email': email, 'organization_name': organization_name}
            )
            raise TenantCreationError()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_schema_name(self, organization_name: str) -> str:
        base = slugify(organization_name)
        if not base:
            raise serializers.ValidationError({"organization_name": "Invalid organization name."})

        candidate = base
        suffix = 1
        while Client.objects.filter(schema_name=candidate).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _create_domain(self, tenant: Client, schema_name: str) -> None:
        domain_suffix = getattr(settings, "DEFAULT_TENANT_DOMAIN_SUFFIX", "localhost")
        domain = f"{schema_name}.{domain_suffix}".strip(".")
        try:
            Domain.objects.get_or_create(
                tenant=tenant,
                domain=domain,
                defaults={"is_primary": True},
            )
        except IntegrityError as e:
            logger.error(
                f"Failed to create domain {domain} for tenant {schema_name}: {str(e)}",
                exc_info=True
            )
            raise SchemaConflictError(
                "Failed to configure organization domain. Please try a different name."
            )

    def _create_owner_user(self, schema_name: str, email: str, password: str) -> None:
        from django.contrib.auth.models import Group
        from django_tenants.utils import schema_context
        from django.utils import timezone

        UserModel = get_user_model()

        try:
            with schema_context(schema_name):
                user = UserModel.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                )
                owner_group, _ = Group.objects.get_or_create(name="Owner")
                user.groups.add(owner_group)
                
                # Create user profile with email verification token
                from .models import UserProfile
                profile = UserProfile.objects.create(
                    user=user,
                    email_verified=False,
                    email_verification_sent_at=timezone.now()
                )
                
                # Send verification email
                from .utils import send_verification_email
                send_verification_email(user, profile.email_verification_token)
                
                logger.info(
                    f"Created user profile and sent verification email to {email}",
                    extra={'email': email, 'schema_name': schema_name}
                )
                
        except IntegrityError as e:
            logger.error(
                f"Failed to create owner user {email} in schema {schema_name}: {str(e)}",
                exc_info=True
            )
            # This will be caught by the outer exception handler
            raise
