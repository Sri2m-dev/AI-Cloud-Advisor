"""Immutable request, plan, and result models for P3 orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext
from data_fabric.foundation.time import require_timezone_aware
from data_fabric.lineage import LineageEvent, ProvenanceRecord
from data_fabric.quality import QualityAssessment, QualityIssue
from data_fabric.semantic import MappingResult
from data_fabric.versioning import VersionRecord
from data_fabric.orchestration.exceptions import OrchestrationValidationError


class EntityWriteAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DEACTIVATE = "deactivate"
    NO_CHANGE = "no_change"
    REJECT = "reject"


class RelationshipWriteAction(str, Enum):
    CREATE = "create"
    DEACTIVATE = "deactivate"
    NO_CHANGE = "no_change"
    REJECT = "reject"


class QualityGateOutcome(str, Enum):
    ALLOW = "allow"
    ALLOW_WITH_WARNING = "allow_with_warning"
    QUARANTINE = "quarantine"
    REJECT = "reject"


class VersionDecisionAction(str, Enum):
    CREATE_INITIAL_VERSION = "create_initial_version"
    CREATE_CHANGED_VERSION = "create_changed_version"
    SKIP_UNCHANGED = "skip_unchanged"
    FORCE_VERSION = "force_version"
    REJECT_OUT_OF_ORDER = "reject_out_of_order"


class IdempotencyState(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class TransactionStatus(str, Enum):
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class ProcessingIssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    tenant_context: TenantContext
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise OrchestrationValidationError("idempotency key value is required")


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_system: str
    source_identifier: str
    source_type: str
    provider: str | None
    payload: Mapping[str, Any]
    received_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_system:
            raise OrchestrationValidationError("source_system is required")
        if not self.source_identifier:
            raise OrchestrationValidationError("source_identifier is required")
        if not self.source_type:
            raise OrchestrationValidationError("source_type is required")
        require_timezone_aware(self.received_at, "received_at")
        object.__setattr__(self, "payload", _freeze(self.payload))
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class IngestionRequest:
    request_id: str
    tenant_context: TenantContext
    source_system: str
    source_identifier: str
    source_type: str
    provider: str | None
    payload: Mapping[str, Any]
    received_at: datetime
    idempotency_key: IdempotencyKey
    correlation_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id:
            raise OrchestrationValidationError("request_id is required")
        if not self.source_system:
            raise OrchestrationValidationError("source_system is required")
        if not self.source_identifier:
            raise OrchestrationValidationError("source_identifier is required")
        if not self.source_type:
            raise OrchestrationValidationError("source_type is required")
        self.tenant_context.assert_matches(self.idempotency_key.tenant_context, "idempotency_key")
        require_timezone_aware(self.received_at, "received_at")
        object.__setattr__(self, "payload", _freeze(self.payload))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    @property
    def source_record(self) -> SourceRecord:
        return SourceRecord(
            source_system=self.source_system,
            source_identifier=self.source_identifier,
            source_type=self.source_type,
            provider=self.provider,
            payload=self.payload,
            received_at=self.received_at,
            metadata=self.metadata,
        )


@dataclass(frozen=True, slots=True)
class CanonicalizationContext:
    request_id: str
    tenant_context: TenantContext
    correlation_id: str | None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        require_timezone_aware(self.started_at, "started_at")


@dataclass(frozen=True, slots=True)
class EntityWritePlan:
    action: EntityWriteAction | str
    entity: EnterpriseEntity | None = None
    existing_entity: EnterpriseEntity | None = None
    reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", EntityWriteAction(self.action))
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class RelationshipWritePlan:
    action: RelationshipWriteAction | str
    relationship: EnterpriseRelationship | None = None
    reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", RelationshipWriteAction(self.action))
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class QualityGateDecision:
    outcome: QualityGateOutcome | str
    assessment: QualityAssessment | None
    explanation: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome", QualityGateOutcome(self.outcome))
        object.__setattr__(self, "explanation", tuple(self.explanation))


@dataclass(frozen=True, slots=True)
class LineageEmissionPlan:
    emit_source_event: bool
    emit_normalization_event: bool
    emit_semantic_mapping_event: bool
    emit_identity_resolution_event: bool
    emit_canonicalization_event: bool
    emit_quality_assessment_event: bool
    emit_version_event: bool
    emit_relationship_event: bool
    emit_rejection_or_quarantine_event: bool
    events: tuple[LineageEvent, ...] = field(default_factory=tuple)
    provenance_records: tuple[ProvenanceRecord, ...] = field(default_factory=tuple)
    explanation: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "provenance_records", tuple(self.provenance_records))
        object.__setattr__(self, "explanation", tuple(self.explanation))


@dataclass(frozen=True, slots=True)
class VersionDecision:
    action: VersionDecisionAction | str
    subject_id: str
    previous_hash: str | None
    new_hash: str | None
    version: int
    explanation: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", VersionDecisionAction(self.action))
        object.__setattr__(self, "explanation", tuple(self.explanation))


@dataclass(frozen=True, slots=True)
class ProcessingIssue:
    code: str
    message: str
    severity: ProcessingIssueSeverity | str = ProcessingIssueSeverity.ERROR

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", ProcessingIssueSeverity(self.severity))


@dataclass(frozen=True, slots=True)
class TransactionResult:
    status: TransactionStatus | str
    entity_writes: tuple[EntityWritePlan, ...] = field(default_factory=tuple)
    relationship_writes: tuple[RelationshipWritePlan, ...] = field(default_factory=tuple)
    lineage_events: tuple[LineageEvent, ...] = field(default_factory=tuple)
    provenance_records: tuple[ProvenanceRecord, ...] = field(default_factory=tuple)
    version_records: tuple[VersionRecord, ...] = field(default_factory=tuple)
    issues: tuple[ProcessingIssue, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", TransactionStatus(self.status))
        object.__setattr__(self, "entity_writes", tuple(self.entity_writes))
        object.__setattr__(self, "relationship_writes", tuple(self.relationship_writes))
        object.__setattr__(self, "lineage_events", tuple(self.lineage_events))
        object.__setattr__(self, "provenance_records", tuple(self.provenance_records))
        object.__setattr__(self, "version_records", tuple(self.version_records))
        object.__setattr__(self, "issues", tuple(self.issues))


@dataclass(frozen=True, slots=True)
class CanonicalizationResult:
    request_id: str
    tenant_context: TenantContext
    source_record: SourceRecord
    entity_plan: EntityWritePlan
    relationship_plans: tuple[RelationshipWritePlan, ...]
    quality_decision: QualityGateDecision
    version_decision: VersionDecision
    lineage_plan: LineageEmissionPlan
    transaction_result: TransactionResult | None
    idempotent_replay: bool = False
    semantic_mapping: MappingResult | None = None
    issues: tuple[ProcessingIssue, ...] = field(default_factory=tuple)
    explanation: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "relationship_plans", tuple(self.relationship_plans))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "explanation", tuple(self.explanation))

    @property
    def succeeded(self) -> bool:
        return not any(issue.severity is ProcessingIssueSeverity.ERROR for issue in self.issues)


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    key: IdempotencyKey
    payload_hash: str
    state: IdempotencyState | str
    created_at: datetime
    updated_at: datetime
    result: CanonicalizationResult | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", IdempotencyState(self.state))
        require_timezone_aware(self.created_at, "created_at")
        require_timezone_aware(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class BatchIngestionRequest:
    batch_id: str
    tenant_context: TenantContext
    requests: tuple[IngestionRequest, ...]
    fail_fast: bool = False

    def __post_init__(self) -> None:
        if not self.batch_id:
            raise OrchestrationValidationError("batch_id is required")
        normalized = tuple(self.requests)
        for request in normalized:
            self.tenant_context.assert_matches(request.tenant_context, "batch request")
        object.__setattr__(self, "requests", normalized)


@dataclass(frozen=True, slots=True)
class RecordProcessingResult:
    index: int
    request_id: str
    success: bool
    result: CanonicalizationResult | None = None
    issues: tuple[ProcessingIssue, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))


@dataclass(frozen=True, slots=True)
class BatchIngestionResult:
    batch_id: str
    tenant_context: TenantContext
    records: tuple[RecordProcessingResult, ...]
    total_records: int
    success_count: int
    failure_count: int
    fail_fast: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))


def payload_hash(payload: Mapping[str, Any]) -> str:
    return DefaultDeterministicSerializer().content_hash(payload)


def _freeze(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(value[key]) for key in sorted(value, key=str)})
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze(item) for item in value)
    return value
