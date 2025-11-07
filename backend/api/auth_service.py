"""
CENTRALIZED MULTI-TENANT AUTHENTICATION SERVICE

This module provides authentication that works across ALL tenant schemas.
When a user logs in at localhost:5173/login, this service:

1. Receives username/password
2. Searches ALL tenant schemas to find the user
3. Authenticates against the correct tenant schema
4. Returns: JWT tokens + tenant information (schema_name, domains)
5. Frontend uses tenant info to redirect to: {tenant}.localhost:5173/dashboard

Location: backend/api/auth_service.py
"""

import logging
from typing import Any

from django.contrib.auth import authenticate
from django.db import connection
from rest_framework_simplejwt.tokens import RefreshToken
from tenants.models import Client

logger = logging.getLogger("api.auth")


class MultiTenantAuthenticationError(Exception):
    """Raised when multi-tenant authentication fails"""

    pass


class MultiTenantAuthService:
    """
    Handles authentication across multiple tenant schemas.

    This service is designed to work from the public schema and search
    all tenant schemas to find and authenticate users.
    """

    @staticmethod
    def find_all_tenants_for_email(email: str) -> list[dict[str, Any]]:
        """
        Find ALL tenants that have a user with the given email.

        Used for smart login: if multiple tenants have the same email,
        ask user to select which tenant they want to login to.

        Args:
            email: The email to search for

        Returns:
            List of dicts with keys: 'schema_name', 'tenant_name',
            'tenant_id', 'user_id', 'username'
        """
        logger.info(f"[MULTI-TENANT-AUTH] Searching all tenants for email: {email}")

        matches = []
        tenants = Client.objects.exclude(schema_name="public")

        for tenant in tenants:
            schema_name = tenant.schema_name

            try:
                # Switch to tenant schema
                with connection.cursor() as cursor:
                    cursor.execute(f'SET search_path TO "{schema_name}"')

                    # Search for user by email
                    cursor.execute(
                        """
                        SELECT id, username, email, is_active
                        FROM auth_user
                        WHERE email = %s AND is_active = true
                        LIMIT 1
                    """,
                        [email],
                    )

                    result = cursor.fetchone()

                    if result:
                        user_id, db_username, db_email, is_active = result
                        matches.append(
                            {
                                "schema_name": schema_name,
                                "tenant_name": tenant.name,
                                "tenant_id": tenant.id,
                                "user_id": user_id,
                                "username": db_username,
                                "email": db_email,
                            }
                        )
                        logger.debug(
                            f"[MULTI-TENANT-AUTH] Found user in schema '{schema_name}': "
                            f"id={user_id}, username={db_username}"
                        )

            except Exception as e:
                logger.error(
                    f"[MULTI-TENANT-AUTH] Error searching schema '{schema_name}': {e}",
                    exc_info=True,
                )
                continue

        logger.info(f"[MULTI-TENANT-AUTH] Found {len(matches)} tenant(s) for email '{email}'")
        return matches

    @staticmethod
    def find_user_in_tenants(
        username: str, tenant_schema: str | None = None
    ) -> dict[str, Any] | None:
        """
        Search all tenant schemas to find a user by username or email.

        Args:
            username: The username or email to search for
            tenant_schema: Optional - specific tenant schema to search in

        Returns:
            Dict with keys: 'schema_name', 'user_id', 'username', 'email'
            or None if user not found in any tenant
        """
        logger.info(
            f"[MULTI-TENANT-AUTH] Searching for user: {username}"
            + (f" in tenant: {tenant_schema}" if tenant_schema else " in all tenants")
        )

        # Get all tenant schemas (exclude public), optionally filter by specific schema
        tenants = Client.objects.exclude(schema_name="public")
        if tenant_schema:
            tenants = tenants.filter(schema_name=tenant_schema)

        for tenant in tenants:
            schema_name = tenant.schema_name

            try:
                # Switch to tenant schema
                with connection.cursor() as cursor:
                    # Escape schema name with hyphens
                    cursor.execute(f'SET search_path TO "{schema_name}"')

                    # Search for user by username or email
                    cursor.execute(
                        """
                        SELECT id, username, email, is_active
                        FROM auth_user
                        WHERE (username = %s OR email = %s) AND is_active = true
                        LIMIT 1
                    """,
                        [username, username],
                    )

                    result = cursor.fetchone()

                    if result:
                        user_id, db_username, email, is_active = result
                        logger.info(
                            f"[MULTI-TENANT-AUTH] ✓ User found in schema '{schema_name}': "
                            f"id={user_id}, username={db_username}, email={email}"
                        )

                        return {
                            "schema_name": schema_name,
                            "tenant_name": tenant.name,
                            "user_id": user_id,
                            "username": db_username,
                            "email": email,
                        }
                    else:
                        logger.debug(
                            f"[MULTI-TENANT-AUTH] User not found in schema '{schema_name}'"
                        )

            except Exception as e:
                logger.error(
                    f"[MULTI-TENANT-AUTH] Error searching schema '{schema_name}': {e}",
                    exc_info=True,
                )
                continue

        logger.warning(f"[MULTI-TENANT-AUTH] ✗ User '{username}' not found in any tenant schema")
        return None

    @staticmethod
    def authenticate_user(
        username: str, password: str, tenant_schema: str | None = None
    ) -> dict[str, Any]:
        """
        Authenticate a user across all tenant schemas (or specific tenant if provided).

        This is the primary authentication method for multi-tenant setup.
        It:
        1. Searches all tenants (or specific tenant) to find the user
        2. Switches to the correct tenant schema
        3. Authenticates the password
        4. Generates JWT tokens
        5. Returns authentication response

        Args:
            username: User's email or username
            password: User's password
            tenant_schema: Optional - specific tenant schema to authenticate in

        Returns:
            Dict containing:
                - access: JWT access token
                - refresh: JWT refresh token
                - tenant_schema: Schema name (e.g., 'marcepokus')
                - tenant_name: Human-readable tenant name
                - tenant_domain: Primary domain for this tenant
                - user: User info (id, username, email)

        Raises:
            MultiTenantAuthenticationError: If user not found or authentication fails
        """
        logger.info(f"[MULTI-TENANT-AUTH] Authentication attempt for: {username}")

        # Step 1: Find which tenant the user belongs to (optionally filtered by tenant_schema)
        user_info = MultiTenantAuthService.find_user_in_tenants(username, tenant_schema)

        if not user_info:
            logger.error(
                f"[MULTI-TENANT-AUTH] Authentication failed: User '{username}' not found "
                f"(tenant_schema filter: {tenant_schema or 'none - searched all tenants'})"
            )
            raise MultiTenantAuthenticationError(
                "No active account found with the given credentials"
            )

        schema_name = user_info["schema_name"]
        tenant_name = user_info["tenant_name"]

        logger.info(
            f"[MULTI-TENANT-AUTH] User found in tenant '{tenant_name}' (schema: {schema_name}), "
            f"proceeding with password verification"
        )

        # Step 2: Switch to tenant schema and authenticate
        try:
            # Get the tenant object and switch to it using django-tenants API
            # This is the CORRECT way to switch schemas - it persists across Django ORM calls
            tenant = Client.objects.get(schema_name=schema_name)
            connection.set_tenant(tenant)  # type: ignore[attr-defined]  # Added by django-tenants

            logger.debug(
                f"[MULTI-TENANT-AUTH] Switched to tenant schema '{schema_name}' "
                f"using connection.set_tenant()"
            )

            # Authenticate using Django's authentication system
            # This will check the password against the user in the current schema
            user = authenticate(username=user_info["username"], password=password)

            if user is None:
                # Try with email as username
                logger.debug(
                    f"[MULTI-TENANT-AUTH] First authentication attempt failed with username, "
                    f"trying with email: {user_info['email']}"
                )
                user = authenticate(username=user_info["email"], password=password)

            if user is None:
                logger.error(
                    f"[MULTI-TENANT-AUTH] Authentication failed: Invalid password for "
                    f"user '{username}' in tenant '{tenant_name}' (schema: {schema_name}). "
                    f"Both username and email authentication attempts failed."
                )

                # Additional diagnostic: check if user still exists and is active
                from django.contrib.auth import get_user_model

                User = get_user_model()
                try:
                    check_user = User.objects.get(email=user_info["email"])
                    logger.error(
                        f"[MULTI-TENANT-AUTH] User exists in DB: is_active={check_user.is_active}, "
                        f"has_usable_password={check_user.has_usable_password()}, "
                        f"password_hash_start={check_user.password[:30]}"
                    )
                except User.DoesNotExist:
                    logger.error("[MULTI-TENANT-AUTH] User no longer exists in schema!")

                raise MultiTenantAuthenticationError("Invalid credentials")

            if not user.is_active:
                logger.warning(
                    f"[MULTI-TENANT-AUTH] Authentication failed: User '{username}' is inactive "
                    f"in tenant '{tenant_name}'"
                )
                raise MultiTenantAuthenticationError("User account is disabled")

            logger.info(
                f"[MULTI-TENANT-AUTH] ✓ Authentication successful for user '{username}' "
                f"in tenant '{tenant_name}'"
            )

            # Step 3: Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            logger.info(f"[MULTI-TENANT-AUTH] JWT tokens generated for user '{username}'")

            # Step 4: Get tenant's primary domain (tenant object already retrieved above)
            try:
                primary_domain = tenant.domains.filter(is_primary=True).first()

                if not primary_domain:
                    # Fallback to any domain
                    primary_domain = tenant.domains.first()

                tenant_domain = primary_domain.domain if primary_domain else schema_name

            except Exception as e:
                logger.error(f"[MULTI-TENANT-AUTH] Error getting tenant domain: {e}", exc_info=True)
                tenant_domain = schema_name

            # Step 5: Return authentication response
            response_data = {
                "access": access_token,
                "refresh": refresh_token,
                "tenant_schema": schema_name,
                "tenant_name": tenant_name,
                "tenant_domain": tenant_domain,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            }

            logger.info(
                f"[MULTI-TENANT-AUTH] ✓ Authentication complete. "
                f"User '{username}' authenticated to tenant '{tenant_name}' "
                f"(domain: {tenant_domain})"
            )

            return response_data

        except MultiTenantAuthenticationError:
            raise
        except Exception as e:
            logger.error(
                f"[MULTI-TENANT-AUTH] Unexpected error during authentication: {e}", exc_info=True
            )
            raise MultiTenantAuthenticationError(f"Authentication error: {str(e)}") from e
        finally:
            # Reset to public schema
            try:
                public_tenant = Client.objects.get(schema_name="public")
                connection.set_tenant(public_tenant)  # type: ignore[attr-defined]  # Added by django-tenants
                logger.debug("[MULTI-TENANT-AUTH] Reset to public schema")
            except Exception as e:
                logger.warning(f"[MULTI-TENANT-AUTH] Failed to reset to public schema: {e}")
