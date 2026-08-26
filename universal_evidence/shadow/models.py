"""Immutable PUE-010 shadow orchestration contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from universal_evidence.contracts import EvidenceSource
from universal_evidence.governance import EffectiveSemanticMapping
from universal_evidence.normalization import AuthorizedSourceValue


class ShadowStage(str, Enum):
    PROFILING = "PUE-001"
    SEMANTIC_DISCOVERY = "PUE-002"
    CONFIRMATION_GOVERNANCE = "PUE-003"
    NORMALIZATION = "PUE-004"
    CAPABILITY = "PUE-005-C5A"
    INTERPRETATION = "PUE-008"
    PLANNING = "PUE-007"
    EXECUTION = "PUE-006"
    ANSWER_COMPOSITION = "PUE-009"


class StageStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ShadowStatus(str, Enum):
    SHADOW_COMPLETE = "SHADOW_COMPLETE"
    SHADOW_COMPLETE_WITH_BLOCKED_QUERY = "SHADOW_COMPLETE_WITH_BLOCKED_QUERY"
    SHADOW_COMPLETE_WITH_UNSUPPORTED_QUERY = "SHADOW_COMPLETE_WITH_UNSUPPORTED_QUERY"
    SHADOW_COMPLETE_WITH_AMBIGUOUS_QUERY = "SHADOW_COMPLETE_WITH_AMBIGUOUS_QUERY"
    SHADOW_BLOCKED = "SHADOW_BLOCKED"
    SHADOW_FAILED = "SHADOW_FAILED"


class ComparisonState(str, Enum):
    MATCH = "MATCH"
    DIFFERENT_BY_DESIGN = "DIFFERENT_BY_DESIGN"
    PUE_BLOCKED = "PUE_BLOCKED"
    LEGACY_ONLY = "LEGACY_ONLY"
    PUE_ONLY = "PUE_ONLY"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class ActivationReadiness(str, Enum):
    NOT_READY = "NOT_READY"
    READY_FOR_LIMITED_SHADOW = "READY_FOR_LIMITED_SHADOW"
    READY_FOR_CONTROLLED_ACTIVATION_REVIEW = "READY_FOR_CONTROLLED_ACTIVATION_REVIEW"


@dataclass(frozen=True, slots=True)
class NormalizationBinding:
    mapping: EffectiveSemanticMapping
    values: tuple[AuthorizedSourceValue, ...]


@dataclass(frozen=True, slots=True)
class ShadowAnalysisInput:
    source: EvidenceSource
    filename: str
    content: bytes
    decision_repository: Any
    normalization_bindings: tuple[NormalizationBinding, ...] = ()


@dataclass(frozen=True, slots=True)
class StageResult:
    stage: ShadowStage
    status: StageStatus
    reason_codes: tuple[str, ...]
    artifact_references: tuple[str, ...]
    duration_ms: float


@dataclass(frozen=True, slots=True)
class PipelineVersions:
    profiler: str
    ontology: str
    semantic_classifier: str
    governance_policy: str
    normalization_policy: str
    coverage_policy: str
    capability_policy: str
    execution_authorization_policy: str
    aggregation_execution_policy: str
    planning_policy: str
    interpretation_policy: str
    answer_composition_policy: str
    shadow_orchestrator: str


@dataclass(frozen=True, slots=True)
class ShadowProvenance:
    source_id: str
    file_id: str
    structural_fingerprint: str
    semantic_fingerprint: str
    mapping_decision_ids: tuple[str, ...]
    normalization_run_ids: tuple[str, ...]
    capability_assessment_id: str | None
    execution_authorization_ids: tuple[str, ...]
    interpretation_id: str | None = None
    analytical_plan_id: str | None = None
    aggregation_result_id: str | None = None
    answer_id: str | None = None


@dataclass(frozen=True, slots=True)
class ShadowAnalysisResult:
    shadow_run_id: str
    scope_key: tuple[str | None, ...]
    current_authority: str
    shadow_status: ShadowStatus
    stage_results: tuple[StageResult, ...]
    profile: Any
    semantic_discovery: Any
    normalization_runs: tuple[Any, ...]
    capability_assessment: Any | None
    warnings: tuple[str, ...]
    provenance: ShadowProvenance
    pipeline_versions: PipelineVersions
    source_size_bytes: int
    source_rows: int | None
    source_sheets: int
    total_duration_ms: float
    fingerprint: str
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class ShadowQuestionResult:
    shadow_question_id: str
    shadow_run_id: str
    question: str
    interpretation: Any
    planning: Any | None
    aggregation_result: Any | None
    answer: Any
    stage_results: tuple[StageResult, ...]
    final_shadow_state: ShadowStatus
    reason_codes: tuple[str, ...]
    provenance: ShadowProvenance
    fingerprint: str
    label: str = "SHADOW / NON-AUTHORITATIVE"


@dataclass(frozen=True, slots=True)
class ShadowComparisonResult:
    comparison_id: str
    state: ComparisonState
    legacy_reference: str | None
    shadow_reference: str | None
    explanation: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class CertificationReport:
    version_chain: tuple[str, ...]
    scenario_outcomes: tuple[tuple[str, str], ...]
    known_limitations: tuple[str, ...]
    activation_blockers: tuple[str, ...]
    readiness: ActivationReadiness
    authority: str = "SHADOW / NON-AUTHORITATIVE"
