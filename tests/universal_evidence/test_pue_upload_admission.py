"""PUE-ACT-002C universal upload admission and region bootstrap tests."""

from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from openpyxl import Workbook

from services.prospect_data_intake_service import (
    ProspectIntakeError,
    ProspectTenant,
    normalize_upload,
)
from universal_evidence.activation import (
    ActivationActor,
    ActivationPermission,
    ActivationScope,
    ActivationStage,
    InMemoryActivationAuditSink,
    InMemoryPueActivationRepository,
    PueActivationResolver,
    PueActivationService,
    ScopeLevel,
)
from universal_evidence.pilot import PueStage12PilotService, admit_uploaded_evidence
from universal_evidence.pilot.dev_harness import (
    ACTIVE_SCOPE_PATH,
    APPLICATION_ROOT,
    bootstrap_dev_upload_pilot,
    clear_active_pilot_scope,
    load_active_prospect_scope,
    publish_active_upload_scope,
    publish_and_verify_active_upload_scope,
    write_control,
)
from universal_evidence.shadow import ShadowOrchestrator

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)


def _tenant():
    return ProspectTenant(
        "prospect-upload-real-shape",
        "audit-upload-real-shape",
        NOW.isoformat(),
        (NOW + timedelta(days=30)).isoformat(),
        30,
    )


def _real_shape_workbook():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "12345678"
    for row, label in enumerate(
        ("Project Name", "Account Number", "Supporting Document", "Account Name"),
        start=1,
    ):
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        sheet.cell(row, 1, label)
    headers = (
        "S.No.",
        "Service",
        "Sub-Service/Type",
        "Region",
        "UoM",
        "Unit Price - Details",
        "Unit Price (USD)",
        "Qty/Request",
        "Individual Price (USD)",
        "Price Per Service (USD)",
    )
    sheet.append(headers)
    for index in range(1, 185):
        sheet.append(
            (
                index,
                "Compute" if index % 2 else "Storage",
                "Observed type",
                "region-1",
                "Hours",
                "source rate",
                1.25,
                2,
                2.5,
                4683 if index < 184 else 4871.62008191,
            )
        )
    sheet.append(
        (None, "Total", None, None, None, None, None, None, None, 861830.62008191)
    )
    sheet.append(())
    sheet.append(())
    sheet.append(())
    sheet.append(("Row Labels", "Sum of Price Per Service (USD)"))
    sheet.append(("Compute", 500000))
    sheet.append(("Storage", 361830.62008191))
    sheet.append(("Grand Total", 861830.62008191))
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _non_cost_workbook():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(("Application", "Owner", "Region", "Contract Renewal Date"))
    sheet.append(("Portal", "Platform", "region-1", "2026-12-01"))
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _pilot():
    repository = InMemoryPueActivationRepository()
    audit = InMemoryActivationAuditSink()
    activation = PueActivationService(
        repository=repository, audit_sink=audit, clock=lambda: NOW
    )
    service = PueStage12PilotService(
        activation_resolver=PueActivationResolver(
            repository=repository, clock=lambda: NOW
        ),
        shadow_orchestrator=ShadowOrchestrator(clock=lambda: NOW),
        audit_sink=audit,
        clock=lambda: NOW,
    )
    return activation, service


def _activate(activation, admission, stage):
    actor = ActivationActor(
        "upload-pilot-admin",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        (
            ActivationPermission.CHANGE_PUE_STAGE,
            ActivationPermission.TRIGGER_PUE_KILL_SWITCH,
            ActivationPermission.TRIGGER_PUE_ROLLBACK,
        ),
    )
    return activation.configure(
        scope=ActivationScope(
            ScopeLevel.ANALYSIS,
            analysis_id=admission.scope.analysis_id,
            prospect_id=admission.scope.prospect_id,
        ),
        stage=stage,
        actor=actor,
        reason="ACT-002C upload admission fixture",
    )


