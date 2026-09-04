from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4

from data_fabric.foundation import TenantContext


class QueryType(str, Enum):
    ENTERPRISE_CONTEXT = "enterprise_context"
    EXPLAIN = "explain"
    DEPENDENCIES = "dependencies"
    DEPENDENTS = "dependents"
    BUSINESS_IMPACT = "business_impact"
    FINANCIAL_IMPACT = "financial_impact"
    OWNERSHIP = "ownership"
    TECHNOLOGY = "technology"
    APPLICATION = "application"
    SERVICE = "service"
    RISK = "risk"
    HEALTH = "health"
    GOVERNANCE = "governance"
    CHANGE_IMPACT = "change_impact"


class DimensionState(str, Enum):
    AVAILABLE = "AVAILABLE"
    STALE = "STALE"
    MISSING = "MISSING"
    UNSUPPORTED = "UNSUPPORTED"


class AvailabilityState(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    QUARANTINED = "QUARANTINED"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class ReconciliationState(str, Enum):
    RECONCILED = "RECONCILED"
    PARTIAL = "PARTIAL"
    NOT_RECONCILABLE = "NOT_RECONCILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class IntelligencePeriod:
    start: date | None = None
    end: date | None = None
    label: str | None = None


@dataclass(frozen=True, slots=True)
class IntelligenceBreakdown:
    key: str
    label: str
    value: Decimal | int | float | str | None
    availability: AvailabilityState = AvailabilityState.AVAILABLE
    entity_ids: tuple[str, ...] = ()
    observation_ids: tuple[str, ...] = ()
    opportunity_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IntelligenceResult:
    """A deterministic, non-persisted projection of canonical authorities."""

    tenant_id: str
    organization_id: str
    scope: str
    query_family: str
    period: IntelligencePeriod
    availability: AvailabilityState
    value: Any = None
    currency: str | None = None
    unit: str | None = None
    breakdown: tuple[IntelligenceBreakdown, ...] = ()
    contributing_observation_ids: tuple[str, ...] = ()
    contributing_opportunity_ids: tuple[str, ...] = ()
    contributing_entity_ids: tuple[str, ...] = ()
    coverage: Decimal | None = None
    reconciliation: ReconciliationState = ReconciliationState.NOT_APPLICABLE
    freshness: str | None = None
    conflicts: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    explanation_references: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    fingerprint: str = ""
    authority: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    current: IntelligenceResult
    comparison: IntelligenceResult
    availability: AvailabilityState
    absolute_change: Decimal | None
    percentage_change: Decimal | None
    reason_codes: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class QueryLimits:
    max_depth: int = 5
    max_results: int = 100
    max_fan_out: int = 50
    max_work: int = 1000
    timeout_ms: int = 2000


@dataclass(frozen=True, slots=True)
class QueryRequest:
    tenant_context: TenantContext
    query_type: QueryType | str
    entity_reference: str | None = None
    filters: Mapping[str, Any] = field(default_factory=dict)
    temporal_context: Mapping[str, Any] = field(default_factory=dict)
    depth: int = 3
    result_limit: int = 100
    include_evidence: bool = True
    include_financial: bool = True
    include_classification: bool = True
    include_risk: bool = True
    include_health: bool = True

    def __post_init__(self):
        object.__setattr__(self, "query_type", QueryType(self.query_type))


@dataclass(frozen=True, slots=True)
class ExplainedValue:
    kind: str
    name: str
    value: Any
    source: str
    confidence: float | None = None
    evidence: tuple[str, ...] = ()
    freshness: str = "UNKNOWN"
    version_reference: str | None = None


@dataclass(frozen=True, slots=True)
class ContextDimension:
    name: str
    state: DimensionState
    values: Mapping[str, Any] = field(default_factory=dict)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class EnterpriseContext:
    identity: ContextDimension
    business: ContextDimension
    technology: ContextDimension
    financial: ContextDimension
    classification: ContextDimension
    operations: ContextDimension
    risk: ContextDimension
    governance: ContextDimension


@dataclass(frozen=True, slots=True)
class QueryResponse:
    query_id: str
    tenant_id: str
    query_type: QueryType
    subject: Mapping[str, Any]
    facts: tuple[ExplainedValue, ...]
    derived_findings: tuple[ExplainedValue, ...]
    paths: tuple[Any, ...]
    context: EnterpriseContext | None
    evidence: tuple[Any, ...]
    lineage: Any
    provenance: Any
    confidence: float | None
    freshness: str
    partial: bool
    partial_reasons: tuple[str, ...]
    checkpoint_references: tuple[str, ...]
    generated_at: datetime
    narrative: str

    @staticmethod
    def identifier():
        return str(uuid4())

    @staticmethod
    def now():
        return datetime.now(timezone.utc)
