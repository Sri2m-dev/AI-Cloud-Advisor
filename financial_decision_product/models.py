"""Immutable WP-014 financial decision product contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping

from data_fabric.versioning.models import freeze_value


class ForecastAvailability(StrEnum):
    AVAILABLE = "forecast_available"
    STALE = "forecast_stale"
    MISSING = "forecast_missing"


class ReconciliationState(StrEnum):
    MATCHED = "matched"
    PARTIAL = "partial"
    UNRECONCILED = "unreconciled"


class SavingsState(StrEnum):
    REALIZED = "realized"
    NOT_REALIZED = "not_realized"
    INDETERMINATE = "indeterminate"


class RecordState(StrEnum):
    CURRENT = "current"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class FinancialEvidenceReference:
    evidence_id: str
    organization_id: str
    tenant_id: str
    source_system: str
    source_identifier: str
    evidence_hash: str
    lineage_ref: str
    provenance_ref: str

    def __post_init__(self) -> None:
        if any(
            not str(value).strip()
            for value in (
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
            raise ValueError("financial evidence requires governed identity and traceability")


@dataclass(frozen=True, slots=True)
class CostRecord:
    cost_id: str
    organization_id: str
    tenant_id: str
    business_service_id: str
    resource_id: str
    amount: float
    currency: str
    period_start: datetime
    period_end: datetime
    evidence: FinancialEvidenceReference

    def __post_init__(self) -> None:
        _period(self.period_start, self.period_end)
        if not self.cost_id or not self.business_service_id or not self.resource_id:
            raise ValueError("cost identity, service, and resource are required")
        if self.amount < 0:
            raise ValueError("cost amount cannot be negative")
        if not self.currency.strip():
            raise ValueError("cost currency is required")


@dataclass(frozen=True, slots=True)
class AllocationResult:
    allocation_id: str
    organization_id: str
    tenant_id: str
    business_service_id: str
    cost_id: str
    allocated_amount: float
    currency: str
    period_start: datetime
    period_end: datetime
    basis: str
    evidence: FinancialEvidenceReference

    def __post_init__(self) -> None:
        _period(self.period_start, self.period_end)
        if not self.allocation_id or not self.business_service_id or not self.cost_id:
            raise ValueError("allocation identity, service, and cost reference are required")
        if self.allocated_amount < 0:
            raise ValueError("allocated amount cannot be negative")
        if not self.currency.strip() or not self.basis.strip():
            raise ValueError("allocation currency and basis are required")


@dataclass(frozen=True, slots=True)
class ForecastRecord:
    forecast_id: str
    organization_id: str
    tenant_id: str
    business_service_id: str
    availability: ForecastAvailability
    projected_cost: float | None
    currency: str
    input_period_start: datetime
    input_period_end: datetime
    forecast_period_start: datetime
    forecast_period_end: datetime
    model: str
    version: str
    generated_at: datetime
    confidence: float | None
    quality: Mapping[str, Any]
    evidence: FinancialEvidenceReference

    def __post_init__(self) -> None:
        object.__setattr__(self, "availability", ForecastAvailability(self.availability))
        object.__setattr__(self, "quality", freeze_value(self.quality))
        _period(self.input_period_start, self.input_period_end)
        _period(self.forecast_period_start, self.forecast_period_end)
        _aware(self.generated_at, "forecast generation")
        if not self.forecast_id or not self.business_service_id:
            raise ValueError("forecast identity and business service are required")
        if not self.model or not self.version or not self.currency:
            raise ValueError("forecast model, version, and currency are required")
        if self.projected_cost is not None and self.projected_cost < 0:
            raise ValueError("projected cost cannot be negative")
        if self.availability is ForecastAvailability.MISSING and self.projected_cost is not None:
            raise ValueError("missing forecast cannot expose projected cost")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("forecast confidence must be between zero and one")


@dataclass(frozen=True, slots=True)
class FinancialAlternative:
    alternative_id: str
    organization_id: str
    tenant_id: str
    decision_id: str
    decision_version: int
    recommendation_id: str
    recommendation_version: int
    business_service_id: str
    resource_id: str
    baseline_cost: float | None
    projected_cost: float | None
    projected_savings: float | None
    forecast_horizon: str | None
    assumptions: tuple[str, ...]
    cost_evidence_id: str | None
    allocation_basis: str | None
    forecast_id: str | None
    forecast_version: str | None
    forecast_availability: ForecastAvailability
    currency: str | None
    effective_period_start: datetime | None
    effective_period_end: datetime | None
    lineage_refs: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    alternative_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "forecast_availability",
            ForecastAvailability(self.forecast_availability),
        )
        object.__setattr__(self, "assumptions", tuple(sorted(set(self.assumptions))))
        object.__setattr__(self, "lineage_refs", tuple(sorted(set(self.lineage_refs))))
        object.__setattr__(self, "provenance_refs", tuple(sorted(set(self.provenance_refs))))
        object.__setattr__(self, "missing_inputs", tuple(sorted(set(self.missing_inputs))))
        if not self.alternative_id or not self.alternative_hash:
            raise ValueError("financial alternative identity and hash are required")


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    reconciliation_id: str
    organization_id: str
    tenant_id: str
    business_service_id: str
    baseline_cost_id: str | None
    actual_cost_id: str | None
    allocation_id: str | None
    state: ReconciliationState
    baseline_amount: float | None
    actual_amount: float | None
    allocated_amount: float | None
    unmatched_amount: float | None
    currency: str | None
    reasons: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    reconciliation_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", ReconciliationState(self.state))
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        if not self.reconciliation_id or not self.reasons or not self.reconciliation_hash:
            raise ValueError("reconciliation identity, reason, and hash are required")


@dataclass(frozen=True, slots=True)
class RealizedSavings:
    savings_id: str
    organization_id: str
    tenant_id: str
    version: int
    state: SavingsState
    record_state: RecordState
    business_service_id: str
    decision_id: str
    decision_version: int
    recommendation_id: str
    recommendation_version: int
    alternative_id: str
    reconciliation_id: str
    plan_id: str | None
    plan_hash: str | None
    evaluation_id: str | None
    authority_type: str | None
    authority_id: str | None
    execution_id: str | None
    verification_id: str | None
    verification_hash: str | None
    baseline_cost_id: str | None
    actual_cost_id: str | None
    amount: float | None
    currency: str | None
    period_start: datetime | None
    period_end: datetime | None
    reasons: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    lineage_refs: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    supersedes_savings_id: str | None
    recorded_at: datetime
    savings_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", SavingsState(self.state))
        object.__setattr__(self, "record_state", RecordState(self.record_state))
        for name in ("reasons", "evidence_ids", "lineage_refs", "provenance_refs"):
            object.__setattr__(self, name, tuple(sorted(set(getattr(self, name)))))
        _aware(self.recorded_at, "savings recording")
        if self.version < 1 or not self.savings_id or not self.savings_hash:
            raise ValueError("savings identity, version, and hash are required")


def _period(start: datetime, end: datetime) -> None:
    _aware(start, "period start")
    _aware(end, "period end")
    if end <= start:
        raise ValueError("financial period end must follow start")


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
