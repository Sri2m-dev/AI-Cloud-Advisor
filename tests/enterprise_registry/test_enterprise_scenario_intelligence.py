from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from statistics import median, quantiles
from time import perf_counter
from types import SimpleNamespace

import pytest

from data_fabric.contracts import EnterpriseRelationship
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from enterprise_copilot.models import CopilotRequest
from enterprise_copilot.orchestrator import EnterpriseAIOrchestrator
from enterprise_registry.adapters import (
    ApplicationEnterpriseAdapter,
    BusinessServiceEnterpriseAdapter,
    CloudAccountEnterpriseAdapter,
)
from enterprise_registry.relationship_intelligence import RelationshipIntelligenceService
from enterprise_scenario import ScenarioRequest, ScenarioService, ScenarioType, TopologyState

CTX = TenantContext("11111111-1111-4111-8111-111111111111", "11111111-1111-4111-8111-111111111111")
OTHER = TenantContext(
    "22222222-2222-4222-8222-222222222222", "22222222-2222-4222-8222-222222222222"
)
NOW = datetime(2026, 8, 13, tzinfo=timezone.utc)


class Registry:
    def __init__(self, context, entity, *, spend=37143.2080151701, enterprise=127678.2170275708):
        self.context, self.entity = context, entity
        self.financial = {
            "account_spend": spend,
            "enterprise_spend": enterprise,
            "period": "2026-07",
        }
        self.classifications = ({"version": 4, "status": "NEEDS_REVIEW"},)
        self.relationship_rows = ()

    def get_detail(self, canonical_id):
        if canonical_id != self.entity.canonical_id:
            raise KeyError(canonical_id)
        return SimpleNamespace(
            entity=self.entity,
            financial_context=self.financial,
            classifications=self.classifications,
            relationships=self.relationship_rows,
        )


def entities(context=CTX):
    account = CloudAccountEnterpriseAdapter().adapt(
        context,
        {
            "account_id": "727482365532",
            "account_name": "HG_AWS01",
            "classification_status": "NEEDS_REVIEW",
            "confidence": 1.0,
        },
    )
    app = ApplicationEnterpriseAdapter().adapt(
        context, {"application_id": "app-1", "name": "Payments App"}
    )
    service = BusinessServiceEnterpriseAdapter().adapt(
        context, {"business_service_id": "svc-1", "name": "Payments"}
    )
    return account, app, service


def edge(source, target):
    return EnterpriseRelationship(
        id=f"{source.id}:{target.id}",
        relationship_type="runs_on" if source.entity_type.value == "application" else "supports",
        source_entity_id=source.id,
        target_entity_id=target.id,
        organization_id=CTX.organization_id,
        tenant_id=CTX.tenant_id,
        source_system="cmdb",
        source_identifier="edge",
        evidence=("cmdb:e1",),
        discovery_timestamp=NOW,
        last_validation=NOW,
    )


def service(*, with_edges=False, role="super_admin", policy=None):
    account, app, business = entities()
    edges = (edge(app, account), edge(business, app)) if with_edges else ()
    relationships = RelationshipIntelligenceService(
        CTX, role="auditor", entities=(account, app, business), relationships=edges
    )
    registry = Registry(CTX, account)
    registry.relationship_rows = tuple(
        row for row in edges if account.id in (row.source_entity_id, row.target_entity_id)
    )
    return (
        ScenarioService(
            CTX, role=role, registry=registry, relationships=relationships, policy_previewer=policy
        ),
        account,
        registry,
    )


def test_cost_growth_exact_financial_invariant_determinism_and_immutability():
    subject_service, account, registry = service()
    request = ScenarioRequest(
        CTX, ScenarioType.COST_GROWTH, account.canonical_id, financial_parameters={"percentage": 20}
    )
    original_financial = deepcopy(registry.financial)
    first = subject_service.simulate(request, generated_at=NOW)
    second = subject_service.simulate(request, generated_at=NOW)
    assert first == second
    assert first.financial_impact["baseline_spend"] == 37143.2080151701
    assert first.financial_impact["simulated_spend"] == 44571.84961820412
    assert first.financial_impact["delta"] == 7428.64160303402
    assert first.financial_impact["simulated_enterprise_spend"] == 135106.85863060484
    assert (
        first.financial_impact["approved_savings"]
        == first.financial_impact["executed_savings"]
        == first.financial_impact["verified_realized_savings"]
        == 0
    )
    assert registry.financial == original_financial
    assert first.authoritative is False


