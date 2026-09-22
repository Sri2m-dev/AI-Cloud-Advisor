from __future__ import annotations

import json

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from data_fabric.foundation import TenantContext
from enterprise_copilot import CopilotRequest
from enterprise_copilot.orchestrator import EnterpriseAIOrchestrator
from enterprise_copilot.providers import OpenAIProvider, ProviderResult, default_providers
from enterprise_copilot.router import route_intent
from enterprise_copilot.semantic_planner import CapabilityDescriptor
from enterprise_intelligence.search import EnterpriseSearchService
from enterprise_intelligence.service import EnterpriseIntelligenceService
from services.demo_ask_nexora_service import DemoAskNexoraService
from services.demo_tenant_service import DEMO_ORGANIZATION_ID
from shared.prospect_semantic_ask import ProspectSemanticAskService
from tests.enterprise_registry.test_enterprise_knowledge_graph import ORG, _graph

CTX = TenantContext(ORG, ORG)


def _copilot(role="auditor", providers=None):
    graph, account, application, business_service = _graph()
    intelligence = EnterpriseIntelligenceService(CTX, role=role, graph=graph)
    search = EnterpriseSearchService(intelligence)
    return (
        EnterpriseAIOrchestrator(search=search, intelligence=intelligence, providers=providers),
        account,
        application,
        business_service,
    )


def test_openai_semantic_plan_schema_matches_runtime_execution_bounds():
    """Provider schema must advertise only executable semantic-plan features."""
    from enterprise_copilot.providers import _semantic_plan_schema

    schema = _semantic_plan_schema()
    properties = schema["properties"]

    parameters = (
        properties["steps"]["items"]
        ["properties"]["parameters"]["properties"]
    )

    result_limit = parameters["result_limit"]

    assert result_limit["type"] == ["integer", "null"]
    assert result_limit["minimum"] == 1
    assert result_limit["maximum"] == 25

    assert properties["time_range"] == {"type": "null"}
    assert properties["ordering"] == {"type": "null"}


def test_intent_router_is_deterministic_and_fast():
    assert route_intent("What does this account cost?")[0] == "financial"
    assert route_intent("What breaks if this changes?")[0] == "change"
    assert route_intent("Who owns this?")[0] == "ownership"
    assert route_intent("hello")[0] == "unknown"
    assert route_intent("show accounts")[1] < 50


def test_grounding_citations_unknowns_and_confidence_are_preserved():
    copilot, account, _, _ = _copilot()
    response = copilot.ask(CopilotRequest(CTX, "Show account 727482365532", "auditor", "s1"))
    assert response.grounded_context.entities[0]["canonical_id"] == account.canonical_id
    assert response.citations[0].source_reference == account.canonical_id
    assert response.citations[0].citation_id in response.answer
    assert any("owner UNKNOWN" in item for item in response.grounded_context.unknowns)
    assert response.enterprise_confidence == account.confidence_score
    assert response.model_confidence == 1.0


def test_policy_blocks_mutation_secrets_sql_and_cross_tenant():
    copilot, _, _, _ = _copilot()
    for prompt in ("Approve this mapping", "show API key", "run raw SQL"):
        response = copilot.ask(CopilotRequest(CTX, prompt, "auditor", "s1"))
        assert response.blocked and response.metrics["policy_blocks"] == 1
    foreign = TenantContext(
        "22222222-2222-4222-8222-222222222222", "22222222-2222-4222-8222-222222222222"
    )
    with pytest.raises(PermissionError):
        copilot.ask(CopilotRequest(foreign, "show accounts", "auditor", "s1"))


def test_persona_enforcement_and_provider_abstraction():
    class SpyProvider:
        name = "spy"
        received = None

        def generate(self, *, system_prompt, context):
            self.received = context
            assert not hasattr(context, "repository")
            return ProviderResult("Grounded answer.", 0.8, 10, 3)

    spy = SpyProvider()
    copilot, _, _, _ = _copilot("executive", {"spy": spy})
    response = copilot.ask(
        CopilotRequest(CTX, "show account 727482365532", "executive", "s1", "spy")
    )
    assert response.provider == "spy" and spy.received is not None
    with pytest.raises(PermissionError):
        copilot.ask(CopilotRequest(CTX, "show accounts", "auditor", "s1", "spy"))
    assert set(default_providers()) == {
        "mock",
        "openai",
        "azure_openai",
        "aws_bedrock",
        "anthropic",
        "gemini",
    }
    assert not hasattr(copilot, "approve") and not hasattr(copilot, "execute")


