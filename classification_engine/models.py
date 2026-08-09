"""Persistence-neutral classification, evidence, and tenant-policy contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class InferenceStatus(StrEnum):
    NEEDS_REVIEW = "NEEDS_REVIEW"
    RESOLVED_INFERRED = "RESOLVED_INFERRED"
    RESOLVED_APPROVED = "RESOLVED_APPROVED"
    SUSPENDED = "SUSPENDED"
    REOPENED = "REOPENED"
    SUPERSEDED = "SUPERSEDED"


class ApprovalStatus(StrEnum):
    UNAPPROVED = "UNAPPROVED"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    APPROVED = "APPROVED"
    AUTO_APPROVED = "AUTO_APPROVED"


@dataclass(frozen=True, slots=True)
class ClassificationEvidence:
    evidence_id: str
    organization_id: str
    tenant_id: str
    source_type: str
    source_name: str
    source_reference: str
    observed_field: str
    observed_value: str
    observed_at: datetime
    source_reliability: float
    evidence_hash: str
    lineage_reference: str | None = None
    provenance_reference: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all((self.evidence_id, self.organization_id, self.tenant_id, self.source_type)):
            raise ValueError("evidence identity and tenant scope are required")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not 0 <= self.source_reliability <= 1:
            raise ValueError("source_reliability must be between 0 and 1")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ClassificationPolicy:
    organization_id: str
    tenant_id: str
    policy_version: int = 1
    minimum_inference_confidence: float = 0.75
    minimum_auto_approval_confidence: float = 0.95
    auto_approval_enabled: bool = False
    allow_provisional_spend_release: bool = False
    allow_allocation_before_approval: bool = False
    source_priority_rules: Mapping[str, int] = field(default_factory=dict)
    conflict_policy: str = "REVIEW"
    freshness_days: int = 365
    effective_from: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    effective_to: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.organization_id or not self.tenant_id or self.policy_version < 1:
            raise ValueError("policy tenant scope and positive version are required")
        for score in (self.minimum_inference_confidence, self.minimum_auto_approval_confidence):
            if not 0 <= score <= 1:
                raise ValueError("policy confidence thresholds must be between 0 and 1")
        if self.auto_approval_enabled and (not self.approved_by or not self.approved_at):
            raise ValueError("auto-approval policy requires explicit approval authority")
        object.__setattr__(
            self, "source_priority_rules", MappingProxyType(dict(self.source_priority_rules))
        )


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    id: str
    organization_id: str
    tenant_id: str
    entity_type: str
    entity_id: str
    field_name: str
    inferred_value: str | None
    confidence_score: float
    inference_method: str
    inference_status: InferenceStatus
    policy_version: int
    engine_version: str
    evidence_set_hash: str
    source_timestamp: datetime
    created_at: datetime
    valid_from: datetime
    valid_to: datetime | None
    approval_status: ApprovalStatus
    evidence_ids: tuple[str, ...]
    candidate_values: Mapping[str, float] = field(default_factory=dict)
    conflict: bool = False
    review_reason: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    correction_reason: str | None = None
    superseded_by: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "inference_status", InferenceStatus(self.inference_status))
        object.__setattr__(self, "approval_status", ApprovalStatus(self.approval_status))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        object.__setattr__(self, "candidate_values", MappingProxyType(dict(self.candidate_values)))
        if not 0 <= self.confidence_score <= 1:
            raise ValueError("confidence_score must be between 0 and 1")
        if self.version < 1:
            raise ValueError("version must be positive")
        if self.approval_status in {ApprovalStatus.APPROVED, ApprovalStatus.AUTO_APPROVED}:
            if not self.approved_by or not self.approved_at:
                raise ValueError("approved classification requires authority and timestamp")
