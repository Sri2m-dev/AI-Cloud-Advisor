from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from services.demo_tenant_service import demo_mode_enabled, is_demo_tenant


class EvidenceContextKind(str, Enum):
    PROSPECT = "PROSPECT"
    TENANT = "TENANT"
    DEMO = "DEMO"
    UNKNOWN = "UNKNOWN"


ACTIVE_WORKSPACE_CONTEXT_KEY = "active_workspace_context"


@dataclass(frozen=True)
class ActiveEvidenceContext:
    kind: EvidenceContextKind
    organization_id: str | None = None
    prospect_analysis: Any | None = None
    evidence_admission: Any | None = None

    @property
    def is_prospect(self) -> bool:
        return self.kind is EvidenceContextKind.PROSPECT

    @property
    def is_demo(self) -> bool:
        return self.kind is EvidenceContextKind.DEMO

    @property
    def label(self) -> str:
        if self.is_demo:
            return "Sample Enterprise · Synthetic Demo"
        if self.is_prospect:
            filename = getattr(self.evidence_admission, "original_filename", None)
            return f"Prospect Analysis · {filename or 'Governed Evidence'}"
        if self.kind is EvidenceContextKind.TENANT:
            return "Enterprise Workspace"
        return "Workspace unavailable"


def activate_demo_workspace(session: Any) -> None:
    """Select the isolated demo presentation without mutating prospect authority."""
    organization_id = str(session.get("organization_id") or session.get("org_id") or "").strip()
    if not (demo_mode_enabled() and is_demo_tenant(organization_id)):
        raise PermissionError("synthetic workspace is not authorized for this tenant")
    session[ACTIVE_WORKSPACE_CONTEXT_KEY] = EvidenceContextKind.DEMO.value


def activate_prospect_workspace(session: Any, *, expected_fingerprint: str | None = None) -> None:
    """Select only the exact governed analysis already authorized in this session."""
    prospect = session.get("prospect_analysis")
    admission = session.get("pue_upload_admission")
    if prospect is None and admission is None:
        raise PermissionError("governed prospect workspace authority is required")
    fingerprint = str(getattr(admission, "fingerprint", "") or "")
    if expected_fingerprint and fingerprint != expected_fingerprint:
        raise PermissionError("governed prospect workspace identity mismatch")
    session[ACTIVE_WORKSPACE_CONTEXT_KEY] = EvidenceContextKind.PROSPECT.value


def activate_tenant_workspace(session: Any) -> None:
    organization_id = str(session.get("organization_id") or session.get("org_id") or "").strip()
    if not organization_id:
        raise PermissionError("tenant workspace authority is required")
    session[ACTIVE_WORKSPACE_CONTEXT_KEY] = EvidenceContextKind.TENANT.value


def resolve_active_evidence_context(
    session: Mapping[str, Any],
    *,
    demo_enabled: bool | None = None,
) -> ActiveEvidenceContext:
    """Resolve the evidence boundary before any page-specific source is loaded."""
    selected = str(session.get(ACTIVE_WORKSPACE_CONTEXT_KEY) or "").strip()
    prospect = session.get("prospect_analysis")
    admission = session.get("pue_upload_admission")
    if selected == EvidenceContextKind.PROSPECT.value:
        if prospect is None and admission is None:
            return ActiveEvidenceContext(EvidenceContextKind.UNKNOWN)
        return ActiveEvidenceContext(
            EvidenceContextKind.PROSPECT,
            organization_id=str(
                getattr(prospect, "tenant_id", "")
                or getattr(getattr(admission, "scope", None), "prospect_id", "")
                or ""
            )
            or None,
            prospect_analysis=prospect,
            evidence_admission=admission,
        )

    # Backward-compatible initial routing only when no explicit selection exists.
    if not selected and (prospect is not None or admission is not None):
        return ActiveEvidenceContext(
            EvidenceContextKind.PROSPECT,
            organization_id=str(
                getattr(prospect, "tenant_id", "")
                or getattr(getattr(admission, "scope", None), "prospect_id", "")
                or ""
            )
            or None,
            prospect_analysis=prospect,
            evidence_admission=admission,
        )

    organization_id = str(session.get("organization_id") or session.get("org_id") or "").strip()
    if not organization_id:
        return ActiveEvidenceContext(EvidenceContextKind.UNKNOWN)
    enabled = demo_mode_enabled() if demo_enabled is None else demo_enabled
    if selected == EvidenceContextKind.DEMO.value:
        if not (enabled and is_demo_tenant(organization_id)):
            return ActiveEvidenceContext(EvidenceContextKind.UNKNOWN)
        return ActiveEvidenceContext(EvidenceContextKind.DEMO, organization_id)
    if selected and selected != EvidenceContextKind.TENANT.value:
        return ActiveEvidenceContext(EvidenceContextKind.UNKNOWN)
    if not selected and enabled and is_demo_tenant(organization_id):
        return ActiveEvidenceContext(EvidenceContextKind.DEMO, organization_id)
    return ActiveEvidenceContext(EvidenceContextKind.TENANT, organization_id)


def clear_prospect_context(session: Any) -> None:
    """Explicitly leave the temporary prospect boundary without changing tenant data."""
    for key in (
        "prospect_tenant",
        "prospect_analysis",
        "prospect_name",
        "prospect_analysis_error",
        "analysis_start_path",
        "pue_upload_admission",
        "pue_upload_admission_error",
        "pue_pilot_context",
        "pue_shadow_analysis",
        "pue_shadow_request",
        "act005_result",
        "pue_enterprise_context_view",
        "pue_reconciliation_view",
        "pue_reconciliation_control",
        "document_closure_result",
    ):
        session.pop(key, None)
    for key in tuple(session):
        if str(key).startswith(("prospect_copilot:", "pue_semantic_")):
            session.pop(key, None)