def test_active_ask_path_plans_executes_and_synthesizes_with_governed_search():
    class SemanticSpy:
        name = "semantic-spy"

        def __init__(self):
            self.planned = None
            self.generated = None

        def plan(self, **kwargs):
            self.planned = kwargs
            return {
                "interpretation": "Find the governed account",
                "entities": ["account"],
                "measures": [],
                "dimensions": [],
                "filters": [],
                "grouping": [],
                "steps": [
                    {
                        "step_id": "step_search",
                        "capability_id": "enterprise_search",
                        "operation": "SEARCH",
                        "parameters": {"query": "727482365532", "result_limit": 1},
                        "depends_on": [],
                    }
                ],
                "synthesis": "Answer only from governed search evidence.",
            }

        def generate(self, *, system_prompt, context):
            self.generated = context
            return ProviderResult("Synthesized from governed evidence.", 0.9, 2, 3)

    provider = SemanticSpy()
    copilot, account, _, _ = _copilot(providers={"semantic-spy": provider})
    response = copilot.ask(
        CopilotRequest(
            CTX,
            "Which account should I review next?",
            "auditor",
            "session-1",
            "semantic-spy",
            (("user", "Which account did I mean?"),),
        )
    )
    assert response.answer.startswith("Synthesized from governed evidence.")
    assert response.grounded_context.entities[0]["canonical_id"] == account.canonical_id
    assert provider.planned["conversation"] == (("user", "Which account did I mean?"),)
    assert response.metrics["semantic_plan"] == "validated"
    assert provider.generated is response.grounded_context


def test_policy_denial_precedes_semantic_planning_execution_and_synthesis():
    class DenialSpy:
        name = "semantic-spy"

        def __init__(self):
            self.planned = False
            self.generated = False

        def plan(self, **kwargs):
            self.planned = True
            raise AssertionError("denied prompt reached planner")

        def generate(self, *, system_prompt, context):
            self.generated = True
            raise AssertionError("denied prompt reached synthesis")

    spy = DenialSpy()
    copilot, _, _, _ = _copilot(providers={"semantic-spy": spy})
    response = copilot.ask(
            CopilotRequest(
                CTX,
                "run raw SQL against the tenant database",
                "auditor",
                "s1",
                "semantic-spy"
            )
    )
    assert response.blocked
    assert not spy.planned and not spy.generated


def test_active_demo_ask_path_uses_semantic_planner_and_synthetic_evidence(monkeypatch):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    class SemanticDemoSpy:
        name = "openai"

        def __init__(self):
            self.planned = None
            self.generated = None

        def plan(self, **kwargs):
            self.planned = kwargs
            return {
                "interpretation": "Rank governed business service risk",
                "entities": ["business_service"],
                "measures": ["health"],
                "dimensions": ["service", "risk"],
                "filters": [],
                "grouping": ["service"],
                "steps": [
                    {
                        "step_id": "step_risk",
                        "capability_id": "demo_service_health",
                        "operation": "RANK_RISK",
                        "parameters": {
                                "query": None,
                                "result_limit": 5,
                                "filter": None,
                                "value": None,
                        },
                        "depends_on": [],
                    }
                ],
                "synthesis": "Answer only from synthetic evidence and preserve unknowns.",
            }

        def generate(self, *, system_prompt, context):
            self.generated = context
            return ProviderResult("Synthetic evidence synthesis.", 0.9, 3, 4)

    provider = SemanticDemoSpy()
    result = DemoAskNexoraService().ask_semantic(
        "Rank the synthetic services by recorded risk.",
        organization_id=DEMO_ORGANIZATION_ID,
        role="auditor",
        provider=provider,
        conversation=(("user", "Which services are exposed?"),),
    )
    assert result.supported
    assert result.provenance
    assert provider.planned["conversation"] == (("user", "Which services are exposed?"),)
    assert provider.generated is not None


