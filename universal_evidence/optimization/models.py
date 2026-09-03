from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any


class OpportunityType(str, Enum):
    IDLE_COMPUTE = "IDLE_COMPUTE"
    RIGHTSIZE_COMPUTE = "RIGHTSIZE_COMPUTE"
    UNATTACHED_STORAGE = "UNATTACHED_STORAGE"
    UNUSED_LICENSE = "UNUSED_LICENSE"
    LOW_UTILIZATION_LICENSE = "LOW_UTILIZATION_LICENSE"
    DUPLICATE_APPLICATION = "DUPLICATE_APPLICATION"


class OpportunityState(str, Enum):
    DETECTED = "DETECTED"
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"
    PROPOSED = "PROPOSED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    IMPLEMENTING = "IMPLEMENTING"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFYING = "VERIFYING"
    REALIZED = "REALIZED"
    PARTIALLY_REALIZED = "PARTIALLY_REALIZED"
    NOT_REALIZED = "NOT_REALIZED"
    SUPERSEDED = "SUPERSEDED"


class EligibilityResult(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EvidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class OverlapRelationship(str, Enum):
    MUTUALLY_EXCLUSIVE = "MUTUALLY_EXCLUSIVE"
    OVERLAPPING = "OVERLAPPING"
    COMPLEMENTARY = "COMPLEMENTARY"
    INDEPENDENT = "INDEPENDENT"


class RealizationState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    VERIFYING = "VERIFYING"
    REALIZED = "REALIZED"
    PARTIALLY_REALIZED = "PARTIALLY_REALIZED"
    NOT_REALIZED = "NOT_REALIZED"


@dataclass(frozen=True, slots=True)
class OptimizationEvidence:
    opportunity_type: OpportunityType
    organization_id: str
    tenant_id: str
    prospect_id: str
    analysis_id: str
    affected_entity: str
    affected_entity_type: str
    evidence_fingerprints: tuple[str, ...]
    evidence_references: tuple[str, ...]
    lineage: tuple[str, ...]
    provenance: tuple[str, ...]
    current_cost: Decimal | None
    cost_period: str | None
    currency: str | None
    currency_authority: str | None
    financial_observation_ids: tuple[str, ...]
    signals: tuple[tuple[str, Any], ...]
    source_authority: float = 1.0
    owner: str | None = None
    business_context: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "opportunity_type", OpportunityType(self.opportunity_type))
        if not self.organization_id or not self.tenant_id or not self.analysis_id:
            raise ValueError("organization, tenant, and analysis scope are required")
        if not self.affected_entity or not self.evidence_fingerprints:
            raise ValueError("entity and evidence fingerprints are required")

    @property
    def signal_map(self) -> dict[str, Any]:
        return dict(self.signals)


@dataclass(frozen=True, slots=True)
class OptimizationOpportunity:
    opportunity_id: str
    version: int
    opportunity_type: OpportunityType
    state: OpportunityState
    tenant_id: str
    organization_id: str
    prospect_id: str
    analysis_id: str
    evidence_fingerprints: tuple[str, ...]
    affected_entity: str
    affected_entity_type: str
    current_cost: Decimal | None
    cost_period: str | None
    currency: str | None
    currency_authority: str | None
    potential_savings: Decimal | None
    savings_percentage: Decimal | None
    eligibility_result: EligibilityResult
    eligibility_reason_codes: tuple[str, ...]
    detection_signals: tuple[tuple[str, Any], ...]
    calculation_model: str | None
    calculation_model_version: str | None
    calculation_inputs: tuple[tuple[str, Any], ...]
    calculation_assumptions: tuple[str, ...]
    evidence_references: tuple[str, ...]
    lineage: tuple[str, ...]
    provenance: tuple[str, ...]
    confidence_score: float
    confidence_band: EvidenceLevel
    confidence_factors: tuple[tuple[str, float], ...]
    technical_risk: EvidenceLevel
    business_risk: EvidenceLevel
    effort: EvidenceLevel
    recommendation: str
    alternatives: tuple[str, ...]
    owner: str | None
    business_context: str | None
    created_at: str
    updated_at: str
    governance_state: OpportunityState
    superseded_by: str | None
    realization_state: RealizationState
    realized_savings: Decimal | None
    realization_evidence: tuple[str, ...]
    fingerprint: str
    cost_basis_id: str


@dataclass(frozen=True, slots=True)
class OpportunityTransition:
    event_id: str
    opportunity_id: str
    version: int
    from_state: OpportunityState
    to_state: OpportunityState
    actor_id: str
    actor_role: str
    reason: str
    occurred_at: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class PortfolioSavings:
    totals_by_currency: tuple[tuple[str, Decimal], ...]
    selected_opportunity_ids: tuple[str, ...]
    excluded_overlap_ids: tuple[str, ...]
