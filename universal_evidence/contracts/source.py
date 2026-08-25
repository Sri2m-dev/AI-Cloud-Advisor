"""Layer 0 source identity and Layer 1 structural observation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from universal_evidence.contracts.scope import EvidenceAnalysisContext


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    context: EvidenceAnalysisContext
    immutable_source_reference: str
    received_at: datetime
    retention_expiry: datetime
    classification_boundary: str = "RAW_EVIDENCE"

    def __post_init__(self) -> None:
        if not self.immutable_source_reference:
            raise ValueError("immutable_source_reference is required")
        if self.retention_expiry <= self.received_at:
            raise ValueError("retention_expiry must be after received_at")


@dataclass(frozen=True, slots=True)
class EvidenceFile:
    context: EvidenceAnalysisContext
    file_id: str
    original_filename: str
    content_hash: str
    source_type: str
    size_bytes: int
    mime_type: str | None = None
    encoding: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceSheet:
    context: EvidenceAnalysisContext
    file_id: str
    sheet_id: str
    original_name: str
    ordinal: int
    hidden: bool
    row_count: int | None
    column_count: int | None
    header_row_candidate: int | None = None
    empty_leading_rows: int = 0
    empty_trailing_rows: int = 0
    has_merged_cells: bool = False
    has_formulas: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceColumn:
    context: EvidenceAnalysisContext
    file_id: str
    sheet_id: str
    column_id: str
    original_header: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class EvidenceRowReference:
    context: EvidenceAnalysisContext
    file_id: str
    sheet_id: str
    row_numbers: tuple[int, ...] = ()
    row_range: tuple[int, int] | None = None
    lineage_expression: str | None = None

    def __post_init__(self) -> None:
        selectors = bool(self.row_numbers), self.row_range is not None, bool(self.lineage_expression)
        if sum(selectors) != 1:
            raise ValueError("exactly one row selector is required")
        if self.row_range and self.row_range[0] > self.row_range[1]:
            raise ValueError("row_range start must not exceed end")


@dataclass(frozen=True, slots=True)
class PrimitiveProfile:
    column_id: str
    primitive_type_candidates: tuple[str, ...]
    null_count: int
    non_null_count: int
    distinct_count: int
    coverage: float
    uniqueness: float
    min_value: Any | None = None
    max_value: Any | None = None
    min_string_length: int | None = None
    max_string_length: int | None = None
    candidate_categorical: bool = False
    candidate_identifier: bool = False
    candidate_numeric_measure: bool = False
    candidate_date_field: bool = False
    mixed_type: bool = False
    safe_representative_samples: tuple[Any, ...] = ()
    sensitive_looking: bool = False
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("coverage", "uniqueness"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0")
        if len(self.safe_representative_samples) > 5:
            raise ValueError("safe representative samples must be bounded to five")


@dataclass(frozen=True, slots=True)
class StructuralObservation:
    observation_id: str
    context: EvidenceAnalysisContext
    subject_reference: str
    observation_type: str
    observed_value: Any
    reproduction_rule: str
    observed_at: datetime
    warnings: tuple[str, ...] = field(default_factory=tuple)
