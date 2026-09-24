"""KG-ASK-05: exercise the same validated adapter across canonical concepts."""

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest

from data_fabric.foundation import TenantContext
from enterprise_copilot.models import CopilotRequest
from enterprise_copilot.orchestrator import EnterpriseAIOrchestrator
from enterprise_copilot.providers import ProviderResult
from enterprise_copilot.semantic_planner import (
    SemanticPlanError,
    execute_semantic_plan,
    validate_semantic_plan,
)
from enterprise_intelligence.search import EnterpriseSearchService
from enterprise_intelligence.service import EnterpriseIntelligenceService
from services.demo_ask_nexora_service import DemoAskNexoraService
from services.demo_tenant_service import DEMO_ORGANIZATION_ID
from services.enterprise_intelligence_query_service import EnterpriseIntelligenceQueryService
from services.enterprise_spend_service import EnterpriseSpendService
from services.governed_enterprise_capabilities import GovernedEnterpriseCapabilities
from tests.cmp_p5.test_enterprise_intelligence_query_service import CTX as FIN_CTX
from tests.cmp_p5.test_enterprise_intelligence_query_service import FinancialAuthority
from tests.enterprise_registry.test_enterprise_knowledge_graph import CTX, _graph


class AllocationAuthority(FinancialAuthority):
    """One coherent allocation fixture, shared by every dimensional plan."""

    def __init__(self, *, coverage="100", partial=False, evidence=True):
        self.coverage, self.partial, self.evidence = coverage, partial, evidence

    def get_financial_posture(self, context, period=None, *, currency="USD"):
        return replace(
            super().get_financial_posture(FIN_CTX, period, currency=currency or "USD"),
            organization_id=context.organization_id,
            allocation_coverage_percentage=Decimal(self.coverage),
        )

    def get_financial_evidence(self, context):
        return super().get_financial_evidence(FIN_CTX) if self.evidence else ()

    def groups(self, context, period=None):
        return (
            {"label": "Commerce", "amount": "60", "observation_ids": ("obs-1",)},
            {
                "label": "Corporate",
                "amount": "30" if self.partial else "40",
                "observation_ids": ("obs-1",),
            },
        )

    get_spend_by_business_unit = groups
    get_spend_by_business_service = groups
    get_spend_by_application = groups
    get_spend_by_provider = groups


def bridge(*, authority=None, role="auditor", scope=CTX):
    graph, _, _, _ = _graph()
    intelligence = EnterpriseIntelligenceService(scope, role=role, graph=graph)
    search = EnterpriseSearchService(intelligence)
    query = EnterpriseIntelligenceQueryService(
        financial_service=authority or AllocationAuthority(),
        financial_context=SimpleNamespace(
            organization_id=scope.organization_id, tenant_id=scope.tenant_id, role=role
        ),
    )
    return GovernedEnterpriseCapabilities(scope, role=role, query_service=query, search=search)


def payload(
    dimension="business_unit",
    operation="RANK_DESC",
    *,
    capability="enterprise_spend",
    parameters=None,
):
    return {
        "interpretation": "Retrieve governed enterprise information",
        "entities": [],
        "measures": ["spend"] if capability == "enterprise_spend" else [],
        "dimensions": [dimension] if dimension else [],
        "filters": [],
        "grouping": [dimension] if dimension else [],
        "time_range": None,
        "ordering": None,
        "steps": [
            {
                "step_id": "step_one",
                "capability_id": capability,
                "operation": operation,
                "parameters": parameters or {},
                "depends_on": [],
            }
        ],
        "synthesis": "Use only evidence and preserve UNKNOWN.",
    }


def run(adapter, plan):
    validated = validate_semantic_plan(
        plan, catalogue=adapter.catalogue(), scope=adapter.context, role=adapter.role
    )
    return execute_semantic_plan(validated, handlers=adapter.handlers())[0]


@pytest.mark.parametrize(
    "dimension", ["business_unit", "business_service", "application", "provider"]
)
def test_same_bridge_groups_and_ranks_authoritative_dimensions(dimension):
    adapter = bridge()
    result = run(adapter, payload(dimension))
    record = result["records"][0]
    assert record["groups"][0]["label"] == "Commerce"
    assert record["groups"][0]["value"] == Decimal("60")
    assert record["currency"] == "USD"
    assert (
        record["fingerprint"]
        == adapter.query_service.spend_by(adapter.context, dimension).fingerprint
    )
    assert set(result["evidence_references"]) == {"ev-1", "obs-1"}
    assert "must-not-leak" not in str(result)
    ascending = run(adapter, payload(dimension, "RANK_ASC"))
    assert ascending["records"][0]["groups"][0]["label"] == "Corporate"


