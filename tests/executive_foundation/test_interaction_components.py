from __future__ import annotations

import inspect

import pytest

from components.executive_foundation.interaction import (
    InteractionKind,
    InteractionOption,
    InteractionView,
    interaction_html,
)
from components.executive_foundation.narrative import SemanticStability
from components.executive_foundation.states import ComponentState
from components.executive_foundation.version import EXECUTIVE_UI_VERSION


def view(**changes):
    values = dict(
        title="Executive search",
        kind=InteractionKind.SEARCH,
        purpose="Presentation intent only.",
        options=(InteractionOption("Search", "search", selected=True),),
        context=(("Persona", "CEO"), ("Scope", "Enterprise")),
        primary_intent="open_search",
        stability=SemanticStability.CONTROLLED,
    )
    values.update(changes)
    return InteractionView(**values)


def test_version_and_all_requested_interaction_kinds():
    assert EXECUTIVE_UI_VERSION == "2.5.0"
    assert len(InteractionKind) == 14


@pytest.mark.parametrize("kind", list(InteractionKind))
def test_every_interaction_has_distinct_semantic_class(kind):
    assert f"nexora-interaction--{kind.value}" in interaction_html(view(kind=kind))


@pytest.mark.parametrize("state", list(ComponentState))
def test_interactions_reuse_every_standard_state(state):
    markup = interaction_html(view(state=state, state_reason="Certified state"))
    assert "nexora-state" in markup and "Certified state" in markup


def test_intents_context_and_disabled_options_are_presentation_only():
    markup = interaction_html(
        view(
            options=(InteractionOption("Execute", "execute", enabled=False),),
            primary_intent="review_recommendation",
        )
    )
    assert 'aria-disabled="true"' in markup
    assert "review_recommendation" in markup and "Persona" in markup
    assert "Presentation intent only" in markup


def test_content_is_escaped():
    markup = interaction_html(view(title="<Search>", purpose="A & B"))
    assert "&lt;Search&gt;" in markup and "A &amp; B" in markup


def test_interaction_module_has_no_forbidden_dependencies():
    import components.executive_foundation.interaction as module

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
