"""Immutable container, document, and structural-region contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TypeAlias

from universal_evidence.contracts import EvidenceAnalysisContext
from universal_evidence.documents.identity import (
    scoped_container_id,
    scoped_document_id,
    scoped_region_id,
    structural_fingerprint,
)


class StructuralState(str, Enum):
    DISCOVERED = "DISCOVERED"
    PARTIAL = "PARTIAL"
    UNRESOLVED = "UNRESOLVED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"


class StructuralType(str, Enum):
    TABULAR = "TABULAR"
    KEY_VALUE = "KEY_VALUE"
    SUMMARY = "SUMMARY"
    TEXT = "TEXT"
    FORM = "FORM"
    UNKNOWN = "UNKNOWN"


class SecurityFinding(str, Enum):
    ENCRYPTED = "ENCRYPTED"
    PASSWORD_PROTECTED = "PASSWORD_PROTECTED"
    MACRO_PRESENT = "MACRO_PRESENT"
    EXTERNAL_LINKS_PRESENT = "EXTERNAL_LINKS_PRESENT"
    EMBEDDED_OBJECTS_PRESENT = "EMBEDDED_OBJECTS_PRESENT"
    HIDDEN_CONTENT_PRESENT = "HIDDEN_CONTENT_PRESENT"
    ACTIVE_CONTENT_PRESENT = "ACTIVE_CONTENT_PRESENT"
    MALFORMED = "MALFORMED"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"


@dataclass(frozen=True, slots=True)
class SecurityDiagnostic:
    finding: SecurityFinding
    safe_detail: str = ""


@dataclass(frozen=True, slots=True)
class ResourceDiagnostics:
    file_size: int
    expanded_size: int | None = None
    sheet_or_page_count: int | None = None
    cell_count: int | None = None
    region_count: int | None = None
    extracted_text_size: int | None = None
    table_count: int | None = None
    limit_exceeded: bool = False
    partial_reason: str | None = None

    def __post_init__(self) -> None:
        values = (
            self.file_size,
            self.expanded_size,
            self.sheet_or_page_count,
            self.cell_count,
            self.region_count,
            self.extracted_text_size,
            self.table_count,
        )
        if any(value is not None and value < 0 for value in values):
            raise ValueError("resource diagnostic counts cannot be negative")
        if self.limit_exceeded and not self.partial_reason:
            raise ValueError("a resource limit finding requires a safe partial reason")


@dataclass(frozen=True, slots=True)
class StructuralLineage:
    source_reference: str
    container_id: str
    physical_locator: str
    parent_region_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_reference or not self.container_id or not self.physical_locator:
            raise ValueError("bounded source, container, and physical lineage are required")


@dataclass(frozen=True, slots=True)
class SpreadsheetLocation:
    sheet_id: str
    start_row: int
    end_row: int
    start_column: int
    end_column: int
    range_locator: str | None = None

    def __post_init__(self) -> None:
        if not self.sheet_id or min(self.start_row, self.start_column) < 1:
            raise ValueError("spreadsheet location requires a sheet and positive bounds")
        if self.end_row < self.start_row or self.end_column < self.start_column:
            raise ValueError("spreadsheet location bounds are reversed")


@dataclass(frozen=True, slots=True)
class PdfLocation:
    page_id: str
    page_number: int
    bounding_box: tuple[float, float, float, float] | None = None
    reading_order: int | None = None

    def __post_init__(self) -> None:
        if not self.page_id or self.page_number < 1:
            raise ValueError("PDF location requires a page and positive page number")
        if self.bounding_box and (
            self.bounding_box[2] < self.bounding_box[0]
            or self.bounding_box[3] < self.bounding_box[1]
        ):
            raise ValueError("PDF bounding box is reversed")
        if self.reading_order is not None and self.reading_order < 0:
            raise ValueError("reading order cannot be negative")


@dataclass(frozen=True, slots=True)
class DelimitedLocation:
    start_row: int
    end_row: int
    start_column: int
    end_column: int

    def __post_init__(self) -> None:
        if min(self.start_row, self.start_column) < 1:
            raise ValueError("delimited location bounds must be positive")
        if self.end_row < self.start_row or self.end_column < self.start_column:
            raise ValueError("delimited location bounds are reversed")


StructuralLocation: TypeAlias = SpreadsheetLocation | PdfLocation | DelimitedLocation


@dataclass(frozen=True, slots=True)
class UploadContainer:
    context: EvidenceAnalysisContext
    content_fingerprint: str
    container_type: str
    size_bytes: int
    admitted_at: datetime
    source_reference: str
    security_status: StructuralState = StructuralState.DISCOVERED
    security_diagnostics: tuple[SecurityDiagnostic, ...] = ()
    resource_diagnostics: ResourceDiagnostics | None = None
    warnings: tuple[str, ...] = ()
    filename: str | None = field(default=None, compare=False)
    container_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.content_fingerprint or not self.container_type or not self.source_reference:
            raise ValueError("container fingerprint, type, and source reference are required")
        if self.size_bytes < 0:
            raise ValueError("container size cannot be negative")
        object.__setattr__(
            self,
            "container_id",
            scoped_container_id(self.context, self.content_fingerprint),
        )

    @property
    def publishable(self) -> bool:
        return self.security_status not in {StructuralState.QUARANTINED, StructuralState.REJECTED}


@dataclass(frozen=True, slots=True)
class EvidenceDocument:
    context: EvidenceAnalysisContext
    container_id: str
    ordinal: int
    structural_locator: str
    structural_extent: str
    representation_type: str
    lineage: StructuralLineage
    structural_confidence: float
    status: StructuralState = StructuralState.DISCOVERED
    warnings: tuple[str, ...] = ()
    structural_fingerprint: str = field(init=False)
    document_id: str = field(init=False)

    def __post_init__(self) -> None:
        if self.ordinal < 0 or not self.structural_locator or not self.structural_extent:
            raise ValueError("document requires an ordinal, locator, and extent")
        if self.lineage.container_id != self.container_id:
            raise ValueError("document lineage must reference its container")
        _validate_confidence(self.structural_confidence)
        fingerprint = structural_fingerprint(
            "pue-011b.document-structure.v1",
            self.container_id,
            self.structural_locator,
            self.structural_extent,
            self.representation_type,
        )
        object.__setattr__(self, "structural_fingerprint", fingerprint)
        object.__setattr__(
            self,
            "document_id",
            scoped_document_id(self.context, self.container_id, self.structural_locator),
        )

    @property
    def publishable(self) -> bool:
        return self.status not in {StructuralState.QUARANTINED, StructuralState.REJECTED}


@dataclass(frozen=True, slots=True)
class EvidenceRegion:
    context: EvidenceAnalysisContext
    container_id: str
    document_id: str | None
    location: StructuralLocation
    structural_type: StructuralType
    raw_structure_reference: str
    extraction_method: str
    structural_confidence: float
    lineage: StructuralLineage
    candidate_schema: tuple[str, ...] = ()
    profile_reference: str | None = None
    warnings: tuple[str, ...] = ()
    status: StructuralState = StructuralState.DISCOVERED
    structural_fingerprint: str = field(init=False)
    region_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.raw_structure_reference or not self.extraction_method:
            raise ValueError("region structure reference and extraction method are required")
        if self.lineage.container_id != self.container_id:
            raise ValueError("region lineage must reference its container")
        _validate_confidence(self.structural_confidence)
        fingerprint = structural_fingerprint(
            "pue-011b.region-structure.v1",
            self.location,
            self.structural_type,
            self.candidate_schema,
            self.profile_reference,
        )
        object.__setattr__(self, "structural_fingerprint", fingerprint)
        object.__setattr__(
            self,
            "region_id",
            scoped_region_id(
                self.context,
                self.container_id,
                self.document_id,
                self.location,
                fingerprint,
            ),
        )

    @property
    def publishable(self) -> bool:
        return self.status not in {StructuralState.QUARANTINED, StructuralState.REJECTED}


class SemanticDecisionState(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class SemanticEvidenceSet:
    """Future semantic/governance boundary; PUE-011B performs no classification."""

    evidence_set_id: str
    context: EvidenceAnalysisContext
    region_ids: tuple[str, ...]
    candidate_semantic_type: str | None
    decision_state: SemanticDecisionState
    semantic_confidence: float | None
    lineage_references: tuple[str, ...]
    governance_reference: str | None = None
    semantic_fingerprint: str | None = None
    business_document_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_set_id or not self.region_ids or not self.lineage_references:
            raise ValueError("semantic evidence set identity, regions, and lineage are required")
        if self.semantic_confidence is not None:
            _validate_confidence(self.semantic_confidence)


def assert_same_scope(left: EvidenceAnalysisContext, right: EvidenceAnalysisContext) -> None:
    boundary = ("organization_id", "tenant_id", "prospect_id")
    if any(getattr(left, name) != getattr(right, name) for name in boundary):
        raise PermissionError("cross-tenant evidence identity resolution is forbidden")


def _validate_confidence(value: float) -> None:
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError("structural confidence must be between 0.0 and 1.0")
