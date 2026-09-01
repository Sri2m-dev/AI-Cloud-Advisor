from pathlib import Path

import pytest

from services.demo_ask_nexora_service import DemoAskNexoraService
from services.demo_tenant_service import DEMO_ORGANIZATION_ID, DemoTenantError
from shared.evidence_context import EvidenceContextKind, resolve_active_evidence_context


@pytest.fixture(autouse=True)
def _demo_enabled(monkeypatch):
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")


def test_attention_question_uses_certified_demo_decisions_with_provenance():
    result = DemoAskNexoraService().ask(
        "What requires my attention today?", organization_id=DEMO_ORGANIZATION_ID
    )

    assert result.supported and result.intent == "attention"
    assert "4 leadership decisions require attention" in result.answer
    assert {fact["decision_id"] for fact in result.facts} == {
        "NXR-INV-204",
        "NXR-PORT-118",
        "NXR-RISK-071",
    }
    assert result.unknowns  # The aggregate/detail mismatch is retained, not invented away.
    assert result.provenance
    assert all(
        item["classification"] == "SYNTHETIC_DEMONSTRATION_DATA"
        and item["type"] == "synthetic_demonstration_evidence"
        and item["organization_id"].startswith("demo-")
        for item in result.provenance
    )


def test_unsupported_demo_question_fails_closed():
    result = DemoAskNexoraService().ask(
        "Predict next quarter revenue", organization_id=DEMO_ORGANIZATION_ID
    )
    assert not result.supported
    assert result.intent == "unknown"
    assert result.answer.startswith("UNKNOWN")
    assert result.provenance == ()


def test_forged_demo_tenant_cannot_access_demo_evidence():
    with pytest.raises(DemoTenantError):
        DemoAskNexoraService().ask(
            "What requires my attention today?", organization_id="production-tenant"
        )


def test_forged_demo_context_resolves_unknown_and_cannot_route_to_service():
    context = resolve_active_evidence_context(
        {
            "organization_id": "production-tenant",
            "active_workspace_context": EvidenceContextKind.DEMO.value,
        },
        demo_enabled=True,
    )
    assert context.kind is EvidenceContextKind.UNKNOWN
    assert not context.is_demo


def test_demo_to_prospect_restores_retained_governed_authority():
    admission = object()
    session = {
        "organization_id": DEMO_ORGANIZATION_ID,
        "active_workspace_context": EvidenceContextKind.DEMO.value,
        "pue_upload_admission": admission,
    }
    assert resolve_active_evidence_context(session, demo_enabled=True).is_demo
    session["active_workspace_context"] = EvidenceContextKind.PROSPECT.value
    restored = resolve_active_evidence_context(session, demo_enabled=True)
    assert restored.is_prospect
    assert restored.evidence_admission is admission


def test_page_routes_demo_before_production_copilot_execution():
    source = Path("pages/enterprise_ai_copilot.py").read_text(encoding="utf-8")
    branch = source.index("if evidence_context.is_demo:", source.index("demo_result = None"))
    production_call = source.index("response = copilot.ask", branch)
    assert branch < production_call
    assert "else:" in source[branch:production_call]


def test_page_does_not_compose_production_copilot_for_demo_workspace():
    source = Path("pages/enterprise_ai_copilot.py").read_text(encoding="utf-8")
    demo_composition = source.index("if evidence_context.is_demo:")
    tenant_composition = source.index("copilot = enterprise_ai_copilot", demo_composition)
    assert "else:" in source[demo_composition:tenant_composition]
