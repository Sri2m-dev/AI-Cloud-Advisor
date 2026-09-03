"""Canonical CMP-P4 contracts separating source assertions from canonical truth."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class FactType(str, Enum):
    RESOURCE_IDENTITY = "resource_identity"
    APPLICATION_MEMBERSHIP = "application_membership"
    APPLICATION_OWNER = "application_owner"
    TEAM_MEMBERSHIP = "team_membership"
    COST_CENTER = "cost_center"
    RESOURCE_LIFECYCLE = "resource_lifecycle"
    APPLICATION_LIFECYCLE = "application_lifecycle"
    CLOUD_COST = "cloud_cost"
    SAAS_COST = "saas_cost"
    LICENSE_ASSIGNMENT = "license_assignment"
    LICENSE_ACTIVITY = "license_activity"
    UTILIZATION = "utilization"
    DEPENDENCY = "dependency"
    CONTRACT_TERM = "contract_term"


class RunMode(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    REPLAY = "replay"


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class SchemaChange(str, Enum):
    COMPATIBLE = "compatible"
    COMPATIBLE_ADDITIVE = "compatible_additive"
    MAPPING_REQUIRED = "mapping_required"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class Freshness(str, Enum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


class LifecycleState(str, Enum):
    ACTIVE = "active"
    TEMPORARILY_ABSENT = "temporarily_absent"
    SOURCE_TOMBSTONE = "source_tombstone"
    DECOMMISSIONED = "decommissioned"
    SOURCE_DISABLED = "source_disabled"
    SOURCE_REPLACED = "source_replaced"
    CONNECTOR_FAILED = "connector_failed"


class ReconciliationOutcome(str, Enum):
    CONSISTENT = "consistent"
    SOURCE_PRIORITY_RESOLVED = "source_priority_resolved"
    CANDIDATE_CONFLICT = "candidate_conflict"
    AMBIGUOUS = "ambiguous"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    STALE_SOURCE = "stale_source"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class SourceInstance:
    source_instance_id: str
    organization_id: str
    tenant_id: str
    source_type: str
    source_system: str
    connector_type: str
    connector_version: str
    configuration_reference: str
    credential_reference: str | None = None
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class SourceFactInput:
    source_record_id: str
    fact_type: FactType
    subject_reference: str
    predicate: str
    value: Any = None
    object_reference: str | None = None
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    source_schema_version: str = "1"
    quality: float = 1.0
    freshness: Freshness = Freshness.UNKNOWN
    evidence_reference: str = ""
    lineage: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    lifecycle: LifecycleState = LifecycleState.ACTIVE


@dataclass(frozen=True, slots=True)
class SourceFact:
    source_fact_id: str
    observation_key: str
    fact_version: int
    organization_id: str
    tenant_id: str
    source_instance_id: str
    source_type: str
    source_system: str
    connector_version: str
    ingestion_run_id: str
    source_record_id: str
    fact_type: FactType
    subject_reference: str
    predicate: str
    value: Any
    object_reference: str | None
    observed_at: datetime
    effective_from: datetime | None
    effective_to: datetime | None
    source_schema_version: str
    quality: float
    freshness: Freshness
    evidence_reference: str
    lineage: Mapping[str, Any]
    provenance: Mapping[str, Any]
    lifecycle: LifecycleState
    fingerprint: str


@dataclass(frozen=True, slots=True)
class AuthorityPolicy:
    policy_id: str
    organization_id: str
    tenant_id: str
    fact_type: FactType
    policy_version: int
    source_priorities: tuple[str, ...]
    permitted_sources: tuple[str, ...] = ()
    confirmation_required: bool = False
    fresh_for_seconds: int | None = None
    effective_from: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    effective_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    reconciliation_id: str
    organization_id: str
    tenant_id: str
    subject_reference: str
    predicate: str
    contributing_fact_ids: tuple[str, ...]
    policy_id: str | None
    policy_version: int | None
    outcome: ReconciliationOutcome
    selected_fact_id: str | None
    reason: str
    decided_at: datetime
    actor: str | None = None
    actor_role: str | None = None
    supersedes: str | None = None


@dataclass(frozen=True, slots=True)
class SourceHealth:
    source_instance_id: str
    last_attempt: datetime | None
    last_success: datetime | None
    status: RunStatus | None
    checkpoint: str | None
    connector_version: str
    schema_fingerprint: str | None
    fresh_count: int
    stale_count: int
    quarantined_count: int
    partial_failure_count: int
    correlation_id: str | None
