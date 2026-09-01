"""ACT013-DEF-004 durable governance across logout, persona, and restart."""

from dataclasses import dataclass
from pathlib import Path

from services.prospect_data_intake_service import ProspectTenant
from services.universal_evidence_runtime_service import initialize_universal_evidence_runtime
from universal_evidence.governance import ActorType, ConfirmationActor
from universal_evidence.persistence import LifecycleScope
from universal_evidence.pilot import admit_uploaded_evidence
from universal_evidence.pilot.runtime import (
    get_measurement_pilot_service,
    get_normalization_pilot_service,
    get_semantic_pilot_service,
    reset_configured_runtime_cache,
)
from universal_evidence.production_workflow import activate_production_workflow

WORKBOOK = Path("temp_uploads/CUR Jan 2026.xlsx")


@dataclass
class PersonaSession:
    role: str
    admission: object | None = None

    def logout(self):
        self.admission = None


def _tenant(prospect="prospect-def004", audit="audit-def004"):
    return ProspectTenant(
        prospect,
        audit,
        "2026-08-31T00:00:00+00:00",
        "2026-09-30T00:00:00+00:00",
        30,
    )


def _admission(tenant=None):
    return admit_uploaded_evidence(
        tenant or _tenant(),
        filename=WORKBOOK.name,
        content=WORKBOOK.read_bytes(),
    )


def _actor(role="executive", actor_id="ceo@company.com"):
    return ConfirmationActor(actor_id, actor_id, role, ActorType.HUMAN)


def _column(service, admission, header):
    return next(
        item
        for item in service.discovery(admission).columns
        if item.original_header == header
    )


def _candidate(service, admission, header):
    column = _column(service, admission, header)
    return column, column.candidates[0].semantic_concept_id


def _lifecycle_scope(admission):
    return LifecycleScope(
        admission.scope.organization_id or "UNKNOWN",
        admission.scope.tenant_id or "UNKNOWN",
        admission.scope.prospect_id,
        admission.scope.analysis_id,
    )


def _govern_cur(admission):
    semantic = get_semantic_pilot_service()
    actor = _actor()
    service, service_concept = _candidate(semantic, admission, "Service")
    region, region_concept = _candidate(semantic, admission, "Region")
    subservice, subservice_concept = _candidate(semantic, admission, "Sub-Service/Type")
    assert service_concept == "technology.service"
    assert region_concept == "cloud.region"
    semantic.confirm(admission, service.source_column_reference, service_concept, actor=actor)
    semantic.confirm(admission, region.source_column_reference, region_concept, actor=actor)
    semantic.reject(
        admission,
        subservice.source_column_reference,
        subservice_concept,
        actor=actor,
        reason="candidate rejected during bounded acceptance",
    )
    return service, region, subservice


def test_governance_reconstructs_after_logout_persona_switch_and_restart(monkeypatch, tmp_path):
    database = tmp_path / "def004.db"
    monkeypatch.setenv("NEXORA_UNIVERSAL_EVIDENCE_DB", str(database))
    reset_configured_runtime_cache()
    admission = _admission()
    activate_production_workflow(admission)
    service, region, subservice = _govern_cur(admission)
    semantic = get_semantic_pilot_service()
    actor = _actor()
    before = semantic.experience(admission, actor=actor)
    normalized_before = get_normalization_pilot_service().experience(admission, actor=actor)
    readiness_before = get_measurement_pilot_service().readiness(admission, actor=actor)
    histories_before = {
        column.original_header: semantic.confirmation_service.get_decision_history(
            column, actor=actor
        ).decisions
        for column in (service, region, subservice)
    }
    assert before.effective_mapping_count == 2
    assert normalized_before.observation_count > 0
    assert "COUNT" in readiness_before.available_operations
    assert "SUM" not in readiness_before.available_operations
    assert not readiness_before.currency_ready

    ceo = PersonaSession("executive", admission)
    ceo.logout()
    admin = PersonaSession("super_admin")
    admin.logout()
    reset_configured_runtime_cache()

    reconstructed = _admission()
    assert reconstructed.fingerprint == admission.fingerprint
    assert reconstructed.evidence_fingerprint == admission.evidence_fingerprint
    assert reconstructed.scope == admission.scope
    semantic_after = get_semantic_pilot_service()
    after = semantic_after.experience(reconstructed, actor=actor)
    normalized_after = get_normalization_pilot_service().experience(reconstructed, actor=actor)
    readiness_after = get_measurement_pilot_service().readiness(reconstructed, actor=actor)
    assert after.effective_mapping_count == 2
    assert normalized_after.fingerprint == normalized_before.fingerprint
    assert "COUNT" in readiness_after.available_operations
    assert "SUM" not in readiness_after.available_operations
    assert not readiness_after.currency_ready
    for header in ("Service", "Region", "Sub-Service/Type"):
        column = _column(semantic_after, reconstructed, header)
        assert (
            semantic_after.confirmation_service.get_decision_history(column, actor=actor).decisions
            == histories_before[header]
        )

    runtime = initialize_universal_evidence_runtime(database)
    rows = runtime.lifecycle.list_scope(_lifecycle_scope(reconstructed))
    assert len([row for row in rows if row.object_type == "mapping_decision"]) == 3
    assert len([row for row in rows if row.object_type == "normalization_run"]) >= 2


def test_scope_isolation_and_explicit_purge_are_preserved(monkeypatch, tmp_path):
    database = tmp_path / "def004-isolation.db"
    monkeypatch.setenv("NEXORA_UNIVERSAL_EVIDENCE_DB", str(database))
    reset_configured_runtime_cache()
    admission = _admission()
    activate_production_workflow(admission)
    _govern_cur(admission)

    other_prospect = _admission(_tenant("prospect-other", "audit-def004"))
    other_analysis = _admission(_tenant("prospect-def004", "audit-other-analysis"))
    for isolated in (other_prospect, other_analysis):
        activate_production_workflow(isolated)
        view = get_semantic_pilot_service().experience(
            isolated, actor=_actor("super_admin", "admin@company.com")
        )
        assert view.effective_mapping_count == 0
        assert all(not item.history for item in view.mappings)

    runtime = initialize_universal_evidence_runtime(database)
    runtime.lifecycle.purge_scope(
        _lifecycle_scope(admission),
        actor_id="privacy-admin",
        reason="explicit governed purge",
    )
    reset_configured_runtime_cache()
    purged = get_semantic_pilot_service().experience(admission, actor=_actor())
    assert purged.effective_mapping_count == 0
    assert all(not item.history for item in purged.mappings)
