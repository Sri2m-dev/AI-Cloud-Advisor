import pytest

from services import demo_tenant_service
from services.demo_tenant_service import DemoTenantError
from services.executive_workspace_composition_service import (
    ExecutiveWorkspaceCompositionService,
)


def test_demo_data_requires_explicit_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEXORA_DEMO_MODE", raising=False)

    with pytest.raises(DemoTenantError, match="not enabled"):
        demo_tenant_service.load_demo_tenant("demo-nexora-global-retail")


def test_demo_data_rejects_production_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    with pytest.raises(DemoTenantError, match="isolated demo tenant"):
        demo_tenant_service.load_demo_tenant("customer-production")


def test_demo_uuid_tenant_loads_in_authenticated_composition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    payload = demo_tenant_service.load_demo_tenant(
        demo_tenant_service.DEMO_ORGANIZATION_ID
    )

    assert payload["organization_name"] == "Nexora Global Retail (Synthetic Demo)"


def test_demo_snapshot_is_labeled_and_decision_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    payload = demo_tenant_service.load_demo_tenant("demo-nexora-global-retail")

    snapshot = ExecutiveWorkspaceCompositionService._demo_snapshot("ceo", payload)

    assert snapshot.synthetic is True
    assert all(metric.available for metric in snapshot.metrics)
    assert "$214.0M" in snapshot.metrics[0].value
    assert "NXR-INV-204" in snapshot.story.action
    assert "realized" in snapshot.story.outcome
    assert set(snapshot.analytics or {}) == {
        "budget_vs_actual",
        "vendor_concentration",
        "business_service_health",
        "technology_portfolio",
        "savings_waterfall",
        "recommendation_pipeline",
    }
    assert snapshot.decisions[2]["financial_impact"] is None
    assert sum(row["count"] for row in snapshot.analytics["technology_portfolio"]) == 4260


def test_demo_classification_is_mandatory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    original = demo_tenant_service.DEMO_DATA_PATH
    monkeypatch.setattr(demo_tenant_service, "DEMO_DATA_PATH", original)
    payload = demo_tenant_service.load_demo_tenant("demo-nexora-global-retail")

    assert payload["classification"] == "SYNTHETIC_DEMONSTRATION_DATA"
    assert payload["organization_id"].startswith("demo-")


def test_demo_personas_share_evidence_but_speak_in_decision_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    payload = demo_tenant_service.load_demo_tenant("demo-nexora-global-retail")

    ceo = ExecutiveWorkspaceCompositionService._demo_snapshot("ceo", payload)
    cio = ExecutiveWorkspaceCompositionService._demo_snapshot("cio", payload)
    cfo = ExecutiveWorkspaceCompositionService._demo_snapshot("cfo", payload)

    assert [metric.title for metric in ceo.metrics] == [
        "Technology investment",
        "Business services",
        "Leadership decisions",
    ]
    assert [metric.title for metric in cio.metrics] == [
        "Technology health",
        "Technologies governed",
        "Critical risks",
    ]
    assert [metric.title for metric in cfo.metrics] == [
        "Technology investment",
        "Qualified opportunity",
        "Verified realized",
    ]
    assert len(ceo.journeys) == len(cio.journeys) == len(cfo.journeys) == 3
    assert {journey["decision_id"] for journey in ceo.journeys} == {
        "NXR-INV-204",
        "NXR-PORT-118",
        "NXR-RISK-071",
    }
    assert ceo.story.today != cio.story.today != cfo.story.today
    assert cfo.metrics[1].value == "$12.4M"
    assert cfo.metrics[2].value == "$3.1M"
    assert ceo.journeys[0]["title"] == "Technology investment"
    assert [item["layer"] for item in ceo.journeys[0]["twin_path"]] == [
        "Business Service",
        "Application",
        "Technology",
        "Cloud",
        "Decision",
    ]
    assert "leadership" in ceo.journeys[0]["next_step"].lower() or "CIO" in ceo.journeys[0][
        "next_step"
    ]
