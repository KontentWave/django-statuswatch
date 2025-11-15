"""Monitoring DTOs shared between legacy DRF viewsets and upcoming modules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from django.utils import timezone
from monitors.models import Endpoint
from monitors.serializers import EndpointSerializer

DateTimeLike = datetime | None


def _format_datetime(value: DateTimeLike) -> str | None:
    """Serialize datetimes to ISO8601 strings compatible with DRF output."""

    if value is None:
        return None

    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


@dataclass(slots=True, frozen=True)
class EndpointDto:
    """Public API representation of an endpoint monitor."""

    id: UUID
    tenant: int | None
    tenant_name: str | None
    name: str
    url: str
    interval_minutes: int
    last_status: str
    last_checked_at: DateTimeLike
    last_latency_ms: float | None
    last_enqueued_at: DateTimeLike
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant": self.tenant,
            "tenant_name": self.tenant_name,
            "name": self.name,
            "url": self.url,
            "interval_minutes": self.interval_minutes,
            "last_status": self.last_status,
            "last_checked_at": _format_datetime(self.last_checked_at),
            "last_latency_ms": self.last_latency_ms,
            "last_enqueued_at": _format_datetime(self.last_enqueued_at),
            "created_at": _format_datetime(self.created_at),
            "updated_at": _format_datetime(self.updated_at),
        }

    @classmethod
    def from_model(cls, endpoint: Endpoint) -> EndpointDto:
        return cls(
            id=endpoint.id,
            tenant=getattr(endpoint, "tenant_id", None),
            tenant_name=getattr(getattr(endpoint, "tenant", None), "name", None),
            name=endpoint.name,
            url=endpoint.url,
            interval_minutes=endpoint.interval_minutes,
            last_status=endpoint.last_status,
            last_checked_at=endpoint.last_checked_at,
            last_latency_ms=endpoint.last_latency_ms,
            last_enqueued_at=endpoint.last_enqueued_at,
            created_at=endpoint.created_at,
            updated_at=endpoint.updated_at,
        )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> EndpointDto:
        return cls(
            id=UUID(str(payload["id"])),
            tenant=_parse_int(payload.get("tenant")),
            tenant_name=str(payload.get("tenant_name")) if payload.get("tenant_name") else None,
            name=str(payload.get("name", "")),
            url=str(payload.get("url", "")),
            interval_minutes=int(payload.get("interval_minutes", 0)),
            last_status=str(payload.get("last_status", "")),
            last_checked_at=_parse_datetime(payload.get("last_checked_at")),
            last_latency_ms=(
                float(payload["last_latency_ms"])
                if payload.get("last_latency_ms") is not None
                else None
            ),
            last_enqueued_at=_parse_datetime(payload.get("last_enqueued_at")),
            created_at=_parse_datetime(payload.get("created_at")) or timezone.now(),
            updated_at=_parse_datetime(payload.get("updated_at")) or timezone.now(),
        )


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True, frozen=True)
class EndpointListResponseDto:
    """Paginated endpoint response matching the frontend contract."""

    count: int
    next: str | None
    previous: str | None
    results: Sequence[EndpointDto]

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "next": self.next,
            "previous": self.previous,
            "results": [endpoint.to_dict() for endpoint in self.results],
        }


@dataclass(slots=True, frozen=True)
class CreateEndpointPayload:
    """Input payload for endpoint creation aligning with REST API fields."""

    url: str
    interval_minutes: int
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: MutableMapping[str, Any] = {
            "url": self.url,
            "interval_minutes": self.interval_minutes,
        }
        if self.name is not None:
            payload["name"] = self.name
        return dict(payload)


@dataclass(slots=True, frozen=True)
class DeleteEndpointResult:
    """Successful deletion response body."""

    endpoint_id: UUID

    def to_dict(self) -> dict[str, Any]:
        return {"endpointId": str(self.endpoint_id)}


def endpoint_to_dto(endpoint: Endpoint) -> EndpointDto:
    """Small helper used by services/tests to convert ORM objects to DTOs."""

    return EndpointDto.from_model(endpoint)


def build_endpoint_serializer(
    *,
    data: Mapping[str, Any] | None = None,
    instance: Endpoint | None = None,
    partial: bool = False,
) -> EndpointSerializer:
    """Return a DRF serializer instance so modules can reuse validation rules."""

    serializer = EndpointSerializer(instance=instance, data=data, partial=partial)
    if data is not None:
        serializer.is_valid(raise_exception=True)
    return serializer


def build_list_dto(
    *,
    count: int,
    next_url: str | None,
    previous_url: str | None,
    endpoints: Iterable[Endpoint],
) -> EndpointListResponseDto:
    """Create a paginated DTO directly from ORM endpoints."""

    return EndpointListResponseDto(
        count=count,
        next=next_url,
        previous=previous_url,
        results=tuple(endpoint_to_dto(endpoint) for endpoint in endpoints),
    )


__all__ = [
    "CreateEndpointPayload",
    "DeleteEndpointResult",
    "EndpointDto",
    "EndpointListResponseDto",
    "build_endpoint_serializer",
    "build_list_dto",
    "endpoint_to_dto",
]
