"""Immutable evidence references, packages, and case-use roles."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class CaseRole(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    CONTEXT = "context"
    BASELINE = "baseline"
    OUTCOME = "outcome"


class EvidencePackageStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    evidence_id: str
    organization_id: str
    tenant_id: str
    subject_id: str
    source_system: str
    source_identifier: str
    evidence_hash: str
    observed_at: datetime
    captured_at: datetime
    lineage_ref: str | None = None
    provenance_ref: str | None = None
    quality_score: float | None = None
    corrects_evidence_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = (
            self.evidence_id,
            self.organization_id,
            self.tenant_id,
            self.subject_id,
            self.source_system,
            self.source_identifier,
            self.evidence_hash,
        )
        if any(not str(value).strip() for value in required):
            raise ValueError("evidence identity, scope, subject, source, and hash are required")
        if self.observed_at.tzinfo is None or self.captured_at.tzinfo is None:
            raise ValueError("evidence timestamps must be timezone-aware")
        if self.quality_score is not None and not 0 <= self.quality_score <= 1:
            raise ValueError("quality_score must be between 0 and 1")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CaseEvidence:
    evidence_id: str
    role: CaseRole
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", CaseRole(self.role))
        if not self.evidence_id or not self.rationale.strip():
            raise ValueError("case evidence id and rationale are required")


@dataclass(frozen=True, slots=True)
class EvidencePackage:
    package_id: str
    organization_id: str
    tenant_id: str
    case_id: str
    version: int
    status: EvidencePackageStatus
    evidence: tuple[CaseEvidence, ...]
    created_by: str
    created_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None
    package_hash: str | None = None
    supersedes_package_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", EvidencePackageStatus(self.status))
        object.__setattr__(
            self,
            "evidence",
            tuple(sorted(self.evidence, key=lambda item: (item.role.value, item.evidence_id))),
        )
        if not self.package_id or not self.case_id or not self.created_by:
            raise ValueError("package identity, case, and creator are required")
        if self.version < 1:
            raise ValueError("package version must be positive")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.status is EvidencePackageStatus.APPROVED:
            if not self.approved_by or self.approved_at is None or not self.package_hash:
                raise ValueError("approved package requires approval and integrity evidence")
