from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.demo_tenant_service import DemoTenantError, load_demo_tenant
from services.enterprise_spend_certification_service import EnterpriseSpendCertificationService
from services.enterprise_spend_service import EnterpriseSpendService


@dataclass(frozen=True)
class WorkspaceMetric:
    title: str
    value: str
    meaning: str
    source: str
    available: bool
    kind: str


@dataclass(frozen=True)
class WorkspaceStory:
    yesterday: str
    today: str
    risk: str
    recommendation: str
    outcome: str
    action: str
    confidence: str
    evidence: str


@dataclass(frozen=True)
class WorkspaceSnapshot:
    metrics: tuple[WorkspaceMetric, ...]
    story: WorkspaceStory
    synthetic: bool = False
    trend: tuple[dict[str, Any], ...] = ()
    decisions: tuple[dict[str, Any], ...] = ()
    analytics: dict[str, tuple[dict[str, Any], ...]] | None = None
    journeys: tuple[dict[str, Any], ...] = ()


def _money(value: Any) -> str:
    return EnterpriseSpendCertificationService.format_compact_currency(value)


class ExecutiveWorkspaceCompositionService:
    """Shapes existing certified outputs for the frozen Executive Experience."""

    @staticmethod
    def get_snapshot(
        key: str,
        context: AuthenticatedTenantContext,
        spend_service: EnterpriseSpendService,
    ) -> WorkspaceSnapshot:
        try:
            return ExecutiveWorkspaceCompositionService._demo_snapshot(
                key, load_demo_tenant(context.organization_id)
            )
        except DemoTenantError:
            pass

        try:
            dashboard = EnterpriseSpendCertificationService.get_dashboard(context, spend_service)
        except Exception:
            return ExecutiveWorkspaceCompositionService._unavailable_snapshot()
        return ExecutiveWorkspaceCompositionService._certified_snapshot(key, dashboard)

    @staticmethod
    def _certified_snapshot(key: str, dashboard: dict[str, Any]) -> WorkspaceSnapshot:
        metrics = dashboard["metrics"]
        availability = metrics["source_availability"]
        reconciliation = dashboard["reconciliation"]
        spend_available = availability["spend"]
        recommendation_available = availability["recommendations"]

        metric_views = (
            WorkspaceMetric(
                "Certified spend",
                _money(metrics["total_spend"]) if spend_available else "UNKNOWN",
                "Tenant-scoped technology spend in the current certified checkpoint.",
                "Enterprise Spend certification service",
                spend_available,
                "financial",
            ),
            WorkspaceMetric(
                "Allocation coverage",
                f"{float(reconciliation.get('allocation_coverage') or 0):.1f}%"
                if spend_available
                else "UNKNOWN",
                "Share of spend mapped through the canonical financial model.",
                "Enterprise Financial Model",
                spend_available,
                "health",
            ),
            WorkspaceMetric(
                "Decision opportunity",
                _money(metrics["savings_opportunity"]) if recommendation_available else "UNKNOWN",
                "Certified recommendation value awaiting governed disposition.",
                "Recommendation registry",
                recommendation_available,
                "decision",
            ),
        )
        summary = dashboard["executive_summary"]
        story = WorkspaceStory(
            yesterday="The previous certified checkpoint is unavailable for comparison.",
            today=summary,
            risk=(
                "Incomplete source coverage limits the decisions that can be certified."
                if not all((spend_available, recommendation_available))
                else "No additional material risk statement is certified by this composition."
            ),
            recommendation=(
                "Review the certified recommendation pipeline and its underlying evidence."
                if recommendation_available
                else "Connect and certify the missing recommendation source before acting."
            ),
            outcome=(
                "A decision remains defensible only when its financial and business "
                "evidence is complete."
            ),
            action=(
                f"Open the authorized {key.replace('_', ' ')} intelligence surface "
                "for evidence and accountable action."
            ),
            confidence="Certified" if spend_available else "UNKNOWN",
            evidence="Available" if spend_available or recommendation_available else "Unavailable",
        )
        return WorkspaceSnapshot(metric_views, story)

    @staticmethod
    def _demo_snapshot(key: str, payload: dict[str, Any]) -> WorkspaceSnapshot:
        values = payload["metrics"]
        workspace = (payload.get("workspaces") or {}).get(key) or {}
        story = workspace.get("story") or payload["story"]
        metric_definitions = workspace.get("metrics") or (
            {
                "title": "Technology investment",
                "field": "annual_technology_spend",
                "format": "money",
                "meaning": (
                    "Synthetic annual technology investment for the demonstration enterprise."
                ),
                "kind": "financial",
            },
            {
                "title": "Technology health",
                "field": "technology_health",
                "format": "percent",
                "meaning": "Synthetic governed health posture across the demonstration estate.",
                "kind": "health",
            },
            {
                "title": "Decisions required",
                "field": "pending_decisions",
                "format": "integer",
                "meaning": "Synthetic executive decisions awaiting accountable review.",
                "kind": "decision",
            },
        )

        def display(metric: dict[str, Any]) -> str:
            value = values[metric["field"]]
            if metric["format"] == "money":
                return _money(value)
            if metric["format"] == "percent":
                return f"{value}%"
            return f"{value:,}" if isinstance(value, int) else str(value)

        metrics = tuple(
            WorkspaceMetric(
                metric["title"],
                display(metric),
                metric["meaning"],
                payload["source"],
                True,
                metric["kind"],
            )
            for metric in metric_definitions
        )
        selected_analytics = workspace.get("analytics") or tuple(
            (payload.get("analytics") or {}).keys()
        )
        return WorkspaceSnapshot(
            metrics,
            WorkspaceStory(
                yesterday=story["yesterday"],
                today=story["today"],
                risk=story["risk"],
                recommendation=story["recommendation"],
                outcome=story["business_outcome"],
                action=story["action"],
                confidence="88% synthetic scenario confidence",
                evidence="94% synthetic evidence coverage",
            ),
            synthetic=True,
            trend=tuple(payload.get("trend") or ()),
            decisions=tuple(payload.get("decisions") or ()),
            analytics={
                name: tuple((payload.get("analytics") or {})[name])
                for name in selected_analytics
                if name in (payload.get("analytics") or {})
            },
            journeys=tuple(payload.get("journeys") or ()),
        )

    @staticmethod
    def _unavailable_snapshot() -> WorkspaceSnapshot:
        unavailable = WorkspaceMetric(
            "Certified posture",
            "UNKNOWN",
            "No certified tenant-scoped source is currently available.",
            "Certified upstream services",
            False,
            "executive",
        )
        return WorkspaceSnapshot(
            (unavailable, unavailable, unavailable),
            WorkspaceStory(
                yesterday="UNKNOWN — no prior certified checkpoint is available.",
                today="UNKNOWN — the current certified posture is unavailable.",
                risk="Decision risk cannot be certified from the available sources.",
                recommendation="Configure and certify the required enterprise data sources.",
                outcome="No executive action should be taken from unavailable evidence.",
                action="Ask an administrator to review source availability and certification.",
                confidence="UNKNOWN",
                evidence="Unavailable",
            ),
        )
