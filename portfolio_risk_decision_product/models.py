"""Immutable WP-015 portfolio and risk Decision profiles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from governed_queries import GovernedQueryResult


class DomainProfile(StrEnum):
    PORTFOLIO_RATIONALIZATION = "portfolio_rationalization"
    RISK_PRIORITY = "risk_priority"


class RationalizationDisposition(StrEnum):
    RETAIN = "retain"
    MODERNIZE = "modernize"
    CONSOLIDATE = "consolidate"
    RETIRE = "retire"
    INDETERMINATE = "indeterminate"


class RiskPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INDETERMINATE = "indeterminate"


class InputState(StrEnum):
    AVAILABLE = "available"
    STALE = "stale"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class DomainEvidenceReference:
    evidence_id: str
    organization_id: str
    tenant_id: str
    source_system: str
    source_identifier: str
    evidence_hash: str
    observed_at: datetime
    lineage_ref: str
    provenance_ref: str

    def __post_init__(self) -> None:
        _aware(self.observed_at, "evidence observation")
        if any(
            not str(item).strip()
            for item in (
                self.evidence_id,
                self.organization_id,
                self.tenant_id,
                self.source_system,
                self.source_identifier,
                self.evidence_hash,
                self.lineage_ref,
                self.provenance_ref,
            )
        ):
            raise ValueError("domain evidence requires identity, integrity, and traceability")


@dataclass(frozen=True, slots=True)
class LifecycleSignal:
    organization_id: str
    tenant_id: str
    entity_id: str
    entity_type: str
    lifecycle_state: str
    version: int
    observed_at: datetime
    state: InputState
    evidence: DomainEvidenceReference

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", InputState(self.state))
        _aware(self.observed_at, "lifecycle observation")
        if not self.entity_id or not self.entity_type or not self.lifecycle_state:
            raise ValueError("lifecycle identity, type, and state are required")
        if self.version < 1:
            raise ValueError("lifecycle version must be positive")


@dataclass(frozen=True, slots=True)
class RiskSignal:
    organization_id: str
    tenant_id: str
    entity_id: str
    risk_id: str
    likelihood: float
    impact: float
    observed_at: datetime
    state: InputState
    evidence: DomainEvidenceReference

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", InputState(self.state))
        _aware(self.observed_at, "risk observation")
        if not self.entity_id or not self.risk_id:
            raise ValueError("risk and entity identity are required")
        if not 0 <= self.likelihood <= 100 or not 0 <= self.impact <= 100:
            raise ValueError("risk likelihood and impact must be between zero and 100")

    @property
    def score(self) -> float:
        return round(self.likelihood * self.impact / 100, 2)


@dataclass(frozen=True, slots=True)
class ScenarioReference:
    scenario_id: str
    organization_id: str
    tenant_id: str
    engine: str
    version: str
    output_hash: str
    generated_at: datetime
    affected_entity_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    lineage_refs: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _aware(self.generated_at, "scenario generation")
        object.__setattr__(
            self, "affected_entity_ids", tuple(sorted(set(self.affected_entity_ids)))
        )
        object.__setattr__(self, "assumptions", tuple(sorted(set(self.assumptions))))
        if not self.scenario_id or not self.engine or not self.version or not self.output_hash:
            raise ValueError("scenario identity, engine version, and output hash are required")


@dataclass(frozen=True, slots=True)
class PortfolioRiskCase:
    case_id: str
    organization_id: str
    tenant_id: str
    version: int
    profile: DomainProfile
    recommendation_id: str
    recommendation_version: int
    decision_id: str
    decision_version: int
    policy_evaluation_id: str
    policy_id: str
    policy_version: int
    authority_type: str
    authority_id: str
    entity_id: str
    entity_type: str
    business_service_id: str
    posture_version: int
    lifecycle_state: str | None
    lifecycle_version: int | None
    rationalization: RationalizationDisposition | None
    risk_priority: RiskPriority | None
    risk_score: float | None
    projection_checkpoint: int
    projection_hash: str
    query_name: str
    query_paths: tuple[str, ...]
    query_partial: bool
    scenario_id: str | None
    scenario_hash: str | None
    evidence_ids: tuple[str, ...]
    lineage_refs: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    assumptions: tuple[str, ...]
    created_at: datetime
    case_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile", DomainProfile(self.profile))
        if self.rationalization is not None:
            object.__setattr__(
                self,
                "rationalization",
                RationalizationDisposition(self.rationalization),
            )
        if self.risk_priority is not None:
            object.__setattr__(self, "risk_priority", RiskPriority(self.risk_priority))
        for name in (
            "query_paths",
            "evidence_ids",
            "lineage_refs",
            "provenance_refs",
            "missing_inputs",
            "assumptions",
        ):
            object.__setattr__(self, name, tuple(sorted(set(getattr(self, name)))))
        _aware(self.created_at, "case creation")
        if self.version < 1 or not self.case_id or not self.case_hash:
            raise ValueError("portfolio/risk case identity, version, and hash are required")


def query_path_identities(result: GovernedQueryResult) -> tuple[str, ...]:
    return tuple(path.identity for path in result.paths)


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
