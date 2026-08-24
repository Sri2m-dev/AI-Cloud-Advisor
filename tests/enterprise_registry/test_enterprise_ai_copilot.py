from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from data_fabric.foundation import TenantContext
from enterprise_copilot import CopilotRequest
from enterprise_copilot.orchestrator import EnterpriseAIOrchestrator
from enterprise_copilot.providers import ProviderResult, default_providers
from enterprise_copilot.router import route_intent
from enterprise_intelligence.search import EnterpriseSearchService
from enterprise_intelligence.service import EnterpriseIntelligenceService
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
