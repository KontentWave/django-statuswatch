"""Auth helpers that proxy to the legacy multi-tenant auth implementation."""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Any

from api.auth_service import MultiTenantAuthenticationError, MultiTenantAuthService
from django.conf import settings
from django.db import connection
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger("api.auth")


@dataclass(slots=True)
class TokenRefreshResult:
    """Return payload for a successful token refresh."""

    data: dict[str, str]
    user_id: Any | None
    old_jti: str | None
    new_jti: str | None
    rotated: bool


class TokenRefreshError(Exception):
    """Raised when refresh token validation or rotation fails."""

    pass


class TenantAuthService:
    """Wrapper around the existing multi-tenant authentication logic."""

    AuthenticationError = MultiTenantAuthenticationError

    @staticmethod
    def authenticate_user(username: str, password: str, *, tenant_schema: str | None = None):
        return MultiTenantAuthService.authenticate_user(
            username, password, tenant_schema=tenant_schema
        )

    @staticmethod
    def find_all_tenants_for_email(email: str):
        return MultiTenantAuthService.find_all_tenants_for_email(email)

    @staticmethod
    def find_user_in_tenants(username: str, tenant_schema: str | None = None):
        return MultiTenantAuthService.find_user_in_tenants(username, tenant_schema)

    @staticmethod
    def refresh_tokens(
        refresh_token: str,
        *,
        token_class: type[RefreshToken] = RefreshToken,
    ) -> TokenRefreshResult:
        """Validate and rotate refresh tokens in the public schema."""

        try:
            token = token_class(refresh_token)
        except TokenError as exc:  # Bubble up as custom error for the API view
            raise TokenRefreshError(str(exc)) from exc

        jwt_config = getattr(settings, "SIMPLE_JWT", {})
        rotate_tokens = jwt_config.get("ROTATE_REFRESH_TOKENS", False)
        blacklist_after_rotation = jwt_config.get("BLACKLIST_AFTER_ROTATION", False)

        user_id = token.get("user_id")
        old_jti = token.get("jti")
        old_exp = token.get("exp")
        rotated = False
        new_jti = old_jti

        data: dict[str, str] = {"access": str(token.access_token)}

        if rotate_tokens:
            rotated = True

            if blacklist_after_rotation and old_jti and old_exp:
                # Blacklist the previous refresh token inside the PUBLIC schema
                try:
                    from rest_framework_simplejwt.token_blacklist.models import (
                        BlacklistedToken,
                        OutstandingToken,
                    )
                except Exception as exc:  # pragma: no cover - import failure edge case
                    logger.warning("[TOKEN-REFRESH] Token blacklist unavailable: %s", exc)
                else:
                    expires_at = datetime.datetime.fromtimestamp(old_exp, tz=datetime.UTC)
                    try:
                        token_obj, _ = OutstandingToken.objects.get_or_create(
                            jti=old_jti,
                            defaults={
                                "token": refresh_token,
                                "created_at": timezone.now(),
                                "expires_at": expires_at,
                                "user": None,
                            },
                        )
                        BlacklistedToken.objects.get_or_create(token=token_obj)
                        logger.info(
                            "[TOKEN-REFRESH] Old refresh token blacklisted (jti: %s)", old_jti
                        )
                    except Exception as exc:  # pragma: no cover - DB failure edge case
                        logger.warning(
                            "[TOKEN-REFRESH] Could not blacklist token %s: %s", old_jti, exc
                        )
                        connection.rollback()

            # Rotate the refresh token so the caller receives a new one
            token.set_jti()
            token.set_exp()
            token.set_iat()
            new_jti = token.get("jti")
            data["refresh"] = str(token)

        return TokenRefreshResult(
            data=data,
            user_id=user_id,
            old_jti=old_jti,
            new_jti=new_jti,
            rotated=rotated,
        )
