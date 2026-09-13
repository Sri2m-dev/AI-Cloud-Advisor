import pytest

from services.demo_ask_nexora_service import DemoAskNexoraService
from services.demo_tenant_service import DEMO_ORGANIZATION_ID, DemoTenantError, load_demo_tenant


@pytest.fixture(autouse=True)
def demo_enabled(monkeypatch):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")


@pytest.mark.parametrize(
    "question",
    [
        "Where can we reduce costs this quarter?",
        "Where can we reduce costs?",
        "What cost reduction opportunities are available?",
        "Where are our qualified savings opportunities?",
        "How can we lower spending?",
    ],
)
def test_financial_questions_use_shared_authority(question):
    payload = load_demo_tenant(DEMO_ORGANIZATION_ID)
    result = DemoAskNexoraService().ask(question, organization_id=DEMO_ORGANIZATION_ID)
    assert result.supported and result.intent == "value"
    assert "$12.4M annual identified" in result.answer
    assert "$9.6M evidence-qualified" in result.answer
    assert "$3.1M is verified as realized" in result.answer
    assert "$4.2M opportunity" in result.answer
    assert "Quarterly timing and realizable amounts remain UNKNOWN" in result.answer
    assert payload["decisions"][1] in result.facts
    assert payload["analytics"]["savings_waterfall"][1] in result.facts
    assert tuple(p["record"] for p in result.provenance) == result.facts
    assert all(
        p["source"] == payload["source"]
        and p["as_of"] == payload["as_of"]
        and p["organization_id"] == payload["organization_id"]
        for p in result.provenance
    )


@pytest.mark.parametrize(
    "question",
    [
        "Which business services have the highest technology risk?",
        "Which services have the greatest technology risk?",
        "Which business services need intervention?",
        "Where is business-service technology risk highest?",
        "Show business service health",
    ],
)
def test_risk_questions_use_recorded_severity_and_provenance(question):
    payload = load_demo_tenant(DEMO_ORGANIZATION_ID)
    result = DemoAskNexoraService().ask(question, organization_id=DEMO_ORGANIZATION_ID)
    assert result.supported and result.intent == "service_risk"
    assert [r["service"] for r in result.facts[:2]] == [
        "Digital Checkout",
        "Payments Authorization",
    ]
    assert "Critical risk; health 61" in result.answer
    assert "High risk; health 66" in result.answer
    assert "not a complete enterprise ranking" in result.answer
    assert all(r in payload["analytics"]["business_service_health"] for r in result.facts)
    assert tuple(p["record"] for p in result.provenance) == result.facts


@pytest.mark.parametrize(
    "question",
    [
        "What will our exact revenue be next quarter?",
        "Predict next quarter revenue",
        "What savings will we realize next quarter?",
        "Forecast service risk next year",
        "Where can we reduce costs and what will revenue be?",
        "What is the weather?",
    ],
)
def test_unsupported_and_mixed_forecasts_stay_unknown(question):
    result = DemoAskNexoraService().ask(question, organization_id=DEMO_ORGANIZATION_ID)
    assert not result.supported and result.intent == "unknown"
    assert result.answer.startswith("UNKNOWN")
    assert result.facts == result.provenance == ()


@pytest.mark.parametrize("organization_id", ["", None, "production-tenant", "demo-other-tenant"])
@pytest.mark.parametrize(
    "question", ["Where can we reduce costs?", "Which services need intervention?"]
)
def test_no_missing_default_or_cross_tenant_authority(organization_id, question):
    with pytest.raises(DemoTenantError):
        DemoAskNexoraService().ask(question, organization_id=organization_id)


def test_demo_disabled_cannot_fall_back(monkeypatch):
    monkeypatch.delenv("NEXORA_DEMO_MODE")
    with pytest.raises(DemoTenantError):
        DemoAskNexoraService().ask(
            "Where can we reduce costs?", organization_id=DEMO_ORGANIZATION_ID
        )


def test_answers_follow_changed_evidence_and_missing_authority(monkeypatch):
    payload = load_demo_tenant(DEMO_ORGANIZATION_ID)
    payload["analytics"]["savings_waterfall"][1]["value"] = 7500000
    payload["decisions"][1]["financial_impact"] = None
    payload["analytics"]["business_service_health"][0]["risk"] = "Controlled"
    monkeypatch.setattr("services.demo_ask_nexora_service.load_demo_tenant", lambda _: payload)
    service = DemoAskNexoraService()
    value = service.ask("Where can we reduce costs?", organization_id=DEMO_ORGANIZATION_ID)
    assert "$7.5M evidence-qualified" in value.answer
    assert "financial impact UNKNOWN" in value.answer
    risk = service.ask("Which services need intervention?", organization_id=DEMO_ORGANIZATION_ID)
    assert risk.facts[0]["service"] == "Payments Authorization"
    payload["analytics"] = {}
    for question in ("Where can we reduce costs?", "Which services need intervention?"):
        result = service.ask(question, organization_id=DEMO_ORGANIZATION_ID)
        assert not result.supported
        assert result.facts == result.provenance == ()


def test_dataset_tenant_identifier_is_supported():
    payload = load_demo_tenant(DEMO_ORGANIZATION_ID)
    assert (
        DemoAskNexoraService()
        .ask("Where can we reduce costs?", organization_id=payload["organization_id"])
        .supported
    )
