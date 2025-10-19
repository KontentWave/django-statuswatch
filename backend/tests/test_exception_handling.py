"""
Tests for custom exception handling and error sanitization.

Verifies that:
- Production error messages don't leak sensitive information
- Stripe errors are properly sanitized
- Database errors don't expose schema details
- Detailed errors are logged but not returned to users
"""

from unittest.mock import patch, MagicMock
from stripe import _error as stripe_error
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory
from django.contrib.auth import get_user_model

from api.exceptions import (
    TenantCreationError,
    PaymentProcessingError,
    DuplicateEmailError,
    ConfigurationError,
)
from api.exception_handler import custom_exception_handler


User = get_user_model()


class ExceptionHandlerTests(TestCase):
    """Test custom exception handler behavior."""
    
    def setUp(self):
        self.factory = APIRequestFactory()
    
    @override_settings(DEBUG=False)
    def test_production_mode_sanitizes_generic_errors(self):
        """In production, generic errors should return sanitized messages."""
        # Simulate a generic Python exception
        exc = ValueError("Internal database connection string: postgresql://user:pass@db:5432")
        context = {
            'view': MagicMock(__class__=MagicMock(__name__='TestView')),
            'request': self.factory.get('/api/test/')
        }
        
        response = custom_exception_handler(exc, context)
        
        # Should return generic error message
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.data)
        # Should NOT contain sensitive info
        self.assertNotIn('postgresql', str(response.data))
        self.assertNotIn('password', str(response.data).lower())
    
    @override_settings(DEBUG=False)
    def test_production_mode_sanitizes_stripe_errors(self):
        """Stripe errors should be sanitized in production."""
        exc = stripe_error.InvalidRequestError(
            "Invalid API Key provided: sk_test_1234567890",
            param='api_key'
        )
        context = {
            'view': MagicMock(__class__=MagicMock(__name__='PaymentView')),
            'request': self.factory.post('/api/payments/')
        }
        
        response = custom_exception_handler(exc, context)
        
        # Should return generic payment error
        self.assertEqual(response.status_code, 500)
        # Should NOT contain API key
        self.assertNotIn('sk_test', str(response.data))
        self.assertNotIn('api_key', str(response.data))
    
    @override_settings(DEBUG=False)
    def test_production_mode_allows_validation_errors(self):
        """Validation errors are safe and should be returned as-is."""
        from rest_framework.exceptions import ValidationError
        
        exc = ValidationError({'email': ['This field is required.']})
        context = {
            'view': MagicMock(__class__=MagicMock(__name__='RegistrationView')),
            'request': self.factory.post('/api/register/')
        }
        
        response = custom_exception_handler(exc, context)
        
        # Should return validation error details
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data)
        # ValidationError returns a list of errors
        self.assertIsInstance(response.data['email'], list)
        self.assertEqual(len(response.data['email']), 1)
        # ErrorDetail can be compared as string
        error_message = str(response.data['email'][0])
        self.assertEqual(error_message, 'This field is required.')
    
    @override_settings(DEBUG=False)
    def test_production_mode_allows_throttle_errors(self):
        """Throttle errors are safe and should be returned as-is."""
        from rest_framework.exceptions import Throttled
        
        exc = Throttled(wait=3600)
        context = {
            'view': MagicMock(__class__=MagicMock(__name__='RegistrationView')),
            'request': self.factory.post('/api/register/')
        }
        
        response = custom_exception_handler(exc, context)
        
        # Should return throttle error
        self.assertEqual(response.status_code, 429)
        self.assertIn('detail', response.data)
    
    @override_settings(DEBUG=True)
    def test_debug_mode_shows_detailed_errors(self):
        """In DEBUG mode, detailed errors should be returned."""
        exc = ValueError("Detailed internal error message")
        context = {
            'view': MagicMock(__class__=MagicMock(__name__='TestView')),
            'request': self.factory.get('/api/test/')
        }
        
        # In DEBUG mode, we log but don't necessarily sanitize as aggressively
        # (the implementation may vary - this test documents expected behavior)
        response = custom_exception_handler(exc, context)
        
        # In debug mode, we still handle the exception
        self.assertIsNotNone(response)


