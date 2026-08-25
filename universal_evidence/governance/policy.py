"""Versioned authorization, reasons, and auto-acceptance policy."""

from __future__ import annotations

from dataclasses import dataclass

from universal_evidence.contracts import ClassificationState, ConfirmationState
from universal_evidence.semantic.models import ColumnDiscoveryResult, SemanticRisk


@dataclass(frozen=True, slots=True)
class GovernancePolicy:
    version: str = "pue-governance-policy-1"
    confirm_roles: frozenset[str] = frozenset(
        {"sales_engineer", "finance", "executive", "client_admin", "super_admin"}
    )
    reject_roles: frozenset[str] = frozenset(
        {"sales_engineer", "finance", "executive", "client_admin", "super_admin"}
    )
    override_roles: frozenset[str] = frozenset(
        {"finance", "client_admin", "super_admin"}
    )
    view_roles: frozenset[str] = frozenset(
        {
            "sales_engineer",
            "finance",
            "executive",
            "client_admin",
            "super_admin",
            "auditor",
        }
    )
    reject_reason_required: bool = True
    override_reason_required: bool = True

    def authorize(self, action: str, role: str) -> None:
        roles = {
            "confirm": self.confirm_roles,
            "reject": self.reject_roles,
            "override": self.override_roles,
            "view": self.view_roles,
        }.get(action, frozenset())
        if role not in roles:
            raise PermissionError(f"role is not authorized to {action} semantic mappings")

    def requires_confirmation(self, discovery: ColumnDiscoveryResult) -> bool:
        return (
            discovery.confirmation_state is ConfirmationState.REQUIRED
            or discovery.classification_state
            is not ClassificationState.AUTO_CLASSIFIED
            or not discovery.candidates
            or discovery.candidates[0].risk
            in {SemanticRisk.HIGH_RISK, SemanticRisk.RESTRICTED}
        )

    def permits_auto_accept(self, discovery: ColumnDiscoveryResult) -> bool:
        return bool(discovery.candidates) and not self.requires_confirmation(discovery)
