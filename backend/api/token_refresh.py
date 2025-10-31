"""
Multi-tenant compatible token refresh view.

Standard TokenRefreshView tries to validate that the user exists by querying
auth_user table. In multi-tenant setups, this causes issues because:
1. User validation requires accessing the specific tenant schema
2. Token blacklist tables exist per-tenant (token_blacklist is in TENANT_APPS)

This custom view works in the current tenant schema and sets user=None to avoid
FK validation errors in OutstandingToken creation.
"""

import datetime
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger("api.auth")


class MultiTenantTokenRefreshView(APIView):
    """
    Token refresh view that works across tenant and public schemas.

    Unlike the default TokenRefreshView, this doesn't validate user existence
    in the database, making it compatible with multi-tenant architectures where
    users exist in tenant schemas but tokens are refreshed from public schema.
    """

    authentication_classes: list[type] = []  # No authentication required for token refresh
    permission_classes: list[type] = []  # Public endpoint

    def post(self, request):
        """
        Refresh an access token using a valid refresh token.

        Multi-tenant note: Token blacklist tables exist in each tenant schema
        (token_blacklist is in TENANT_APPS per settings_base.py line 55).
        This view works in the current tenant schema set by TenantMainMiddleware.

        Request body:
            {
                "refresh": "<refresh_token>"
            }

        Response:
            {
                "access": "<new_access_token>",
                "refresh": "<new_refresh_token>"  # Only if ROTATE_REFRESH_TOKENS=True
            }
        """
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            logger.warning(
                f"[TOKEN-REFRESH] Missing refresh token in request from "
                f"IP: {request.META.get('REMOTE_ADDR')}"
            )
            return Response(
                {"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Parse and validate the refresh token
            # This checks the blacklist in the current tenant schema
            refresh = RefreshToken(refresh_token)

            logger.info(
                f"[TOKEN-REFRESH] Token refresh request for user_id: {refresh.get('user_id')}, "
                f"jti: {refresh.get('jti')}"
            )

            # Generate new access token
            data = {"access": str(refresh.access_token)}

            # Get JWT settings (allow runtime modifications in tests)
            from django.conf import settings as django_settings

            jwt_config = getattr(django_settings, "SIMPLE_JWT", {})
            rotate_tokens = jwt_config.get("ROTATE_REFRESH_TOKENS", False)
            blacklist_after = jwt_config.get("BLACKLIST_AFTER_ROTATION", False)

            # If token rotation is enabled, blacklist old token and return new refresh token
            if rotate_tokens:
                if blacklist_after:
                    try:
                        # Manually blacklist the token without validating user exists
                        from django.utils import timezone
                        from rest_framework_simplejwt.token_blacklist.models import (
                            BlacklistedToken,
                            OutstandingToken,
                        )

                        jti = refresh.get("jti")
                        exp = refresh.get("exp")

                        # Get or create outstanding token
                        # NOTE: user field set to None to avoid FK validation
                        # The token itself contains user_id claim, so user association is preserved
                        token, created = OutstandingToken.objects.get_or_create(
                            jti=jti,
                            defaults={
                                "token": str(refresh),
                                "created_at": timezone.now(),
                                "expires_at": datetime.datetime.fromtimestamp(exp, tz=datetime.UTC),
                                # Explicitly NULL - FK validation fails in multi-tenant setup
                                "user": None,
                            },
                        )

                        # Blacklist it
                        BlacklistedToken.objects.get_or_create(token=token)

                        logger.info(f"[TOKEN-REFRESH] Old refresh token blacklisted (jti: {jti})")
                    except Exception as e:
                        # Token blacklist not installed or other error
                        logger.warning(f"[TOKEN-REFRESH] Could not blacklist token: {e}")

                # Generate new refresh token
                refresh.set_jti()
                refresh.set_exp()
                refresh.set_iat()

                data["refresh"] = str(refresh)
                logger.info(
                    f"[TOKEN-REFRESH] New refresh token generated (jti: {refresh.get('jti')})"
                )

            logger.info(
                f"[TOKEN-REFRESH] ✓ Token refresh successful for user_id: {refresh.get('user_id')}"
            )

            return Response(data, status=status.HTTP_200_OK)

        except TokenError as e:
            logger.warning(f"[TOKEN-REFRESH] ✗ Invalid or expired token: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        except Exception as e:
            logger.error(f"[TOKEN-REFRESH] ✗ Unexpected error: {e}", exc_info=True)
            return Response(
                {"error": "An error occurred while refreshing the token"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
