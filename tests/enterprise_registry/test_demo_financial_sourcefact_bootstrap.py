"""KG-ASK-09: persisted canonical publication through financial intelligence and Ask."""

from dataclasses import replace
from decimal import Decimal

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from data_fabric.contracts import EntityType
from data_fabric.source_facts.models import (
    FactType,
    LifecycleState,
    SourceFactInput,
    SourceInstance,
)
from data_fabric.source_facts.persistence import SQLiteSourceFactRepository
from data_fabric.source_facts.service import SourceFactService
from enterprise_intelligence.search import EnterpriseSearchService
from enterprise_intelligence.service import EnterpriseIntelligenceService
from enterprise_registry.canonical import enterprise_entity_from_source
from enterprise_registry.knowledge_graph import EnterpriseKnowledgeGraphService
from enterprise_registry.relationship_intelligence import RelationshipIntelligenceService
from repositories.source_fact_financial_repository import SourceFactFinancialRepository
from services.demo_ask_nexora_service import DemoAskNexoraService
from services.demo_financial_sourcefact_bootstrap import (
    EVIDENCE_REFERENCE,
    SOURCE_ID,
    bootstrap_demo_financial_sourcefacts,
)
from services.demo_tenant_service import DEMO_ORGANIZATION_ID
from services.enterprise_intelligence_query_service import EnterpriseIntelligenceQueryService
from services.enterprise_spend_composition import enterprise_spend_service
from services.enterprise_spend_service import EnterpriseSpendService
from services.governed_enterprise_capabilities import GovernedEnterpriseCapabilities
from tests.enterprise_registry.test_canonical_enterprise_registry import (
    _service as registry_service,
)
from tests.enterprise_registry.test_governed_enterprise_bridge import (
    AllocationAuthority,
    Planner,
    payload,
    run,
)

CUSTOMER = "11111111-1111-4111-8111-111111111111"


def context(organization=DEMO_ORGANIZATION_ID, role="auditor"):
    return AuthenticatedTenantContext(
        organization, "Enterprise", "user", "user@example.com", role, frozenset(), organization
    )


@pytest.fixture
def authority(tmp_path, monkeypatch):
    database = tmp_path / "existing-sourcefacts.sqlite"
    repository = SQLiteSourceFactRepository(database)
    monkeypatch.setenv("NEXORA_UNIVERSAL_EVIDENCE_DB", str(database))
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    return context(), repository


def adapter(ctx, financial):
    registry = registry_service(context=ctx.fabric_context)
    graph = EnterpriseKnowledgeGraphService(
        registry,
        RelationshipIntelligenceService(
            ctx.fabric_context,
            role=ctx.role,
            entities=(),
            relationships=(),
        ),
    )
    search = EnterpriseSearchService(
        EnterpriseIntelligenceService(
            ctx.fabric_context,
            role=ctx.role,
            graph=graph,
        )
    )
    return GovernedEnterpriseCapabilities(
        ctx.fabric_context,
        role=ctx.role,
        search=search,
        query_service=EnterpriseIntelligenceQueryService(
            financial_service=financial, financial_context=ctx
        ),
    )


def publish(ctx, repository, records, *, source="billing", run_id="billing-1"):
    instance = SourceInstance(
        source, ctx.organization_id, ctx.tenant_id, "billing", source, "billing", "1", "fixture"
    )
    service = SourceFactService(ctx.fabric_context, repository)
    service.register(instance)
    return service.publish(instance, tuple(records), run_id=run_id)


def cost(provider="AWS", service="Compute", amount="60", currency="USD"):
    return SourceFactInput(
        source_record_id=f"{provider}:{service}",
        fact_type=FactType.CLOUD_COST,
        subject_reference=provider,
        predicate="cost",
        value={
            "provider": provider,
            "account_id": provider,
            "service": service,
            "period_start": "2026-01-01",
            "period_end": "2026-02-01",
            "amount": amount,
            "currency": currency,
        },
        evidence_reference=f"billing:{provider}:{service}",
        lineage={"report": "certified-billing"},
        provenance={"source": provider},
    )


