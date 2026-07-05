from __future__ import annotations

from typing import Any

from services.enterprise_financial_model import EnterpriseFinancialModel
from services.platform.formatting import format_currency, format_percent, safe_float


class ReconciliationService:
    """Shared adapter for canonical Enterprise Financial Model reconciliation."""

    @staticmethod
    def get_status_cards() -> dict[str, Any]:
        summary = EnterpriseFinancialModel.get_enterprise_summary()
        reconciliation = EnterpriseFinancialModel.get_reconciliation_status()
        coverage = safe_float(reconciliation.get("allocation_coverage"))
        status = reconciliation.get("status") or "Unknown"
        return {
            "status": status,
            "allocation_coverage": coverage,
            "allocation_coverage_display": format_percent(coverage),
            "allocated_spend": safe_float(summary.get("allocated_spend")),
            "allocated_spend_display": format_currency(summary.get("allocated_spend")),
            "unallocated_spend": safe_float(summary.get("unallocated_spend")),
            "unallocated_spend_display": format_currency(summary.get("unallocated_spend")),
            "enterprise_total": safe_float(summary.get("enterprise_total")),
            "enterprise_total_display": format_currency(summary.get("enterprise_total")),
            "variance_status": status,
            "generated_at": summary.get("generated_at") or "Unknown",
            "summary": summary,
            "reconciliation": reconciliation,
        }

    @staticmethod
    def evidence_rows(cards: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"Metric": "Data Reconciliation Status", "Value": cards.get("status", "Unknown")},
            {"Metric": "Allocation Coverage", "Value": cards.get("allocation_coverage_display", "0.0%")},
            {"Metric": "Allocated Spend", "Value": cards.get("allocated_spend_display", "$0")},
            {"Metric": "Unallocated Spend", "Value": cards.get("unallocated_spend_display", "$0")},
            {"Metric": "Enterprise Total", "Value": cards.get("enterprise_total_display", "$0")},
            {"Metric": "Variance Status", "Value": cards.get("variance_status", "Unknown")},
        ]
