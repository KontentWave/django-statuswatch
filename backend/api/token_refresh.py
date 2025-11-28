"""
Multi-tenant compatible token refresh view.

Standard TokenRefreshView tries to validate that the user exists by querying
auth_user table. In multi-tenant setups, this causes issues because:
1. User validation requires accessing the specific tenant schema
2. Token blacklist tables exist per-tenant (token_blacklist is in TENANT_APPS)

This custom view works in the current tenant schema and sets user=None to avoid
FK validation errors in OutstandingToken creation.
"""

import logging

from modules.accounts.authentication import TenantAuthService, TokenRefreshError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken as _RefreshToken

from api.audit_log import AuditEvent, log_audit_event
from api.performance_log import PerformanceMonitor

# Backwards compatibility for existing tests that patch this module attribute
RefreshToken = _RefreshToken

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
        client_ip = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT")

        if not refresh_token:
            logger.warning(
                f"[TOKEN-REFRESH] Missing refresh token in request from "
                f"IP: {request.META.get('REMOTE_ADDR')}"
            )
            log_audit_event(
                AuditEvent.TOKEN_REFRESH,
                ip_address=client_ip,
                user_agent=user_agent,
                success=False,
                details={"reason": "missing_refresh_token"},
            )
            return Response(
                {"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with PerformanceMonitor("token_refresh", threshold_ms=250):
                result = TenantAuthService.refresh_tokens(refresh_token, token_class=RefreshToken)

            logger.info(f"[TOKEN-REFRESH] ✓ Token refresh successful for user_id: {result.user_id}")

            log_audit_event(
                AuditEvent.TOKEN_REFRESH,
                user_id=result.user_id,
                ip_address=client_ip,
                user_agent=user_agent,
                success=True,
                details={
                    "rotated": result.rotated,
                    "old_jti": result.old_jti,
                    "new_jti": result.new_jti,
                },
            )

            return Response(result.data, status=status.HTTP_200_OK)

        except (TokenRefreshError, TokenError) as e:
            logger.warning(f"[TOKEN-REFRESH] ✗ Invalid or expired token: {str(e)}")
            log_audit_event(
                AuditEvent.TOKEN_REFRESH,
                ip_address=client_ip,
                user_agent=user_agent,
                success=False,
                details={"reason": str(e)},
            )
            return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        except Exception as e:
            logger.error(f"[TOKEN-REFRESH] ✗ Unexpected error: {e}", exc_info=True)
            log_audit_event(
                AuditEvent.TOKEN_REFRESH,
                ip_address=client_ip,
                user_agent=user_agent,
                success=False,
                details={"reason": "unexpected_error"},
            )
            return Response(
                {"error": "An error occurred while refreshing the token"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
