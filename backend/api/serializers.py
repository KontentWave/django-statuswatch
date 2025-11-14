from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify
from modules.tenancy.provisioning import TenantProvisioner
from rest_framework import serializers

from api.performance_log import log_performance


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for authenticated user information.

    Returns core user fields and group memberships.
    """

    groups = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "date_joined",
            "groups",
        ]
        read_only_fields = fields

    def get_groups(self, obj):
        """Return list of group names the user belongs to."""
        return [group.name for group in obj.groups.all()]


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

    provisioner_class = TenantProvisioner

    @log_performance(threshold_ms=2000)  # Warn if registration takes > 2 seconds
    def create(self, validated_data: dict) -> dict:
        provisioner = self.provisioner_class(detail_message=self.default_detail_message)
        return provisioner.register(
            organization_name=validated_data["organization_name"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
