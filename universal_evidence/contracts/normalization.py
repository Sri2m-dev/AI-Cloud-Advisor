"""Layer 3 normalized evidence and Layer 4 derived-result contracts."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from universal_evidence.contracts.enums import ConfirmationState
from universal_evidence.contracts.provenance import EvidenceProvenance
from universal_evidence.contracts.scope import EvidenceAnalysisContext


@dataclass(frozen=True, slots=True)
class NormalizedEvidenceField:
    normalized_field_id: str
    context: EvidenceAnalysisContext
    semantic_concept_id: str
    semantic_concept_version: int
    normalized_value: Any
    normalized_unit: str | None
    source_value: Any
    mapping_id: str
    mapping_version: int
    mapping_confidence: float
    confirmation_state: ConfirmationState
    provenance: EvidenceProvenance
    created_at: datetime

    def __post_init__(self) -> None:
        if self.provenance.analysis_id != self.context.analysis_id:
            raise ValueError("provenance must belong to the normalized field analysis")


@dataclass(frozen=True, slots=True)
class DerivedEvidenceResult:
    result_id: str
    context: EvidenceAnalysisContext
    result_kind: str
    value: Any
    normalized_record_ids: tuple[str, ...]
    semantic_concept_ids: tuple[str, ...]
    derivation_rule: str
    provenance: EvidenceProvenance
    evidence_sufficiency: str
    unsupported_dimensions: tuple[str, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.normalized_record_ids:
            raise ValueError("derived results require normalized evidence references")
        if not self.derivation_rule:
            raise ValueError("derived results require a derivation rule")
