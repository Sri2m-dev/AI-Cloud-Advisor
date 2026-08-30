"""Production activation helpers for the certified Universal Evidence workflow."""

from __future__ import annotations

import os
from dataclasses import dataclass

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
        len(tuple(header for header in region.original_headers if header))
        for region in primary
    )
    return records, fields


def activate_production_workflow(admission, *, activation_service=None) -> None:
    """Advance an admitted analysis to certified workflow visibility.

    This is a service-owned routing decision, not a user-facing activation control. Existing
    backend kill-switch resolution remains authoritative.
    """
    if activation_service is None:
        from universal_evidence.pilot.runtime import ACTIVATION_SERVICE

        activation_service = ACTIVATION_SERVICE
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