def test_demo_semantic_filters_reach_governed_execution(monkeypatch):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    class FilterProvider:
        name = "semantic-spy"

        def plan(self, **kwargs):
            return {
                "interpretation": "Show high risk services",
                "entities": ["business_service"],
                "measures": ["health"],
                "dimensions": ["service", "risk"],
                "filters": [{"dimension": "risk", "operator": "EQUALS", "value": "High"}],
                "grouping": ["service"],
                "steps": [
                    {
                        "step_id": "step_risk",
                        "capability_id": "demo_service_health",
                        "operation": "RANK_RISK",
                        "parameters": {
                            "query": None,
                            "result_limit": 5,
                            "filter": None,
                            "value": None,
                        },
                        "depends_on": [],
                    }
                ],
                "synthesis": "Answer only from filtered synthetic evidence.",
            }

        def generate(self, *, system_prompt, context):
            return ProviderResult("Filtered synthesis.", 0.9)

    result = DemoAskNexoraService().ask_semantic(
        "Which high risk service is recorded?",
        organization_id=DEMO_ORGANIZATION_ID,
        role="auditor",
        provider=FilterProvider(),
    )
    assert result.supported
    assert {fact["risk"] for fact in result.facts} == {"High"}


def test_prospect_unsupported_nonempty_facts_remain_unsupported(monkeypatch):
    monkeypatch.setattr(
        "shared.prospect_semantic_ask.prospect_evidence_answer",
        lambda question, analysis: "UNKNOWN — unsupported evidence.",
    )

    class UnknownProvider:
        name = "semantic-spy"

        def plan(self, **kwargs):
            return {
                "interpretation": "Unsupported prospect conclusion",
                "entities": [],
                "measures": [],
                "dimensions": [],
                "filters": [],
                "grouping": [],
                "steps": [
                    {
                        "step_id": "prospect_analysis",
                        "capability_id": "prospect_analysis",
                        "operation": "ANSWER",
                        "parameters": {
                            "query": None,
                            "result_limit": None,
                            "filter": None,
                            "value": None,
                        },
                        "depends_on": [],
                    }
                ],
                "synthesis": "Preserve unsupported status.",
            }

        def generate(self, *, system_prompt, context):
            return ProviderResult("Qualified unknown.", 0.5)

    analysis = type(
        "Analysis", (), {"tenant_id": "prospect-1", "currency_resolution_required": True}
    )()
    result = ProspectSemanticAskService().ask(
        "What is unsupported?",
        analysis=analysis,
        admission=None,
        organization_id="prospect-1",
        role="auditor",
        provider=UnknownProvider(),
    )
    assert result["facts"] and not result["supported"]
    assert result["provenance"]


def test_active_prospect_ask_path_uses_admitted_semantic_authority():
    class SemanticProspectSpy:
        name = "openai"

        def __init__(self):
            self.planned = None
            self.generated = None

        def plan(self, **kwargs):
            self.planned = kwargs
            return {
                "interpretation": "Answer from admitted prospect totals",
                "entities": ["prospect_evidence"],
                "measures": ["total_spend"],
                "dimensions": ["currency", "total_spend"],
                "filters": [],
                "grouping": [],
                "time_range": None,
                "ordering": None,
                "steps": [
                    {
                        "step_id": "prospect_analysis",
                        "capability_id": "prospect_analysis",
                        "operation": "ANSWER",
                        "parameters": {
                            "query": None,
                            "result_limit": None,
                            "filter": None,
                            "value": None,
                        },
                        "depends_on": [],
                    }
                ],
                "synthesis": "Answer only from admitted evidence.",
            }

        def generate(self, *, system_prompt, context):
            self.generated = context
            return ProviderResult("Admitted evidence synthesis.", 0.9, 2, 3)

    analysis = type(
        "Analysis",
        (),
        {
            "tenant_id": "prospect-1",
            "total_spend": 861828,
            "currency": "USD",
            "currency_resolution_required": False,
            "row_count": 184,
            "evidence_coverage": 100.0,
            "opportunity_evidence_qualified": 0,
            "confidence": 0.95,
        },
    )()
    admission = type("Admission", (), {"fingerprint": "admission-1"})()
    provider = SemanticProspectSpy()
    result = ProspectSemanticAskService().ask(
        "What is the total observed spend in this upload?",
        analysis=analysis,
        admission=admission,
        organization_id="prospect-1",
        role="auditor",
        provider=provider,
        conversation=(("user", "How much was observed?"),),
    )
    assert result["supported"]
    assert result["provenance"][0]["reference"] == "admission-1"
    assert provider.planned["conversation"] == (("user", "How much was observed?"),)
    assert provider.generated is result["context"]


