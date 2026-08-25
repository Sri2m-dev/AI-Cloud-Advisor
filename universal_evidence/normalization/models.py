"""Immutable row-level PUE-004 normalization contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from universal_evidence.contracts import EvidenceRowReference
from universal_evidence.governance import DecisionScope, MappingDecisionState
from universal_evidence.normalization.warnings import NormalizationWarning


class NormalizationStatus(str, Enum):
    NORMALIZED = "NORMALIZED"
    UNCHANGED = "UNCHANGED"
    PARTIAL = "PARTIAL"
    INVALID = "INVALID"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    SUPPRESSED = "SUPPRESSED"
    SKIPPED = "SKIPPED"


class NormalizationRunStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True, slots=True)
class AuthorizedSourceValue:
    """A value supplied by an authorized in-memory source reader."""

    row_reference: EvidenceRowReference
    source_value: Any
    formula_expression: str | None = None
    cached_formula_value: Any | None = None


@dataclass(frozen=True, slots=True)
class NormalizationProvenance:
    scope: DecisionScope
    row_reference: EvidenceRowReference
    semantic_concept_id: str
    mapping_decision_id: str
    mapping_decision_state: MappingDecisionState
    structural_profile_fingerprint: str
    semantic_fingerprint: str
    classifier_version: str
    ontology_version: str
    governance_policy_version: str
    normalization_policy_version: str
    formula_expression: str | None = None
    used_cached_formula_value: bool = False


@dataclass(frozen=True, slots=True)
class NormalizedEvidenceField:
    normalized_field_id: str
    analysis_id: str
    prospect_id: str
    organization_id: str | None
    tenant_id: str | None
    source_id: str
    file_id: str
    sheet_id: str
    column_id: str
    row_reference: EvidenceRowReference
    semantic_concept_id: str
    source_value: Any
    normalized_value: Any
    normalized_type: str | None
    normalized_unit: str | None
    mapping_decision_id: str
    mapping_decision_state: MappingDecisionState
    mapping_version: str
    ontology_version: str
    classifier_version: str
    governance_policy_version: str
    normalization_policy_version: str
    normalization_status: NormalizationStatus
    warnings: tuple[NormalizationWarning, ...]
    created_at: datetime
    provenance: NormalizationProvenance
    fingerprint: str


@dataclass(frozen=True, slots=True)
class NormalizationRun:
    normalization_run_id: str
    analysis_id: str
    mapping_set_fingerprint: str
    mapping_decision_id: str
    normalization_policy_version: str
    started_at: datetime
    completed_at: datetime
    status: NormalizationRunStatus
    records: tuple[NormalizedEvidenceField, ...]
    processed_count: int
    normalized_count: int
    invalid_count: int
    skipped_count: int
    supersedes_run_id: str | None
    fingerprint: str
