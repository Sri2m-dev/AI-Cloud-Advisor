"""Isolation context required by every PUE artifact."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvidenceAnalysisContext:
    analysis_id: str
    source_id: str
    prospect_id: str
    organization_id: str | None = None
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("analysis_id", "source_id", "prospect_id"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")
