"""Production activation helpers for the certified Universal Evidence workflow."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from universal_evidence.activation import (
    ActivationActor,
    ActivationPermission,
    ActivationScope,
    ActivationStage,
    ScopeLevel,
)
from universal_evidence.persistence import LifecycleScope


@dataclass(frozen=True, slots=True)
class UploadOutcome:
    admitted: bool
    legacy_available: bool
    state: str
    message: str
    compatibility_notice: str | None = None


@dataclass(frozen=True, slots=True)
class ResumableAnalysis:
    workspace_id: str
    organization_id: str
    tenant_id: str
    prospect_id: str
    analysis_id: str
    filename: str
    prospect_name: str
    created_at: str
    updated_at: str
    record_count: int
    field_count: int
    governed_mapping_count: int
    status: str


def upload_outcome(*, admission=None, legacy_analysis=None, legacy_error=None) -> UploadOutcome:
    """Give governed admission precedence without concealing a total failure."""
    if admission is not None:
        notice = None
        if legacy_analysis is None and legacy_error:
            notice = (
                "Evidence discovery succeeded. The legacy billing parser could not create its "
                "additional compatibility analysis; continue by reviewing mappings."
            )
        return UploadOutcome(
            True,
            legacy_analysis is not None,
            "ADMITTED",
            "Evidence uploaded successfully.",
            notice,
        )
    if legacy_analysis is not None:
        return UploadOutcome(
            False,
            True,
            "LEGACY_ONLY",
            "The billing analysis is available, but governed evidence discovery is "
            "temporarily unavailable.",
        )
    return UploadOutcome(
        False,
        False,
        "FAILED",
        str(legacy_error or "The file could not be admitted or analyzed."),
    )


def evidence_counts(admission) -> tuple[int, int]:
    """Return certified primary detail records and discovered fields."""
    primary = tuple(
        region for region in admission.regions if region.region_kind == "PRIMARY_DETAIL"
    )
    records = sum(int(region.detail_record_count or 0) for region in primary)
    fields = sum(
        len(tuple(header for header in region.original_headers if header)) for region in primary
    )
    return records, fields


def persist_production_workspace(
    admission,
    *,
    prospect_tenant,
    prospect_name,
    input_profile,
    authorization,
):
    """Persist a safe locator plus encrypted source for a resumable governed analysis."""
    authorization.authorize_scope(admission.scope)
    from services.prospect_data_intake_service import (
        prospect_encryption_key,
        store_governed_upload,
    )
    from services.universal_evidence_runtime_service import (
        initialize_universal_evidence_runtime,
    )

    database = os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB")
    runtime = initialize_universal_evidence_runtime(database)
    if runtime is None:
        return None
    root = Path(os.getenv("NEXORA_PROSPECT_DATA_ROOT", "var/prospect_data"))
    store_governed_upload(
        prospect_tenant,
        filename=admission.original_filename,
        content=admission.source_content,
        input_profile=input_profile,
        actor=authorization.actor_id,
        root=root,
        key=prospect_encryption_key(),
    )
    records, fields = evidence_counts(admission)
    scope = _workspace_scope(admission)
    return runtime.lifecycle.put(
        "evidence_workspace",
        admission.fingerprint,
        scope,
        payload={
            "owner_subject_id": authorization.actor_id,
            "prospect_audit_id": prospect_tenant.audit_id,
            "prospect_created_at": prospect_tenant.created_at,
            "prospect_expires_at": prospect_tenant.expires_at,
            "retention_days": prospect_tenant.retention_days,
            "prospect_name": str(prospect_name),
            "filename": admission.original_filename,
            "input_profile": input_profile,
            "evidence_fingerprint": admission.evidence_fingerprint,
            "admission_fingerprint": admission.fingerprint,
            "record_count": records,
            "field_count": fields,
            "status": "GOVERNANCE_REQUIRED",
        },
        fingerprint_value=admission.fingerprint,
        actor_id=authorization.actor_id,
        reason="governed evidence workspace admitted",
    )


def persist_document_closure(
    admission, result, *, prospect_tenant, files, input_profile, authorization
):
    """Persist a closure view and encrypted sources in the existing workspace."""
    authorization.authorize_scope(admission.scope)
    from services.prospect_data_intake_service import prospect_encryption_key, store_governed_bundle
    from services.universal_evidence_runtime_service import initialize_universal_evidence_runtime

    root = Path(os.getenv("NEXORA_PROSPECT_DATA_ROOT", "var/prospect_data"))
    store_governed_bundle(
        prospect_tenant,
        files=tuple(files),
        input_profile=input_profile,
        actor=authorization.actor_id,
        root=root,
        key=prospect_encryption_key(),
    )
    runtime = initialize_universal_evidence_runtime(os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB"))
    if runtime is None:
        return None
    return runtime.lifecycle.put(
        "document_closure",
        admission.fingerprint,
        _workspace_scope(admission),
        payload={"owner_subject_id": authorization.actor_id, "result": result.to_dict()},
        fingerprint_value=admission.fingerprint,
        actor_id=authorization.actor_id,
        reason="integrated document intelligence closure persisted",
    )


def resume_document_closure(locator, *, authorization):
    """Restore and verify a retained closure without another browser upload."""
    from services.prospect_data_intake_service import load_governed_bundle, prospect_encryption_key
    from services.universal_evidence_runtime_service import initialize_universal_evidence_runtime
    from universal_evidence.product_closure import ProductClosureResult

    scope = LifecycleScope(
        locator.organization_id, locator.tenant_id, locator.prospect_id, locator.analysis_id
    )
    authorization.authorize_scope(_capability_scope(scope))
    runtime = initialize_universal_evidence_runtime(os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB"))
    if runtime is None:
        raise RuntimeError("durable evidence workspace service is unavailable")
    record = runtime.lifecycle.get("document_closure", locator.workspace_id, scope)
    if (record.payload or {}).get("owner_subject_id") != authorization.actor_id:
        raise PermissionError("document closure is not authorized for this subject")
    root = Path(os.getenv("NEXORA_PROSPECT_DATA_ROOT", "var/prospect_data"))
    files = load_governed_bundle(locator.prospect_id, root=root, key=prospect_encryption_key())
    return ProductClosureResult.from_dict(record.payload["result"]), files


def resumable_production_workspaces(authorization) -> tuple[ResumableAnalysis, ...]:
    """Discover only this trusted subject's active workspaces inside its tenant."""
    from services.universal_evidence_runtime_service import (
        initialize_universal_evidence_runtime,
    )

    runtime = initialize_universal_evidence_runtime(os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB"))
    if runtime is None:
        return ()
    results = []
    for row in runtime.lifecycle.list_type("evidence_workspace"):
        payload = row.payload or {}
        expires_at = payload.get("prospect_expires_at")
        if (
            row.scope.organization_id != authorization.tenant.organization_id
            or row.scope.tenant_id != authorization.tenant.tenant_id
            or payload.get("owner_subject_id") != authorization.actor_id
            or not expires_at
            or datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc)
        ):
            continue
        authorization.authorize_scope(_capability_scope(row.scope))
        mapping_count = sum(
            item.object_type == "mapping_decision"
            and (item.payload or {}).get("decision_state")
            in {"AUTO_ACCEPTED", "CONFIRMED", "OVERRIDDEN"}
            for item in runtime.lifecycle.list_scope(row.scope)
        )
        results.append(
            ResumableAnalysis(
                row.object_key,
                row.scope.organization_id,
                row.scope.tenant_id,
                row.scope.prospect_id or "",
                row.scope.analysis_id or "",
                str(payload.get("filename") or "Governed evidence"),
                str(payload.get("prospect_name") or "Prospect analysis"),
                row.created_at,
                row.updated_at,
                int(payload.get("record_count") or 0),
                int(payload.get("field_count") or 0),
                mapping_count,
                str(payload.get("status") or "ACTIVE"),
            )
        )
    return tuple(sorted(results, key=lambda item: (item.updated_at, item.workspace_id)))