def test_prospect_semantic_scope_and_malformed_plans_fail_closed():
    analysis = type(
        "Analysis", (), {"tenant_id": "prospect-1", "currency_resolution_required": True}
    )()

    class Malformed:
        def plan(self, **kwargs):
            return {"steps": [{"capability_id": "unregistered", "operation": "READ"}]}

    with pytest.raises(PermissionError):
        ProspectSemanticAskService().ask(
            "What is total spend?",
            analysis=analysis,
            admission=None,
            organization_id="prospect-2",
            role="auditor",
            provider=Malformed(),
        )
    with pytest.raises(Exception):
        ProspectSemanticAskService().ask(
            "What is total spend?",
            analysis=analysis,
            admission=None,
            organization_id="prospect-1",
            role="auditor",
            provider=Malformed(),
        )


def test_openai_provider_uses_bounded_responses_payload_without_network():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "output_text": "Grounded provider answer.",
                "usage": {"input_tokens": 12, "output_tokens": 4},
            },
            request=request,
        )

    copilot, _, _, _ = _copilot()
    context = copilot.ask(
        CopilotRequest(CTX, "show account 727482365532", "auditor", "s1")
    ).grounded_context
    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
        client=httpx.Client(
            base_url="https://api.openai.test/v1", transport=httpx.MockTransport(handler)
        ),
    )

    result = provider.generate(system_prompt="Answer from evidence.", context=context)
    payload = json.loads(requests[0].content)
    assert requests[0].url.path == "/v1/responses"
    assert payload["model"] == "test-model"
    assert json.loads(payload["input"])["question"] == "show account 727482365532"
    assert "repository" not in payload["input"]
    assert result.text == "Grounded provider answer."
    assert (result.input_tokens, result.output_tokens) == (12, 4)


def test_openai_provider_requires_local_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIProvider(client=httpx.Client(transport=httpx.MockTransport(lambda _: None)))
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        provider.generate(system_prompt="Answer.", context=None)


def test_openai_provider_plans_from_catalogue_without_authority_access():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "interpretation": "total governed cost",
                        "steps": [
                            {
                                "step_id": "step_cost",
                                "capability_id": "cap_cost",
                                "operation": "SUM",
                                "parameters": {},
                                "depends_on": [],
                            }
                        ],
                        "synthesis": "Answer from evidence.",
                    }
                )
            },
            request=request,
        )

    provider = OpenAIProvider(
        api_key="test-key",
        client=httpx.Client(
            base_url="https://api.openai.test/v1", transport=httpx.MockTransport(handler)
        ),
    )
    catalogue = (
        CapabilityDescriptor(
            "cap_cost",
            "MONETARY_TOTAL",
            "financial",
            ("cost_total",),
            (),
            ("SUM",),
            (),
            False,
            False,
            "auditor",
            "UNKNOWN",
            "provenance",
        ),
    )
    plan = provider.plan(
        question="What is total spend?",
        catalogue=catalogue,
        scope=CTX,
    )
    payload = json.loads(requests[0].content)
    assert requests[0].url.path == "/v1/responses"
    assert json.loads(payload["input"])["question"] == "What is total spend?"
    assert plan["steps"][0]["capability_id"] == "cap_cost"


def test_unsupported_query_and_performance_targets():
    copilot, _, _, _ = _copilot()
    response = copilot.ask(CopilotRequest(CTX, "hello", "auditor", "s1"))
    assert response.unsupported
    assert response.metrics["routing_ms"] < 50
    assert response.metrics["grounding_ms"] < 500
    assert response.metrics["latency_ms"] < 1000


def test_financial_and_relationship_context_receive_distinct_citations():
    copilot, _, _, business_service = _copilot()
    financial = copilot.ask(
        CopilotRequest(CTX, "What does account 727482365532 cost?", "auditor", "s1")
    )
    assert "financial_context" in {item.source_type for item in financial.citations}
    relationships = copilot.ask(
        CopilotRequest(
            CTX,
            f"Show dependencies for {business_service.canonical_id}",
            "auditor",
            "s1",
        )
    )
    assert "relationship_context" in {item.source_type for item in relationships.citations}