def test_summary_and_filter_do_not_recalculate_authoritative_totals():
    adapter = bridge()
    assert run(adapter, payload(None, "SUMMARY"))["records"][0]["total"] == Decimal("100")
    plan = payload("application", "GROUP")
    plan["filters"] = [{"dimension": "application", "operator": "EQUALS", "value": "Corporate"}]
    result = run(adapter, plan)["records"][0]
    assert len(result["groups"]) == 1
    assert result["groups"][0]["value"] == Decimal("40")
    assert result["total"] is None


@pytest.mark.parametrize(
    "authority", [AllocationAuthority(partial=True), AllocationAuthority(coverage="50")]
)
def test_incomplete_bu_allocation_preserves_entities_but_not_ranking_or_amount(authority):
    result = run(bridge(authority=authority), payload())
    assert result["availability"] == "PARTIAL"
    assert result["records"][0]["ranking"] is None
    assert result["records"][0]["amount"] is None
    assert result["records"][0]["known_groups"][0]["label"] == "Commerce"
    assert "ranking" in " ".join(result["unknowns"])


def test_absent_bu_allocation_and_missing_provenance_are_unknown():
    missing = AllocationAuthority()
    missing.get_spend_by_business_unit = None
    for authority in (AllocationAuthority(evidence=False), missing):
        adapter = bridge(authority=authority)
        result = run(adapter, payload())
        assert result["availability"] == "UNKNOWN"
        assert not result["records"]


def test_financial_role_and_tenant_boundaries():
    adapter = bridge(role="operations")
    assert "enterprise_spend" not in adapter.handlers()
    with pytest.raises(SemanticPlanError):
        run(adapter, payload())
    adapter = bridge()
    handler = adapter.handlers()["enterprise_spend"]
    with pytest.raises(PermissionError):
        handler(
            operation="SUMMARY",
            parameters={},
            dependencies=(),
            scope=TenantContext("other", "other"),
            constraints={},
        )
    with pytest.raises(PermissionError):
        GovernedEnterpriseCapabilities(
            CTX, role="finance", query_service=adapter.query_service, search=adapter.search
        )
    adapter.query_service.financial_context = SimpleNamespace(
        organization_id="other", tenant_id="other"
    )
    with pytest.raises(PermissionError):
        run(adapter, payload())


@pytest.mark.parametrize(
    "change",
    [
        {"time_range": {"start": "2026-01-01"}},
        {"ordering": {"direction": "desc"}},
        {"grouping": ["vendor"]},
        {"grouping": ["application", "business_unit"]},
        {"filters": [{"dimension": "application", "operator": "EQUALS", "value": "Commerce"}]},
    ],
)
def test_unsupported_constraints_are_not_silently_ignored(change):
    plan = payload()
    plan.update(change)
    with pytest.raises(SemanticPlanError):
        run(bridge(), plan)


@pytest.mark.parametrize("role", ["auditor", "operations"])
def test_entity_financial_context_relationship_coverage_and_evidence_policy(role):
    adapter = bridge(role=role)
    result = run(
        adapter,
        payload(
            None, "LOOKUP", capability="enterprise_context", parameters={"query": "727482365532"}
        ),
    )
    record = result["records"][0]
    assert record["financial_summary"] == ({"total_spend": 42.0} if role == "auditor" else {})
    assert record["relationship_summary"]["count"] == 1
    assert bool(record["evidence"]) == (role == "auditor")
    assert record["canonical_id"] in result["evidence_references"]
    assert "topology is UNKNOWN" in " ".join(result["unknowns"])


class Planner:
    name = "openai"

    def __init__(self, plan):
        self.plan_payload = plan
        self.received = None

    def plan(self, **kwargs):
        self.received = kwargs
        assert self.plan_payload["steps"][0]["capability_id"] in {
            item.capability_id for item in kwargs["catalogue"]
        }
        return self.plan_payload

    def generate(self, *, system_prompt, context):
        self.grounded = context
        return ProviderResult("Governed synthesis.")


def test_unseen_question_uses_plan_in_production_orchestrator():
    adapter = bridge()
    provider = Planner(payload("application", "RANK_ASC"))
    copilot = EnterpriseAIOrchestrator(
        search=adapter.search,
        intelligence=adapter.search.intelligence,
        enterprise_capabilities=adapter,
        providers={"openai": provider},
    )
    question = "Compare the smallest recorded application allocations in the portfolio."
    response = copilot.ask(CopilotRequest(CTX, question, "auditor", "session", "openai"))
    assert not response.unsupported
    assert response.citations
    assert provider.received["question"] == question
    assert provider.grounded.evidence.facts[0]["records"][0]["groups"][0]["label"] == "Corporate"


