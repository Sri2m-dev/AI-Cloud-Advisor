from __future__ import annotations

from typing import Any

from services.platform.business_context_service import BusinessContextService
from services.platform.reconciliation_service import ReconciliationService


class EvidenceService:
    """Standard evidence payload builder for certification-ready pages."""

    @staticmethod
    def build(
        *,
        source_data: list[dict[str, Any]],
        data_coverage: list[dict[str, Any]],
        business_context: dict[str, Any],
        reconciliation_cards: dict[str, Any],
        ai_interpretation: str,
        raw_evidence: dict[str, list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        return {
            "source_data": source_data,
            "data_coverage": data_coverage,
            "relationship_summary": BusinessContextService.relationship_rows(business_context),
            "financial_reconciliation": ReconciliationService.evidence_rows(reconciliation_cards),
            "ai_interpretation": ai_interpretation,
            "raw_evidence": raw_evidence or {},
        }