def test_copilot_page_renders_without_provider_or_supabase(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    for key in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file("pages/enterprise_ai_copilot.py", default_timeout=30)
    for key, value in {
        "authenticated": True,
        "auth_backend": "local",
        "user": "auditor@company.com",
        "user_id": "auditor@company.com",
        "email": "auditor@company.com",
        "role": "auditor",
        "organization_id": ORG,
        "organization_name": "Default Org",
        "authorized_organization_ids": [ORG],
        "permissions": [],
    }.items():
        app.session_state[key] = value
    app.run()
    assert not app.exception
    assert any("Enterprise AI Copilot" in title.value for title in app.title)

def test_demo_savings_grouping_matches_governed_evidence():
    """Savings capability must advertise only grouping evidenced by its facts."""
    from services.demo_ask_nexora_service import DemoAskNexoraService

    service = DemoAskNexoraService()
    catalogue = service.semantic_catalogue("executive")

    savings = next(
        item
        for item in catalogue
        if item.capability_id == "demo_savings"
    )

    assert savings.grouping is True
    assert savings.dimensions == ("stage",)

def test_demo_savings_stage_grouping_uses_only_stage_evidenced_facts(monkeypatch):
    """Stage grouping must not fabricate stage on heterogeneous savings facts."""
    from services.demo_ask_nexora_service import DemoAskNexoraService
    from services.demo_tenant_service import (
        DEMO_ORGANIZATION_ID,
        load_demo_tenant,
    )

    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    service = DemoAskNexoraService()
    payload = load_demo_tenant(DEMO_ORGANIZATION_ID)

    ungrouped = service._value(payload)

    assert ungrouped.supported is True
    assert any("stage" in fact for fact in ungrouped.facts)
    assert any("stage" not in fact for fact in ungrouped.facts)

    handler = service._semantic_handler(
        payload,
        service._value,
    )

    grouped = handler(
        operation="SUM_SAVINGS",
        parameters={
            "query": None,
            "result_limit": None,
            "filter": None,
            "value": None,
        },
        dependencies=(),
        scope=None,
        constraints={
            "filters": (),
            "grouping": ("stage",),
        },
    )

    facts = tuple(grouped["facts"])

    assert facts
    assert all("stage" in fact for fact in facts)

    source_stages = {
        row["stage"]
        for row in (payload.get("analytics") or {}).get(
            "savings_waterfall",
            (),
        )
    }

    assert {
        fact["stage"]
        for fact in facts
    }.issubset(source_stages)

    # Portfolio opportunity remains heterogeneous evidence;
    # grouping must not manufacture a stage for it.
    assert not any(
        fact.get("id") == "NXR-PORT-118"
        for fact in facts
    )

def test_demo_ask_semantic_invalid_plan_fails_closed(monkeypatch):
    from services.demo_ask_nexora_service import DemoAskNexoraService
    from services.demo_tenant_service import DEMO_ORGANIZATION_ID

    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    class InvalidPlanProvider:
        name = "invalid-test-provider"

        def plan(self, *, question, catalogue, scope, conversation=()):
            descriptor = next(
                item for item in catalogue
                if item.capability_id == "demo_decisions"
            )
            return {
                "interpretation": "invalid governed plan",
                "entities": ["business_service"],
                "measures": [],
                "dimensions": ["invented_dimension"],
                "filters": [],
                "grouping": [],
                "time_range": None,
                "ordering": None,
                "steps": [
                    {
                        "step_id": "step_1",
                        "capability_id": descriptor.capability_id,
                        "operation": "LIST_ATTENTION",
                        "parameters": {
                            "query": question,
                            "filter": None,
                            "value": None,
                            "result_limit": None,
                        },
                        "depends_on": [],
                    }
                ],
                "synthesis": "Do not infer unsupported facts.",
            }

        def generate(self, *, system_prompt, context):
            raise AssertionError(
                "generate must not run after invalid semantic planning"
            )

    result = DemoAskNexoraService().ask_semantic(
        "Which services need intervention?",
        organization_id=DEMO_ORGANIZATION_ID,
        role="executive",
        provider=InvalidPlanProvider(),
    )

    assert result.supported is False
    assert result.facts == ()
    assert result.provenance == ()
    assert result.unknowns
    assert "UNKNOWN remains UNKNOWN" in result.answer

def test_openai_semantic_planner_preserves_supported_current_state_under_temporal_qualifiers():
    """Conversational time qualifiers must not suppress supported current-state evidence."""
    from enterprise_copilot.providers import OpenAIProvider

    class FakeResponse:
        is_error = False
        headers = {}

        @staticmethod
        def json():
            return {
                "output_text": (
                    '{"interpretation":"attention","entities":[],"measures":[],'
                    '"dimensions":[],"filters":[],"time_range":null,"grouping":[],'
                    '"ordering":null,"steps":[{"step_id":"step_1",'
                    '"capability_id":"demo_decisions","operation":"LIST_ATTENTION",'
                    '"parameters":{"query":"What requires my attention today?",'
                    '"result_limit":null,"filter":null,"value":null},'
                    '"depends_on":[]}],"synthesis":"Use governed current-state evidence; '
                    'unsupported temporal precision remains UNKNOWN."}'
                )
            }

    class FakeClient:
        def __init__(self):
            self.request = None

        def post(self, path, *, headers, json):
            self.request = {
                "path": path,
                "headers": headers,
                "json": json,
            }
            return FakeResponse()

    client = FakeClient()
    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
        client=client,
    )

    class Scope:
        organization_id = "demo-org"
        tenant_id = "demo-org"

    provider.plan(
        question="What requires my attention today?",
        catalogue=(),
        scope=Scope(),
    )

    instructions = client.request["json"]["instructions"]

    assert "always return null for time_range and ordering" in instructions
    assert "'today' or 'this quarter'" in instructions
    assert "supported current-state capability" in instructions
    assert "forecasts and unsupported future conclusions" in instructions



