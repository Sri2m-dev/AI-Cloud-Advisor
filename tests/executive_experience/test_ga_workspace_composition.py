import pytest
from streamlit.testing.v1 import AppTest

from components import executive_experience
from services import demo_tenant_service
from services.demo_tenant_service import (
    DEMO_ORGANIZATION_ID,
    DEMO_ORGANIZATION_NAME,
    DemoTenantError,
)
from services.executive_workspace_composition_service import (
    ExecutiveWorkspaceCompositionService,
)
from shared.evidence_context import EvidenceContextKind


@pytest.mark.parametrize("demo_mode", [None, "false"])
def test_demo_data_requires_explicit_mode(
    monkeypatch: pytest.MonkeyPatch, demo_mode: str | None
) -> None:
    if demo_mode is None:
        monkeypatch.delenv("NEXORA_DEMO_MODE", raising=False)
    else:
        monkeypatch.setenv("NEXORA_DEMO_MODE", demo_mode)

    with pytest.raises(DemoTenantError, match="not enabled"):
        demo_tenant_service.load_demo_tenant(demo_tenant_service.DEMO_ORGANIZATION_ID)


def test_demo_data_rejects_production_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    with pytest.raises(DemoTenantError, match="isolated demo tenant"):
        demo_tenant_service.load_demo_tenant("customer-production")
    with pytest.raises(DemoTenantError, match="isolated demo tenant"):
        demo_tenant_service.load_demo_tenant("demo-nexora-global-retail")


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
    payload = demo_tenant_service.load_demo_tenant(demo_tenant_service.DEMO_ORGANIZATION_ID)

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
    payload = demo_tenant_service.load_demo_tenant(demo_tenant_service.DEMO_ORGANIZATION_ID)

    assert payload["classification"] == "SYNTHETIC_DEMONSTRATION_DATA"
    assert payload["organization_id"] == demo_tenant_service.DEMO_ORGANIZATION_ID


def test_demo_personas_share_evidence_but_speak_in_decision_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    payload = demo_tenant_service.load_demo_tenant(demo_tenant_service.DEMO_ORGANIZATION_ID)

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


def test_demo_executive_command_center_renders_canonical_tenant_and_synthetic_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    monkeypatch.delenv("NEXORA_UNIVERSAL_EVIDENCE_DB", raising=False)
    monkeypatch.setattr(executive_experience.st, "page_link", lambda *args, **kwargs: None)
    app = AppTest.from_file(
        "pages/executive_command_center.py",
        default_timeout=60,
    )
    app.session_state["authenticated"] = True
    app.session_state["role"] = "super_admin"
    app.session_state["user"] = "admin@company.com"
    app.session_state["email"] = "admin@company.com"
    app.session_state["user_id"] = "demo-admin"
    app.session_state["organization_id"] = DEMO_ORGANIZATION_ID
    app.session_state["org_id"] = DEMO_ORGANIZATION_ID
    app.session_state["tenant_id"] = DEMO_ORGANIZATION_ID
    app.session_state["organization_name"] = DEMO_ORGANIZATION_NAME
    app.session_state["auth_backend"] = "local"
    app.session_state["authorized_organization_ids"] = [DEMO_ORGANIZATION_ID]
    app.session_state["active_workspace_context"] = EvidenceContextKind.DEMO.value
    app.run()

    assert not app.exception
    assert app.session_state["organization_id"] == DEMO_ORGANIZATION_ID
    assert app.session_state["organization_name"] == DEMO_ORGANIZATION_NAME
    rendered = "\n".join(
        str(item.value)
        for kind in ("markdown", "caption", "title", "subheader", "warning")
        for item in app.get(kind)
    )
    assert DEMO_ORGANIZATION_NAME in rendered
    assert "Demo Enterprise" not in rendered
    assert "SYNTHETIC DEMONSTRATION DATA" in rendered
    assert "Technology investment" in rendered
    assert "$214.0M" in rendered