def test_real_workbook_shape_detects_header_detail_and_separate_summary():
    admission = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=_real_shape_workbook(), now=NOW
    )
    primary = next(item for item in admission.regions if item.region_kind == "PRIMARY_DETAIL")
    secondary = next(
        item for item in admission.regions if item.region_kind == "SECONDARY_SUMMARY"
    )
    assert primary.sheet_name == "12345678"
    assert primary.header_row == 5
    assert primary.start_row == 5 and primary.end_row == 189
    assert primary.detail_record_count == 184
    assert "Price Per Service (USD)" in primary.original_headers
    assert secondary.start_row == 194
    assert admission.profile.sheets[0].sheet.has_merged_cells
    assert admission.profile.logical_data_row_count is None


def test_legacy_schema_failure_does_not_prevent_pue_admission():
    content = _real_shape_workbook()
    with pytest.raises(ProspectIntakeError, match="supported cost or amount"):
        normalize_upload("Generic technology-cost Excel/CSV", "evidence.xlsx", content)
    admission = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=content, now=NOW
    )
    assert admission.regions
    assert admission.authority == "SHADOW / NON-AUTHORITATIVE"


def test_legacy_failure_upload_publishes_through_runtime_helper(monkeypatch, tmp_path):
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    content = _real_shape_workbook()
    with pytest.raises(ProspectIntakeError, match="supported cost or amount"):
        normalize_upload("Generic technology-cost Excel/CSV", "evidence.xlsx", content)
    admission = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=content, now=NOW
    )
    path = tmp_path / "missing" / ".streamlit" / "active.json"
    published = publish_and_verify_active_upload_scope(admission, path=path)
    assert path.is_file()
    assert load_active_prospect_scope(path) == published
    assert published.scope_source == "UPLOAD_EVIDENCE"


def test_non_cost_enterprise_evidence_is_admitted_without_monetary_requirement():
    admission = admit_uploaded_evidence(
        _tenant(), filename="inventory.xlsx", content=_non_cost_workbook(), now=NOW
    )
    primary = admission.regions[0]
    assert primary.detail_record_count == 1
    assert primary.original_headers == (
        "Application",
        "Owner",
        "Region",
        "Contract Renewal Date",
    )


def test_stage_one_shows_structural_observation_as_pending_not_semantic_truth():
    admission = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=_real_shape_workbook(), now=NOW
    )
    activation, service = _pilot()
    _activate(activation, admission, ActivationStage.EVIDENCE_DISCOVERY_VISIBLE)
    model = service.experience_upload(admission)
    assert model.capability_items == ()
    assert model.details.record_count == 184
    assert all(item.state == "PENDING_GOVERNANCE" for item in model.evidence_items)
    assert "861830" not in repr(model)


def test_stage_two_blocks_total_without_calculation_or_currency_authority():
    admission = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=_real_shape_workbook(), now=NOW
    )
    activation, service = _pilot()
    _activate(activation, admission, ActivationStage.CAPABILITY_VISIBLE)
    model = service.experience_upload(admission)
    total = next(item for item in model.capability_items if item.label == "Total cost")
    assert total.state == "BLOCKED"
    assert "governed monetary measure and currency" in total.reason
    assert not hasattr(model, "amount")
    assert "861830" not in repr(model)


def test_upload_active_scope_handoff_is_exact_and_non_sensitive(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    admission = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=_real_shape_workbook(), now=NOW
    )
    path = tmp_path / "active.json"
    published = publish_active_upload_scope(admission, path=path)
    loaded = load_active_prospect_scope(path)
    assert loaded == published
    assert loaded.scope_source == "UPLOAD_EVIDENCE"
    assert loaded.evidence_fingerprint == admission.evidence_fingerprint
    assert "861830" not in path.read_text(encoding="utf-8")


def test_upload_active_scope_is_deterministic_and_replaced_by_changed_evidence(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    path = tmp_path / "active.json"
    content = _real_shape_workbook()
    first = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=content, now=NOW
    )
    repeated = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=content, now=NOW
    )
    assert publish_active_upload_scope(first, path=path) == publish_active_upload_scope(
        repeated, path=path
    )

    changed_content = _real_shape_workbook() + b"changed"
    changed = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=changed_content, now=NOW
    )
    publish_active_upload_scope(changed, path=path)
    loaded = load_active_prospect_scope(path)
    assert loaded.analysis_id != first.scope.analysis_id
    assert loaded.evidence_fingerprint != first.evidence_fingerprint
    clear_active_pilot_scope(path=path)
    assert not path.exists()


