from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from shared.evidence_context import (
    EvidenceContextKind,
    clear_prospect_context,
    resolve_active_evidence_context,
)
from shared.prospect_answers import prospect_evidence_answer


ROOT = Path(__file__).parents[2]
SYNTHETIC_MARKERS = (
    "NXR-INV-204",
    "NXR-PORT-118",
    "NXR-RISK-071",
    "$214M",
    "$12.4M",
)

PROSPECT_GATED_PAGES = (
    "enterprise_ai_copilot.py",
    "decision_intelligence.py",
    "risk_governance.py",
    "business_services.py",
    "reports.py",
    "leadership_dashboard.py",
)


def test_prospect_context_takes_precedence_over_demo_tenant() -> None:
    analysis = SimpleNamespace(tenant_id="prospect-123")
    context = resolve_active_evidence_context(
        {
            "organization_id": "demo-nexora-global-retail",
            "prospect_analysis": analysis,
        },
        demo_enabled=True,
    )
    assert context.kind is EvidenceContextKind.PROSPECT
    assert context.prospect_analysis is analysis


def test_resolver_distinguishes_demo_tenant_and_unknown() -> None:
    assert resolve_active_evidence_context({}, demo_enabled=True).kind is EvidenceContextKind.UNKNOWN
    assert (
        resolve_active_evidence_context(
            {"organization_id": "demo-nexora-global-retail"}, demo_enabled=True
        ).kind
        is EvidenceContextKind.DEMO
    )
    assert (
        resolve_active_evidence_context(
            {"organization_id": "customer-production"}, demo_enabled=True
        ).kind
        is EvidenceContextKind.TENANT
    )


def test_return_to_demo_clears_entire_prospect_boundary() -> None:
    session = {
        "prospect_tenant": object(),
        "prospect_analysis": object(),
        "prospect_name": "ASN",
        "prospect_analysis_error": "old",
        "analysis_start_path": "upload",
        "organization_id": "demo-nexora-global-retail",
    }
    clear_prospect_context(session)
    assert not any(key.startswith("prospect_") for key in session)
    assert "analysis_start_path" not in session
    assert session["organization_id"] == "demo-nexora-global-retail"


def test_every_named_surface_has_a_prospect_first_gate() -> None:
    for filename in PROSPECT_GATED_PAGES:
        source = (ROOT / "pages" / filename).read_text(encoding="utf-8")
        gate = source.index("if evidence_context.is_prospect:")
        assert gate < source.find("load_demo_tenant", gate) or source.find(
            "load_demo_tenant", gate
        ) == -1

    twin = (ROOT / "pages" / "twin_explorer.py").read_text(encoding="utf-8")
    render_page = twin.index("def render_page()")
    gate = twin.index("if evidence_context.is_prospect:", render_page)
    demo_load = twin.index("_render_demo_decision_twin", gate)
    assert gate < demo_load


def test_prospect_branches_do_not_contain_synthetic_identifiers_or_values() -> None:
    for filename in PROSPECT_GATED_PAGES:
        source = (ROOT / "pages" / filename).read_text(encoding="utf-8")
        start = source.index("if evidence_context.is_prospect:")
        end = source.index("st.stop()", start) + len("st.stop()")
        prospect_branch = source[start:end]
        assert all(marker not in prospect_branch for marker in SYNTHETIC_MARKERS)

    shared = (ROOT / "shared" / "executive_page.py").read_text(encoding="utf-8")
    start = shared.index("def _render_prospect_workspace")
    end = shared.index("def run_executive_workspace", start)
    prospect_branch = shared[start:end]
    assert all(marker not in prospect_branch for marker in SYNTHETIC_MARKERS)


def _analysis() -> SimpleNamespace:
    return SimpleNamespace(
        total_spend=861_828,
        currency="USD",
        currency_resolution_required=False,
        row_count=184,
        evidence_coverage=100.0,
        opportunity_evidence_qualified=0,
    )


def test_prospect_answer_distinguishes_total_from_ec2_specific_cost() -> None:
    assert prospect_evidence_answer("what is the total cost", _analysis()) == (
        "Total observed spend in the current prospect analysis is $861,828."
    )
    answer = prospect_evidence_answer("what is the total cost of EC2", _analysis())
    assert answer.startswith("EC2-specific spend is not evidenced")
    assert "$861,828" in answer
    assert "184 records" in answer


def test_prospect_answer_preserves_unknown_for_unsupported_domains() -> None:
    for question in (
        "What is the risk?",
        "Which business service needs attention?",
        "What is the EC2 forecast?",
    ):
        answer = prospect_evidence_answer(question, _analysis())
        assert answer.startswith("UNKNOWN")
        assert "$214M" not in answer
        assert "NXR-" not in answer
