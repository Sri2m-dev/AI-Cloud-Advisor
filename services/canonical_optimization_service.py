"""Bounded production consumers of canonical CMP-P2 optimization authority."""

from __future__ import annotations

from universal_evidence.optimization.production import configured_optimization_authority


class CanonicalOptimizationService:
    def __init__(self, repository=None):
        self.repository = repository or configured_optimization_authority()[1]

    def savings_governance(self, context):
        return self.repository.savings_summary(context)

    def executive_summary(self, context):
        summary = self.repository.savings_summary(context)
        return {
            "opportunity_count": summary["opportunity_count"],
            "governed_potential_savings": summary["potential_by_currency"],
            "governed_approved_savings": summary["approved_by_currency"],
            "governed_implemented_savings": summary["implemented_by_currency"],
            "governed_realized_savings": summary["realized_by_currency"],
        }

    def ask(self, context, intent):
        summary = self.repository.savings_summary(context)
        answers = {
            "where_can_we_save": self.repository.list(context),
            "potential_savings": summary["potential_by_currency"],
            "approved_savings": summary["approved_by_currency"],
            "realized_savings": summary["realized_by_currency"],
        }
        if intent not in answers:
            raise ValueError("unsupported bounded optimization intent")
        return answers[intent]

    def rejected(self, context):
        return tuple(
            item for item in self.repository.list(context) if item.state.value == "REJECTED"
        )

    def explain(self, context, opportunity_id):
        item = next(
            (row for row in self.repository.list(context) if row.opportunity_id == opportunity_id),
            None,
        )
        if item is None:
            raise LookupError("opportunity is unavailable in tenant scope")
        return {
            "opportunity_id": item.opportunity_id,
            "recommendation": item.recommendation,
            "calculation_model": item.calculation_model or "UNKNOWN",
            "calculation_inputs": item.calculation_inputs,
            "evidence_references": item.evidence_references,
            "confidence": item.confidence_score,
            "state": item.state.value,
        }
