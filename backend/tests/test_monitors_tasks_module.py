"""Regression tests for the legacy `monitors.tasks` re-export module."""

from __future__ import annotations

import requests
from modules.monitoring.scheduler import _is_endpoint_due as scheduler_is_endpoint_due


def test_monitors_tasks_exposes_requests_module():
    """`monitors.tasks.requests` remains patchable for legacy tests/callers."""

    import monitors.tasks as legacy_tasks

    assert legacy_tasks.requests is requests


def test_monitors_tasks_exposes_is_endpoint_due_helper():
    """`monitors.tasks._is_endpoint_due` points at the scheduler helper."""

    import monitors.tasks as legacy_tasks

    assert legacy_tasks._is_endpoint_due is scheduler_is_endpoint_due