def resume_production_workspace(locator, *, authorization):
    """Reconstruct one explicitly scoped workspace from encrypted retained evidence."""
    from services.prospect_data_intake_service import (
        load_governed_upload,
        prospect_encryption_key,
    )
    from services.universal_evidence_runtime_service import (
        initialize_universal_evidence_runtime,
    )
    from universal_evidence.pilot.admission import admit_uploaded_evidence

    scope = LifecycleScope(
        locator.organization_id,
        locator.tenant_id,
        locator.prospect_id,
        locator.analysis_id,
    )
    authorization.authorize_scope(_capability_scope(scope))
    runtime = initialize_universal_evidence_runtime(os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB"))
    if runtime is None:
        raise RuntimeError("durable evidence workspace service is unavailable")
    record = runtime.lifecycle.get("evidence_workspace", locator.workspace_id, scope)
    payload = record.payload or {}
    if payload.get("owner_subject_id") != authorization.actor_id:
        raise PermissionError("workspace is not authorized for this subject")
    root = Path(os.getenv("NEXORA_PROSPECT_DATA_ROOT", "var/prospect_data"))
    prospect, prospect_name, metadata, content = load_governed_upload(
        locator.prospect_id,
        root=root,
        key=prospect_encryption_key(),
    )
    admission = admit_uploaded_evidence(
        prospect,
        filename=metadata["filename"],
        content=content,
        now=datetime.fromisoformat(payload["prospect_created_at"]),
        tenant_context=authorization.tenant,
    )
    if (
        admission.fingerprint != payload.get("admission_fingerprint")
        or admission.evidence_fingerprint != payload.get("evidence_fingerprint")
        or admission.scope.analysis_id != locator.analysis_id
        or admission.scope.prospect_id != locator.prospect_id
    ):
        raise PermissionError("retained evidence does not match its governed workspace")
    return admission, prospect, prospect_name, metadata["input_profile"]


def _workspace_scope(admission):
    return LifecycleScope(
        admission.scope.organization_id or "UNKNOWN",
        admission.scope.tenant_id or "UNKNOWN",
        admission.scope.prospect_id,
        admission.scope.analysis_id,
    )


def _capability_scope(scope):
    from universal_evidence.capability import CapabilityScope

    return CapabilityScope(
        scope.analysis_id or "",
        scope.prospect_id or "",
        scope.organization_id,
        scope.tenant_id,
    )


def activate_production_workflow(admission, *, activation_service=None) -> None:
    """Advance an admitted analysis to certified workflow visibility.

    This is a service-owned routing decision, not a user-facing activation control. Existing
    backend kill-switch resolution remains authoritative.
    """
    if activation_service is None:
        from universal_evidence.pilot.runtime import get_activation_service

        activation_service = get_activation_service()
    actor = ActivationActor(
        "nexora-production-workflow",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        (ActivationPermission.CHANGE_PUE_STAGE,),
    )
    activation_service.configure(
        scope=ActivationScope(
            ScopeLevel.ANALYSIS,
            organization_id=admission.scope.organization_id,
            tenant_id=admission.scope.tenant_id,
            prospect_id=admission.scope.prospect_id,
            analysis_id=admission.scope.analysis_id,
        ),
        stage=ActivationStage.CAPABILITY_VISIBLE,
        actor=actor,
        reason="certified production evidence workflow",
        expires_at=admission.expires_at,
    )


def load_configured_production_views(admission, *, database=None):
    """Reconstruct ACT-010B views from configured ACT-009 durable authority."""
    configured = database or os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB")
    if not configured:
        return None
    from services.universal_evidence_runtime_service import (
        initialize_universal_evidence_runtime,
    )
    from universal_evidence.persistence import LifecyclePersistenceError
    from universal_evidence.pilot.production_views import load_production_views

    runtime = initialize_universal_evidence_runtime(configured)
    scope = LifecycleScope(
        admission.scope.organization_id or "UNKNOWN",
        admission.scope.tenant_id or "UNKNOWN",
        admission.scope.prospect_id,
        admission.scope.analysis_id,
    )
    try:
        return load_production_views(runtime.lifecycle, scope)
    except LifecyclePersistenceError as exc:
        if str(exc) == "lifecycle record not found in scope":
            return None
        raise


def load_live_canonical_views(session, admission, *, role):
    """Read the same canonical stores used by graph, dependency, and Ask experiences."""
    from services.enterprise_registry_composition import enterprise_registry_service
    from services.enterprise_spend_composition import authenticated_tenant_context
    from services.relationship_intelligence_composition import (
        relationship_intelligence_service,
    )
    from universal_evidence.pilot.production_views import (
        build_enterprise_context,
        build_reconciliation_view,
    )

    authenticated = authenticated_tenant_context(session)
    context = authenticated.fabric_context
    registry = enterprise_registry_service(context, role=role)
    relationship_service = relationship_intelligence_service(context, role=role)
    entities = registry.list_entities()
    relationships = {
        relationship.id: relationship
        for entity in entities
        for relationship in relationship_service.get_relationships(entity.canonical_id)
    }
    enterprise = build_enterprise_context(
        entities,
        relationships.values(),
        prospect_id=admission.scope.prospect_id,
        analysis_id=admission.scope.analysis_id,
    )
    return enterprise, build_reconciliation_view()
