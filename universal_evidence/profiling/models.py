"""Immutable PUE-001 structural output contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from universal_evidence.contracts import (
    EvidenceColumn,
    EvidenceFile,
    EvidenceRowReference,
    EvidenceSheet,
    PrimitiveProfile,
)


class ProfileStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    UNSUPPORTED_STRUCTURE = "UNSUPPORTED_STRUCTURE"
    MALFORMED = "MALFORMED"
    FAILED = "FAILED"


class PrimitiveType(str, Enum):
    NULL = "NULL"
    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    STRING = "STRING"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIME = "TIME"
    FORMULA = "FORMULA"
    UNKNOWN = "UNKNOWN"


class StructuralRole(str, Enum):
    IDENTIFIER_LIKE = "IDENTIFIER_LIKE"
    MEASURE_LIKE = "MEASURE_LIKE"
    DATE_LIKE = "DATE_LIKE"
    CATEGORICAL_LIKE = "CATEGORICAL_LIKE"
    FREE_TEXT_LIKE = "FREE_TEXT_LIKE"
    BOOLEAN_LIKE = "BOOLEAN_LIKE"
    HIGH_CARDINALITY = "HIGH_CARDINALITY"
    LOW_CARDINALITY = "LOW_CARDINALITY"
    MOSTLY_NULL = "MOSTLY_NULL"
    CONSTANT_VALUE = "CONSTANT_VALUE"


class WarningCode(str, Enum):
    DUPLICATE_HEADERS = "DUPLICATE_HEADERS"
    UNNAMED_COLUMNS = "UNNAMED_COLUMNS"
    MIXED_PRIMITIVE_TYPES = "MIXED_PRIMITIVE_TYPES"
    EMPTY_SHEET = "EMPTY_SHEET"
    HIDDEN_SHEET = "HIDDEN_SHEET"
    MERGED_CELLS = "MERGED_CELLS"
    FORMULAS_PRESENT = "FORMULAS_PRESENT"
    INCONSISTENT_ROW_WIDTH = "INCONSISTENT_ROW_WIDTH"
    REPEATED_HEADER_ROWS = "REPEATED_HEADER_ROWS"
    MULTIPLE_TABLE_REGIONS = "MULTIPLE_TABLE_REGIONS"
    LOW_DATA_DENSITY = "LOW_DATA_DENSITY"
    UNSUPPORTED_CELL_TYPE = "UNSUPPORTED_CELL_TYPE"
    SAMPLE_SUPPRESSED = "SAMPLE_SUPPRESSED"
    MALFORMED_RECORDS = "MALFORMED_RECORDS"
    RESOURCE_LIMIT_REACHED = "RESOURCE_LIMIT_REACHED"
    HEADER_UNCERTAIN = "HEADER_UNCERTAIN"
    ENCODING_FALLBACK = "ENCODING_FALLBACK"


@dataclass(frozen=True, slots=True)
class StructuralWarning:
    code: WarningCode
    subject_reference: str
    safe_detail: str
    row_reference: EvidenceRowReference | None = None


@dataclass(frozen=True, slots=True)
class StructuralSample:
    display_value: str
    row_reference: EvidenceRowReference
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    column: EvidenceColumn
    observed_rows: int
    primitive_profile: PrimitiveProfile
    primitive_type_distribution: tuple[tuple[PrimitiveType, int], ...]
    dominant_primitive_type: PrimitiveType
    structural_roles: tuple[StructuralRole, ...]
    samples: tuple[StructuralSample, ...]
    warnings: tuple[StructuralWarning, ...] = ()


@dataclass(frozen=True, slots=True)
class SheetProfile:
    sheet: EvidenceSheet
    status: ProfileStatus
    observed_region: tuple[int, int, int, int] | None
    header_detection_confidence: float
    header_detection_method: str
    columns: tuple[ColumnProfile, ...]
    exact_duplicate_row_count: int
    warnings: tuple[StructuralWarning, ...] = ()


@dataclass(frozen=True, slots=True)
class FileProfile:
    evidence_file: EvidenceFile
    status: ProfileStatus
    container_format: str
    profiler_version: str
    profiled_at: datetime
    sheets: tuple[SheetProfile, ...]
    encoding: str | None = None
    delimiter: str | None = None
    quote_character: str | None = None
    physical_record_count: int | None = None
    logical_data_row_count: int | None = None
    warnings: tuple[StructuralWarning, ...] = ()

    @property
    def structural_fingerprint(self) -> tuple[object, ...]:
        """Deterministic comparison surface; excludes operational timestamps."""
        return (
            self.evidence_file.content_hash,
            self.status,
            self.container_format,
            self.profiler_version,
            self.sheets,
            self.encoding,
            self.delimiter,
            self.quote_character,
            self.physical_record_count,
            self.logical_data_row_count,
            self.warnings,
        )


@dataclass(frozen=True, slots=True)
class ProfilerConfig:
    max_file_size: int = 25 * 1024 * 1024
    max_expanded_xlsx_size: int = 100 * 1024 * 1024
    max_sheets: int = 50
    max_rows_profiled: int = 500_000
    max_columns: int = 2_000
    max_sample_values: int = 3
    max_string_sample_length: int = 80
    header_scan_rows: int = 12
    low_cardinality_ratio: float = 0.20
    high_cardinality_ratio: float = 0.90
    mostly_null_coverage: float = 0.50

    def __post_init__(self) -> None:
        positive = (
            self.max_file_size,
            self.max_expanded_xlsx_size,
            self.max_sheets,
            self.max_rows_profiled,
            self.max_columns,
            self.max_sample_values,
            self.max_string_sample_length,
            self.header_scan_rows,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("profiler limits must be positive")
        if self.max_sample_values > 5:
            raise ValueError("PUE contract permits at most five samples")
