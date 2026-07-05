from __future__ import annotations

from typing import Any

from services.platform.business_context_service import BusinessContextService
from services.platform.evidence_service import EvidenceService
from services.platform.executive_summary_service import ExecutiveSummaryService
from services.platform.reconciliation_service import ReconciliationService


class CertificationService:
    """Facade for common certification payloads across Nexora workspaces."""

    @staticmethod
    def base_context(extra_context: dict[str, Any] | None = None) -> dict[str, Any]:
        reconciliation_cards = ReconciliationService.get_status_cards()
        business_context = BusinessContextService.get_context(extra_context)
        return {
            "reconciliation_cards": reconciliation_cards,
            "business_context": business_context,
        }

    @staticmethod
    def build_payload(
        *,
        summary_title: str,
        summary_sentences: list[str],
        summary_metrics: list[dict[str, Any]],
        source_data: list[dict[str, Any]],
        data_coverage: list[dict[str, Any]],
        ai_interpretation: str,
        raw_evidence: dict[str, list[dict[str, Any]]] | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = CertificationService.base_context(extra_context)
        summary = ExecutiveSummaryService.build(
            title=summary_title,
            sentences=summary_sentences,
            metrics=summary_metrics,
        )
        evidence = EvidenceService.build(
            source_data=source_data,
            data_coverage=data_coverage,
            business_context=context["business_context"],
            reconciliation_cards=context["reconciliation_cards"],
            ai_interpretation=ai_interpretation,
            raw_evidence=raw_evidence,
        )
        return {
            **context,
            "executive_summary": summary,
            "evidence": evidence,
        }
