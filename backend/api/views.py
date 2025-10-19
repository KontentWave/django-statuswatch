from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserProfile
from .serializers import RegistrationSerializer
from .throttles import RegistrationRateThrottle, BurstRateThrottle


class PingView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"ok": True})


class SecurePingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"ok": True, "user": str(request.user)})


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
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Import here to avoid issues if blacklist not installed
            from rest_framework_simplejwt.tokens import RefreshToken
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {"detail": "Logout successful."},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            return Response(
                {"error": f"Invalid token: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

