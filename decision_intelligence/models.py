from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping


class FindingType(StrEnum):
    COST = "cost"
    OWNERSHIP = "ownership"
    CLASSIFICATION = "classification"
    RISK = "risk"
    DEPENDENCY = "dependency"
    GOVERNANCE = "governance"
    HEALTH = "health"
    PORTFOLIO = "portfolio"
    OPTIMIZATION = "optimization"
    DATA_QUALITY = "data_quality"


@dataclass(frozen=True, slots=True)
class PriorityBreakdown:
    business_criticality: float
    financial_exposure: float
    risk_severity: float
    confidence: float
    evidence_quality: float
    freshness: float
    governance_urgency: float
    blast_radius: float
    time_sensitivity: float

    @property
    def score(self):
        values = tuple(getattr(self, name) for name in self.__dataclass_fields__)
        return round(sum(values) / len(values), 4)


@dataclass(frozen=True, slots=True)
class IntelligenceFinding:
    finding_id: str
    organization_id: str
    tenant_id: str
    subject_canonical_id: str
    finding_type: FindingType
    title: str
    description: str
    severity: str
    priority: PriorityBreakdown
    facts: tuple[Mapping[str, Any], ...]
    derived_findings: tuple[Mapping[str, Any], ...]
    confidence: float
    financial_exposure: float
    risk_exposure: float
    business_impact: Mapping[str, Any]
    evidence_references: tuple[str, ...]
    lineage: Any
    provenance: Any
    freshness: str
    query_reference: str
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class RecommendationProposal:
    finding: IntelligenceFinding
    proposed_action: str
    expected_outcome: str
    alternatives: tuple[Mapping[str, Any], ...]
    limitations: tuple[str, ...]
    potential_savings: float
    approved_savings: float = 0
    executed_savings: float = 0
    verified_realized_savings: float = 0
