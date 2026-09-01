from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from services.demo_tenant_service import load_demo_tenant


@dataclass(frozen=True)
class DemoAskResult:
    answer: str
    intent: str
    supported: bool
    provenance: tuple[Mapping[str, Any], ...]
    facts: tuple[Mapping[str, Any], ...]
    unknowns: tuple[str, ...] = ()


class DemoAskNexoraService:
    """Fail-closed answers from the isolated certified demonstration dataset."""

    SOURCE_TYPE = "synthetic_demonstration_evidence"

    def ask(self, question: str, *, organization_id: str) -> DemoAskResult:
        payload = load_demo_tenant(organization_id)
        intent = self._intent(question)
        if intent == "attention":
            return self._attention(payload)
        if intent == "value":
            return self._value(payload)
        return DemoAskResult(
            answer="UNKNOWN — the certified demonstration evidence does not support this question.",
            intent="unknown",
            supported=False,
            provenance=(),
            facts=(),
            unknowns=("No certified Sample Enterprise answer rule matched the question.",),
        )

    @staticmethod
    def _intent(question: str) -> str:
        normalized = " ".join(str(question or "").casefold().split())
        attention_terms = (
            "requires my attention",
            "require my attention",
            "needs my attention",
            "need my attention",
            "leadership decision",
            "executive decision",
        )
        if any(term in normalized for term in attention_terms):
            return "attention"
        if any(term in normalized for term in ("saving", "opportunity", "realized value")):
            return "value"
        return "unknown"

    def _attention(self, payload: Mapping[str, Any]) -> DemoAskResult:
        decisions = tuple(payload.get("decisions") or ())
        facts = tuple(
            {
                "decision_id": item["id"],
                "title": item["title"],
                "status": item["status"],
                "business_service": item["business_service"],
                "financial_impact": item.get("financial_impact"),
                "confidence": item.get("confidence"),
                "evidence_coverage": item.get("evidence_coverage"),
            }
            for item in decisions
        )
        lines = [
            f"{item['id']} — {item['title']} ({item['status'].replace('_', ' ').lower()}); "
            f"business service: {item['business_service']}."
            for item in decisions
        ]
        pending = int((payload.get("metrics") or {}).get("pending_decisions") or len(decisions))
        answer = (
            "Certified Sample Enterprise demonstration evidence shows "
            f"{pending} leadership decisions require attention. "
            + " ".join(lines)
        )
        return DemoAskResult(
            answer=answer,
            intent="attention",
            supported=True,
            provenance=self._provenance(payload, decisions),
            facts=facts,
            unknowns=(
                (
                    "The dataset reports four pending decisions but provides three "
                    "detailed decision records."
                ),
            )
            if pending != len(decisions)
            else (),
        )

    def _value(self, payload: Mapping[str, Any]) -> DemoAskResult:
        metrics = payload.get("metrics") or {}
        identified = float(metrics.get("identified_savings") or 0)
        realized = float(metrics.get("verified_realized_savings") or 0)
        facts = (
            {"metric": "identified_savings", "value": identified},
            {"metric": "verified_realized_savings", "value": realized},
        )
        return DemoAskResult(
            answer=(
                "Certified Sample Enterprise demonstration evidence identifies "
                f"${identified / 1_000_000:.1f}M of qualified opportunity, not booked savings. "
                f"${realized / 1_000_000:.1f}M is verified as realized value."
            ),
            intent="value",
            supported=True,
            provenance=self._provenance(payload, facts),
            facts=facts,
        )

    def _provenance(
        self, payload: Mapping[str, Any], records: tuple[Mapping[str, Any], ...]
    ) -> tuple[Mapping[str, Any], ...]:
        base = {
            "type": self.SOURCE_TYPE,
            "classification": payload["classification"],
            "organization_id": payload["organization_id"],
            "source": payload["source"],
            "as_of": payload["as_of"],
        }
        return tuple({**base, "record": dict(record)} for record in records)
