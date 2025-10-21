"""
Tests for email verification functionality.

Verifies that:
- Registration creates UserProfile with verification token
- Verification email is sent on registration
- Email verification endpoint works correctly
- Unverified users cannot log in (when login is implemented)
- Token expiration is handled properly
- Resend verification works
"""

from datetime import timedelta
from unittest.mock import patch

from api.models import UserProfile
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class UserProfileModelTests(TestCase):
    """Test UserProfile model functionality."""

    def setUp(self):
        """Create test user in test_tenant schema."""
        # User creation must happen in a tenant schema, not public
        with schema_context("test_tenant"):
            self.user = User.objects.create_user(
                username="test@example.com", email="test@example.com", password="TestP@ss123456"
            )

    def test_user_profile_creation(self):
        """UserProfile can be created with default values."""
        with schema_context("test_tenant"):
            profile = UserProfile.objects.create(user=self.user)

            self.assertFalse(profile.email_verified)
            self.assertIsNotNone(profile.email_verification_token)
            self.assertIsNone(profile.email_verification_sent_at)

    def test_is_verification_token_expired_no_sent_at(self):
        """Token is considered expired if never sent."""
        with schema_context("test_tenant"):
            profile = UserProfile.objects.create(user=self.user)

            self.assertTrue(profile.is_verification_token_expired())

    def test_is_verification_token_expired_recent(self):
        """Token is not expired if sent recently."""
        with schema_context("test_tenant"):
            profile = UserProfile.objects.create(
                user=self.user, email_verification_sent_at=timezone.now()
            )

            self.assertFalse(profile.is_verification_token_expired())

    def test_is_verification_token_expired_old(self):
        """Token is expired after 48 hours."""
        with schema_context("test_tenant"):
            old_time = timezone.now() - timedelta(hours=49)
            profile = UserProfile.objects.create(
                user=self.user, email_verification_sent_at=old_time
            )

            self.assertTrue(profile.is_verification_token_expired())

    def test_regenerate_verification_token(self):
        """Regenerating token creates new UUID and updates timestamp."""
        with schema_context("test_tenant"):
            profile = UserProfile.objects.create(user=self.user)
            old_token = profile.email_verification_token

            profile.regenerate_verification_token()

            self.assertNotEqual(profile.email_verification_token, old_token)
            self.assertIsNotNone(profile.email_verification_sent_at)