def test_demo_semantic_path_reuses_bridge_and_evidence(monkeypatch):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    scope = TenantContext(DEMO_ORGANIZATION_ID, DEMO_ORGANIZATION_ID)
    adapter = bridge(scope=scope)
    provider = Planner(payload())
    response = DemoAskNexoraService(enterprise_capabilities=adapter).ask_semantic(
        "Which BU is spending the most?",
        organization_id=DEMO_ORGANIZATION_ID,
        role="auditor",
        provider=provider,
    )
    assert response.supported
    assert response.facts[0]["groups"][0]["label"] == "Commerce"
    assert {row["source"] for row in response.provenance} == {"obs-1", "ev-1"}
    assert all(row["type"] == "canonical_enterprise_evidence" for row in response.provenance)
    with pytest.raises(PermissionError):
        DemoAskNexoraService(enterprise_capabilities=bridge()).ask_semantic(
            "Which BU is spending the most?",
            organization_id=DEMO_ORGANIZATION_ID,
            role="auditor",
            provider=provider,
        )


def test_cloud_products_are_not_business_service_allocation():
    repository = SimpleNamespace(
        get_spend_by_service=lambda *args: ({"service": "EC2", "spend": "100"},)
    )
    service = EnterpriseSpendService(repository)
    assert service.get_spend_by_service(object())[0]["service"] == "EC2"
    assert service.get_spend_by_business_service(object()) == ()


def test_real_sourcefact_financial_adapter_preserves_provider_spend_and_bu_unknown():
    from dataclasses import asdict

    from auth.authenticated_tenant import AuthenticatedTenantContext
    from data_fabric.source_facts.models import FactType, Freshness, SourceFact, SourceFactInput
    from repositories.source_fact_financial_repository import SourceFactFinancialRepository

    context = AuthenticatedTenantContext(
        CTX.organization_id,
        "Test enterprise",
        "user",
        "user@example.com",
        "auditor",
        frozenset(),
        CTX.tenant_id,
    )
    facts = tuple(
        SourceFact(
            **asdict(
                SourceFactInput(
                    source_record_id=provider,
                    fact_type=FactType.CLOUD_COST,
                    subject_reference=provider,
                    predicate="observed_cost",
                    freshness=Freshness.FRESH,
                    evidence_reference=f"billing:{provider}",
                    value={
                        "provider": provider,
                        "account_id": provider,
                        "period_start": "2026-01-01",
                        "period_end": "2026-02-01",
                        "service": "Compute",
                        "currency": "USD",
                        "amount": amount,
                    },
                )
            ),
            source_fact_id=f"fact:{provider}",
            observation_key=provider,
            fact_version=1,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            source_instance_id=provider,
            source_type="billing",
            source_system=provider,
            connector_version="1",
            ingestion_run_id=f"run:{provider}",
            fingerprint=f"fingerprint:{provider}",
        )
        for provider, amount in (("AWS", "60"), ("Azure", "40"))
    )

    def current(organization_id, tenant_id):
        assert (organization_id, tenant_id) == (context.organization_id, context.tenant_id)
        return facts

    authority = EnterpriseSpendService(
        SourceFactFinancialRepository(SimpleNamespace(list_current_facts=current)),
        cache_ttl_seconds=0,
    )
    adapter = bridge(authority=authority)
    adapter.query_service.financial_context = context
    ranked = run(adapter, payload("provider"))
    assert ranked["records"][0]["groups"][0]["label"] == "AWS"
    assert ranked["records"][0]["groups"][0]["value"] == Decimal("60")
    assert {"fact:AWS", "fact:Azure", "billing:AWS", "billing:Azure"} == set(
        ranked["evidence_references"]
    )
    assert run(adapter, payload())["availability"] == "UNKNOWN"
    missing_service = run(adapter, payload("business_service"))
    assert missing_service["availability"] == "PARTIAL"
    assert missing_service["records"][0]["amount"] is None


def test_demo_unknown_does_not_call_synthesis_or_invent_bu_amount(monkeypatch):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    missing = AllocationAuthority()
    missing.get_spend_by_business_unit = None
    adapter = bridge(
        authority=missing, scope=TenantContext(DEMO_ORGANIZATION_ID, DEMO_ORGANIZATION_ID)
    )
    provider = Planner(payload())
    result = DemoAskNexoraService(enterprise_capabilities=adapter).ask_semantic(
        "Which BU is spending the most?",
        organization_id=DEMO_ORGANIZATION_ID,
        role="auditor",
        provider=provider,
    )
    assert not result.supported and not result.facts
    assert "UNKNOWN" in result.answer
    assert not hasattr(provider, "grounded")


def test_partial_ranking_respects_filter_without_exposing_other_groups():
    plan = payload()
    plan["filters"] = [{"dimension": "business_unit", "operator": "EQUALS", "value": "Corporate"}]
    result = run(bridge(authority=AllocationAuthority(partial=True)), plan)
    assert [row["label"] for row in result["records"][0]["known_groups"]] == ["Corporate"]
