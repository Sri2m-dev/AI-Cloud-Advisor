from __future__ import annotations

from time import perf_counter

from enterprise_copilot.models import (
    CopilotCitation,
    CopilotContext,
    CopilotEvidence,
    CopilotRequest,
    CopilotResponse,
)
from enterprise_copilot.policy import POLICY_VERSION, evaluate_prompt
from enterprise_copilot.prompts import prompt as system_prompt
from enterprise_copilot.providers import default_providers
from enterprise_copilot.router import route_intent
from enterprise_intelligence import SearchRequest


class EnterpriseAIOrchestrator:
    """Policy -> route -> retrieve -> ground -> provider -> cited response."""

    def __init__(self, *, search, intelligence, providers=None):
        self.search = search
        self.intelligence = intelligence
        self.providers = providers or default_providers()

    def ask(self, request: CopilotRequest) -> CopilotResponse:
        started = perf_counter()
        if request.tenant_context != self.intelligence.context:
            raise PermissionError("copilot request crosses tenant boundary")
        allowed, decision = evaluate_prompt(request.prompt, request.persona)
        if request.persona != self.intelligence.role:
            raise PermissionError("copilot persona does not match authorization scope")
        if not allowed:
            return self._blocked(request, decision, started)
        intent, routing_ms = route_intent(request.prompt)
        retrieval_started = perf_counter()
        response = self.search.search(
            SearchRequest(
                request.tenant_context,
                request.prompt,
                result_limit=5,
                include_classification=True,
                include_financial=intent == "financial",
                include_relationships=intent in {"dependency", "change"},
                include_evidence=request.persona in {"super_admin", "client_admin", "auditor"},
                authorization_scope=request.persona,
            )
        )
        if not response.results:
            # Exact identifiers and names are often embedded in natural questions.
            tokens = [token.strip("?,.!:;()") for token in request.prompt.split()]
            for token in sorted(tokens, key=len, reverse=True):
                if len(token) < 3:
                    continue
                response = self.search.search(
                    SearchRequest(
                        request.tenant_context,
                        token,
                        result_limit=5,
                        include_classification=True,
                        include_financial=intent == "financial",
                        include_relationships=intent in {"dependency", "change"},
                        include_evidence=request.persona
                        in {"super_admin", "client_admin", "auditor"},
                        authorization_scope=request.persona,
                    )
                )
                if response.results:
                    break
        retrieval_ms = (perf_counter() - retrieval_started) * 1000
        context = self._ground(intent, response.results)
        grounding_ms = (perf_counter() - retrieval_started) * 1000
        provider = self.providers.get(request.provider)
        if provider is None:
            raise ValueError("unknown AI provider")
        generated = provider.generate(system_prompt=system_prompt(), context=context)
        answer = generated.text
        citations = context.evidence.citations
        if citations:
            answer += " " + " ".join(f"[{item.citation_id}]" for item in citations)
        confidence = min(
            (item.confidence for item in citations if item.confidence is not None),
            default=None,
        )
        return CopilotResponse(
            CopilotResponse.identifier(),
            answer,
            intent,
            context,
            citations,
            confidence,
            generated.model_confidence,
            (decision,),
            provider.name,
            False,
            intent == "unknown",
            {
                "latency_ms": (perf_counter() - started) * 1000,
                "routing_ms": routing_ms,
                "retrieval_ms": retrieval_ms,
                "grounding_ms": grounding_ms,
                "input_tokens": generated.input_tokens,
                "output_tokens": generated.output_tokens,
                "citations_used": len(citations),
                "policy_blocks": 0,
            },
            CopilotResponse.now(),
        )

    @staticmethod
    def _ground(intent, results):
        entities, citations, facts, unknowns = [], [], [], []
        for index, result in enumerate(results, 1):
            citation = CopilotCitation(
                f"C{index}",
                "canonical_entity",
                result.canonical_id,
                result.match_reason,
                result.confidence,
                result.freshness,
            )
            citations.append(citation)
            if result.financial_summary:
                citations.append(
                    CopilotCitation(
                        f"F{index}",
                        "financial_context",
                        result.canonical_id,
                        "Authoritative Financial Data Fabric context",
                        1.0,
                        result.freshness,
                    )
                )
            if result.relationship_summary:
                citations.append(
                    CopilotCitation(
                        f"R{index}",
                        "relationship_context",
                        result.canonical_id,
                        "Governed relationship projection",
                        result.confidence,
                        result.freshness,
                    )
                )
            entities.append(
                {
                    "canonical_id": result.canonical_id,
                    "display_name": result.display_name,
                    "entity_type": result.entity_type,
                    "classification_state": result.classification_state,
                    "financial_summary": dict(result.financial_summary),
                    "relationship_summary": dict(result.relationship_summary),
                }
            )
            facts.append(
                {
                    "citation_id": citation.citation_id,
                    "source": result.source_reference,
                    "canonical_id": result.canonical_id,
                    "name": result.display_name,
                }
            )
            if not result.owner:
                unknowns.append(f"{result.canonical_id}: owner UNKNOWN")
            if not result.business_context:
                unknowns.append(f"{result.canonical_id}: business context UNKNOWN")
        return CopilotContext(
            intent,
            tuple(entities),
            CopilotEvidence(tuple(facts), (), tuple(citations)),
            tuple(unknowns),
            POLICY_VERSION,
        )

    @staticmethod
    def _blocked(request, decision, started):
        return CopilotResponse(
            CopilotResponse.identifier(),
            "Request blocked by read-only Copilot policy.",
            "blocked",
            None,
            (),
            None,
            None,
            (decision,),
            request.provider,
            True,
            False,
            {"latency_ms": (perf_counter() - started) * 1000, "policy_blocks": 1},
            CopilotResponse.now(),
        )
