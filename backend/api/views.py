import json
import logging
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import OperationalError, ProgrammingError, connection, transaction
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenViewBase
from tenants.models import Client, SubscriptionStatus

from .audit_log import AuditEvent, log_audit_event
from .logging_utils import sanitize_log_value
from .models import UserProfile
from .serializers import RegistrationSerializer, UserSerializer
from .throttles import BurstRateThrottle, LoginRateThrottle, RegistrationRateThrottle
from .utils import send_verification_email

auth_logger = logging.getLogger("api.auth")
User = get_user_model()


def _ordered_schema_names(current_schema: str | None = None) -> list[str]:
    """
    Return tenant schemas to search, excluding the public schema.

    Email/user data lives in tenant schemas only; querying public first would
    throw relation errors (no user_profiles table) and close the connection.
    We therefore skip public entirely and deduplicate while preserving order.
    """

    public_schema = get_public_schema_name()

    schema_candidates: list[str] = []
    if current_schema and current_schema != public_schema:
        schema_candidates.append(current_schema)

    with schema_context(public_schema):
        tenant_schemas = list(
            Client.objects.exclude(schema_name=public_schema).values_list("schema_name", flat=True)
        )
        schema_candidates.extend(tenant_schemas)

    if settings.DEBUG and "test_tenant" not in schema_candidates:
        schema_candidates.append("test_tenant")

    ordered_schemas: list[str] = []
    seen: set[str] = set()
    for schema_name in schema_candidates:
        if schema_name and schema_name not in seen:
            ordered_schemas.append(schema_name)
            seen.add(schema_name)

    return ordered_schemas


