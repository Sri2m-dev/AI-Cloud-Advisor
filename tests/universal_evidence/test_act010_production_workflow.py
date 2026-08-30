from types import SimpleNamespace

from shared.evidence_context import clear_prospect_context, resolve_active_evidence_context
from universal_evidence.production_workflow import (
    activate_production_workflow,
    evidence_counts,
    upload_outcome,
)


def test_universal_evidence_success_overrides_legacy_failure_presentation():
    admission = object()
    outcome = upload_outcome(
        admission=admission,
        legacy_error="a supported cost or amount column is required",
    )
    assert outcome.state == "ADMITTED"
    assert outcome.message == "Evidence uploaded successfully."
    assert "legacy billing parser" in outcome.compatibility_notice
    assert "amount column" not in outcome.compatibility_notice


def test_both_paths_fail_is_an_actual_failure():
    outcome = upload_outcome(legacy_error="unsupported file")
    assert outcome.state == "FAILED"
    assert not outcome.admitted
    assert outcome.message == "unsupported file"


def test_evidence_summary_uses_primary_detail_region_only():
    primary = SimpleNamespace(
        region_kind="PRIMARY_DETAIL",
        detail_record_count=184,
        original_headers=tuple(f"Field {index}" for index in range(10)),
    )
    summary = SimpleNamespace(
        region_kind="SECONDARY_SUMMARY", detail_record_count=None, original_headers=("Total",)
    )
    assert evidence_counts(SimpleNamespace(regions=(primary, summary))) == (184, 10)


def test_admission_alone_establishes_prospect_scope():
    admission = SimpleNamespace(scope=SimpleNamespace(prospect_id="prospect-1"))
    context = resolve_active_evidence_context({"pue_upload_admission": admission})
    assert context.is_prospect
    assert context.evidence_admission is admission


def test_context_switch_clears_governed_and_conversation_state():
    session = {
        "prospect_analysis": object(),
        "pue_upload_admission": object(),
        "act005_result": object(),
        "prospect_copilot:analysis": ["stale"],
        "pue_semantic_reason:field": "stale",
        "organization_id": "retained-org",
    }
    clear_prospect_context(session)
    assert session == {"organization_id": "retained-org"}


def test_production_admission_activates_capabilities_without_user_stage_controls():
    from datetime import datetime, timezone

    from tests.universal_evidence.test_pue_governed_measurement_pilot import _admission
    from universal_evidence.activation import (
        ActivationScope,
        ActivationStage,
        InMemoryActivationAuditSink,
        InMemoryPueActivationRepository,
        PueActivationResolver,
        PueActivationService,
        ScopeLevel,
    )

    admission = _admission()
    repository = InMemoryPueActivationRepository()
    clock = lambda: datetime.now(timezone.utc)  # noqa: E731
    service = PueActivationService(
        repository=repository,
        audit_sink=InMemoryActivationAuditSink(),
        clock=clock,
    )
    activate_production_workflow(admission, activation_service=service)
    resolved = PueActivationResolver(repository=repository, clock=clock).resolve(
        ActivationScope(
            ScopeLevel.ANALYSIS,
            organization_id=admission.scope.organization_id,
            tenant_id=admission.scope.tenant_id,
            prospect_id=admission.scope.prospect_id,
            analysis_id=admission.scope.analysis_id,
        )
    )
    assert resolved.stage is ActivationStage.CAPABILITY_VISIBLE
