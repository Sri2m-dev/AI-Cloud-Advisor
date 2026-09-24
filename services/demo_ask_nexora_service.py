from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from data_fabric.foundation import TenantContext
from enterprise_copilot.models import CopilotCitation, CopilotContext, CopilotEvidence
from enterprise_copilot.prompts import prompt as system_prompt
from enterprise_copilot.semantic_planner import (
    CapabilityDescriptor,
    SemanticPlanError,
    execute_semantic_plan,
    validate_semantic_plan,
)
from services.demo_tenant_service import DEMO_ORGANIZATION_ID, DemoTenantError, load_demo_tenant


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

    def __init__(self, *, enterprise_capabilities=None):
        self.enterprise_capabilities = enterprise_capabilities

    @staticmethod
    def semantic_catalogue(role: str) -> tuple[CapabilityDescriptor, ...]:
        return (
            CapabilityDescriptor(
                "demo_decisions",
                "Synthetic decision evidence",
                "governance",
                (),
                ("business_service", "status"),
                ("LIST_ATTENTION",),
                ("business_service", "status"),
                False,
                False,
                role,
                "missing decision evidence remains UNKNOWN",
                "decision records retain synthetic source provenance",
                parameters=("query", "result_limit"),
            ),
            CapabilityDescriptor(
                "demo_savings",
                "Synthetic savings evidence",
                "financial",
                ("identified_savings", "qualified_savings", "verified_value"),
                ("stage",),
                ("SUM_SAVINGS",),
                ("stage",),
                True,
                False,
                role,
                "unqualified or missing savings evidence remains UNKNOWN",
                "savings stages retain synthetic source provenance and qualification",
                parameters=("query", "result_limit"),
            ),
            CapabilityDescriptor(
                "demo_service_health",
                "Synthetic business service health",
                "risk",
                ("health",),
                ("service", "risk"),
                ("RANK_RISK",),
                ("service", "risk"),
                True,
                False,
                role,
                "missing service health remains UNKNOWN",
                "health records retain synthetic source provenance",
                parameters=("query", "result_limit"),
            ),
            CapabilityDescriptor(
                "demo_evidence",
                "Synthetic governed evidence retrieval",
                "evidence",
                (),
                ("record_type", "source"),
                ("RETRIEVE_EVIDENCE",),
                ("record_type", "source"),
                False,
                False,
                role,
                "absent evidence remains UNKNOWN",
                "retrieved records retain synthetic source provenance",
                parameters=("query", "result_limit"),
            ),
            CapabilityDescriptor(
                "demo_unknown",
                "Explicit unsupported or insufficient evidence boundary",
                "governance",
                (),
                (),
                ("UNKNOWN",),
                (),
                False,
                False,
                role,
                "the answer remains UNKNOWN",
                "no evidence is asserted",
            ),
        )

    def ask_semantic(self, question, *, organization_id, role, provider, conversation=()):
        payload = load_demo_tenant(organization_id)
        if organization_id not in (DEMO_ORGANIZATION_ID, payload["organization_id"]):
            raise DemoTenantError("demonstration authority is outside the active tenant scope")
        scope = TenantContext(organization_id, organization_id)
        catalogue = self.semantic_catalogue(role)
        if self.enterprise_capabilities is not None:
            if (
                self.enterprise_capabilities.context != scope
                or self.enterprise_capabilities.role != role
            ):
                raise PermissionError("Enterprise authority is outside the active demo scope")
            catalogue += self.enterprise_capabilities.catalogue()
        try:
            plan = validate_semantic_plan(
                provider.plan(
                    question=question,
                    catalogue=catalogue,
                    scope=scope,
                    conversation=conversation,
                ),
                catalogue=catalogue,
                scope=scope,
                role=role,
            )
        except (SemanticPlanError, PermissionError):
            unknown = (
                "I cannot certify an answer from the requested governed plan. "
                "UNKNOWN remains UNKNOWN."
            )
            return DemoAskResult(
                answer=unknown,
                intent="unknown",
                supported=False,
                provenance=(),
                facts=(),
                unknowns=(unknown,),
            )
        handlers = {
            "demo_decisions": self._semantic_handler(payload, self._attention),
            "demo_savings": self._semantic_handler(payload, self._value),
            "demo_service_health": self._semantic_handler(payload, self._service_risk),
            "demo_evidence": self._evidence_handler(payload),
            "demo_unknown": self._unknown_handler,
        }
        if self.enterprise_capabilities is not None:
            handlers.update(self.enterprise_capabilities.handlers())
        try:
            results = execute_semantic_plan(plan, handlers=handlers)
        except (SemanticPlanError, PermissionError):
            return DemoAskResult(
                answer="The requested governed execution is unsupported. UNKNOWN remains UNKNOWN.",
                intent="unknown",
                supported=False,
                provenance=(),
                facts=(),
                unknowns=("The requested governed execution is unsupported.",),
            )
        facts = tuple(
            fact for result in results for fact in result.get("facts", result.get("records", ()))
        )
        provenance = tuple(
            reference
            for result in results
            for reference in result.get(
                "provenance",
                tuple(
                    {
                        "type": "canonical_enterprise_evidence",
                        "source": ref,
                        "organization_id": organization_id,
                        "tenant_id": scope.tenant_id,
                    }
                    for ref in result.get("evidence_references", ())
                ),
            )
        )
        unknowns = tuple(unknown for result in results for unknown in result.get("unknowns", ()))
        citations = tuple(
            CopilotCitation(
                f"D{index}",
                str(reference.get("type", self.SOURCE_TYPE)),
                str(reference.get("record", {}).get("id", reference.get("source", "synthetic"))),
                str(reference.get("type", self.SOURCE_TYPE)),
                1.0,
                str(reference.get("as_of", "CURRENT")),
            )
            for index, reference in enumerate(provenance, 1)
        )
        context = CopilotContext(
            plan.interpretation,
            facts,
            CopilotEvidence(facts, (), citations),
            unknowns,
            "SYNTHETIC_DEMO_GOVERNED",
            question,
        )
        answer = (
            provider.generate(
                system_prompt=system_prompt() + " Report supplied deterministic totals and ranks; "
                "do not calculate allocations, totals or rankings from context.",
                context=context,
            ).text
            if facts
            else "UNKNOWN: no governed evidence supports the requested conclusion."
        )
        if unknowns:
            answer += " Unknowns: " + "; ".join(unknowns)
        return DemoAskResult(
            answer=answer,
            intent=plan.interpretation,
            supported=bool(facts),
            provenance=provenance,
            facts=facts,
            unknowns=unknowns,
        )

    @staticmethod
    def _unknown_handler(*, operation, parameters, dependencies, scope, constraints):
        del parameters, dependencies, scope, constraints
        if operation != "UNKNOWN":
            raise SemanticPlanError("unsupported synthetic operation")
        return {
            "facts": (),
            "provenance": (),
            "unknowns": ("The synthetic evidence does not support this conclusion.",),
        }

    @staticmethod
    def _semantic_handler(payload, formatter):
        def handler(*, operation, parameters, dependencies, scope, constraints):
            del dependencies, scope
            if operation not in {"LIST_ATTENTION", "SUM_SAVINGS", "RANK_RISK"}:
                raise SemanticPlanError("unsupported synthetic operation")
            result = formatter(payload)
            facts = tuple(result.facts)
            filters = tuple(constraints.get("filters", ()))
            grouping = tuple(constraints.get("grouping", ()))
            allowed_dimensions = {
                "business_service": "business_service",
                "service": "service",
                "stage": "stage",
                "risk": "risk",
                "status": "status",
            }
            if any(item.get("dimension") not in allowed_dimensions for item in filters):
                raise SemanticPlanError("unsupported synthetic filter")
            if any(dimension not in allowed_dimensions for dimension in grouping):
                raise SemanticPlanError("unsupported synthetic grouping")
            for item in filters:
                key = allowed_dimensions[item["dimension"]]
                facts = tuple(
                    fact for fact in facts if str(fact.get(key)) == str(item.get("value"))
                )
            if grouping:
                evidenced_facts = tuple(
                    fact for fact in facts if all(dimension in fact for dimension in grouping)
                )
                if not evidenced_facts:
                    raise SemanticPlanError("synthetic grouping is not evidenced")
                facts = evidenced_facts
            return {
                "facts": facts,
                "provenance": tuple(
                    reference
                    for reference in result.provenance
                    if not filters
                    or all(
                        str(reference.get("record", {}).get(item["dimension"]))
                        == str(item.get("value"))
                        for item in filters
                    )
                ),
                "unknowns": result.unknowns
                if facts
                else ("The requested synthetic constraints have no governed evidence.",),
            }

        return handler

    def _evidence_handler(self, payload):
        def handler(*, operation, parameters, dependencies, scope, constraints):
            del parameters, dependencies, scope, constraints
            if operation != "RETRIEVE_EVIDENCE":
                raise SemanticPlanError("unsupported synthetic operation")
            records = tuple(dict(item) for item in payload.get("decisions", ()))
            return {
                "facts": records,
                "provenance": self._provenance(payload, records),
                "unknowns": (),
            }

        return handler

    def ask(self, question: str, *, organization_id: str) -> DemoAskResult:
        payload = load_demo_tenant(organization_id)
        if organization_id not in (DEMO_ORGANIZATION_ID, payload["organization_id"]):
            raise DemoTenantError("demonstration authority is outside the active tenant scope")
        intent = self._intent(question)
        if intent == "attention":
            return self._attention(payload)
        if intent == "value":
            return self._value(payload)
        if intent == "service_risk":
            return self._service_risk(payload)
        return self._unknown()

    @staticmethod
    def _unknown() -> DemoAskResult:
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
        words = set(re.findall(r"[a-z]+", normalized))
        # Forecasts and mixed requests must not be answered by a keyword match.
        if words & {"forecast", "predict", "prediction", "revenue", "exact", "guaranteed"}:
            return "unknown"
        if "will" in words or re.search(r"\bnext\s+(quarter|year|month)\b", normalized):
            return "unknown"
        service = bool(words & {"service", "services"})
        risk = bool(words & {"risk", "risks", "health", "intervention"})
        value = (
            bool(words & {"saving", "savings", "opportunity", "opportunities"})
            or (
                any(re.fullmatch(r"costs?|spend(?:ing)?", word) for word in words)
                and bool(words & {"reduce", "reduction", "cut", "lower", "optimize"})
            )
            or "realized value" in normalized
        )
        if service and risk:
            return "unknown" if value else "service_risk"
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
        if value:
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
            f"{pending} leadership decisions require attention. " + " ".join(lines)
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
        stages = {
            row["stage"]: row
            for row in (payload.get("analytics") or {}).get("savings_waterfall", ())
        }
        required = ("Identified", "Evidence qualified", "Verified realized")
        if any(stages.get(stage, {}).get("value") is None for stage in required):
            return self._unknown()
        identified, qualified, realized = (float(stages[stage]["value"]) for stage in required)
        decisions = tuple(
            dict(row)
            for row in payload.get("decisions", ())
            if row.get("type") == "portfolio_rationalization"
        )
        facts = tuple(dict(stages[stage]) for stage in required) + decisions
        opportunities = " ".join(
            f"{row['id']} — {row['title']}: "
            + (
                f"${float(row['financial_impact']) / 1_000_000:.1f}M opportunity"
                if row.get("financial_impact") is not None
                else "financial impact UNKNOWN"
            )
            + f"; status {row['status']}; business service {row['business_service']}."
            for row in decisions
        )
        return DemoAskResult(
            answer=(
                "Certified Sample Enterprise demonstration evidence identifies "
                f"${identified / 1_000_000:.1f}M annual identified opportunity, including "
                f"${qualified / 1_000_000:.1f}M evidence-qualified opportunity, "
                "not booked savings. "
                f"${realized / 1_000_000:.1f}M is verified as realized value."
                f" {opportunities} Quarterly timing and realizable amounts remain UNKNOWN; "
                "these annual opportunities are candidates for review, not a quarterly forecast."
            ),
            intent="value",
            supported=True,
            provenance=self._provenance(payload, facts),
            facts=facts,
            unknowns=("Quarter-specific timing and savings are not certified by this dataset.",),
        )

    def _service_risk(self, payload: Mapping[str, Any]) -> DemoAskResult:
        severity = {"Critical": 0, "High": 1, "Moderate": 2, "Controlled": 3}
        records = (payload.get("analytics") or {}).get("business_service_health", ())
        facts = tuple(
            sorted(
                (dict(row) for row in records if row.get("risk") in severity),
                key=lambda row: severity[row["risk"]],
            )
        )
        if not facts:
            return self._unknown()
        return DemoAskResult(
            answer=(
                "Certified Sample Enterprise demonstration evidence ranks the listed business "
                "services by recorded risk severity: "
                + " ".join(
                    f"{row['service']}: {row['risk']} risk; health {row.get('health', 'UNKNOWN')}."
                    for row in facts
                )
                + " This covers only the listed services, not a complete enterprise ranking. "
                "Financial loss and future service outcomes remain UNKNOWN."
            ),
            intent="service_risk",
            supported=True,
            provenance=self._provenance(payload, facts),
            facts=facts,
            unknowns=("No certified financial-loss estimate or future service outcome.",),
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
