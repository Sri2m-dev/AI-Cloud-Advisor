from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class ReviewState(StrEnum):
    DISCOVERED = "discovered"
    CLASSIFIED = "classified"
    UNDER_REVIEW = "under_review"
    STEWARD_APPROVED = "steward_approved"
    CANONICAL = "canonical"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class AuthorityRule:
    organization_id: str
    tenant_id: str
    domain: str
    subject: str
    source_system: str
    steward_role: str
    effective_from: datetime
    effective_to: datetime | None = None
    priority: int = 0

    def applies(self, at: datetime) -> bool:
        return self.effective_from <= at and (self.effective_to is None or at < self.effective_to)


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    organization_id: str
    tenant_id: str
    domain: str
    expected_refresh: timedelta
    warning_after: timedelta
    stale_after: timedelta
    escalation_after: timedelta

    def __post_init__(self):
        if not (
            self.expected_refresh <= self.warning_after <= self.stale_after <= self.escalation_after
        ):
            raise ValueError("freshness thresholds must be monotonic")

    def status(self, observed_at: datetime | None, now: datetime) -> str:
        if observed_at is None:
            return "unknown"
        age = now - observed_at
        return (
            "escalated"
            if age >= self.escalation_after
            else "stale"
            if age >= self.stale_after
            else "warning"
            if age >= self.warning_after
            else "fresh"
        )


@dataclass(frozen=True, slots=True)
class ReviewItem:
    review_id: str
    organization_id: str
    tenant_id: str
    review_key: str
    review_type: str
    domain: str
    subject_type: str
    subject_id: str
    state: ReviewState = ReviewState.DISCOVERED
    revision: int = 1
    payload_hash: str = ""
    evidence_references: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True, slots=True)
class CoverageResult:
    organization_id: str
    tenant_id: str
    domain: str
    eligible: int
    covered: int
    excluded: int
    unresolved: int
    missing_source: int
    freshness: Mapping[str, int]
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def percentage(self) -> float:
        return round((self.covered / self.eligible * 100) if self.eligible else 0.0, 2)