def test_bootstrap_idempotence_semantics_and_provenance_through_ask(authority):
    ctx, repository = authority
    first = bootstrap_demo_financial_sourcefacts(ctx)
    second = bootstrap_demo_financial_sourcefacts(ctx)
    financial = enterprise_spend_service(ctx)
    facts = repository.list_current_facts(ctx.organization_id, ctx.tenant_id)
    assert first["run_id"] == second["run_id"]
    assert second["status"] == "UNCHANGED"
    assert len(facts) == 1
    assert repository.run_counts(ctx.organization_id, ctx.tenant_id, SOURCE_ID) == {"success": 1}
    fact = facts[0]
    assert fact.fact_type is FactType.CLOUD_COST
    assert Decimal(fact.value["amount"]) == Decimal("87000000")
    assert fact.value["provider"] is fact.value["service"] is fact.value["account_id"] is None
    assert fact.value["currency"] == "UNKNOWN"
    assert fact.value["period_start"] is fact.value["period_end"] is None
    assert fact.lineage["json_pointer"] == "/metrics/annual_cloud_spend"
    assert fact.provenance["classification"] == "SYNTHETIC_DEMONSTRATION_DATA"
    evidence = financial.get_financial_evidence(ctx)[0]
    assert evidence["lineage"] == fact.lineage and evidence["provenance"] == fact.provenance
    bridge = adapter(ctx, financial)
    provider = Planner(payload(None, "SUMMARY"))
    result = DemoAskNexoraService(enterprise_capabilities=bridge).ask_semantic(
        "Explain the reported cloud financial baseline and its source limits.",
        organization_id=ctx.organization_id,
        role=ctx.role,
        provider=provider,
    )
    assert result.facts[0]["total"] == Decimal("87000000")
    assert result.facts[0]["currency"] == "UNKNOWN"
    assert result.facts[0]["source_period_labels"] == ("annual; exact dates UNKNOWN",)
    assert {row["source"] for row in result.provenance} == {EVIDENCE_REFERENCE, fact.source_fact_id}
    assert "ISO currency is UNKNOWN" in result.answer
    assert enterprise_spend_service(ctx).get_financial_posture(
        ctx, currency=None
    ).cloud_spend == Decimal("87000000")


@pytest.mark.parametrize(
    "dimension", ["provider", "service", "business_unit", "application", "business_service"]
)
def test_demo_does_not_invent_dimensional_allocation(authority, dimension):
    ctx, _ = authority
    result = run(adapter(ctx, enterprise_spend_service(ctx)), payload(dimension))
    assert result["availability"] == "UNKNOWN"
    assert not result["records"]
    assert "allocation" in " ".join(result["unknowns"])


def test_canonical_bu_identity_without_allocation_remains_partial(authority):
    ctx, _ = authority
    bridge = adapter(ctx, enterprise_spend_service(ctx))
    entity = enterprise_entity_from_source(
        context=ctx.fabric_context,
        entity_type=EntityType.BUSINESS_UNIT,
        source_system="certified-org-chart",
        source_entity_id="division-1",
        canonical_name="Division One",
    )
    bridge.search.intelligence.graph.registry.register_entity(entity)
    result = run(bridge, payload())
    assert result["availability"] == "PARTIAL"
    assert result["records"][0]["known_groups"][0]["label"] == "Division One"
    assert result["records"][0]["amount"] is result["records"][0]["ranking"] is None


def test_real_tenant_demo_flag_and_roles_cannot_publish_synthetic_facts(authority, monkeypatch):
    ctx, repository = authority
    for forbidden in (context(CUSTOMER), context(role="operations")):
        with pytest.raises(PermissionError):
            bootstrap_demo_financial_sourcefacts(forbidden)
    assert repository.list_current_facts(CUSTOMER, CUSTOMER) == ()
    assert repository.list_current_facts(ctx.organization_id, ctx.tenant_id) == ()
    monkeypatch.setenv("NEXORA_DEMO_MODE", "false")
    with pytest.raises(RuntimeError):
        bootstrap_demo_financial_sourcefacts(ctx)


def test_bootstrap_uses_no_default_or_second_database(authority, monkeypatch):
    ctx, repository = authority
    monkeypatch.delenv("NEXORA_UNIVERSAL_EVIDENCE_DB")
    assert bootstrap_demo_financial_sourcefacts(ctx)["status"] == "UNKNOWN"
    assert repository.list_current_facts(ctx.organization_id, ctx.tenant_id) == ()


