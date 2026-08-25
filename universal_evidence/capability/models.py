"""Immutable PUE-005 coverage and capability contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CoverageState(str, Enum):
    NOT_EVIDENCED = "NOT_EVIDENCED"
    OBSERVED = "OBSERVED"
    PARTIAL = "PARTIAL"
    EVIDENCED = "EVIDENCED"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICTED = "CONFLICTED"
    BLOCKED = "BLOCKED"


class CapabilityState(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class ReasonCode(str, Enum):
    GOVERNED_EVIDENCE_PRESENT = "GOVERNED_EVIDENCE_PRESENT"
    NO_GOVERNED_EVIDENCE = "NO_GOVERNED_EVIDENCE"
    BELOW_COVERAGE_THRESHOLD = "BELOW_COVERAGE_THRESHOLD"
    BELOW_VALIDITY_THRESHOLD = "BELOW_VALIDITY_THRESHOLD"
    INVALID_RATIO_EXCEEDED = "INVALID_RATIO_EXCEEDED"
    DIMENSION_ELIGIBLE = "DIMENSION_ELIGIBLE"
    MEASURE_ELIGIBLE = "MEASURE_ELIGIBLE"
    UNIT_NOT_EVIDENCED = "UNIT_NOT_EVIDENCED"
    ROW_BINDING_INCOMPLETE = "ROW_BINDING_INCOMPLETE"
    MIXED_CURRENCY = "MIXED_CURRENCY"
    SINGLE_CURRENCY_EVIDENCED = "SINGLE_CURRENCY_EVIDENCED"
    REQUIRED_DIMENSION_MISSING = "REQUIRED_DIMENSION_MISSING"
    REQUIRED_MEASURE_MISSING = "REQUIRED_MEASURE_MISSING"
    REQUIRED_TIME_DIMENSION_MISSING = "REQUIRED_TIME_DIMENSION_MISSING"
    FX_NOT_SUPPORTED = "FX_NOT_SUPPORTED"
    CAPABILITY_PREREQUISITES_MET = "CAPABILITY_PREREQUISITES_MET"
    SCOPE_CONFLICT = "SCOPE_CONFLICT"


@dataclass(frozen=True, slots=True)
class CapabilityScope:
    analysis_id: str
    prospect_id: str
    organization_id: str | None
    tenant_id: str | None

    @property
    def key(self) -> tuple[str | None, ...]:
        return (
            self.analysis_id,
            self.prospect_id,
            self.organization_id,
            self.tenant_id,
        )


@dataclass(frozen=True, slots=True)
class CapabilityProvenance:
    normalization_run_ids: tuple[str, ...]
    normalized_field_ids: tuple[str, ...]
    normalized_fingerprints: tuple[str, ...]
    mapping_decision_ids: tuple[str, ...]
    source_references: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True, slots=True)
class EvidenceCoverage:
    coverage_id: str
    semantic_concept_id: str
    scope: CapabilityScope
    observed_records: int
    normalized_records: int
    valid_records: int
    null_records: int
    invalid_records: int
    partial_records: int
    unsupported_records: int
    coverage_ratio: float
    validity_ratio: float
    distinct_count: int | None
    mapping_decision_ids: tuple[str, ...]
    normalization_run_ids: tuple[str, ...]
    provenance: CapabilityProvenance
    coverage_state: CoverageState
    reason_codes: tuple[ReasonCode, ...]
    policy_version: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class GovernedDimension:
    dimension_id: str
    semantic_concept_id: str
    scope: CapabilityScope
    coverage_id: str
    state: CapabilityState
    cardinality: int | None
    reason_codes: tuple[ReasonCode, ...]
    policy_version: str
    provenance: CapabilityProvenance
    fingerprint: str


@dataclass(frozen=True, slots=True)
class GovernedMeasure:
    measure_id: str
    semantic_concept_id: str
    scope: CapabilityScope
    value_coverage_id: str
    currency_coverage_id: str | None
    currency_concept_id: str | None
    detected_currencies: tuple[str, ...]
    row_binding_ratio: float
    state: CapabilityState
    aggregation_eligibility: CapabilityState
    permitted_aggregation_functions: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    policy_version: str
    provenance: CapabilityProvenance
    fingerprint: str


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    requirement_type: str
    semantic_concept_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceCapability:
    capability_id: str
    capability_name: str
    scope: CapabilityScope
    state: CapabilityState
    requirements: tuple[CapabilityRequirement, ...]
    supporting_coverage_ids: tuple[str, ...]
    supporting_dimension_ids: tuple[str, ...]
    supporting_measure_ids: tuple[str, ...]
    reason_codes: tuple[ReasonCode, ...]
    policy_version: str
    provenance: CapabilityProvenance
    fingerprint: str


@dataclass(frozen=True, slots=True)
class CapabilityAssessment:
    assessment_id: str
    scope: CapabilityScope
    coverage: tuple[EvidenceCoverage, ...]
    dimensions: tuple[GovernedDimension, ...]
    measures: tuple[GovernedMeasure, ...]
    capabilities: tuple[EvidenceCapability, ...]
    coverage_policy_version: str
    capability_policy_version: str
    fingerprint: str
