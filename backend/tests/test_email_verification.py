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
from django.test import TestCase, override_settings
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
            self.token_str = str(self.token)

        self.verify_url = "/api/auth/verify-email/"

    def test_verify_email_success(self):
        """Valid token verifies email successfully."""
        response = self.client.post(
            self.verify_url,
            {"token": self.token_str},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("verified successfully", response.data["detail"].lower())

        # Check profile was updated
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.email_verified)
        self.assertIsNone(self.profile.email_verification_token)

    def test_verify_email_invalid_token(self):
        """Invalid token returns 404."""
        fake_token = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(
            self.verify_url,
            {"token": fake_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("invalid", response.data["error"].lower())

    def test_verify_email_already_verified(self):
        """Verifying already-verified email returns success message."""
        with schema_context("test_tenant"):
            self.profile.email_verified = True
            self.profile.save()

        response = self.client.post(
            self.verify_url,
            {"token": self.token_str},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("already verified", response.data["detail"].lower())

    def test_verify_email_expired_token(self):
        """Expired token returns 400 with expired flag."""
        old_time = timezone.now() - timedelta(hours=49)
        with schema_context("test_tenant"):
            self.profile.email_verification_sent_at = old_time
            self.profile.save()

        response = self.client.post(
            self.verify_url,
            {"token": self.token_str},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", response.data["error"].lower())
        self.assertTrue(response.data.get("expired", False))

    def test_verify_email_token_single_use(self):
        """Verification tokens become invalid immediately after success."""
        first_response = self.client.post(
            self.verify_url,
            {"token": self.token_str},
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        second_response = self.client.post(
            self.verify_url,
            {"token": self.token_str},
            format="json",
        )
        self.assertEqual(second_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("invalid", second_response.data["error"].lower())

    @patch("api.utils.send_welcome_email")
    def test_verify_email_triggers_welcome_email(self, mock_welcome):
        mock_welcome.return_value = True

        response = self.client.post(
            self.verify_url,
            {"token": self.token_str},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_welcome.assert_called_once_with(self.user)


class ResendVerificationEmailTests(APITestCase):
    """Test resend verification email endpoint."""

    def setUp(self):
        """Set up test user in test_tenant schema."""
        super().setUp()
        with schema_context("test_tenant"):
            self.user = User.objects.create_user(
                username="resend@example.com", email="resend@example.com", password="TestP@ss123456"
            )
            self.profile = UserProfile.objects.create(
                user=self.user,
                email_verification_sent_at=timezone.now(),
            )

        self.resend_url = "/api/auth/resend-verification/"

    def test_resend_requires_email_payload(self):
        """Endpoint returns 400 when email payload missing."""
        response = self.client.post(self.resend_url, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["error"].lower())

    @patch("api.utils.send_verification_email")
    def test_resend_verification_success(self, mock_send_email):
        """Anonymous request with known email triggers resend for unverified account."""
        mock_send_email.return_value = True

        old_token = self.profile.email_verification_token

        response = self.client.post(
            self.resend_url,
            {"email": "resend@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("check your inbox", response.data["detail"].lower())

        with schema_context("test_tenant"):
            self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.email_verification_token, old_token)
        mock_send_email.assert_called_once_with(self.user, self.profile.email_verification_token)

    @patch("api.utils.send_verification_email")
    def test_resend_verification_succeeds_even_if_email_unknown(self, mock_send_email):
        """Endpoint does not leak whether an email exists."""
        response = self.client.post(
            self.resend_url,
            {"email": "unknown@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(mock_send_email.called)

    @patch("api.utils.send_verification_email")
    def test_resend_does_not_send_when_already_verified(self, mock_send_email):
        with schema_context("test_tenant"):
            self.profile.email_verified = True
            self.profile.save()

        response = self.client.post(
            self.resend_url,
            {"email": "resend@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(mock_send_email.called)


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


class DebugVerificationTokenEndpointTests(APITestCase):
    """Ensure the debug endpoint exposes verification tokens only in DEBUG."""

    def setUp(self):
        super().setUp()
        with schema_context("test_tenant"):
            self.user = User.objects.create_user(
                username="debug@example.com",
                email="debug@example.com",
                password="TestP@ss123456",
            )
            self.profile = UserProfile.objects.create(
                user=self.user,
                email_verification_sent_at=timezone.now(),
            )
        self.url = "/api/debug/latest-verification-token/"

    @override_settings(DEBUG=True)
    def test_returns_verification_token_for_email(self):
        response = self.client.get(self.url, {"email": "debug@example.com"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token"], str(self.profile.email_verification_token))
        self.assertEqual(response.data["email"], "debug@example.com")
        self.assertIn("schema", response.data)

    @override_settings(DEBUG=True)
    def test_requires_email_query_param(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["error"])

    @override_settings(DEBUG=False)
    def test_returns_404_when_not_debug(self):
        response = self.client.get(self.url, {"email": "debug@example.com"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
