from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from data_fabric.foundation import TenantContext


class ScenarioType(StrEnum):
    ACCOUNT_SUSPENSION = "ACCOUNT_SUSPENSION"
    APPLICATION_RETIREMENT = "APPLICATION_RETIREMENT"
    TECHNOLOGY_RETIREMENT = "TECHNOLOGY_RETIREMENT"
    VENDOR_FAILURE = "VENDOR_FAILURE"
    BUSINESS_SERVICE_DEGRADATION = "BUSINESS_SERVICE_DEGRADATION"
    COST_GROWTH = "COST_GROWTH"
    COST_REDUCTION = "COST_REDUCTION"
    OWNERSHIP_CHANGE = "OWNERSHIP_CHANGE"
    CLASSIFICATION_CHANGE = "CLASSIFICATION_CHANGE"
    RECOMMENDATION_ACCEPTANCE = "RECOMMENDATION_ACCEPTANCE"
    POLICY_CHANGE_PREVIEW = "POLICY_CHANGE_PREVIEW"


class TopologyState(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


def _mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class ScenarioRequest:
    tenant_context: TenantContext
    scenario_type: ScenarioType | str
    subject_canonical_id: str
    proposed_change: Mapping[str, Any] = field(default_factory=dict)
    temporal_context: str = "NOW"
    assumptions: Mapping[str, Any] = field(default_factory=dict)
    scope: str = "ENTITY"
    depth: int = 3
    financial_parameters: Mapping[str, Any] = field(default_factory=dict)
    policy_context: Mapping[str, Any] = field(default_factory=dict)
    include_business_impact: bool = True
    include_financial_impact: bool = True
    include_risk: bool = True
    include_dependencies: bool = True
    include_recommendations: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_context, TenantContext):
            raise TypeError("TenantContext is required")
        object.__setattr__(self, "scenario_type", ScenarioType(self.scenario_type))
        if not self.subject_canonical_id.strip():
            raise ValueError("subject canonical_id is required")
        if self.depth < 0 or self.depth > 5:
            raise ValueError("scenario depth must be between 0 and 5")
        if self.temporal_context.upper() not in {"NOW", "30_DAYS", "90_DAYS", "12_MONTHS"}:
            raise ValueError("unsupported temporal context")
        object.__setattr__(self, "proposed_change", _mapping(self.proposed_change))
        object.__setattr__(self, "assumptions", _mapping(self.assumptions))
        object.__setattr__(self, "financial_parameters", _mapping(self.financial_parameters))
        object.__setattr__(self, "policy_context", _mapping(self.policy_context))


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_id: str
    subject: Mapping[str, Any]
    baseline_state: Mapping[str, Any]
    simulated_state: Mapping[str, Any]
    changed_dimensions: tuple[str, ...]
    impacted_entities: tuple[Mapping[str, Any], ...]
    relationship_paths: tuple[Mapping[str, Any], ...]
    business_impact: Mapping[str, Any]
    financial_impact: Mapping[str, Any]
    operational_impact: Mapping[str, Any]
    risk_impact: Mapping[str, Any]
    governance_impact: Mapping[str, Any]
    assumptions: Mapping[str, Any]
    unknowns: tuple[str, ...]
    confidence: float
    evidence: tuple[str, ...]
    partial: bool
    partial_reasons: tuple[str, ...]
    topology_state: TopologyState
    generated_at: datetime
    policy_preview: Any = None
    authoritative: bool = False

    def __post_init__(self) -> None:
        if self.authoritative:
            raise ValueError("scenario results can never be authoritative")
        for name in (
            "subject",
            "baseline_state",
            "simulated_state",
            "business_impact",
            "financial_impact",
            "operational_impact",
            "risk_impact",
            "governance_impact",
            "assumptions",
        ):
            object.__setattr__(self, name, _mapping(getattr(self, name)))
        object.__setattr__(
            self, "impacted_entities", tuple(_mapping(x) for x in self.impacted_entities)
        )
        object.__setattr__(
            self, "relationship_paths", tuple(_mapping(x) for x in self.relationship_paths)
        )


@dataclass(frozen=True, slots=True)
class ScenarioComparison:
    comparison_id: str
    baseline: Mapping[str, Any]
    scenarios: tuple[ScenarioResult, ...]
    rows: tuple[Mapping[str, Any], ...]
    generated_at: datetime
    authoritative: bool = False