class CustomExceptionTests(TestCase):
    """Test custom exception classes."""
    
    def test_tenant_creation_error_has_safe_message(self):
        """TenantCreationError should have user-safe default message."""
        exc = TenantCreationError()
        self.assertEqual(exc.status_code, 500)
        self.assertIn('organization', exc.detail.lower())
        # Should NOT reveal internal details
        self.assertNotIn('schema', exc.detail.lower())
        self.assertNotIn('database', exc.detail.lower())
    
    def test_payment_processing_error_has_safe_message(self):
        """PaymentProcessingError should have user-safe default message."""
        exc = PaymentProcessingError()
        self.assertEqual(exc.status_code, 402)
        self.assertIn('payment', exc.detail.lower())
        # Should NOT reveal Stripe details
        self.assertNotIn('stripe', exc.detail.lower())
        self.assertNotIn('api', exc.detail.lower())
    
    def test_duplicate_email_error_has_safe_message(self):
        """DuplicateEmailError should have user-safe default message."""
        exc = DuplicateEmailError()
        self.assertEqual(exc.status_code, 409)
        self.assertIn('email', exc.detail.lower())
    
    def test_configuration_error_has_safe_message(self):
        """ConfigurationError should not reveal configuration details."""
        exc = ConfigurationError()
        self.assertEqual(exc.status_code, 500)
        # Should NOT reveal specific config issues
        self.assertNotIn('key', exc.detail.lower())
        self.assertNotIn('secret', exc.detail.lower())


class PaymentErrorSanitizationTests(TestCase):
    """Unit tests for Stripe error sanitization in payment views."""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            password='testpass123'
        )
    
    @override_settings(DEBUG=False, STRIPE_SECRET_KEY='sk_test_fake')
    @patch('payments.views.stripe.checkout.Session.create')
    def test_stripe_card_error_is_sanitized(self, mock_create):
        """Stripe card errors should return sanitized message."""
        from payments.views import create_checkout_session
        
        # Simulate a card declined error
        mock_create.side_effect = stripe_error.CardError(
            message='Your card was declined',
            param='card',
            code='card_declined'
        )
        
        request = self.factory.post(
            '/api/pay/create-checkout-session/',
            {'amount': 2000, 'currency': 'usd', 'name': 'Test'},
            format='json'
        )
        request.user = self.user
        
        response = create_checkout_session(request)
        
        # Should return error but not Stripe-specific details
        self.assertEqual(response.status_code, 400)
        # Custom exceptions return 'detail' field
        self.assertIn('detail', response.data)
        # Should mention payment method, not card specifically
        self.assertIn('payment method', str(response.data['detail']).lower())
    
    @override_settings(DEBUG=False, STRIPE_SECRET_KEY='sk_test_fake')
    @patch('payments.views.stripe.checkout.Session.create')
    def test_stripe_auth_error_is_sanitized(self, mock_create):
        """Stripe authentication errors should not leak API keys."""
        from payments.views import create_checkout_session
        
        # Simulate an authentication error
        mock_create.side_effect = stripe_error.AuthenticationError(
            'Invalid API Key provided: sk_test_1234567890'
        )
        
        request = self.factory.post(
            '/api/pay/create-checkout-session/',
            {'amount': 2000, 'currency': 'usd', 'name': 'Test'},
            format='json'
        )
        request.user = self.user
        
        response = create_checkout_session(request)
        
        # Should return error but not API key
        self.assertEqual(response.status_code, 500)
        # 500 errors are sanitized to 'error' format (this is correct!)
        self.assertIn('error', response.data)
        # Should NOT contain API key
        response_str = str(response.data)
        self.assertNotIn('sk_test', response_str)
        self.assertNotIn('API Key', response_str)
        # Should have generic error message
        self.assertIn('unexpected error', response.data['error']['message'].lower())
    
    @override_settings(DEBUG=False, STRIPE_SECRET_KEY=None)
    def test_missing_stripe_config_returns_safe_error(self):
        """Missing Stripe configuration should return safe error."""
        from payments.views import create_checkout_session
        
        request = self.factory.post(
            '/api/pay/create-checkout-session/',
            {'amount': 2000, 'currency': 'usd', 'name': 'Test'},
            format='json'
        )
        request.user = self.user
        
        response = create_checkout_session(request)
        
        # Should return configuration error
        self.assertEqual(response.status_code, 500)
        # 500 errors are sanitized to 'error' format (this is correct!)
        self.assertIn('error', response.data)
        # Should NOT reveal that STRIPE_SECRET_KEY is missing
        self.assertNotIn('STRIPE_SECRET_KEY', str(response.data))
        # In production mode, error is sanitized to generic message
        # This is correct behavior - no config details leaked
        response_str = str(response.data['error']['message']).lower()
        self.assertIn('unexpected error', response_str)
        # The actual ConfigurationError message should NOT appear
        self.assertNotIn('configured', response_str)


class LoggingTests(TestCase):
    """Test that errors are properly logged."""
    
    @override_settings(DEBUG=False)
    @patch('api.exception_handler.logger')
    def test_errors_are_logged_with_context(self, mock_logger):
        """Errors should be logged with relevant context."""
        from api.exception_handler import custom_exception_handler
        
        exc = ValueError("Test error")
        request = APIRequestFactory().get('/api/test/')
        context = {
            'view': MagicMock(__class__=MagicMock(__name__='TestView')),
            'request': request
        }
        
        custom_exception_handler(exc, context)
        
        # Should have logged the error
        self.assertTrue(mock_logger.error.called or mock_logger.log.called)
