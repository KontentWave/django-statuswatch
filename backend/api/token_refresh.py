"""
Multi-tenant compatible token refresh view.

Standard TokenRefreshView tries to validate that the user exists by querying
auth_user table. In multi-tenant setups, auth_user only exists in tenant schemas,
not in PUBLIC schema. This causes token refresh to fail when accessed from
the centralized hub (localhost:5173).

This custom view skips user validation since:
1. Token signature already validates authenticity
2. User existence is checked when token is used (via JWT authentication)
3. Token blacklist works globally from PUBLIC schema
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger("api.auth")


class MultiTenantTokenRefreshView(APIView):
    """
    Token refresh view that works across tenant and public schemas.

    Unlike the default TokenRefreshView, this doesn't validate user existence
    in the database, making it compatible with multi-tenant architectures where
    users exist in tenant schemas but tokens are refreshed from public schema.
    """

    authentication_classes = []  # No authentication required for token refresh
    permission_classes = []  # Public endpoint

    def post(self, request):
        """
        Refresh an access token using a valid refresh token.

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
            refresh = RefreshToken(refresh_token)

            logger.info(
                f"[TOKEN-REFRESH] Token refresh request for user_id: {refresh.get('user_id')}, "
                f"jti: {refresh.get('jti')}"
            )

            # Generate new access token
            data = {"access": str(refresh.access_token)}

            # If token rotation is enabled, blacklist old token and return new refresh token
            if api_settings.ROTATE_REFRESH_TOKENS:
                if api_settings.BLACKLIST_AFTER_ROTATION:
                    try:
                        # Manually blacklist the token without validating user exists
                        # (avoid auth_user query which fails in PUBLIC schema)
                        from django.utils import timezone
                        from rest_framework_simplejwt.token_blacklist.models import (
                            BlacklistedToken,
                            OutstandingToken,
                        )

                        jti = refresh.get("jti")
                        exp = refresh.get("exp")

                        # Get or create outstanding token
                        token, created = OutstandingToken.objects.get_or_create(
                            jti=jti,
                            defaults={
                                "token": str(refresh),
                                "created_at": timezone.now(),
                                "expires_at": timezone.datetime.fromtimestamp(exp, tz=timezone.utc),
                                "user_id": refresh.get("user_id"),
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
            return Response(
                {"error": "Token is invalid or expired"}, status=status.HTTP_401_UNAUTHORIZED
            )

        except Exception as e:
            logger.error(f"[TOKEN-REFRESH] ✗ Unexpected error: {e}", exc_info=True)
            return Response(
                {"error": "An error occurred while refreshing the token"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