def test_account_suspension_zero_edge_is_incomplete_and_never_destructive():
    subject_service, account, _ = service()
    result = subject_service.simulate(
        ScenarioRequest(CTX, "ACCOUNT_SUSPENSION", account.canonical_id), generated_at=NOW
    )
    assert result.baseline_state["canonical_id"] == account.canonical_id
    assert result.financial_impact["baseline_spend"] == 37143.2080151701
    assert result.impacted_entities == ()
    assert result.topology_state is TopologyState.INCOMPLETE
    assert result.business_impact["conclusion"] == "UNKNOWN"
    assert "INCOMPLETE_TOPOLOGY" in result.unknowns[0]
    assert result.operational_impact["execution_permitted"] is False
    assert "safe to terminate" not in str(result).lower()


def test_governed_impact_propagation_and_bounded_path_evidence():
    subject_service, account, _ = service(with_edges=True)
    result = subject_service.simulate(
        ScenarioRequest(CTX, "ACCOUNT_SUSPENSION", account.canonical_id, depth=2), generated_at=NOW
    )
    assert [row["type"] for row in result.impacted_entities] == ["application", "business_service"]
    assert result.topology_state is TopologyState.COMPLETE
    assert result.relationship_paths[-1]["relationships"] == ("runs_on", "supports")
    assert "cmdb:e1" in result.evidence


@pytest.mark.parametrize("scenario_type", list(ScenarioType))
def test_all_authorized_scenario_types_are_analysis_only(scenario_type):
    subject_service, account, _ = service()
    result = subject_service.simulate(
        ScenarioRequest(CTX, scenario_type, account.canonical_id), generated_at=NOW
    )
    assert result.authoritative is False
    assert result.operational_impact["execution_permitted"] is False
    assert result.governance_impact["decision_created"] is False
    assert result.governance_impact["authorization_created"] is False


def test_tenant_isolation_and_persona_scope():
    subject_service, account, _ = service(role="finance")
    with pytest.raises(DataFabricTenantBoundaryError):
        subject_service.simulate(ScenarioRequest(OTHER, "COST_GROWTH", account.canonical_id))
    with pytest.raises(PermissionError, match="persona scope"):
        subject_service.simulate(ScenarioRequest(CTX, "ACCOUNT_SUSPENSION", account.canonical_id))


def test_ownership_classification_policy_preview_and_comparison():
    preview = SimpleNamespace(authoritative=False, result="REVIEW_REQUIRED")
    subject_service, account, _ = service(policy=lambda request: preview)
    owner = subject_service.simulate(
        ScenarioRequest(
            CTX, "OWNERSHIP_CHANGE", account.canonical_id, proposed_change={"owner": "team-finops"}
        ),
        generated_at=NOW,
    )
    classification = subject_service.simulate(
        ScenarioRequest(
            CTX,
            "CLASSIFICATION_CHANGE",
            account.canonical_id,
            proposed_change={"classification": "CLASSIFIED"},
        ),
        generated_at=NOW,
    )
    policy = subject_service.simulate(
        ScenarioRequest(
            CTX, "POLICY_CHANGE_PREVIEW", account.canonical_id, policy_context={"policy_id": "p1"}
        ),
        generated_at=NOW,
    )
    assert owner.simulated_state["ownership_reference"] == "team-finops"
    assert classification.simulated_state["classification_status"] == "CLASSIFIED"
    assert policy.policy_preview is preview and policy.policy_preview.authoritative is False
    comparison = subject_service.compare(
        (
            ScenarioRequest(
                CTX, "COST_GROWTH", account.canonical_id, financial_parameters={"percentage": 20}
            ),
            ScenarioRequest(
                CTX, "COST_REDUCTION", account.canonical_id, financial_parameters={"percentage": 10}
            ),
        ),
        generated_at=NOW,
    )
    assert len(comparison.rows) == 2
    assert comparison.rows[0]["cost"] == 44571.84961820412
    assert comparison.rows[1]["cost"] == pytest.approx(33428.88721365309)
    assert comparison.authoritative is False


