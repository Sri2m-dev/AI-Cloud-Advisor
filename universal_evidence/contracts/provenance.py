"""End-to-end PUE provenance references without duplicating raw evidence."""

from dataclasses import dataclass

from universal_evidence.contracts.source import EvidenceRowReference


@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    source_id: str
    file_id: str
    sheet_id: str
    column_ids: tuple[str, ...]
    row_references: tuple[EvidenceRowReference, ...]
    mapping_ids: tuple[str, ...]
    mapping_versions: tuple[int, ...]
    classifier_versions: tuple[str, ...]
    confirmation_references: tuple[str, ...]
    analysis_id: str
    derivation_rule: str | None = None
    normalized_record_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        required = (self.source_id, self.file_id, self.sheet_id, self.analysis_id)
        if not all(required) or not self.column_ids or not self.row_references:
            raise ValueError("source, file, sheet, column, row, and analysis provenance are required")
        if len(self.mapping_ids) != len(self.mapping_versions):
            raise ValueError("mapping ids and versions must align")