def test_provider_and_service_ranking_use_published_sourcefacts_for_customer(authority):
    _, repository = authority
    ctx = context(CUSTOMER)
    publish(ctx, repository, (cost(), cost("Azure", "Storage", "40")))
    financial = EnterpriseSpendService(
        SourceFactFinancialRepository(repository), cache_ttl_seconds=0
    )
    bridge = adapter(ctx, financial)
    for dimension, label in (("provider", "AWS"), ("service", "Compute")):
        record = run(bridge, payload(dimension))["records"][0]
        assert record["groups"][0]["label"] == label
        assert record["groups"][0]["value"] == Decimal("60")
        assert record["currency"] == "USD"
    assert financial.get_financial_evidence(context()) == ()
    assert run(bridge, payload())["availability"] == "UNKNOWN"


def test_existing_attribution_provider_contract_enables_bu_without_question_code(authority):
    _, repository = authority
    ctx = context(CUSTOMER)
    publish(ctx, repository, (cost(), cost("Azure", "Storage", "40")))
    bridge = adapter(ctx, AllocationAuthority())
    allocation = AllocationAuthority()
    bridge.query_service.attribution_provider = allocation
    assert run(bridge, payload())["records"][0]["groups"][0]["value"] == Decimal("60")
    bridge.query_service.attribution_provider = object()
    assert run(bridge, payload())["availability"] == "UNKNOWN"


@pytest.mark.parametrize(
    "records",
    [
        (cost(), cost("Azure", "Storage", "40", "EUR")),
        (cost(), replace(cost(), source_record_id="another-row")),
    ],
)
def test_mixed_currency_and_overlapping_authorities_fail_closed(authority, records):
    _, repository = authority
    ctx = context(CUSTOMER)
    publish(ctx, repository, records)
    financial = EnterpriseSpendService(
        SourceFactFinancialRepository(repository), cache_ttl_seconds=0
    )
    with pytest.raises(ValueError):
        financial.get_financial_posture(ctx, currency=None)
    assert run(adapter(ctx, financial), payload(None, "SUMMARY"))["availability"] == "UNKNOWN"


def test_aggregate_cannot_be_added_to_detail_or_prorated(authority):
    from datetime import date

    ctx, repository = authority
    financial = enterprise_spend_service(ctx)
    with pytest.raises(ValueError, match="period boundaries"):
        financial.get_financial_posture(ctx, (date(2026, 1, 1), date(2026, 12, 31)), currency=None)
    publish(ctx, repository, (cost(),))
    assert run(adapter(ctx, financial), payload(None, "SUMMARY"))["availability"] == "UNKNOWN"


def test_lifecycle_and_disabled_authority_are_preserved(authority):
    ctx, repository = authority
    bootstrap_demo_financial_sourcefacts(ctx)
    repository.purge_source(ctx.organization_id, ctx.tenant_id, SOURCE_ID)
    with pytest.raises(PermissionError):
        bootstrap_demo_financial_sourcefacts(ctx)
    customer = context(CUSTOMER)
    publish(customer, repository, (replace(cost(), lifecycle=LifecycleState.SOURCE_DISABLED),))
    assert SourceFactFinancialRepository(repository).observations(customer) == ()


def test_unsupported_forecast_stays_unknown_without_generation(authority):
    ctx, _ = authority
    bridge = adapter(ctx, enterprise_spend_service(ctx))
    plan = payload(None, "UNKNOWN", capability="demo_unknown")
    provider = Planner(plan)
    result = DemoAskNexoraService(enterprise_capabilities=bridge).ask_semantic(
        "Predict the next fiscal year's cloud cost.",
        organization_id=ctx.organization_id,
        role=ctx.role,
        provider=provider,
    )
    assert not result.supported and "UNKNOWN" in result.answer
    assert not hasattr(provider, "grounded")


def test_active_demo_composition_uses_canonical_sourcefact_authority(authority, monkeypatch):
    import enterprise_copilot.composition as composition

    ctx, repository = authority
    search = adapter(ctx, AllocationAuthority()).search
    monkeypatch.setattr(composition, "enterprise_search_service", lambda *args, **kwargs: search)
    with pytest.raises(PermissionError):
        composition.enterprise_intelligence_capabilities(
            context(CUSTOMER).fabric_context,
            role=ctx.role,
            financial_context=ctx,
        )
    assert repository.list_current_facts(ctx.organization_id, ctx.tenant_id) == ()
    bridge = composition.enterprise_intelligence_capabilities(
        ctx.fabric_context,
        role=ctx.role,
        financial_context=ctx,
    )
    assert run(bridge, payload(None, "SUMMARY"))["records"][0]["total"] == Decimal("87000000")
    assert run(bridge, payload())["availability"] == "UNKNOWN"
