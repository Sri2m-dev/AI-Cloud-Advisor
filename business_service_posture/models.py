"""Versioned, dimensional Business Service posture contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class PostureDimension(StrEnum):
    COST = "cost"
    RISK = "risk"
    HEALTH = "health"


class PostureAvailability(StrEnum):
    AVAILABLE = "available"
    STALE = "stale"
    MISSING = "missing"


REQUIRED_POSTURE_DIMENSIONS = tuple(PostureDimension)


@dataclass(frozen=True, slots=True)
class PostureSignal:
    """One tenant-owned domain input with source and evidence attribution."""

    dimension: PostureDimension
    organization_id: str
    tenant_id: str
    source_system: str
    observed_at: datetime
    score: float
    value: Mapping[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension", PostureDimension(self.dimension))
        object.__setattr__(self, "value", MappingProxyType(dict(self.value)))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not 0.0 <= float(self.score) <= 100.0:
            raise ValueError("score must be between 0 and 100")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not self.source_system.strip():
            raise ValueError("source_system is required")


@dataclass(frozen=True, slots=True)
class PostureDimensionResult:
    """One visible posture dimension, including stale or missing state."""

    dimension: PostureDimension
    availability: PostureAvailability
    score: float | None
    source_system: str | None
    observed_at: datetime | None
    age_seconds: int | None
    evidence_ids: tuple[str, ...]
    value: Mapping[str, Any]
    confidence: float | None
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension", PostureDimension(self.dimension))
        object.__setattr__(
            self,
            "availability",
            PostureAvailability(self.availability),
        )
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        object.__setattr__(self, "value", MappingProxyType(dict(self.value)))
        if self.availability is PostureAvailability.MISSING and self.score is not None:
            raise ValueError("missing posture cannot expose a synthetic score")


@dataclass(frozen=True, slots=True)
class BusinessServicePosture:
    """Immutable version of the dimensional service-posture data product."""

    organization_id: str
    tenant_id: str
    business_service_id: str
    business_service_version: int
    posture_version: int
    generated_at: datetime
    dimensions: Mapping[PostureDimension, PostureDimensionResult]

    def __post_init__(self) -> None:
        normalized = {
            PostureDimension(key): value for key, value in self.dimensions.items()
        }
        missing = set(REQUIRED_POSTURE_DIMENSIONS) - set(normalized)
        if missing:
            raise ValueError(
                "posture must expose every required dimension: "
                + ", ".join(sorted(item.value for item in missing))
            )
        object.__setattr__(self, "dimensions", MappingProxyType(normalized))
        if self.posture_version < 1:
            raise ValueError("posture_version must be positive")

    @property
    def completeness(self) -> float:
        available = sum(
            result.availability is not PostureAvailability.MISSING
            for result in self.dimensions.values()
        )
        return round(available / len(REQUIRED_POSTURE_DIMENSIONS), 4)

    @property
    def has_stale_data(self) -> bool:
        return any(
            result.availability is PostureAvailability.STALE
            for result in self.dimensions.values()
        )

    @property
    def missing_dimensions(self) -> tuple[PostureDimension, ...]:
        return tuple(
            dimension
            for dimension in REQUIRED_POSTURE_DIMENSIONS
            if self.dimensions[dimension].availability is PostureAvailability.MISSING
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
