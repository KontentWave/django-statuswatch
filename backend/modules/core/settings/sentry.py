"""Sentry configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def configure_sentry(env, *, default_environment: str = "production") -> Mapping[str, Any]:
    """Initialize Sentry based on environment variables and return config data."""

    dsn = env("SENTRY_DSN", default="")
    environment_override = env("SENTRY_ENVIRONMENT", default="")
    traces_sample_rate = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1)
    release = env("SENTRY_RELEASE", default=None)

    if not dsn:
        result = {
            "dsn": "",
            "traces_sample_rate": traces_sample_rate,
        }
        if environment_override:
            result["environment"] = environment_override
        return result

    import logging

    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    def _scrub_sentry_event(event, hint):
        if "request" in event:
            headers = event["request"].get("headers", {})
            for header in ["Authorization", "Cookie", "X-CSRF-Token"]:
                if header in headers:
                    headers[header] = "[Filtered]"

        if "contexts" in event and "runtime" in event["contexts"]:
            env_vars = event["contexts"]["runtime"].get("env", {})
            for key in [
                "SECRET_KEY",
                "DATABASE_URL",
                "REDIS_URL",
                "STRIPE_SECRET_KEY",
                "EMAIL_HOST_PASSWORD",
            ]:
                if key in env_vars:
                    env_vars[key] = "[Filtered]"

        return event

    def _traces_sampler(sampling_context):
        path = sampling_context.get("wsgi_environ", {}).get("PATH_INFO", "")
        if path.startswith("/health"):
            return 0.0
        return traces_sample_rate

    environment = environment_override or default_environment

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=0.1,
        integrations=[
            DjangoIntegration(transaction_style="url", middleware_spans=True, signals_spans=True),
            CeleryIntegration(monitor_beat_tasks=True, exclude_beat_tasks=[]),
            RedisIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        send_default_pii=False,
        attach_stacktrace=True,
        enable_tracing=True,
        traces_sampler=_traces_sampler,
        release=release,
        before_send=_scrub_sentry_event,
    )

    return {
        "dsn": dsn,
        "environment": environment,
        "traces_sample_rate": traces_sample_rate,
    }
