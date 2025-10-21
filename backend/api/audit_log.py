"""
Business audit logging for StatusWatch.

Logs critical business events for compliance, security, and analytics.
"""

import logging
from enum import Enum
from typing import Any

audit_logger = logging.getLogger("api.audit")


class AuditEvent(Enum):
    """
    Enumeration of auditable business events.

    These events are logged for:
    - Security audits
    - Compliance requirements
    - Business analytics
    - User activity tracking
    """

    # Authentication events
    USER_REGISTERED = "user_registered"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_LOGIN_FAILED = "user_login_failed"

    # Email events
    EMAIL_VERIFIED = "email_verified"
    EMAIL_VERIFICATION_SENT = "email_verification_sent"

    # Account management
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"

    # Tenant events
    TENANT_CREATED = "tenant_created"
    TENANT_UPDATED = "tenant_updated"
    TENANT_DELETED = "tenant_deleted"

    # Payment events
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_FAILED = "payment_failed"
    SUBSCRIPTION_CREATED = "subscription_created"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"

    # Permission events
    USER_ROLE_CHANGED = "user_role_changed"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"

    # Data access events (for GDPR compliance)
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"
    DATA_ACCESS_REQUESTED = "data_access_requested"


def log_audit_event(
    event: AuditEvent,
    user_id: int | None = None,
    user_email: str | None = None,
    tenant_schema: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    success: bool = True,
) -> None:
    """
    Log a business-critical audit event.

    Args:
        event: The type of event from AuditEvent enum
        user_id: ID of the user who triggered the event
        user_email: Email of the user who triggered the event
        tenant_schema: Schema name of the tenant
        ip_address: IP address of the client
        user_agent: User agent string of the client
        details: Additional event-specific data (primary parameter)
        metadata: Alternative name for details (for backwards compatibility)
        success: Whether the event was successful

    Example:
        log_audit_event(
            AuditEvent.USER_REGISTERED,
            user_id=user.id,
            user_email=user.email,
            tenant_schema=tenant.schema_name,
            ip_address=request.META.get('REMOTE_ADDR'),
            details={'organization': tenant.name}
        )
    """
    # Use details if provided, otherwise fall back to metadata
    event_data = details or metadata or {}

    audit_logger.info(
        f"Audit: {event.value}",
        extra={
            "audit_event": event.value,
            "audit_category": _get_event_category(event),
            "audit_user_id": user_id,
            "audit_user_email": user_email,
            "audit_tenant": tenant_schema,
            "audit_ip": ip_address,
            "audit_user_agent": user_agent,
            "audit_details": event_data,
            "audit_success": success,
        },
    )


def _get_event_category(event: AuditEvent) -> str:
    """
    Categorize events for easier filtering and analysis.

    Args:
        event: The audit event

    Returns:
        Category name (authentication, account, tenant, payment, permission, data)
    """
    auth_events = {
        AuditEvent.USER_REGISTERED,
        AuditEvent.USER_LOGIN,
        AuditEvent.USER_LOGOUT,
        AuditEvent.USER_LOGIN_FAILED,
    }

    account_events = {
        AuditEvent.EMAIL_VERIFIED,
        AuditEvent.EMAIL_VERIFICATION_SENT,
        AuditEvent.PASSWORD_CHANGED,
        AuditEvent.PASSWORD_RESET_REQUESTED,
        AuditEvent.PASSWORD_RESET_COMPLETED,
        AuditEvent.ACCOUNT_LOCKED,
        AuditEvent.ACCOUNT_UNLOCKED,
    }

    tenant_events = {
        AuditEvent.TENANT_CREATED,
        AuditEvent.TENANT_UPDATED,
        AuditEvent.TENANT_DELETED,
    }

    payment_events = {
        AuditEvent.PAYMENT_INITIATED,
        AuditEvent.PAYMENT_SUCCEEDED,
        AuditEvent.PAYMENT_FAILED,
        AuditEvent.SUBSCRIPTION_CREATED,
        AuditEvent.SUBSCRIPTION_CANCELLED,
    }

    permission_events = {
        AuditEvent.USER_ROLE_CHANGED,
        AuditEvent.PERMISSION_GRANTED,
        AuditEvent.PERMISSION_REVOKED,
    }

    data_events = {
        AuditEvent.DATA_EXPORTED,
        AuditEvent.DATA_DELETED,
        AuditEvent.DATA_ACCESS_REQUESTED,
    }

    if event in auth_events:
        return "authentication"
    elif event in account_events:
        return "account"
    elif event in tenant_events:
        return "tenant"
    elif event in payment_events:
        return "payment"
    elif event in permission_events:
        return "permission"
    elif event in data_events:
        return "data"
    else:
        return "other"
