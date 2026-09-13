from __future__ import annotations

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
from shared.prospect_answers import prospect_evidence_answer
from universal_evidence.product_closure import answer_document_question


class ProspectSemanticAskService:
    """Plan and answer only from the admitted prospect analysis contract."""

    @staticmethod
    def catalogue(
        analysis: Any, role: str, closure: Any | None = None
    ) -> tuple[CapabilityDescriptor, ...]:
        if analysis is None and closure is not None:
            return (
                CapabilityDescriptor(
                    "prospect_documents",
                    "Admitted prospect document evidence",
                    "prospect_evidence",
                    (),
                    ("document", "license"),
                    ("ANSWER",),
                    ("document", "license"),
                    False,
                    False,
                    role,
                    "missing document evidence remains UNKNOWN",
                    "document closure provenance is retained",
                ),
                CapabilityDescriptor(
                    "prospect_unknown",
                    "Explicit unsupported prospect evidence boundary",
                    "prospect_evidence",
                    (),
                    (),
                    ("UNKNOWN",),
                    (),
                    False,
                    False,
                    role,
                    "the answer remains UNKNOWN",
                    "no unsupported evidence is asserted",
                ),
            )
        dimensions = ["record_count", "coverage"]
        measures = ["row_count", "evidence_coverage"]
        if not getattr(analysis, "currency_resolution_required", True):
            dimensions.extend(("currency", "total_spend", "opportunity"))
            measures.extend(("total_spend", "opportunity_evidence_qualified"))
        return (
            CapabilityDescriptor(
                "prospect_analysis",
                "Admitted prospect aggregate analysis",
                "prospect_evidence",
                tuple(measures),
                tuple(dimensions),
                ("ANSWER",),
                tuple(dimensions),
                False,
                False,
                role,
                "missing dimensions remain UNKNOWN",
                "analysis fingerprint and admission provenance are retained",
            ),
            CapabilityDescriptor(
                "prospect_unknown",
                "Explicit unsupported prospect evidence boundary",
                "prospect_evidence",
                (),
                (),
                ("UNKNOWN",),
                (),
                False,
                False,
                role,
                "the answer remains UNKNOWN",
                "no unsupported evidence is asserted",
            ),
        )

    def ask(
        self,
        question: str,
        *,
        analysis: Any,
        closure: Any | None = None,
        admission: Any | None,
        organization_id: str,
        role: str,
        provider,
        conversation: tuple[Mapping[str, str], ...] = (),
    ):
        analysis_tenant = str(getattr(analysis, "tenant_id", "") or "")
        if analysis_tenant and analysis_tenant != organization_id:
            raise PermissionError("prospect semantic scope does not match admitted analysis")
        admission_tenant = str(
            getattr(getattr(admission, "scope", None), "prospect_id", "") or ""
        )
        if admission_tenant and admission_tenant != organization_id:
            raise PermissionError("prospect semantic scope does not match admission")
        scope = TenantContext(organization_id, organization_id)
        catalogue = self.catalogue(analysis, role, closure)
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
        results = execute_semantic_plan(
            plan,
            handlers={
                "prospect_analysis": self._analysis_handler(
                    question, analysis, admission
                ),
                "prospect_documents": self._document_handler(question, closure),
                "prospect_unknown": self._unknown_handler,
            },
        )
        facts = tuple(fact for result in results for fact in result["facts"])
        provenance = tuple(reference for result in results for reference in result["provenance"])
        unknowns = tuple(unknown for result in results for unknown in result["unknowns"])
        citations = tuple(
            CopilotCitation(
                f"P{index}",
                str(reference["type"]),
                str(reference["reference"]),
                "Admitted prospect evidence",
                reference.get("confidence"),
                str(reference.get("freshness", "CURRENT")),
            )
            for index, reference in enumerate(provenance, 1)
        )
        context = CopilotContext(
            plan.interpretation,
            facts,
            CopilotEvidence(facts, (), citations),
            unknowns,
            "PROSPECT_ADMITTED_EVIDENCE",
            question,
        )
        generated = provider.generate(system_prompt=system_prompt(), context=context)
        answer = generated.text
        if unknowns:
            answer += " Unknowns: " + "; ".join(unknowns)
        supported = any(
            bool(fact.get("supported")) for fact in facts if isinstance(fact, Mapping)
        )
        return {
            "answer": answer,
            "supported": supported,
            "provenance": provenance,
            "facts": facts,
            "unknowns": unknowns,
            "plan": plan,
            "context": context,
        }

    @staticmethod
    def _document_handler(question, closure):
        def handler(*, operation, parameters, dependencies, scope, constraints):
            del parameters, dependencies, scope, constraints
            if operation != "ANSWER" or closure is None:
                raise SemanticPlanError("unsupported prospect document operation")
            answer, provenance = answer_document_question(question, closure)
            if answer is None:
                return {
                    "facts": (),
                    "provenance": (),
                    "unknowns": ("The admitted documents do not support this conclusion.",),
                }
            return {
                "facts": ({"answer": answer, "supported": True},),
                "provenance": tuple(
                    {
                        "type": str(item.get("type", "admitted_document")),
                        "reference": str(item.get("reference", "document")),
                        "confidence": item.get("confidence"),
                        "freshness": str(item.get("as_of", "CURRENT")),
                    }
                    for item in provenance
                ),
                "unknowns": (),
            }

        return handler

    @staticmethod
    def _analysis_handler(question, analysis, admission):
        def handler(*, operation, parameters, dependencies, scope, constraints):
            del parameters, dependencies, scope, constraints
            if operation != "ANSWER":
                raise SemanticPlanError("unsupported prospect operation")
            answer = prospect_evidence_answer(question, analysis)
            supported = not answer.startswith("UNKNOWN")
            fingerprint = str(
                getattr(admission, "fingerprint", None)
                or getattr(analysis, "audit_id", "prospect-analysis")
            )
            return {
                "facts": ({"answer": answer, "supported": supported},),
                "provenance": (
                    {
                        "type": "admitted_prospect_analysis",
                        "reference": fingerprint,
                        "confidence": getattr(analysis, "confidence", None),
                        "freshness": "CURRENT",
                    },
                ),
                "unknowns": () if supported else (answer,),
            }

        return handler

    @staticmethod
    def _unknown_handler(*, operation, parameters, dependencies, scope, constraints):
        del parameters, dependencies, scope, constraints
        if operation != "UNKNOWN":
            raise SemanticPlanError("unsupported prospect operation")
        return {
            "facts": (),
            "provenance": (),
            "unknowns": ("The admitted prospect evidence does not support this conclusion.",),
        }
