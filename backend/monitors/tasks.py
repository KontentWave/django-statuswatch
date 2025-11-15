"""Legacy task module re-exporting the new modular implementations."""

import requests as _requests
from modules.monitoring.scheduler import PENDING_REQUEUE_GRACE, _is_endpoint_due  # noqa: F401
from modules.monitoring.tasks import (  # noqa: F401
    notify_endpoint_failure,
    ping_endpoint,
    schedule_endpoint_checks,
)

# Preserve historic attribute access used by tests and legacy callers.
requests = _requests

__all__ = [
    "PENDING_REQUEUE_GRACE",
    "notify_endpoint_failure",
    "ping_endpoint",
    "schedule_endpoint_checks",
    "requests",
    "_is_endpoint_due",
]
