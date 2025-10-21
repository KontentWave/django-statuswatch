"""
API models for StatusWatch.

Includes UserProfile for email verification and user metadata.
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class UserProfile(models.Model):
    """
    Extended user profile with email verification support.

    In early MVP phase, keeps verification simple. Each user has exactly
    one profile created automatically on registration.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    email_verified = models.BooleanField(
        default=False, help_text="Whether the user has verified their email address"
    )

    email_verification_token = models.UUIDField(
        default=uuid.uuid4, editable=False, help_text="Token sent to user's email for verification"
    )

    email_verification_sent_at = models.DateTimeField(
        null=True, blank=True, help_text="When the verification email was last sent"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profiles"
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        indexes = [
            models.Index(fields=["email_verified"], name="userprof_verified_idx"),
            models.Index(fields=["email_verification_token"], name="userprof_token_idx"),
            models.Index(fields=["created_at"], name="userprof_created_idx"),
            models.Index(fields=["email_verified", "-created_at"], name="userprof_ver_created_idx"),
        ]

    def __str__(self):
        return f"Profile for {self.user.email}"

    def is_verification_token_expired(self, hours=48):
        """
        Check if verification token has expired.

        Args:
            hours: Number of hours before token expires (default 48)

        Returns:
            True if token is expired, False otherwise
        """
        if not self.email_verification_sent_at:
            return True

        expiry_time = self.email_verification_sent_at + timedelta(hours=hours)
        return timezone.now() > expiry_time

    def regenerate_verification_token(self):
        """Generate a new verification token and update sent_at timestamp."""
        self.email_verification_token = uuid.uuid4()
        self.email_verification_sent_at = timezone.now()
        self.save()
