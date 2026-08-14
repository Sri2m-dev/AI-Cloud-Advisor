from __future__ import annotations

import inspect

import pytest

from components.executive_foundation.evidence import CitationView
from components.executive_foundation.narrative import (
    NarrativeKind,
    NarrativeLength,
    NarrativeView,
    SemanticStability,
    assumption_panel_html,
    citation_footer_html,
    narrative_html,
    unknown_statement_html,
)
from components.executive_foundation.states import ComponentState
from components.executive_foundation.version import EXECUTIVE_UI_VERSION


def view(**changes):
    values = dict(
        title="Executive brief",
        text="Governed supplied narrative.",
        kind=NarrativeKind.EXECUTIVE,
        timeframe="Current month",
        authority="Insight",
        status="Informational",
        confidence="High",
        evidence="EV-204",
        citations=(CitationView("Claim", "evidence://204", "Registry"),),
    )
    values.update(changes)
    return NarrativeView(**values)


def test_version_and_stability_contract():
    assert EXECUTIVE_UI_VERSION == "2.5.0"
    assert {item.value for item in SemanticStability} == {"stable", "controlled", "experimental"}


@pytest.mark.parametrize("kind", list(NarrativeKind))
def test_all_narrative_kinds_have_distinct_semantic_class(kind):
    assert f"nexora-narrative--{kind.value}" in narrative_html(view(kind=kind))


@pytest.mark.parametrize("length", list(NarrativeLength))
def test_short_medium_long_contract(length):
    assert f"nexora-narrative--{length.value}" in narrative_html(view(length=length))


@pytest.mark.parametrize("state", list(ComponentState))
def test_narratives_reuse_every_standard_state(state):
    markup = narrative_html(view(state=state, state_reason="Certified state"))
    assert "nexora-state" in markup and "Certified state" in markup


def test_content_is_escaped_and_authority_is_explicit():
    markup = narrative_html(
        view(title="<Decision>", text="A & B", authority="Recommendation proposal")
    )
    assert "&lt;Decision&gt;" in markup and "A &amp; B" in markup
    assert "Recommendation proposal" in markup and "aria-label=" in markup


def test_unknown_assumptions_and_citations_are_supplied_only():
    assert "could not be determined" in unknown_statement_html("Owner could not be determined")
    assert "Provided assumption" in assumption_panel_html(("Provided assumption",))
    assert "evidence://204" in citation_footer_html(
        (CitationView("Claim", "evidence://204", "Registry"),)
    )


def test_narrative_module_has_no_forbidden_dependencies():
    import components.executive_foundation.narrative as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "repository",
        "sqlite",
        "sqlalchemy",
        "requests",
        "httpx",
        "supabase",
        "openai",
    ):
        assert forbidden not in source
