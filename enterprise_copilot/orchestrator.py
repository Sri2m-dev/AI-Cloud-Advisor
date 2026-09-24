from __future__ import annotations

from dataclasses import replace
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
from enterprise_copilot.providers import ProviderResult, default_providers
from enterprise_copilot.router import route_intent
from enterprise_copilot.semantic_planner import (
    CapabilityDescriptor,
    SemanticPlanError,
    execute_semantic_plan,
    validate_semantic_plan,
)
from enterprise_intelligence import SearchRequest
from universal_evidence.pilot.governed_intelligence import AskState


class EnterpriseAIOrchestrator:
    """Policy -> route -> retrieve -> ground -> provider -> cited response."""

    def __init__(
        self,
        *,
        search,
        intelligence,
        providers=None,
        scenario_service=None,
        governed_ask=None,
        source_capabilities=None,
        enterprise_capabilities=None,
    ):
        self.search = search
        self.intelligence = intelligence
        self.providers = providers or default_providers()
        self.scenario_service = scenario_service
        self.governed_ask = governed_ask
        self.source_capabilities = source_capabilities
        self.enterprise_capabilities = enterprise_capabilities

    def explain_scenario(self, request: CopilotRequest, scenario_request) -> CopilotResponse:
        """Explain an explicit ScenarioRequest without silently changing its inputs."""

        started = perf_counter()
        if self.scenario_service is None:
            raise RuntimeError("ScenarioService is not configured")
        if request.tenant_context != scenario_request.tenant_context:
            raise PermissionError("copilot scenario crosses tenant boundary")
        if request.persona != self.intelligence.role:
            raise PermissionError("copilot persona does not match authorization scope")
        result = self.scenario_service.simulate(scenario_request)
        answer = (
            f"SIMULATION — NOT AUTHORIZATION. {result.subject['name']} has "
            f"{len(result.impacted_entities)} governed downstream impact(s). "
            f"Baseline spend {result.financial_impact['baseline_spend']}; simulated spend "
            f"{result.financial_impact['simulated_spend']}. "
            f"Assumptions: {dict(result.assumptions)}. Unknowns: {result.unknowns or ('none',)}."
        )
        return CopilotResponse(
            CopilotResponse.identifier(),
            answer,
            "scenario",
            None,
            (),
            result.confidence,
            None,
            ("scenario_analysis_only",),
            "deterministic",
            False,
            False,
            {
                "latency_ms": (perf_counter() - started) * 1000,
                "scenario_id": result.scenario_id,
                "authoritative": False,
            },
            CopilotResponse.now(),
        )

    def ask(self, request: CopilotRequest) -> CopilotResponse:
        started = perf_counter()
        if request.tenant_context != self.intelligence.context:
            raise PermissionError("copilot request crosses tenant boundary")
        allowed, decision = evaluate_prompt(request.prompt, request.persona)
        if request.persona != self.intelligence.role:
            raise PermissionError("copilot persona does not match authorization scope")
        if not allowed:
            return self._blocked(request, decision, started)
        provider = self.providers.get(request.provider)
        if provider is None:
            raise ValueError("unknown AI provider")
        if request.provider != "mock" and hasattr(provider, "plan"):
            return self._semantic_ask(request, provider, decision, started)
        if self.governed_ask is not None and self._is_governed_question(request.prompt):
            governed = self.governed_ask.ask(
                request.prompt,
                scope=request.tenant_context,
                actor_id=request.session_id,
            )
            return self._governed_response(request, governed, started)
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
        context = self._ground(intent, response.results, request.prompt)
        grounding_ms = (perf_counter() - retrieval_started) * 1000
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

    def _semantic_ask(self, request, provider, decision, started):
        catalogue = (
            CapabilityDescriptor(
                "enterprise_search",
                "Governed enterprise search",
                "enterprise",
                (),
                ("lifecycle", "classification_state", "owner_state", "shortcut"),
                ("SEARCH",),
                ("lifecycle", "classification_state", "owner_state", "shortcut"),
                False,
                False,
                request.persona,
                "missing or unsupported evidence remains UNKNOWN",
                "search results retain governed source and provenance references",
                parameters=("query", "result_limit"),
            ),
        )
        handlers = {"enterprise_search": self._search_handler(request, None)}
        if self.enterprise_capabilities is not None:
            catalogue += self.enterprise_capabilities.catalogue()
            handlers.update(self.enterprise_capabilities.handlers())
        if self.source_capabilities is not None:
            catalogue += self.source_capabilities.catalogue()
            handlers.update(self.source_capabilities.handlers())
        payload = provider.plan(
            question=request.prompt,
            catalogue=catalogue,
            scope=request.tenant_context,
            conversation=request.conversation,
        )
        try:
            plan = validate_semantic_plan(
                payload,
                catalogue=catalogue,
                scope=request.tenant_context,
                role=request.persona,
            )
            results = execute_semantic_plan(
                plan,
                handlers={**handlers, "enterprise_search": self._search_handler(request, plan)},
            )
        except (SemanticPlanError, PermissionError) as error:
            return CopilotResponse(
                CopilotResponse.identifier(),
                "I cannot certify an answer from the requested governed plan. "
                "UNKNOWN remains UNKNOWN.",
                "unknown",
                None,
                (),
                None,
                None,
                (decision, f"semantic_plan:{type(error).__name__}"),
                provider.name,
                True,
                True,
                {"latency_ms": (perf_counter() - started) * 1000, "semantic_plan": "rejected"},
                CopilotResponse.now(),
            )
        search_results = tuple(
            result for response in results for result in getattr(response, "results", ())
        )
        context = self._ground(plan.interpretation, search_results, request.prompt)
        authority_results = tuple(result for result in results if isinstance(result, dict))
        context = self._with_authority_evidence(context, authority_results)
        supported = bool(search_results) or any(
            result.get("availability") in {"AVAILABLE", "PARTIAL"}
            and (result.get("records") or result.get("count") is not None)
            for result in authority_results
        )
        generated = (
            ProviderResult("UNKNOWN. " + " ".join(context.unknowns))
            if authority_results and not supported
            else provider.generate(
                system_prompt=system_prompt() + " Report supplied deterministic totals and ranks; "
                "do not calculate allocations, totals or rankings from context.",
                context=context,
            )
        )
        answer = generated.text
        if authority_results and context.unknowns:
            answer += " Unknowns: " + "; ".join(context.unknowns)
        if context.evidence.citations:
            answer += " " + " ".join(f"[{item.citation_id}]" for item in context.evidence.citations)
        confidence = min(
            (item.confidence for item in context.evidence.citations if item.confidence is not None),
            default=None,
        )
        return CopilotResponse(
            CopilotResponse.identifier(),
            answer,
            plan.interpretation,
            context,
            context.evidence.citations,
            confidence,
            generated.model_confidence,
            (decision, "semantic_plan:validated"),
            provider.name,
            False,
            not supported,
            {
                "latency_ms": (perf_counter() - started) * 1000,
                "semantic_plan": "validated",
                "plan_steps": len(plan.steps),
                "input_tokens": generated.input_tokens,
                "output_tokens": generated.output_tokens,
            },
            CopilotResponse.now(),
        )

    @staticmethod
    def _with_authority_evidence(context, results):
        facts, citations, unknowns = (
            list(context.evidence.facts),
            list(context.evidence.citations),
            list(context.unknowns),
        )
        for index, result in enumerate(results):
            ids = []
            for offset, reference in enumerate(result.get("evidence_references", ())[:25]):
                identifier = f"A{index}_{offset}"
                ids.append(identifier)
                citations.append(
                    CopilotCitation(
                        identifier,
                        "governed_authority",
                        reference,
                        result["capability"],
                        None,
                        result["availability"],
                    )
                )
            facts.append(
                {
                    "capability": result["capability"],
                    "availability": result["availability"],
                    "records": result.get("records", ()),
                    "count": result.get("count"),
                    "citation_ids": tuple(ids),
                }
            )
            unknowns.extend(result.get("unknowns", ()))
        return replace(
            context,
            evidence=CopilotEvidence(tuple(facts), context.evidence.derived, tuple(citations)),
            unknowns=tuple(unknowns),
        )

    def _search_handler(self, request, plan):
        def execute(*, operation, parameters, dependencies, scope, constraints):
            if dependencies:
                raise SemanticPlanError("search dependency execution is unsupported")
            if operation != "SEARCH" or scope != request.tenant_context:
                raise PermissionError("semantic search scope is not authorized")
            query = parameters.get("query") or request.prompt
            filters = {}
            for item in constraints["filters"]:
                if item.get("operator") != "EQUALS":
                    raise SemanticPlanError("only equality filters are supported")
                filters[str(item["dimension"])] = item.get("value")
            return self.search.search(
                SearchRequest(
                    request.tenant_context,
                    str(query),
                    result_limit=parameters.get("result_limit") or 5,
                    filters=filters,
                    include_classification=True,
                    include_financial=True,
                    include_relationships=True,
                    include_evidence=request.persona in {"super_admin", "client_admin", "auditor"},
                    authorization_scope=request.persona,
                )
            )

        return execute

    @staticmethod
    def _is_governed_question(prompt: str) -> bool:
        text = str(prompt or "").casefold()
        return any(
            term in text
            for term in (
                "who owns",
                "owner",
                "cost centre",
                "cost center",
                "depend",
                "what applications",
                "sources describe",
                "provenance",
                "total cost",
                "governed records",
                "cost by service",
                "spend",
                "saving",
                "optimization",
                "source health",
                "unresolved",
                "conflict",
                "impact",
            )
        )

    @staticmethod
    def _governed_response(request, governed, started):
        citations = tuple(
            CopilotCitation(
                f"G{index}",
                str(item.get("type", "governed_evidence")),
                str(item.get("canonical_id", item.get("relationship", "governed"))),
                "ACT-008 governed evidence",
                1.0 if governed.state is AskState.SUPPORTED else None,
                governed.state.value,
            )
            for index, item in enumerate(governed.citations, 1)
        )
        return CopilotResponse(
            CopilotResponse.identifier(),
            governed.answer,
            governed.question_class,
            None,
            citations,
            1.0 if governed.state is AskState.SUPPORTED else None,
            None,
            (f"ACT-008:{governed.state.value}",),
            "deterministic-governed",
            governed.state is AskState.BLOCKED,
            governed.state is AskState.UNSUPPORTED,
            {
                "latency_ms": (perf_counter() - started) * 1000,
                "governed_state": governed.state.value,
                "answer_fingerprint": governed.answer_fingerprint,
                "canonical_result_fingerprint": getattr(
                    getattr(governed, "canonical_result", None), "fingerprint", None
                ),
            },
            CopilotResponse.now(),
        )

    @staticmethod
    def _ground(intent, results, question=""):
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
            question,
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
