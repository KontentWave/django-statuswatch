"""
Custom password validators for enforcing strong password requirements.

These validators work with Django's built-in password validation system and
can be configured in settings.AUTH_PASSWORD_VALIDATORS.
"""

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class MinimumLengthValidator:
    """
    Validate that the password is of a minimum length.
    
    Default: 12 characters (stronger than Django's default of 8)
    """
    
    def __init__(self, min_length=12):
        self.min_length = min_length
    
    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                _("Password must be at least %(min_length)d characters long."),
                code="password_too_short",
                params={"min_length": self.min_length},
            )
    
    def get_help_text(self):
        return _(
            "Your password must contain at least %(min_length)d characters."
            % {"min_length": self.min_length}
        )


class UppercaseValidator:
    """
    Validate that the password contains at least one uppercase letter.
    """
    
    def validate(self, password, user=None):
        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                _("Password must contain at least one uppercase letter (A-Z)."),
                code="password_no_upper",
            )
    
    def get_help_text(self):
        return _("Your password must contain at least one uppercase letter (A-Z).")


class LowercaseValidator:
    """
    Validate that the password contains at least one lowercase letter.
    """
    
    def validate(self, password, user=None):
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                _("Password must contain at least one lowercase letter (a-z)."),
                code="password_no_lower",
            )
    
    def get_help_text(self):
        return _("Your password must contain at least one lowercase letter (a-z).")


class NumberValidator:
    """
    Validate that the password contains at least one digit.
    """
    
    def validate(self, password, user=None):
        if not re.search(r"\d", password):
            raise ValidationError(
                _("Password must contain at least one number (0-9)."),
                code="password_no_number",
            )
    
    def get_help_text(self):
        return _("Your password must contain at least one number (0-9).")


class SpecialCharacterValidator:
    """
    Validate that the password contains at least one special character.
    
    Special characters: !@#$%^&*()_+-=[]{}|;:,.<>?
    """
    
    def __init__(self, special_chars=r"!@#$%^&*()_+\-=\[\]{}|;:,.<>?"):
        self.special_chars = special_chars
    
    def validate(self, password, user=None):
        pattern = f"[{re.escape(self.special_chars)}]"
        if not re.search(pattern, password):
            raise ValidationError(
                _("Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)."),
                code="password_no_special",
            )
    
    def get_help_text(self):
        return _(
            "Your password must contain at least one special character "
            "(!@#$%^&*()_+-=[]{}|;:,.<>?)."
        )


class MaximumLengthValidator:
    """
    Validate that the password is not too long.
    
    Default: 128 characters (prevents DoS via bcrypt/argon2 hashing)
    """
    
    def __init__(self, max_length=128):
        self.max_length = max_length
    
    def validate(self, password, user=None):
        if len(password) > self.max_length:
            raise ValidationError(
                _("Password must be no more than %(max_length)d characters long."),
                code="password_too_long",
                params={"max_length": self.max_length},
            )
    
    def get_help_text(self):
        return _(
            "Your password must be no more than %(max_length)d characters."
            % {"max_length": self.max_length}
        )
