from __future__ import annotations

import inspect

import pytest

from components.executive_foundation.kpi import (
    DeltaView,
    KpiKind,
    KpiView,
    SparklinePlaceholder,
    ThresholdView,
    TrendDirection,
    TrendView,
    kpi_card_html,
)
from components.executive_foundation.states import ComponentState
from components.executive_foundation.version import EXECUTIVE_UI_VERSION


def _view(**overrides):
    values = {
        "title": "Current spend",
        "value": "$1.2M",
        "meaning": "Authoritative current spend.",
        "source": "Financial Data Fabric",
        "period": "August 2026",
        "freshness": "Reconciled 10 min ago",
    }
    values.update(overrides)
    return KpiView(**values)


def test_ui_library_has_independent_semantic_version():
    assert EXECUTIVE_UI_VERSION == "2.4.0"


def test_kpi_escapes_content_and_discloses_provenance():
    markup = kpi_card_html(_view(title="<Spend>", meaning="A & B"))
    for expected in (
        "&lt;Spend&gt;",
        "A &amp; B",
        "Financial Data Fabric",
        "August 2026",
        "Reconciled 10 min ago",
        "aria-label=",
    ):
        assert expected in markup


@pytest.mark.parametrize("kind", list(KpiKind))
def test_all_six_kpi_variants_have_stable_semantic_class(kind):
    assert f"nexora-kpi--{kind.value}" in kpi_card_html(_view(kind=kind))


def test_supporting_elements_render_supplied_metadata_only():
    markup = kpi_card_html(
        _view(
            delta=DeltaView("-8%", "prior month"),
            trend=TrendView("Stable", TrendDirection.STABLE),
            confidence="Supplied: medium",
            coverage="82%",
            evidence="12 sources",
            materiality="Not assessed",
            authority="Decision",
            threshold=ThresholdView("Within approved band", "Band B"),
            sparkline=SparklinePlaceholder(),
        )
    )
    for expected in ("-8%", "Stable", "82%", "12 sources", "Not assessed", "Decision", "Band B"):
        assert expected in markup


@pytest.mark.parametrize("state", list(ComponentState))
def test_kpi_uses_foundation_state_contract(state):
    markup = kpi_card_html(_view(state=state, state_reason="Governed reason"))
    assert "nexora-state" in markup
    assert "Governed reason" in markup
    assert "nexora-kpi__value" not in markup


def test_kpi_module_has_no_forbidden_data_or_service_imports():
    import components.executive_foundation.kpi as module

    source = inspect.getsource(module).lower()
    for forbidden in ("repository", "sqlite", "sqlalchemy", "requests", "httpx", "supabase"):
        assert forbidden not in source
