import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenViewBase

from .logging_utils import sanitize_log_value
from .models import UserProfile
from .serializers import RegistrationSerializer, UserSerializer
from .throttles import BurstRateThrottle, LoginRateThrottle, RegistrationRateThrottle


auth_logger = logging.getLogger("api.auth")


class PingView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"ok": True})


class SecurePingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"ok": True, "user": str(request.user)})


class CurrentUserView(APIView):
    """
    Return information about the currently authenticated user.
    
    Returns user details including groups. Requires valid JWT.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        auth_logger.info(
            "Fetched current user profile",
            extra={
                "user_id": getattr(request.user, "id", None),
                "email": getattr(request.user, "email", None),
                "schema_name": getattr(tenant, "schema_name", "public"),
                "ip_address": TokenObtainPairWithLoggingView._extract_ip(request),
            },
        )
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class RegistrationView(APIView):
    """
    User registration endpoint with rate limiting.
    
    Creates a new tenant (organization) and owner user account.
    Protected by rate limiting to prevent spam and abuse.
    
    Rate limits:
    - 5 registrations per hour per IP
    - 20 requests per minute burst protection
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [RegistrationRateThrottle, BurstRateThrottle]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        if serializer.is_valid():
            payload = serializer.save()
            return Response(payload, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class TokenObtainPairWithLoggingView(TokenViewBase):
    """JWT login endpoint with structured logging and throttling."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle, BurstRateThrottle]
    serializer_class = TokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        username = request.data.get("username") or request.data.get("email")
        ip_address = self._extract_ip(request)
        tenant = getattr(request, "tenant", None)
        schema_name = getattr(tenant, "schema_name", "public")
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            reason = exc.args[0] if exc.args else "Invalid credentials"
            auth_logger.warning(
                "Login failed",
                extra={
                    "email": username,
                    "schema_name": schema_name,
                    "ip_address": ip_address,
                    "reason": reason,
                    "user_agent": user_agent,
                },
            )
            raise InvalidToken(reason) from exc

        user = getattr(serializer, "user", None)
        auth_logger.info(
            "Login successful",
            extra={
                "email": username or getattr(user, "email", None),
                "user_id": getattr(user, "id", None),
                "schema_name": schema_name,
                "ip_address": ip_address,
                "user_agent": user_agent,
            },
        )

        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    @staticmethod
    def _extract_ip(request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


@api_view(['GET', 'POST'])
def verify_email(request, token):
    """
    Verify user's email address using the token sent via email.
    
    This endpoint is public (no authentication required) and uses the
    verification token to identify and verify the user.
    Accepts both GET (for email links) and POST (for API calls).
    
    Args:
        token: UUID token sent to user's email
        
    Returns:
        200: Email verified successfully
        400: Invalid or expired token
        404: Token not found
    """
    try:
        profile = UserProfile.objects.select_related('user').get(
            email_verification_token=token
        )
    except UserProfile.DoesNotExist:
        return Response(
            {"error": "Invalid verification token."},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if already verified
    if profile.email_verified:
        return Response(
            {"detail": "Email already verified. You can now log in."},
            status=status.HTTP_200_OK
        )
    
    # Check if token expired
    if profile.is_verification_token_expired():
        return Response(
            {
                "error": "Verification token has expired. Please request a new one.",
                "expired": True
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify the email
    profile.email_verified = True
    profile.save()
    
    return Response(
        {"detail": "Email verified successfully! You can now log in."},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
def resend_verification_email(request):
    """
    Resend verification email to the user.
    
    User must be authenticated but not yet verified. This allows users
    who didn't receive the email or whose token expired to get a new one.
    
    Rate limited to prevent abuse.
    
    Returns:
        200: Email resent successfully
        400: Email already verified or rate limit exceeded
    """
    if not request.user.is_authenticated:
        return Response(
            {"error": "Authentication required."},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return Response(
            {"error": "User profile not found."},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if profile.email_verified:
        return Response(
            {"error": "Email is already verified."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Regenerate token and send email
    profile.regenerate_verification_token()
    
    # Import here to avoid circular dependency
    from .utils import send_verification_email
    send_verification_email(request.user, profile.email_verification_token)
    
    return Response(
        {"detail": "Verification email has been resent. Please check your inbox."},
        status=status.HTTP_200_OK
    )


class LogoutView(APIView):
    """
    Logout endpoint with JWT token blacklisting (P1-05).
    
    Blacklists the refresh token to prevent it from being used again.
    The access token will expire naturally (15 minutes).
    
    Requires authentication via access token.
    
    Request body:
        refresh: The refresh token to blacklist
    
    Returns:
        205: Logout successful, token blacklisted
        400: Invalid or missing refresh token
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        user = request.user
        tenant = getattr(request, "tenant", None)
        schema_name = getattr(tenant, "schema_name", "public")
        ip_address = TokenObtainPairWithLoggingView._extract_ip(request)

        if not refresh_token:
            auth_logger.warning(
                "Logout rejected: refresh token missing",
                extra={
                    "user_id": getattr(user, "id", None),
                    "email": getattr(user, "email", None),
                    "schema_name": schema_name,
                    "ip_address": ip_address,
                },
            )
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from rest_framework_simplejwt.tokens import RefreshToken

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as exc:
            auth_logger.warning(
                "Logout failed",
                extra={
                    "user_id": getattr(user, "id", None),
                    "email": getattr(user, "email", None),
                    "schema_name": schema_name,
                    "ip_address": ip_address,
                    "reason": sanitize_log_value(str(exc)),
                },
            )
            return Response(
                {"error": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            auth_logger.error(
                "Logout failed",
                extra={
                    "user_id": getattr(user, "id", None),
                    "email": getattr(user, "email", None),
                    "schema_name": schema_name,
                    "ip_address": ip_address,
                    "reason": sanitize_log_value(str(exc)),
                },
            )
            return Response(
                {"error": "Could not complete logout."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        auth_logger.info(
            "Logout successful",
            extra={
                "user_id": getattr(user, "id", None),
                "email": getattr(user, "email", None),
                "schema_name": schema_name,
                "ip_address": sanitize_log_value(ip_address),
            },
        )

        return Response(
            {"detail": "Logout successful. You have been logged out."},
            status=status.HTTP_205_RESET_CONTENT,
        )

