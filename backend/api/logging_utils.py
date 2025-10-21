"""Utilities for keeping log output free of secrets."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# Common patterns for secrets we never want written to disk.
_PATTERNS = (
    # Stripe API keys (sk_* and pk_* variants)
    (re.compile(r"(sk|pk)_(test|live)_[A-Za-z0-9]+"), "[REDACTED_STRIPE_KEY]"),
    # Database / cache connection strings
    (
        re.compile(r"(?i)(?:postgres(?:ql)?|mysql|redis|mongodb|amqp)://[^\s]+"),
        "[REDACTED_DSN]",
    ),
    # Bearer tokens / JWTs that may slip into error messages
    (
        re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+"),
        "Bearer [REDACTED_TOKEN]",
    ),
)


def _sanitize_str(value: str) -> str:
    sanitized = value
    for pattern, replacement in _PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def sanitize_log_value(value: Any) -> Any:
    """Recursively sanitize log payloads before writing to disk."""
    if isinstance(value, str):
        return _sanitize_str(value)

    if isinstance(value, Mapping):
        return {k: sanitize_log_value(v) for k, v in value.items()}

    if isinstance(value, list):
        return [sanitize_log_value(item) for item in value]

    if isinstance(value, tuple):
        return tuple(sanitize_log_value(item) for item in value)

    if isinstance(value, set):
        return {sanitize_log_value(item) for item in value}

    # ErrorDetail and similar types stringify cleanly.
    return value