def test_openai_semantic_planner_does_not_add_unknown_step_for_partial_temporal_support():
    """Partial temporal uncertainty belongs in synthesis, not a conflicting UNKNOWN step."""
    from enterprise_copilot.providers import OpenAIProvider

    class FakeResponse:
        is_error = False
        headers = {}

        @staticmethod
        def json():
            return {
                "output_text": (
                    '{"interpretation":"cost reduction","entities":[],"measures":'
                    '["identified_savings","qualified_savings","verified_value"],'
                    '"dimensions":["stage"],"filters":[],"time_range":null,'
                    '"grouping":["stage"],"ordering":null,"steps":['
                    '{"step_id":"step_1","capability_id":"demo_savings",'
                    '"operation":"SUM_SAVINGS","parameters":{"query":'
                    '"Where can we reduce costs?","result_limit":null,'
                    '"filter":null,"value":null},"depends_on":[]}],'
                    '"synthesis":"Use current savings evidence; quarter-specific '
                    'timing remains UNKNOWN."}'
                )
            }

    class FakeClient:
        def __init__(self):
            self.request = None

        def post(self, path, *, headers, json):
            self.request = {
                "path": path,
                "headers": headers,
                "json": json,
            }
            return FakeResponse()

    client = FakeClient()

    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
        client=client,
    )

    class Scope:
        organization_id = "demo-org"
        tenant_id = "demo-org"

    plan = provider.plan(
        question="Where can we reduce costs this quarter?",
        catalogue=(),
        scope=Scope(),
    )

    instructions = client.request["json"]["instructions"]

    assert "do not add the UNKNOWN capability as an additional execution step" in instructions
    assert "UNKNOWN is an execution capability only when" in instructions
    assert "valid for every selected execution capability" in instructions

    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["capability_id"] == "demo_savings"
    assert plan["steps"][0]["operation"] == "SUM_SAVINGS"
    assert plan["time_range"] is None
    assert plan["ordering"] is None


def test_openai_semantic_plan_schema_keeps_temporal_execution_disabled():
    """The remediation must not enable unsupported temporal execution."""
    from enterprise_copilot.providers import _semantic_plan_schema

    schema = _semantic_plan_schema()

    assert schema["properties"]["time_range"] == {"type": "null"}
    assert schema["properties"]["ordering"] == {"type": "null"}
