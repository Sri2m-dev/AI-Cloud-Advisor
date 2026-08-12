from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from data_fabric.foundation import TenantContext
from enterprise_intelligence import DimensionState, QueryLimits, QueryRequest, QueryType
from enterprise_intelligence.service import EnterpriseIntelligenceService
from tests.enterprise_registry.test_enterprise_knowledge_graph import ORG, _graph

CTX = TenantContext(ORG, ORG)


def _service(role="auditor", limits=None):
    graph, account, application, business_service = _graph()
    return (
        EnterpriseIntelligenceService(CTX, role=role, graph=graph, limits=limits),
        account,
        application,
        business_service,
    )


def test_context_separates_facts_from_inference_and_exposes_dimensions():
    service, account, _, _ = _service()
    response = service.get_enterprise_context(account.canonical_id)
    assert response.facts[0].kind == "FACT"
    assert all(item.kind == "DERIVED" for item in response.derived_findings)
    assert response.context.identity.state is DimensionState.AVAILABLE
    assert response.context.business.state is DimensionState.MISSING
    assert response.context.financial.state is DimensionState.AVAILABLE
    assert response.checkpoint_references == (f"entity-version:{account.version}",)


def test_named_queries_and_zero_edge_impact_are_deterministic():
    service, account, application, business_service = _service()
    assert service.get_dependencies(business_service.canonical_id).paths
    assert service.get_dependents(account.canonical_id).paths
    first = service.get_business_impact(application.canonical_id)
    second = service.get_business_impact(application.canonical_id)
    assert first.narrative == second.narrative
    isolated_graph, isolated, _, _ = _graph()
    isolated_graph.relationships._relationships = ()
    zero = EnterpriseIntelligenceService(
        CTX, role="auditor", graph=isolated_graph
    ).find_change_impact(isolated.canonical_id, {"action": "suspend"})
    assert zero.paths == ()
    assert zero.partial
    assert "INCOMPLETE TOPOLOGY" in zero.partial_reasons[0]


def test_limits_and_historical_disclosure_are_explicit():
    service, account, _, _ = _service(
        limits=QueryLimits(max_depth=1, max_results=1, max_work=1, timeout_ms=0)
    )
    response = service.query(
        QueryRequest(CTX, QueryType.EXPLAIN, account.canonical_id, depth=99, result_limit=99)
    )
    assert response.partial
    assert "maximum depth reached" in response.partial_reasons
    historical = service.query(
        QueryRequest(
            CTX, QueryType.EXPLAIN, account.canonical_id, temporal_context={"as_of": "2025-01-01"}
        )
    )
    assert historical.freshness == "UNSUPPORTED"


def test_authorization_tenant_isolation_and_evidence_filtering():
    with pytest.raises(PermissionError):
        _service(role="unknown")
    service, account, _, _ = _service(role="executive")
    assert service.explain_entity(account.canonical_id).evidence == ()
    foreign = TenantContext(
        "22222222-2222-4222-8222-222222222222", "22222222-2222-4222-8222-222222222222"
    )
    with pytest.raises(PermissionError):
        service.query(QueryRequest(foreign, QueryType.EXPLAIN, account.canonical_id))
    assert not hasattr(service, "register_entity")
    assert not hasattr(service, "approve")


def test_inventory_queries_financial_and_stale_states():
    service, _, _, _ = _service()
    assert service.find_unowned_entities()
    assert service.find_unclassified_entities()
    assert service.find_high_cost_entities(40)
    assert service._dimension("TEST", {"x": 1}, stale=True).state is DimensionState.STALE
    assert service._dimension("TEST", {}, supported=False).state is DimensionState.UNSUPPORTED


def test_intelligence_page_renders_safe_empty_local_runtime(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    for key in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file("pages/enterprise_intelligence.py", default_timeout=30)
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
    assert any("Enterprise Intelligence" in title.value for title in app.title)
