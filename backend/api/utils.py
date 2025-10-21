"""
Email utility functions for StatusWatch.

Handles sending verification emails, password resets, and other transactional emails.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_verification_email(user, verification_token):
    """
    Send email verification link to user.

    Args:
        user: User object
        verification_token: UUID token for verification

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    # Build verification URL
    verification_url = f"{settings.FRONTEND_URL}/verify-email/{verification_token}"

    # Email context
    context = {
        "user": user,
        "verification_url": verification_url,
        "frontend_url": settings.FRONTEND_URL,
    }

    # Render email template
    html_message = render_to_string("emails/verify_email.html", context)
    plain_message = strip_tags(html_message)

    subject = "Verify your email address - StatusWatch"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Verification email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {str(e)}", exc_info=True)
        return False


def send_welcome_email(user):
    """
    Send welcome email after successful verification.

    Args:
        user: User object

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    context = {
        "user": user,
        "frontend_url": settings.FRONTEND_URL,
    }

    html_message = render_to_string("emails/welcome.html", context)
    plain_message = strip_tags(html_message)

    subject = "Welcome to StatusWatch!"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=True,  # Don't block on welcome email failure
        )
        logger.info(f"Welcome email sent to {user.email}")
        return True
    except Exception as e:
        logger.warning(f"Failed to send welcome email to {user.email}: {str(e)}")
        return False
