from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import serializers

from tenants.models import Client, Domain


class RegistrationSerializer(serializers.Serializer):
    organization_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    default_detail_message = "Registration successful. Please log in."

    def validate_organization_name(self, value: str) -> str:
        slug = slugify(value)
        if not slug:
            raise serializers.ValidationError("Organization name must contain letters or numbers.")
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data: dict) -> dict:
        organization_name: str = validated_data["organization_name"].strip()
        email: str = validated_data["email"].lower()
        password: str = validated_data["password"]

        schema_name = self._build_schema_name(organization_name)

        tenant = Client(schema_name=schema_name, name=organization_name)
        tenant.save()  # auto-creates the schema via django-tenants

        self._create_domain(tenant, schema_name)
        self._create_owner_user(schema_name, email, password)

        return {"detail": self.default_detail_message}

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
        Domain.objects.get_or_create(
            tenant=tenant,
            domain=domain,
            defaults={"is_primary": True},
        )

    def _create_owner_user(self, schema_name: str, email: str, password: str) -> None:
        from django.contrib.auth.models import Group
        from django_tenants.utils import schema_context

        UserModel = get_user_model()

        with schema_context(schema_name):
            user = UserModel.objects.create_user(
                username=email,
                email=email,
                password=password,
            )
            owner_group, _ = Group.objects.get_or_create(name="Owner")
            user.groups.add(owner_group)