@pytest.mark.parametrize(
    ("pilot_mode", "environment"),
    (("false", "development"), ("true", "production")),
)
def test_upload_active_scope_publication_fails_closed(
    monkeypatch, tmp_path, pilot_mode, environment
):
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", pilot_mode)
    monkeypatch.setenv("ENVIRONMENT", environment)
    admission = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=_real_shape_workbook(), now=NOW
    )
    path = tmp_path / "active.json"
    assert publish_active_upload_scope(admission, path=path) is None
    assert not path.exists()


def test_default_handoff_path_is_application_root_derived_and_cwd_independent(
    monkeypatch, tmp_path
):
    expected = APPLICATION_ROOT / ".streamlit" / "pue-pilot-active-scope.json"
    assert ACTIVE_SCOPE_PATH == expected
    assert ACTIVE_SCOPE_PATH.is_absolute()
    monkeypatch.chdir(tmp_path)
    assert ACTIVE_SCOPE_PATH == expected


def test_upload_active_scope_surfaces_real_filesystem_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("occupied", encoding="utf-8")
    admission = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=_real_shape_workbook(), now=NOW
    )
    with pytest.raises(OSError):
        publish_active_upload_scope(admission, path=blocked_parent / "active.json")


def test_upload_harness_rejects_wrong_scope_and_accepts_exact_scope(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    admission = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=_real_shape_workbook(), now=NOW
    )
    control = tmp_path / "control.json"
    write_control(
        analysis_id="wrong-analysis",
        prospect_id=admission.scope.prospect_id,
        stage=1,
        scope_source="UPLOAD_EVIDENCE",
        evidence_fingerprint=admission.evidence_fingerprint,
        path=control,
    )
    assert not bootstrap_dev_upload_pilot(admission, path=control)
    write_control(
        analysis_id=admission.scope.analysis_id,
        prospect_id=admission.scope.prospect_id,
        stage=1,
        scope_source="UPLOAD_EVIDENCE",
        evidence_fingerprint=admission.evidence_fingerprint,
        path=control,
    )
    assert bootstrap_dev_upload_pilot(admission, path=control)


def test_upload_backed_kill_switch_and_rollback_hide_pue_without_mutation():
    admission = admit_uploaded_evidence(
        _tenant(), filename="evidence.xlsx", content=_real_shape_workbook(), now=NOW
    )
    activation, service = _pilot()
    _activate(activation, admission, ActivationStage.CAPABILITY_VISIBLE)
    assert service.experience_upload(admission) is not None
    actor = ActivationActor(
        "upload-pilot-admin",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        (
            ActivationPermission.CHANGE_PUE_STAGE,
            ActivationPermission.TRIGGER_PUE_KILL_SWITCH,
            ActivationPermission.TRIGGER_PUE_ROLLBACK,
        ),
    )
    activation.set_kill_switch(
        enabled=True, actor=actor, reason="ACT-002C kill-switch fixture"
    )
    assert service.experience_upload(admission) is None

    clean_activation, clean_service = _pilot()
    config = _activate(
        clean_activation, admission, ActivationStage.CAPABILITY_VISIBLE
    )
    clean_activation.rollback(
        config,
        target_stage=ActivationStage.SHADOW_ONLY,
        actor=actor,
        reason="ACT-002C rollback fixture",
    )
    assert clean_service.experience_upload(admission) is None
    assert admission.profile.evidence_file.content_hash == admission.evidence_fingerprint


def test_page_admits_upload_before_legacy_ingestion_and_keeps_ask_nexora_untouched():
    page = open("pages/analyze_environment.py", encoding="utf-8").read()
    assert page.index("admit_uploaded_evidence(") < page.index("prospect_analysis = ingest_upload(")
    admission_index = page.index("admission = admit_uploaded_evidence(")
    ingestion_index = page.index("prospect_analysis = ingest_upload(")
    assert admission_index < ingestion_index
    assert "publish_and_verify_active_upload_scope(admission)" not in page
    assert "render_dev_control(st, admission)" in page
    assert "PueQuestionRouter" not in page
    assert "run_shadow_question" not in page
