"""Persistence-neutral WP-009 query and disclosure results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class EvidenceState(StrEnum):
    AVAILABLE = "available"
    STALE = "stale"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class QueryLimits:
    max_depth: int = 3
    max_results: int = 50
    max_fan_out: int = 20
    work_budget: int = 500


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    subject_id: str
    organization_id: str
    tenant_id: str
    evidence_id: str | None
    observed_at: datetime | None
    state: EvidenceState
    source_system: str | None = None
    lineage_ref: str | None = None
    provenance_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", EvidenceState(self.state))
        if self.observed_at is not None and self.observed_at.tzinfo is None:
            raise ValueError("evidence observed_at must be timezone-aware")
        if self.state is EvidenceState.MISSING and self.evidence_id is not None:
            raise ValueError("missing evidence cannot fabricate an evidence id")


@dataclass(frozen=True, slots=True)
class QueryPath:
    entity_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]

    @property
    def identity(self) -> str:
        return "/".join(self.relationship_ids) or self.entity_ids[0]


@dataclass(frozen=True, slots=True)
class QueryMetadata:
    query_name: str
    organization_id: str
    tenant_id: str
    parameters: Mapping[str, Any]
    checkpoint_sequence: int
    projection_state_hash: str
    projection_time: datetime | None
    evaluated_at: datetime
    as_of: datetime | None
    work_budget: int
    work_consumed: int
    truncated: bool
    truncation_reason: str | None
    partial: bool
    partial_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "parameters", MappingProxyType(dict(sorted(self.parameters.items())))
        )


@dataclass(frozen=True, slots=True)
class GovernedQueryResult:
    metadata: QueryMetadata
    entity_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    entity_versions: Mapping[str, int]
    relationship_versions: Mapping[str, int]
    paths: tuple[QueryPath, ...]
    evidence: tuple[EvidenceReference, ...] = field(default_factory=tuple)
    inference: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "entity_versions",
            MappingProxyType(dict(sorted(self.entity_versions.items()))),
        )
        object.__setattr__(
            self,
            "relationship_versions",
            MappingProxyType(dict(sorted(self.relationship_versions.items()))),
        )
