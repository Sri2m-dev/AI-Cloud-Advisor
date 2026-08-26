"""PUE-010 certification-report and negative-boundary contracts."""

from dataclasses import fields

from universal_evidence.shadow import (
    ActivationReadiness,
    ShadowAnalysisResult,
    ShadowQuestionResult,
    build_certification_report,
)


def test_certification_report_keeps_activation_explicitly_blocked():
    report = build_certification_report(
        (("fully_governed", "PASS"), ("missing_currency", "BLOCKED_BY_DESIGN"))
    )
    assert report.readiness is ActivationReadiness.READY_FOR_LIMITED_SHADOW
    assert report.activation_blockers
    assert "NON-AUTHORITATIVE" in report.authority


def test_shadow_contracts_have_no_production_activation_or_session_surface():
    names = {
        item.name
        for contract in (ShadowAnalysisResult, ShadowQuestionResult)
        for item in fields(contract)
    }
    forbidden = {
        "session_state",
        "production_repository",
        "activate",
        "legacy_total",
        "streamlit",
        "database",
        "ask_nexora",
    }
    assert not names & forbidden


def test_documented_certification_matrix_contains_required_safety_scenarios():
    text = open("docs/pue/PUE_010_ACCEPTANCE_MATRIX.md", encoding="utf-8").read()
    for scenario in (
        "184-row missing currency",
        "Fully governed CSV",
        "Mixed currency",
        "Irregular XLSX",
        "Ambiguous semantics",
        "Rejected mapping",
        "Stale authorization",
        "Cross-tenant",
        "Deterministic replay",
        "Purge",
    ):
        assert scenario in text