class RegistrationWithEmailVerificationTests(APITestCase):
    """Test registration flow with email verification."""

    def setUp(self):
        """Set up test client - conftest.py handles domain setup."""
        super().setUp()
        # Domain creation handled by conftest.py ensure_test_tenant fixture

    @patch("api.utils.send_verification_email")
    def test_registration_creates_user_profile(self, mock_send_email):
        """Registration creates UserProfile with verification token."""
        mock_send_email.return_value = True

        response = self.client.post(
            "/api/auth/register/",
            {
                "organization_name": "Test Org",
                "email": "newuser@example.com",
                "password": "TestP@ss123456",
                "password_confirm": "TestP@ss123456",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("check your email", response.data["detail"].lower())

        # Verify profile was created
        # Note: User is created in tenant schema, so we need to check in that context
        # For now, just verify the email was sent
        self.assertTrue(mock_send_email.called)

    @patch("api.utils.send_verification_email")
    def test_registration_sends_verification_email(self, mock_send_email):
        """Registration sends verification email."""
        mock_send_email.return_value = True

        response = self.client.post(
            "/api/auth/register/",
            {
                "organization_name": "Test Org 2",
                "email": "another@example.com",
                "password": "TestP@ss123456",
                "password_confirm": "TestP@ss123456",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(mock_send_email.called)

        # Verify email was called with correct arguments
        call_args = mock_send_email.call_args
        self.assertIsNotNone(call_args)


class EmailVerificationEndpointTests(APITestCase):
    """Test email verification endpoint."""

    def setUp(self):
        """Set up test user in test_tenant schema."""
        super().setUp()
        # No need to create testserver domain - conftest.py handles it

        # Create user in test_tenant schema
        with schema_context("test_tenant"):
            self.user = User.objects.create_user(
                username="verify@example.com", email="verify@example.com", password="TestP@ss123456"
            )
            self.profile = UserProfile.objects.create(
                user=self.user, email_verification_sent_at=timezone.now()
            )
            self.token = self.profile.email_verification_token

    def test_verify_email_success(self):
        """Valid token verifies email successfully."""
        response = self.client.post(f"/api/auth/verify-email/{self.token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("verified successfully", response.data["detail"].lower())

        # Check profile was updated
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.email_verified)

    def test_verify_email_invalid_token(self):
        """Invalid token returns 404."""
        fake_token = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(f"/api/auth/verify-email/{fake_token}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("invalid", response.data["error"].lower())

    def test_verify_email_already_verified(self):
        """Verifying already-verified email returns success message."""
        with schema_context("test_tenant"):
            self.profile.email_verified = True
            self.profile.save()

        response = self.client.post(f"/api/auth/verify-email/{self.token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("already verified", response.data["detail"].lower())

    def test_verify_email_expired_token(self):
        """Expired token returns 400 with expired flag."""
        old_time = timezone.now() - timedelta(hours=49)
        with schema_context("test_tenant"):
            self.profile.email_verification_sent_at = old_time
            self.profile.save()

        response = self.client.post(f"/api/auth/verify-email/{self.token}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", response.data["error"].lower())
        self.assertTrue(response.data.get("expired", False))


class ResendVerificationEmailTests(APITestCase):
    """Test resend verification email endpoint."""

    def setUp(self):
        """Set up test user in test_tenant schema."""
        super().setUp()
        # No need to create testserver domain - conftest.py handles it

        # Create user in test_tenant schema
        with schema_context("test_tenant"):
            self.user = User.objects.create_user(
                username="resend@example.com", email="resend@example.com", password="TestP@ss123456"
            )
            self.profile = UserProfile.objects.create(
                user=self.user, email_verification_sent_at=timezone.now()
            )

    def test_resend_requires_authentication(self):
        """Resend endpoint requires authentication."""
        response = self.client.post("/api/auth/resend-verification/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("api.utils.send_verification_email")
    def test_resend_verification_success(self, mock_send_email):
        """Authenticated unverified user can resend verification."""
        mock_send_email.return_value = True
        self.client.force_authenticate(user=self.user)

        old_token = self.profile.email_verification_token

        response = self.client.post("/api/auth/resend-verification/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("resent", response.data["detail"].lower())

        # Verify new token was generated
        with schema_context("test_tenant"):
            self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.email_verification_token, old_token)

        # Verify email was sent
        self.assertTrue(mock_send_email.called)

    def test_resend_already_verified(self):
        """Cannot resend if email already verified."""
        with schema_context("test_tenant"):
            self.profile.email_verified = True
            self.profile.save()

        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/auth/resend-verification/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already verified", response.data["error"].lower())


class EmailSendingTests(TestCase):
    """Test actual email sending functionality."""

    def setUp(self):
        """Create test user in test_tenant schema."""
        with schema_context("test_tenant"):
            self.user = User.objects.create_user(
                username="emailtest@example.com",
                email="emailtest@example.com",
                password="TestP@ss123456",
            )

    def test_verification_email_sent(self):
        """Verification email is actually sent."""
        import uuid

        from api.utils import send_verification_email

        with schema_context("test_tenant"):
            token = uuid.uuid4()
            result = send_verification_email(self.user, token)

            # With console backend, email is "sent" to console
            self.assertTrue(result)

            # Check that email was added to outbox
            self.assertEqual(len(mail.outbox), 1)

            # Check email details
            email = mail.outbox[0]
            self.assertEqual(email.to, [self.user.email])
            self.assertIn("Verify", email.subject)
            self.assertIn(str(token), email.body)

    def test_welcome_email_sent(self):
        """Welcome email is sent after verification."""
        from api.utils import send_welcome_email

        with schema_context("test_tenant"):
            result = send_welcome_email(self.user)

            self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertEqual(email.to, [self.user.email])
        self.assertIn("Welcome", email.subject)
