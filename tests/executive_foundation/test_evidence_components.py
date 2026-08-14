from __future__ import annotations

import inspect

import pytest

from components.executive_foundation.evidence import (
    CitationView,
    EvidenceEventView,
    EvidenceItemView,
    EvidenceSummaryView,
    citation_html,
    evidence_card_html,
    evidence_summary_html,
    evidence_timeline_html,
    indicator_html,
    source_badge_html,
)
from components.executive_foundation.states import ComponentState
from components.executive_foundation.version import EXECUTIVE_UI_VERSION

STATES = tuple(ComponentState)


def item(**changes):
    values = dict(
        title="Cost fact",
        source="AWS",
        observed_at="13 Aug",
        version="v3",
        confidence="High",
        freshness="Fresh",
        classification="Internal",
        authority="Fact",
        citation=CitationView("CUR row", "ev://123", "AWS"),
    )
    values.update(changes)
    return EvidenceItemView(**values)


def test_version_and_state_baseline():
    assert EXECUTIVE_UI_VERSION == "2.3.0"
    assert ComponentState.UNSUPPORTED in STATES


@pytest.mark.parametrize("state", STATES)
def test_evidence_card_supports_every_certification_state(state):
    markup = evidence_card_html(item(state=state, state_reason="Certified fixture"))
    assert "nexora-state" in markup and "Certified fixture" in markup


@pytest.mark.parametrize("state", STATES)
def test_summary_and_timeline_support_every_certification_state(state):
    summary = evidence_summary_html(
        EvidenceSummaryView("8", "92%", "Fresh", "High", "Fact", state=state)
    )
    timeline = evidence_timeline_html((), state=state)
    assert "nexora-state" in summary and "nexora-state" in timeline


def test_authorized_and_unauthorized_citations_are_distinct():
    assert "ev://123" in citation_html(CitationView("Row", "ev://123", "AWS"))
    denied = citation_html(CitationView("Secret", "secret://id", "CMDB", authorized=False))
    assert "secret://id" not in denied and "not disclosed" in denied


def test_evidence_content_is_escaped_and_semantic():
    markup = evidence_card_html(item(title="<Fact>", source="A & B"))
    assert "&lt;Fact&gt;" in markup and "A &amp; B" in markup and "aria-label=" in markup
    assert "Evidence chronology" in evidence_timeline_html(
        (EvidenceEventView("Observed", "1", "2", "AWS", "Fact", "EV-1"),)
    )


def test_indicators_and_source_badge_are_accessible():
    assert 'role="status"' in indicator_html("Freshness", "Fresh", kind="freshness")
    assert "Evidence source: AWS" in source_badge_html("AWS")


def test_evidence_module_has_no_forbidden_dependencies():
    import components.executive_foundation.evidence as module

    source = inspect.getsource(module).lower()
    for forbidden in ("repository", "sqlite", "sqlalchemy", "requests", "httpx", "supabase"):
        assert forbidden not in source