def _write_debug_log(log_type: str, data: dict) -> None:
    """Write detailed debug logs to file for EC2 troubleshooting."""
    try:
        log_dir = Path("/app/logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / "auth_debug.log"

        entry = {"timestamp": timezone.now().isoformat(), "type": log_type, "data": data}

        with open(log_file, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception as e:
        # Don't let logging failures break authentication
        auth_logger.error(f"Failed to write debug log: {e}")


class PingView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

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
        data = dict(serializer.data)
        plan = getattr(tenant, "subscription_status", SubscriptionStatus.FREE)
        data["plan"] = plan
        return Response(data)


class RegistrationView(APIView):
    """
    User registration endpoint with rate limiting.

    Creates a new tenant (organization) and owner user account.
    Protected by rate limiting to prevent spam and abuse.

    Rate limits:
    - 5 registrations per hour per IP
    - 20 requests per minute burst protection
    """

    authentication_classes: list[type] = []
    permission_classes = [AllowAny]
    throttle_classes = [RegistrationRateThrottle, BurstRateThrottle]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        if serializer.is_valid():
            payload = serializer.save()

            # Log audit events for registration
            log_audit_event(
                event=AuditEvent.USER_REGISTERED,
                user_id=payload.get("user", {}).get("id"),
                user_email=payload.get("user", {}).get("email"),
                ip_address=TokenObtainPairWithLoggingView._extract_ip(request),
                tenant_schema=payload.get("tenant", {}).get("schema_name"),
                details={"org_name": payload.get("tenant", {}).get("name")},
            )

            log_audit_event(
                event=AuditEvent.TENANT_CREATED,
                user_id=payload.get("user", {}).get("id"),
                user_email=payload.get("user", {}).get("email"),
                ip_address=TokenObtainPairWithLoggingView._extract_ip(request),
                tenant_schema=payload.get("tenant", {}).get("schema_name"),
                details={
                    "org_name": payload.get("tenant", {}).get("name"),
                    "schema_name": payload.get("tenant", {}).get("schema_name"),
                },
            )

            return Response(payload, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class TokenObtainPairWithLoggingView(TokenViewBase):
    """JWT login endpoint with structured logging and throttling."""

    authentication_classes = ()  # type: ignore[assignment]
    permission_classes = (AllowAny,)  # type: ignore[assignment]
    throttle_classes = [LoginRateThrottle, BurstRateThrottle]
    serializer_class = TokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        username = request.data.get("username") or request.data.get("email")
        password = request.data.get("password", "")
        ip_address = self._extract_ip(request)
        tenant = getattr(request, "tenant", None)
        schema_name = getattr(tenant, "schema_name", "public")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        host = request.get_host()
        origin = request.META.get("HTTP_ORIGIN", "")

        # DETAILED DEBUG LOGGING FOR EC2 TROUBLESHOOTING
        debug_data = {
            "email": username,
            "password_length": len(password) if password else 0,
            "password_has_value": bool(password),
            "schema_name": schema_name,
            "host": host,
            "origin": origin,
            "ip_address": ip_address,
            "user_agent": user_agent[:100] if user_agent else "",
            "is_public_schema": schema_name == "public",
            "tenant_id": getattr(tenant, "id", None),
            "tenant_name": getattr(tenant, "name", None),
        }

        # Check if user exists in this schema for richer logging context
        try:
            with schema_context(schema_name):
                try:
                    user = User.objects.get(email=username)
                    debug_data["user_exists"] = True
                    debug_data["user_id"] = user.id
                    debug_data["user_is_active"] = user.is_active
                    debug_data["user_has_usable_password"] = user.has_usable_password()
                    debug_data["password_hash_prefix"] = (
                        user.password[:20] if user.password else None
                    )

                    password_check = user.check_password(password)
                    debug_data["password_check_result"] = password_check
                except User.DoesNotExist:
                    debug_data["user_exists"] = False
                    debug_data["error"] = f"User {username} not found in schema {schema_name}"
        except Exception as e:  # pragma: no cover - defensive debug fallback
            debug_data["user_lookup_error"] = str(e)

        _write_debug_log(
            "login_attempt",
            {
                **debug_data,
                "origin": origin,
                "ip_address": ip_address,
                "user_agent": user_agent[:100] if user_agent else "",
                "is_public_schema": schema_name == "public",
            },
        )

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            reason = exc.args[0] if exc.args else "Invalid credentials"

            # Enhanced debug logging for failures
            _write_debug_log(
                "login_failed",
                {
                    "email": username,
                    "schema_name": schema_name,
                    "host": host,
                    "ip_address": ip_address,
                    "reason": reason,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                },
            )

            auth_logger.warning(
                "Login failed",
                extra={
                    "email": username,
                    "schema_name": schema_name,
                    "host": host,
                    "ip_address": ip_address,
                    "reason": reason,
                    "user_agent": user_agent,
                },
            )

            # Log audit event for failed login
            log_audit_event(
                event=AuditEvent.USER_LOGIN_FAILED,
                user_email=username,
                ip_address=ip_address,
                tenant_schema=schema_name,
                details={"reason": reason, "user_agent": user_agent, "host": host},
            )

            raise InvalidToken(reason) from exc

        user = getattr(serializer, "user", None)
        if user is None and username:
            lookup_filters = (
                {"email__iexact": username},
                {"username__iexact": username},
            )
            with schema_context(schema_name):
                for filters in lookup_filters:
                    try:
                        user = User.objects.get(**filters)
                        break
                    except User.DoesNotExist:
                        continue

        profile = None
        profile_created = False
        profile_is_verified = True
        if user is not None:
            with schema_context(schema_name):
                # select_for_update requires an explicit transaction; wrap the profile
                # fetch/create logic to avoid TransactionManagementError during login.
                with transaction.atomic():
                    profile = (
                        UserProfile.objects.select_for_update()
                        .filter(user=user)
                        .select_related("user")
                        .first()
                    )

                    if profile is None:
                        profile = UserProfile.objects.create(
                            user=user,
                            email_verified=False,
                            email_verification_sent_at=timezone.now(),
                        )
                        profile_created = True

                    # Always ensure we have the latest values from DB before decision making
                    profile.refresh_from_db(fields=["email_verified", "email_verification_sent_at"])
                    profile_is_verified = profile.email_verified

                    if not profile_is_verified and profile.email_verification_sent_at is None:
                        profile.email_verification_sent_at = timezone.now()
                        profile.save(update_fields=["email_verification_sent_at", "updated_at"])

            if profile_created:
                send_verification_email(user, profile.email_verification_token)

        if profile and not profile_is_verified:
            _write_debug_log(
                "login_profile_state",
                {
                    "email": username or getattr(user, "email", None),
                    "user_id": getattr(user, "id", None),
                    "schema_name": schema_name,
                    "email_verified": profile_is_verified,
                    "profile_updated_at": getattr(profile, "updated_at", None),
                },
            )
            message = (
                "Email not verified. Please verify your address via the link in your inbox"
                " or request a new verification email."
            )

            _write_debug_log(
                "login_blocked_unverified",
                {
                    "email": username or getattr(user, "email", None),
                    "user_id": getattr(user, "id", None),
                    "schema_name": schema_name,
                },
            )

            auth_logger.warning(
                "Login blocked until email verification",
                extra={
                    "email": username or getattr(user, "email", None),
                    "user_id": getattr(user, "id", None),
                    "schema_name": schema_name,
                    "host": host,
                    "ip_address": ip_address,
                },
            )

            log_audit_event(
                event=AuditEvent.USER_LOGIN_FAILED,
                user_id=getattr(user, "id", None),
                user_email=username or getattr(user, "email", None),
                ip_address=ip_address,
                tenant_schema=schema_name,
                details={
                    "reason": "email_unverified",
                    "user_agent": user_agent,
                    "host": host,
                },
            )

            return Response(
                {
                    "error": {
                        "code": "email_unverified",
                        "message": message,
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        elif profile:
            _write_debug_log(
                "login_profile_state",
                {
                    "email": username or getattr(user, "email", None),
                    "user_id": getattr(user, "id", None),
                    "schema_name": schema_name,
                    "email_verified": profile_is_verified,
                    "profile_updated_at": getattr(profile, "updated_at", None),
                    "blocked": False,
                },
            )

        # Log successful authentication
        _write_debug_log(
            "login_success",
            {
                "email": username or getattr(user, "email", None),
                "user_id": getattr(user, "id", None),
                "schema_name": schema_name,
                "host": host,
                "ip_address": ip_address,
            },
        )

        auth_logger.info(
            "Login successful",
            extra={
                "email": username or getattr(user, "email", None),
                "user_id": getattr(user, "id", None),
                "schema_name": schema_name,
                "host": host,
                "ip_address": ip_address,
                "user_agent": user_agent,
            },
        )

        # Log audit event for successful login
        log_audit_event(
            event=AuditEvent.USER_LOGIN,
            user_id=getattr(user, "id", None),
            user_email=username or getattr(user, "email", None),
            ip_address=ip_address,
            tenant_schema=schema_name,
            details={"user_agent": user_agent, "host": host},
        )

        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    @staticmethod
    def _extract_ip(request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


@api_view(["POST"])
def verify_email(request):
    """Verify a user's email using a JSON payload that includes the token."""

    token_value = request.data.get("token")
    if not token_value:
        return Response(
            {"error": "Verification token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        token_uuid = uuid.UUID(str(token_value))
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid verification token."},
            status=status.HTTP_404_NOT_FOUND,
        )

    current_schema = getattr(getattr(request, "tenant", None), "schema_name", None)
    ordered_schemas = _ordered_schema_names(current_schema)

    for schema_name in ordered_schemas:
        try:
            with schema_context(schema_name):
                with transaction.atomic():
                    profile = (
                        UserProfile.objects.select_related("user")
                        .select_for_update()
                        .filter(email_verification_token=token_uuid)
                        .first()
                    )

                    if not profile:
                        continue

                    user_email = profile.user.email

                    if profile.email_verified:
                        return Response(
                            {
                                "detail": "Email already verified. You can now log in.",
                                "email": user_email,
                            },
                            status=status.HTTP_200_OK,
                        )

                    if profile.is_verification_token_expired():
                        return Response(
                            {
                                "error": "Verification token has expired. Please request a new one.",
                                "expired": True,
                                "email": user_email,
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    profile.email_verified = True
                    profile.email_verification_token = None
                    profile.save(
                        update_fields=[
                            "email_verified",
                            "email_verification_token",
                            "updated_at",
                        ]
                    )

                    from .utils import send_welcome_email

                    send_welcome_email(profile.user)

                    return Response(
                        {
                            "detail": "Email verified successfully! You can now log in.",
                            "email": user_email,
                        },
                        status=status.HTTP_200_OK,
                    )
        except (ProgrammingError, OperationalError):
            if connection.in_atomic_block:
                transaction.set_rollback(True)
            connection.close_if_unusable_or_obsolete()
            continue
        except Exception:
            if connection.in_atomic_block:
                transaction.set_rollback(True)
            connection.close_if_unusable_or_obsolete()
            continue

    return Response(
        {"error": "Invalid verification token."},
        status=status.HTTP_404_NOT_FOUND,
    )


@api_view(["POST"])
def resend_verification_email(request):
    """Resend a verification email without leaking whether the account exists."""

    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return Response(
            {"error": "Email address is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    generic_detail = (
        "If an account exists for this email, we've sent a fresh verification link. Please check"
        " your inbox."
    )

    current_schema = getattr(getattr(request, "tenant", None), "schema_name", None)
    ordered_schemas = _ordered_schema_names(current_schema)

    for schema_name in ordered_schemas:
        try:
            with schema_context(schema_name):
                with transaction.atomic():
                    user_profile = (
                        UserProfile.objects.select_related("user")
                        .select_for_update()
                        .filter(user__email__iexact=email)
                        .order_by("-updated_at")
                        .first()
                    )

                    if not user_profile:
                        continue

                    if user_profile.email_verified:
                        return Response(
                            {"detail": "Email is already verified. You can now log in."},
                            status=status.HTTP_200_OK,
                        )

                    user_profile.regenerate_verification_token()

                    from .utils import send_verification_email

                    send_verification_email(
                        user_profile.user, user_profile.email_verification_token
                    )

                    return Response({"detail": generic_detail}, status=status.HTTP_200_OK)
        except (ProgrammingError, OperationalError):
            if connection.in_atomic_block:
                transaction.set_rollback(True)
            connection.close_if_unusable_or_obsolete()
            continue

    return Response({"detail": generic_detail}, status=status.HTTP_200_OK)


@api_view(["POST"])
def resend_verification_email_debug(request):
    """Development-only helper that forces a verification email resend for an email."""

    if not settings.DEBUG:
        return Response(status=status.HTTP_404_NOT_FOUND)

    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return Response(
            {"error": "Email address is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    current_schema = getattr(getattr(request, "tenant", None), "schema_name", None)
    ordered_schemas = _ordered_schema_names(current_schema)

    for schema_name in ordered_schemas:
        try:
            with schema_context(schema_name):
                with transaction.atomic():
                    profile = (
                        UserProfile.objects.select_related("user")
                        .select_for_update()
                        .filter(user__email__iexact=email)
                        .order_by("-updated_at")
                        .first()
                    )
                    if not profile:
                        continue

                    profile.email_verified = False
                    profile.regenerate_verification_token()

                    from .utils import send_verification_email

                    send_verification_email(profile.user, profile.email_verification_token)

                    return Response(
                        {
                            "detail": "Verification email resent.",
                            "schema": schema_name,
                            "token": str(profile.email_verification_token),
                        }
                    )
        except (ProgrammingError, OperationalError):
            if connection.in_atomic_block:
                transaction.set_rollback(True)
            connection.close_if_unusable_or_obsolete()
            continue

    return Response({"error": "Email not found."}, status=status.HTTP_404_NOT_FOUND)


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


@api_view(["GET"])
def validate_domain_for_tls(request):
    """
    Endpoint for Caddy on-demand TLS validation.
    Returns 200 if domain exists in tenant domains, 404 if not.

    Called by Caddy when a new subdomain is accessed to determine
    if an SSL certificate should be issued automatically.

    Query params:
        domain: The domain to validate (e.g., "newclient.statuswatch.kontentwave.digital")

    Returns:
        200 OK: Domain exists and certificate should be issued
        404 Not Found: Domain does not exist
        400 Bad Request: Missing domain parameter
    """
    from tenants.models import Domain

    domain = request.GET.get("domain", "").strip().lower()

    if not domain:
        return Response(
            {"error": "domain parameter required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check if domain exists in tenant domains
    exists = Domain.objects.filter(domain=domain).exists()

    if exists:
        auth_logger.info(
            f"TLS validation SUCCESS for domain: {domain}",
            extra={
                "domain": domain,
                "validation": "success",
                "source": "caddy_on_demand_tls",
            },
        )
        return Response(
            {"domain": domain, "valid": True},
            status=status.HTTP_200_OK,
        )
    else:
        auth_logger.warning(
            f"TLS validation REJECTED for domain: {domain}",
            extra={
                "domain": domain,
                "validation": "rejected",
                "source": "caddy_on_demand_tls",
            },
        )
        return Response(
            {"domain": domain, "valid": False},
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["GET"])
def latest_verification_token(request):
    """Development-only helper that exposes the latest verification token for an email."""

    if not settings.DEBUG:
        return Response(status=status.HTTP_404_NOT_FOUND)

    email = (request.GET.get("email") or "").strip().lower()
    if not email:
        return Response(
            {"error": "email query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    current_schema = getattr(getattr(request, "tenant", None), "schema_name", None)
    ordered_schemas = _ordered_schema_names(current_schema)

    for schema_name in ordered_schemas:
        try:
            with schema_context(schema_name):
                with transaction.atomic():
                    profile = (
                        UserProfile.objects.select_related("user")
                        .filter(user__email__iexact=email)
                        .order_by("-updated_at")
                        .first()
                    )
                    if not profile or not profile.email_verification_token:
                        continue
                    return Response(
                        {
                            "email": profile.user.email,
                            "token": str(profile.email_verification_token),
                            "schema": schema_name,
                        }
                    )
        except (ProgrammingError, OperationalError):
            if connection.in_atomic_block:
                transaction.set_rollback(True)
            connection.close_if_unusable_or_obsolete()
            continue

    return Response(
        {"error": "Verification token not found for the supplied email."},
        status=status.HTTP_404_NOT_FOUND,
    )


@api_view(["POST"])
def expire_verification_token(request):
    """Development-only helper to mark a verification token as expired."""

    if not settings.DEBUG:
        return Response(status=status.HTTP_404_NOT_FOUND)

    email = (request.data.get("email") or "").strip().lower()
    token_value = request.data.get("token")

    if not email and not token_value:
        return Response(
            {"error": "Either email or token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    token_uuid: uuid.UUID | None = None
    if token_value:
        try:
            token_uuid = uuid.UUID(str(token_value))
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid verification token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    current_schema = getattr(getattr(request, "tenant", None), "schema_name", None)
    ordered_schemas = _ordered_schema_names(current_schema)

    for schema_name in ordered_schemas:
        try:
            with schema_context(schema_name):
                with transaction.atomic():
                    query = UserProfile.objects.select_related("user")
                    if email:
                        query = query.filter(user__email__iexact=email)
                    if token_uuid:
                        query = query.filter(email_verification_token=token_uuid)

                    profile = query.order_by("-updated_at").first()
                    if not profile:
                        continue

                    profile.email_verification_sent_at = timezone.now() - timedelta(days=3)
                    profile.email_verified = False
                    profile.save(
                        update_fields=[
                            "email_verification_sent_at",
                            "email_verified",
                            "updated_at",
                        ]
                    )

                    return Response(
                        {
                            "detail": "Verification token marked as expired.",
                            "email": profile.user.email,
                            "schema": schema_name,
                        },
                        status=status.HTTP_200_OK,
                    )
        except (ProgrammingError, OperationalError):
            if connection.in_atomic_block:
                transaction.set_rollback(True)
            connection.close_if_unusable_or_obsolete()
            continue

    return Response(
        {"error": "Matching verification token not found."},
        status=status.HTTP_404_NOT_FOUND,
    )