def test_validation_and_three_scenario_budget():
    subject_service, account, _ = service()
    with pytest.raises(ValueError, match="depth"):
        ScenarioRequest(CTX, "COST_GROWTH", account.canonical_id, depth=6)
    requests = tuple(ScenarioRequest(CTX, "COST_GROWTH", account.canonical_id) for _ in range(4))
    with pytest.raises(ValueError, match="one to three"):
        subject_service.compare(requests)


def test_copilot_calls_scenario_service_and_exposes_inputs():
    subject_service, account, _ = service()
    orchestrator = EnterpriseAIOrchestrator(
        search=SimpleNamespace(),
        intelligence=SimpleNamespace(context=CTX, role="super_admin"),
        scenario_service=subject_service,
    )
    response = orchestrator.explain_scenario(
        CopilotRequest(CTX, "What if cloud spend grows 20%?", "super_admin", "session-1"),
        ScenarioRequest(
            CTX,
            "COST_GROWTH",
            account.canonical_id,
            financial_parameters={"percentage": 20},
            assumptions={"growth": "20%"},
        ),
    )
    assert response.intent == "scenario"
    assert "SIMULATION — NOT AUTHORIZATION" in response.answer
    assert "growth" in response.answer
    assert response.metrics["authoritative"] is False


def test_formal_performance_certification():
    subject_service, account, _ = service()
    copilot = EnterpriseAIOrchestrator(
        search=SimpleNamespace(),
        intelligence=SimpleNamespace(context=CTX, role="super_admin"),
        scenario_service=subject_service,
    )
    cost = ScenarioRequest(
        CTX,
        "COST_GROWTH",
        account.canonical_id,
        financial_parameters={"percentage": 20},
    )
    suspension = ScenarioRequest(CTX, "ACCOUNT_SUSPENSION", account.canonical_id)
    comparison = (
        cost,
        ScenarioRequest(
            CTX,
            "COST_REDUCTION",
            account.canonical_id,
            financial_parameters={"percentage": 10},
        ),
        ScenarioRequest(CTX, "OWNERSHIP_CHANGE", account.canonical_id),
    )
    copilot_request = CopilotRequest(
        CTX, "What if cloud spend grows 20%?", "super_admin", "performance"
    )
    operations = {
        "cost_growth": lambda: subject_service.simulate(cost, generated_at=NOW),
        "account_suspension": lambda: subject_service.simulate(suspension, generated_at=NOW),
        "three_scenario_comparison": lambda: subject_service.compare(comparison, generated_at=NOW),
        "copilot_explanation": lambda: copilot.explain_scenario(copilot_request, cost),
    }
    limits = {
        "cost_growth": 500,
        "account_suspension": 1000,
        "three_scenario_comparison": 2500,
        "copilot_explanation": 1500,
    }
    report = {}
    for name, operation in operations.items():
        samples = []
        operation()  # warm-up is intentionally excluded
        for _ in range(100):
            started = perf_counter()
            operation()
            samples.append((perf_counter() - started) * 1000)
        report[name] = {
            "samples": len(samples),
            "min_ms": round(min(samples), 4),
            "p50_ms": round(median(samples), 4),
            "p95_ms": round(quantiles(samples, n=100)[94], 4),
            "max_ms": round(max(samples), 4),
        }
        assert report[name]["p95_ms"] < limits[name]
    print(f"PERFORMANCE_CERTIFICATION={report}")


def test_standard_copilot_composition_wires_scenario_service(monkeypatch):
    from enterprise_copilot import composition

    intelligence = SimpleNamespace(context=CTX, role="super_admin")
    search = SimpleNamespace()
    scenarios = SimpleNamespace(simulate=lambda request: request)
    monkeypatch.setattr(
        composition, "enterprise_intelligence_service", lambda *a, **k: intelligence
    )
    monkeypatch.setattr(composition, "enterprise_search_service", lambda *a, **k: search)
    monkeypatch.setattr(composition, "enterprise_scenario_service", lambda *a, **k: scenarios)

    copilot = composition.enterprise_ai_copilot(CTX, role="super_admin")

    assert copilot.intelligence is intelligence
    assert copilot.search is search
    assert copilot.scenario_service is scenarios
