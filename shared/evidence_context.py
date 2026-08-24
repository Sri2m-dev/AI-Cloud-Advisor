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


@dataclass(frozen=True)
class ActiveEvidenceContext:
    kind: EvidenceContextKind
    organization_id: str | None = None
    prospect_analysis: Any | None = None

    @property
    def is_prospect(self) -> bool:
        return self.kind is EvidenceContextKind.PROSPECT


def resolve_active_evidence_context(
    session: Mapping[str, Any],
    *,
    demo_enabled: bool | None = None,
) -> ActiveEvidenceContext:
    """Resolve the evidence boundary before any page-specific source is loaded."""
    prospect = session.get("prospect_analysis")
    if prospect is not None:
        return ActiveEvidenceContext(
            EvidenceContextKind.PROSPECT,
            organization_id=str(getattr(prospect, "tenant_id", "") or "") or None,
            prospect_analysis=prospect,
        )

    organization_id = str(
        session.get("organization_id") or session.get("org_id") or ""
    ).strip()
    if not organization_id:
        return ActiveEvidenceContext(EvidenceContextKind.UNKNOWN)
    enabled = demo_mode_enabled() if demo_enabled is None else demo_enabled
    if enabled and is_demo_tenant(organization_id):
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
    ):
        session.pop(key, None)
