from auth.authenticated_tenant import AuthenticatedTenantContext
from enterprise_copilot.composition import enterprise_intelligence_capabilities
from services.demo_tenant_service import (
    DEMO_ORGANIZATION_ID,
    DEMO_ORGANIZATION_NAME,
)


def _context():
    return AuthenticatedTenantContext(
        organization_id=DEMO_ORGANIZATION_ID,
        organization_name=DEMO_ORGANIZATION_NAME,
        user_id="aenterprise-authority-test-token",
        user_email="executive@nexora.demo",
        role="executive",
        authorization_claims=frozenset(),
        tenant_id=DEMO_ORGANIZATION_ID,
        environment="development",
    )


def test_ask_enterprise_context_has_canonical_authorities(monkeypatch):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    authenticated = _context()

    capabilities = enterprise_intelligence_capabilities(
        authenticated.fabric_context,
        role=authenticated.role,
        financial_context=authenticated,
    )

    query_service = capabilities.query_service

    assert query_service.registry is not None
    assert query_service.relationship_service is not None

    handler = capabilities.handlers()["enterprise_context"]

    result = handler(
        operation="LOOKUP",
        parameters={
            "query": "Global Digital Checkout",
            "result_limit": 5,
        },
        dependencies={},
        scope=authenticated.fabric_context,
        constraints={
            "measures": [],
            "dimensions": [],
            "filters": [],
            "grouping": [],
            "time_range": None,
            "ordering": None,
        },
    )

    assert result["availability"] in {
        "AVAILABLE",
        "PARTIAL",
    }

    records = tuple(result["records"])

    checkout = next(
        record
        for record in records
        if record.get("display_name")
        == "Global Digital Checkout"
    )

    assert checkout["canonical_id"]
    assert checkout["relationship_summary"]["count"] >= 1

    paths = tuple(
        checkout.get("governed_relationship_paths")
        or ()
    )

    assert paths

    flattened_names = {
        entity["name"]
        for path in paths
        for entity in path["entities"]
    }

    assert "Global Digital Checkout" in flattened_names
    assert "Checkout Orchestration Platform" in flattened_names
    assert "End-of-support runtime" in flattened_names
