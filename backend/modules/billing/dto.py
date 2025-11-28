"""Billing DTOs that mirror the frontend client contracts."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any


def compact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Strip keys with ``None`` values to match existing API responses."""

    return {key: value for key, value in payload.items() if value is not None}


@dataclass(slots=True, frozen=True)
class BillingCheckoutResponseDto:
    """Response body for the checkout session endpoint."""

    url: str | None = None
    detail: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return compact_payload({"url": self.url, "detail": self.detail, "error": self.error})


@dataclass(slots=True, frozen=True)
class BillingPortalResponseDto:
    """Response body for the billing portal endpoint."""

    url: str | None = None
    detail: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return compact_payload({"url": self.url, "detail": self.detail, "error": self.error})


@dataclass(slots=True, frozen=True)
class BillingCancelResponseDto:
    """Response body for cancellation endpoint."""

    plan: str | None = None
    detail: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: MutableMapping[str, Any] = {
            "plan": self.plan,
            "detail": self.detail,
            "error": self.error,
        }
        return compact_payload(payload)


__all__ = [
    "BillingCancelResponseDto",
    "BillingCheckoutResponseDto",
    "BillingPortalResponseDto",
    "compact_payload",
]
