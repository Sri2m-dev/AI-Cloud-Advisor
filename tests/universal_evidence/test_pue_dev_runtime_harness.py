"""PUE-ACT-002A local runtime acceptance harness safety tests."""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from universal_evidence.activation import ActivationStage
from universal_evidence.pilot.dev_harness import (
    DevHarnessError,
    bootstrap_dev_pilot_session,
    harness_enabled,
    load_active_prospect_scope,
    load_control,
    publish_active_prospect_scope,
    resolve_active_prospect_scope,
    write_control,
)


def _enable(monkeypatch):
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")


def _payload(*, stage=1, expires_at=None):
    return {
        "analysis_id": "analysis-runtime-cert",
        "prospect_id": "prospect-runtime-cert",
        "organization_id": None,
        "tenant_id": None,
        "stage": stage,
        "expires_at": (
            expires_at or datetime.now(timezone.utc) + timedelta(minutes=30)
        ).isoformat(),
        "kill_switch": False,
        "fixture": "legacy-184",
    }


def _prospect():
    return SimpleNamespace(
        tenant_id="prospect-runtime-authoritative",
        audit_id="audit-runtime-cert",
        analysis_timestamp="2026-08-27T10:00:00+00:00",
        row_count=184,
        currency_source="UNRESOLVED",
        currency_resolution_required=True,
        total_spend=861828,
    )


def test_harness_is_off_by_default_and_in_production(monkeypatch):
    monkeypatch.delenv("PUE_PILOT_DEV_MODE", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert not harness_enabled()
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert not harness_enabled()


def test_write_requires_explicit_non_production_enablement(monkeypatch, tmp_path):
    monkeypatch.delenv("PUE_PILOT_DEV_MODE", raising=False)
    with pytest.raises(DevHarnessError):
        write_control(
            analysis_id="analysis-1",
            prospect_id="prospect-1",
            stage=1,
            path=tmp_path / "control.json",
        )


@pytest.mark.parametrize("stage", [0, 1, 2])
def test_only_stage_zero_one_and_two_controls_are_accepted(monkeypatch, tmp_path, stage):
    _enable(monkeypatch)
    path = write_control(
        analysis_id="analysis-1",
        prospect_id="prospect-1",
        stage=stage,
        expires_minutes=10,
        path=tmp_path / f"stage-{stage}.json",
    )
    assert load_control(path).stage is ActivationStage(stage)


@pytest.mark.parametrize("stage", [3, 4, 5])
def test_stage_three_and_higher_cannot_be_written(monkeypatch, tmp_path, stage):
    _enable(monkeypatch)
    with pytest.raises(DevHarnessError):
        write_control(
            analysis_id="analysis-1",
            prospect_id="prospect-1",
            stage=stage,
            path=tmp_path / "control.json",
        )


def test_target_analysis_and_prospect_are_mandatory(monkeypatch, tmp_path):
    _enable(monkeypatch)
    with pytest.raises(DevHarnessError):
        write_control(
            analysis_id="",
            prospect_id="prospect-1",
            stage=1,
            path=tmp_path / "control.json",
        )


def test_expired_or_excessively_long_controls_fail_closed(monkeypatch, tmp_path):
    _enable(monkeypatch)
    for name, expiry in (
        ("expired", datetime.now(timezone.utc) - timedelta(minutes=1)),
        ("too-long", datetime.now(timezone.utc) + timedelta(hours=5)),
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(_payload(expires_at=expiry)), encoding="utf-8")
        with pytest.raises(DevHarnessError):
            load_control(path)


def test_expired_control_clears_only_dev_harness_session_without_page_failure(
    monkeypatch, tmp_path
):
    _enable(monkeypatch)
    path = tmp_path / "expired.json"
    path.write_text(
        json.dumps(
            _payload(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        ),
        encoding="utf-8",
    )
    session = {
        "pue_dev_harness_active": True,
        "pue_pilot_context": object(),
        "pue_shadow_analysis": object(),
        "unrelated": "preserved",
    }
    assert not bootstrap_dev_pilot_session(session, SimpleNamespace(), path=path)
    assert "pue_pilot_context" not in session
    assert "pue_shadow_analysis" not in session
    assert session["unrelated"] == "preserved"


def test_scope_and_absent_tenant_context_are_preserved(monkeypatch, tmp_path):
    _enable(monkeypatch)
    path = tmp_path / "control.json"
    path.write_text(json.dumps(_payload(stage=2)), encoding="utf-8")
    control = load_control(path)
    assert control.analysis_id == "analysis-runtime-cert"
    assert control.prospect_id == "prospect-runtime-cert"
    assert control.organization_id is None
    assert control.tenant_id is None


def test_active_scope_comes_only_from_authoritative_prospect_identity():
    prospect = _prospect()
    scope = resolve_active_prospect_scope(prospect)
    assert scope.prospect_id == prospect.tenant_id
    assert scope.analysis_id.startswith("prospect-analysis-")
    assert scope.organization_id is None
    assert scope.tenant_id is None
    assert scope == resolve_active_prospect_scope(prospect)


def test_dev_scope_handoff_contains_no_prospect_result_or_credentials(
    monkeypatch, tmp_path
):
    _enable(monkeypatch)
    path = tmp_path / "active.json"
    expected = publish_active_prospect_scope(_prospect(), path=path)
    assert load_active_prospect_scope(path) == expected
    raw = path.read_text(encoding="utf-8")
    assert "861828" not in raw
    assert "authenticated" not in raw
    assert "currency_source" not in raw


@pytest.mark.parametrize("wrong_field", ["analysis_id", "prospect_id", "tenant_id"])
def test_wrong_analysis_prospect_or_tenant_scope_cannot_activate(
    monkeypatch, tmp_path, wrong_field
):
    _enable(monkeypatch)
    prospect = _prospect()
    active = resolve_active_prospect_scope(prospect)
    payload = _payload(stage=2)
    payload.update(
        analysis_id=active.analysis_id,
        prospect_id=active.prospect_id,
        organization_id=active.organization_id,
        tenant_id=active.tenant_id,
    )
    payload[wrong_field] = "wrong-scope"
    path = tmp_path / f"wrong-{wrong_field}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    session = {}
    assert not bootstrap_dev_pilot_session(session, prospect, path=path)
    assert "pue_pilot_context" not in session


def test_bootstrap_runs_real_synthetic_184_shadow_without_changing_prospect(
    monkeypatch, tmp_path
):
    _enable(monkeypatch)
    path = tmp_path / "control.json"
    prospect = _prospect()
    active = resolve_active_prospect_scope(prospect)
    payload = _payload(stage=2)
    payload.update(
        analysis_id=active.analysis_id,
        prospect_id=active.prospect_id,
        organization_id=active.organization_id,
        tenant_id=active.tenant_id,
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = vars(prospect).copy()
    session = {}
    assert bootstrap_dev_pilot_session(session, prospect, path=path)
    shadow = session["pue_shadow_analysis"]
    context = session["pue_pilot_context"]
    assert shadow.source_rows == 184
    assert shadow.capability_assessment.scope == context.scope
    currency = next(
        coverage
        for coverage in shadow.capability_assessment.coverage
        if coverage.semantic_concept_id == "financial.currency"
    )
    assert currency.coverage_state.value == "NOT_EVIDENCED"
    assert "861828" not in repr(shadow.capability_assessment)
    assert vars(prospect) == before
    second_session = {}
    assert bootstrap_dev_pilot_session(second_session, prospect, path=path)
    assert second_session["pue_shadow_analysis"] is shadow
