"""PUE-ACT-002G session-local development control tests."""

from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from openpyxl import Workbook

from services.prospect_data_intake_service import ProspectTenant
from universal_evidence.activation import (
    InMemoryActivationAuditSink,
    InMemoryPueActivationRepository,
    PueActivationResolver,
    PueActivationService,
)
from universal_evidence.pilot import PueStage12PilotService, admit_uploaded_evidence
from universal_evidence.pilot.dev_control import (
    SESSION_KILL_SWITCH_KEY,
    SESSION_SCOPE_KEY,
    SESSION_STAGE_KEY,
    apply_dev_control,
    dev_control_enabled,
)
from universal_evidence.shadow import ShadowOrchestrator

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)


def _admission(*, monetary=True):
    workbook = Workbook()
    sheet = workbook.active
    if monetary:
        sheet.title = "12345678"
        for row in range(1, 5):
            sheet.cell(row, 1, f"Metadata {row}")
        sheet.append(("S.No.", "Service", "Price Per Service (USD)"))
        for index in range(1, 185):
            sheet.append((index, "Compute", 10))
    else:
        sheet.append(("Application", "Owner", "Region"))
        sheet.append(("Portal", "Platform", "region-1"))
    stream = BytesIO()
    workbook.save(stream)
    tenant = ProspectTenant(
        "canonical-upload-prospect",
        "audit-upload",
        NOW.isoformat(),
        (NOW + timedelta(days=30)).isoformat(),
        30,
    )
    return admit_uploaded_evidence(
        tenant, filename="CUR Jan 2026.xlsx", content=stream.getvalue(), now=NOW
    )


def _runtime():
    repository = InMemoryPueActivationRepository()
    audit = InMemoryActivationAuditSink()
    activation = PueActivationService(
        repository=repository, audit_sink=audit, clock=lambda: NOW
    )
    pilot = PueStage12PilotService(
        activation_resolver=PueActivationResolver(
            repository=repository, clock=lambda: NOW
        ),
        shadow_orchestrator=ShadowOrchestrator(clock=lambda: NOW),
        audit_sink=audit,
        clock=lambda: NOW,
    )
    return activation, pilot


@pytest.fixture(autouse=True)
def _development_mode(monkeypatch):
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")


@pytest.mark.parametrize(
    "environment",
    ({}, {"PUE_PILOT_DEV_MODE": "false", "ENVIRONMENT": "development"},
     {"PUE_PILOT_DEV_MODE": "true", "ENVIRONMENT": "production"}),
)
def test_controls_absent_by_default_and_in_production(environment):
    assert not dev_control_enabled(environment)


def test_controls_present_only_with_both_development_guards():
    assert dev_control_enabled(
        {"PUE_PILOT_DEV_MODE": "true", "ENVIRONMENT": "development"}
    )


def test_controls_require_canonical_upload_backed_scope():
    activation, _ = _runtime()
    session = {SESSION_STAGE_KEY: 2}
    assert not apply_dev_control(
        object(),
        stage=1,
        kill_switch=False,
        session_state=session,
        activation_service=activation,
    )
    assert SESSION_STAGE_KEY not in session


def test_stage_zero_one_two_and_no_numerical_pue_output():
    admission = _admission()
    activation, pilot = _runtime()
    session = {}

    assert apply_dev_control(
        admission, stage=0, kill_switch=False, session_state=session,
        activation_service=activation,
    )
    assert pilot.experience_upload(admission) is None

    apply_dev_control(
        admission, stage=1, kill_switch=False, session_state=session,
        activation_service=activation,
    )
    discovery = pilot.experience_upload(admission)
    assert discovery is not None and discovery.capability_items == ()
    assert discovery.details.record_count == 184

    apply_dev_control(
        admission, stage=2, kill_switch=False, session_state=session,
        activation_service=activation,
    )
    capabilities = pilot.experience_upload(admission)
    total = next(item for item in capabilities.capability_items if item.label == "Total cost")
    assert total.state == "BLOCKED"
    assert "governed monetary measure and currency" in total.reason
    assert "1840" not in repr(capabilities)
    assert session[SESSION_SCOPE_KEY] == admission.fingerprint


@pytest.mark.parametrize("stage", (3, 4, 5, -1, "invalid"))
def test_stage_three_and_beyond_are_impossible(stage):
    activation, _ = _runtime()
    with pytest.raises(ValueError, match="0, 1, or 2"):
        apply_dev_control(
            _admission(), stage=stage, kill_switch=False, session_state={},
            activation_service=activation,
        )


def test_kill_switch_and_stage_zero_rollback_suppress_panels_without_scope_loss():
    admission = _admission()
    activation, pilot = _runtime()
    session = {}
    apply_dev_control(
        admission, stage=2, kill_switch=False, session_state=session,
        activation_service=activation,
    )
    assert pilot.experience_upload(admission) is not None
    apply_dev_control(
        admission, stage=2, kill_switch=True, session_state=session,
        activation_service=activation,
    )
    assert pilot.experience_upload(admission) is None
    assert session[SESSION_KILL_SWITCH_KEY]
    assert session[SESSION_SCOPE_KEY] == admission.fingerprint
    apply_dev_control(
        admission, stage=0, kill_switch=False, session_state=session,
        activation_service=activation,
    )
    assert pilot.experience_upload(admission) is None
    assert session[SESSION_STAGE_KEY] == 0
    assert not session[SESSION_KILL_SWITCH_KEY]


def test_non_cost_workbook_reaches_stage_one():
    admission = _admission(monetary=False)
    activation, pilot = _runtime()
    apply_dev_control(
        admission, stage=1, kill_switch=False, session_state={},
        activation_service=activation,
    )
    model = pilot.experience_upload(admission)
    assert model is not None
    assert model.details.record_count == 1
    assert model.capability_items == ()
