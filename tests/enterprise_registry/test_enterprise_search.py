from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from data_fabric.foundation import TenantContext
from enterprise_intelligence import SearchRequest
from enterprise_intelligence.search import EnterpriseSearchService
from enterprise_intelligence.service import EnterpriseIntelligenceService
from tests.enterprise_registry.test_enterprise_knowledge_graph import ORG, _graph

CTX = TenantContext(ORG, ORG)


def _service(role="auditor"):
    graph, account, application, business_service = _graph()
    search = EnterpriseSearchService(EnterpriseIntelligenceService(CTX, role=role, graph=graph))
    return search, account, application, business_service


def test_exact_source_and_canonical_id_rank_first_stably():
    service, account, _, _ = _service()
    by_source = service.search(SearchRequest(CTX, "727482365532"))
    assert by_source.results[0].canonical_id == account.canonical_id
    assert by_source.results[0].match_reason == "Exact authoritative source ID"
    first = service.search(SearchRequest(CTX, account.canonical_id))
    second = service.search(SearchRequest(CTX, account.canonical_id))
    assert first.results[0].relevance_score == second.results[0].relevance_score


def test_name_alias_classification_and_explanation():
    service, account, application, _ = _service()
    assert (
        service.search(SearchRequest(CTX, "KordiaSoc")).results[0].canonical_id
        == application.canonical_id
    )
    result = service.search(SearchRequest(CTX, "HG_AWS01")).results[0]
    assert result.canonical_id == account.canonical_id
    assert result.match_reason


def test_filters_pagination_financial_and_zero_edge_behavior():
    service, account, _, _ = _service()
    assert service.search(SearchRequest(CTX, filters={"owner_state": "Unowned"})).results
    financial = service.search(SearchRequest(CTX, "727482365532", include_financial=True))
    assert financial.results[0].financial_summary["total_spend"] == 42.0
    page = service.search(SearchRequest(CTX, result_limit=1, offset=1))
    assert page.offset == 1 and len(page.results) == 1 and page.partial
    service.intelligence.graph.relationships._relationships = ()
    assert service.connected_to(account.canonical_id) == ()


def test_tenant_persona_evidence_and_no_mutation_interface():
    service, account, _, _ = _service("executive")
    foreign = TenantContext(
        "22222222-2222-4222-8222-222222222222", "22222222-2222-4222-8222-222222222222"
    )
    with pytest.raises(PermissionError):
        service.search(SearchRequest(foreign, "727482365532"))
    result = service.search(
        SearchRequest(CTX, account.canonical_id, include_evidence=True, include_relationships=True)
    ).results[0]
    assert result.evidence == ()
    assert not hasattr(service, "register_entity") and not hasattr(service, "approve")


def test_approved_classification_outweighs_inferred_classification():
    service, account, application, _ = _service()
    original = service.intelligence.graph.registry.get_classifications

    def classifications(canonical_id):
        if canonical_id == account.canonical_id:
            return (
                {
                    "field_name": "application",
                    "inferred_value": "Shared",
                    "confidence_score": 0.99,
                    "approval_status": "NEEDS_REVIEW",
                },
            )
        if canonical_id == application.canonical_id:
            return (
                {
                    "field_name": "application",
                    "inferred_value": "Shared",
                    "confidence_score": 0.7,
                    "approval_status": "APPROVED",
                },
            )
        return original(canonical_id)

    service.intelligence.graph.registry.get_classifications = classifications
    results = service.search(SearchRequest(CTX, "Shared")).results
    assert results[0].canonical_id == application.canonical_id
    assert results[0].match_reason.startswith("Approved")


def test_search_page_renders_safe_empty_local_runtime(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    for key in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file("pages/enterprise_search.py", default_timeout=30)
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
    assert any("Enterprise Search" in title.value for title in app.title)


def test_search_performance_targets_at_current_fixture_scale():
    service, account, _, _ = _service()
    exact = service.performance_probe(SearchRequest(CTX, account.canonical_id))
    simple = service.performance_probe(SearchRequest(CTX, "AWS"))
    enriched = service.performance_probe(
        SearchRequest(CTX, "AWS", include_financial=True, include_relationships=True)
    )
    assert exact["p95_ms"] < 100
    assert simple["p95_ms"] < 300
    assert enriched["p95_ms"] < 1500
