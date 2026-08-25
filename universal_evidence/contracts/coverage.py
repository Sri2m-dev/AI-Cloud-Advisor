"""Evidence coverage matrix contract."""

from dataclasses import dataclass

from universal_evidence.contracts.enums import AvailabilityStatus, ConfirmationState
from universal_evidence.contracts.scope import EvidenceAnalysisContext


@dataclass(frozen=True, slots=True)
class EvidenceCoverage:
    context: EvidenceAnalysisContext
    semantic_concept_id: str
    availability_status: AvailabilityStatus
    record_coverage: float
    confidence: float | None
    confirmation_state: ConfirmationState
    source_count: int
    file_count: int
    quality_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.record_coverage) <= 1.0:
            raise ValueError("record_coverage must be between 0.0 and 1.0")
        if self.confidence is not None and not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
