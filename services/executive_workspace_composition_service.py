from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auth.authenticated_tenant import AuthenticatedTenantContext
from enterprise_intelligence.models import AvailabilityState, IntelligenceResult
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
    availability: str | None = None
    fingerprint: str | None = None


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
    canonical_results: tuple[IntelligenceResult, ...] = ()
    persona: str | None = None


def _money(value: Any) -> str:
    return EnterpriseSpendCertificationService.format_compact_currency(value)


class ExecutiveWorkspaceCompositionService:
    """Shapes existing certified outputs for the frozen Executive Experience."""

    @staticmethod
    def get_canonical_optimization(context, repository=None):
        from services.canonical_optimization_service import CanonicalOptimizationService

        return CanonicalOptimizationService(repository).executive_summary(context)

    @staticmethod
    def get_snapshot(
        key: str,
        context: AuthenticatedTenantContext,
        spend_service: EnterpriseSpendService,
        *,
        query_service=None,
        role: str | None = None,
    ) -> WorkspaceSnapshot:
        try:
            return ExecutiveWorkspaceCompositionService._demo_snapshot(
                key, load_demo_tenant(context.organization_id)
            )
        except DemoTenantError:
            pass

        if query_service is not None:
            return ExecutiveWorkspaceCompositionService._canonical_snapshot(
                key, context, query_service, role=role
            )

        try:
            dashboard = EnterpriseSpendCertificationService.get_dashboard(context, spend_service)
        except Exception:
            return ExecutiveWorkspaceCompositionService._unavailable_snapshot()
        return ExecutiveWorkspaceCompositionService._certified_snapshot(key, dashboard)

    @staticmethod
    def _canonical_snapshot(key, context, query_service, *, role=None):
        spend = query_service.enterprise_spend_summary(context)
        optimization = query_service.optimization_summary(context)
        stages = optimization.metadata.get("stages", {})

        def money_metric(title, value, result, meaning, kind="financial"):
            available = value is not None and result.availability in {
                AvailabilityState.AVAILABLE,
                AvailabilityState.PARTIAL,
            }
            return WorkspaceMetric(
                title,
                _money(value) if available else result.availability.value,
                meaning,
                result.authority,
                available,
                kind,
                result.availability.value,
                result.fingerprint,
            )

        values = spend.metadata
        metrics = [
            money_metric(
                "Total Technology Spend",
                spend.value,
                spend,
                "Canonical P1 technology spend for the selected period.",
            ),
            money_metric(
                "Cloud Spend",
                values.get("cloud_spend"),
                spend,
                "Cloud spend reported by canonical P1 authority.",
            ),
            money_metric(
                "Shared Spend",
                values.get("shared_spend"),
                spend,
                "Spend deliberately retained as shared and unallocated.",
            ),
            money_metric(
                "Unresolved Spend",
                values.get("unresolved_spend"),
                spend,
                "Spend whose canonical context remains unresolved.",
            ),
        ]
        for stage in ("potential", "approved", "planned", "implemented", "verified", "realized"):
            rows = stages.get(stage)
            if rows is None:
                value, state = None, AvailabilityState.UNKNOWN
            elif len(rows) == 1:
                value, state = rows[0][1], optimization.availability
            else:
                value, state = None, AvailabilityState.CONFLICTED
            stage_result = IntelligenceResult(
                optimization.tenant_id,
                optimization.organization_id,
                optimization.scope,
                f"{stage}_savings",
                optimization.period,
                state,
                value,
                rows[0][0] if rows and len(rows) == 1 else None,
                contributing_opportunity_ids=optimization.contributing_opportunity_ids,
                reason_codes=("MULTIPLE_CURRENCIES",) if rows and len(rows) > 1 else (),
                fingerprint=optimization.fingerprint,
                authority="P2",
            )
            metrics.append(
                money_metric(
                    f"{stage.title()} Savings",
                    value,
                    stage_result,
                    f"Canonical P2 {stage} savings lifecycle value.",
                    "decision",
                )
            )
        visible = ExecutiveWorkspaceCompositionService._persona_metrics(metrics, role)
        story = WorkspaceStory(
            yesterday="Use an explicit comparable period to establish change.",
            today=f"Technology spend is {visible[0].value} ({spend.availability.value}).",
            risk="Data quality exceptions remain visible and are not converted to zero.",
            recommendation="Review canonical opportunities and their governed evidence.",
            outcome="Executive and Ask surfaces share the same result fingerprints.",
            action=f"Open the authorized {key.replace('_', ' ')} drill-down.",
            confidence=spend.availability.value,
            evidence="Available" if spend.evidence_references else "UNKNOWN",
        )
        return WorkspaceSnapshot(
            tuple(visible), story, canonical_results=(spend, optimization), persona=role
        )

    @staticmethod
    def _persona_metrics(metrics, role):
        """Personas change visibility/order only; never values or fingerprints."""
        normalized = str(role or "").casefold().replace(" ", "_")
        preferred = {
            "ceo": ("Total Technology Spend", "Potential Savings", "Realized Savings"),
            "cio": ("Total Technology Spend", "Cloud Spend", "Unresolved Spend"),
            "cto": ("Cloud Spend", "Shared Spend", "Implemented Savings"),
            "finops": (
                "Total Technology Spend",
                "Potential Savings",
                "Approved Savings",
                "Realized Savings",
            ),
            "application_owner": ("Total Technology Spend", "Potential Savings"),
            "technology_owner": ("Cloud Spend", "Potential Savings", "Implemented Savings"),
            "tam": ("Total Technology Spend", "Unresolved Spend", "Approved Savings"),
        }.get(normalized)
        if not preferred:
            return metrics
        by_title = {metric.title: metric for metric in metrics}
        return [by_title[title] for title in preferred if title in by_title]

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
