from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from services.ai_context_service import AIContextService


class AIInsightService:
    SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

    @staticmethod
    def get_cost_insights(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = AIInsightService._context(organization_id)
        cost = context["cost"]
        insights = []

        top_capability = AIInsightService._top(cost.get("capability_spend", []), "cost")
        if top_capability:
            insights.append(
                AIInsightService._insight(
                    category="Cost Intelligence",
                    severity="Medium",
                    title=f"{top_capability['name']} is the highest-cost business capability",
                    description=(
                        f"{top_capability['name']} currently represents "
                        f"{AIInsightService._money(top_capability.get('cost'))} of attributed cloud spend."
                    ),
                    evidence=top_capability,
                    recommended_action="Review optimization and investment priority for this capability first.",
                    business_impact="Focuses FinOps attention on the largest business-aligned cost pool.",
                    confidence=95,
                )
            )

        top_application = AIInsightService._top(cost.get("application_spend", []), "cost")
        if top_application:
            insights.append(
                AIInsightService._insight(
                    category="Cost Intelligence",
                    severity="Medium",
                    title=f"{top_application['name']} is the highest-spend application",
                    description=(
                        f"{top_application['name']} accounts for "
                        f"{AIInsightService._money(top_application.get('cost'))} in attributed cost."
                    ),
                    evidence=top_application,
                    recommended_action="Prioritize rightsizing, usage review, and architecture optimization for this application.",
                    business_impact="Connects application ownership to measurable cloud spend.",
                    confidence=94,
                )
            )

        summary = cost.get("summary", {})
        unattributed = float(summary.get("unattributed_cost") or 0)
        total = float(summary.get("total_cost") or 0)
        if unattributed > 0:
            insights.append(
                AIInsightService._insight(
                    category="Cost Intelligence",
                    severity="High" if AIInsightService._percent(unattributed, total) >= 10 else "Medium",
                    title="Unattributed spend remains concentrated outside the enterprise twin",
                    description=(
                        f"{AIInsightService._money(unattributed)} is not yet attributed, representing "
                        f"{AIInsightService._percent(unattributed, total):.1f}% of total cloud cost."
                    ),
                    evidence={
                        "unattributed_cost": round(unattributed, 2),
                        "total_cost": round(total, 2),
                        "unattributed_rows": summary.get("unattributed_rows"),
                    },
                    recommended_action="Approve provider/account/category mapping recommendations or add resource-level asset IDs.",
                    business_impact="Improves chargeback accuracy and Digital Twin cost quality.",
                    confidence=92,
                )
            )

        top_cost_center = AIInsightService._top(cost.get("cost_center_spend", []), "cost")
        if top_cost_center:
            insights.append(
                AIInsightService._insight(
                    category="Cost Intelligence",
                    severity="Low",
                    title=f"{top_cost_center['name']} is the largest cost center by attributed spend",
                    description=(
                        f"{top_cost_center['name']} owns "
                        f"{AIInsightService._money(top_cost_center.get('cost'))} of attributed cloud cost."
                    ),
                    evidence=top_cost_center,
                    recommended_action="Attach monthly budget targets to cost centers so future insights can flag budget overruns.",
                    business_impact="Prepares the platform for budget variance and chargeback automation.",
                    confidence=88,
                )
            )

        return insights

    @staticmethod
    def get_governance_insights(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = AIInsightService._context(organization_id)
        insights = []

        unowned_assets = [row for row in context["assets"] if not row.get("owner")]
        if unowned_assets:
            insights.append(
                AIInsightService._insight(
                    category="Governance Intelligence",
                    severity="Critical",
                    title="Assets without owners require governance action",
                    description=f"{len(unowned_assets)} enterprise assets have no assigned owner.",
                    evidence={"asset_count": len(unowned_assets), "assets": unowned_assets[:10]},
                    recommended_action="Assign technical, business, and executive owners.",
                    business_impact="Reduces operational accountability and audit risk.",
                    confidence=98,
                )
            )

        apps_without_exec = AIInsightService._applications_without_executive_sponsor(context)
        if apps_without_exec:
            insights.append(
                AIInsightService._insight(
                    category="Governance Intelligence",
                    severity="High",
                    title="Applications without executive sponsorship need review",
                    description=f"{len(apps_without_exec)} applications do not have an executive sponsor mapped.",
                    evidence={"applications": apps_without_exec},
                    recommended_action="Map executive owners through the ownership workflow.",
                    business_impact="Improves decision accountability for critical workloads.",
                    confidence=90,
                )
            )

        low_governance = [
            row
            for row in context["capabilities"]
            if float(row.get("governance_score") or 100) < 90
        ]
        if low_governance:
            worst = sorted(low_governance, key=lambda row: float(row.get("governance_score") or 0))[0]
            insights.append(
                AIInsightService._insight(
                    category="Governance Intelligence",
                    severity="Medium",
                    title=f"{worst.get('name')} has a low governance score",
                    description=(
                        f"{worst.get('name')} governance is "
                        f"{float(worst.get('governance_score') or 0):.1f}%."
                    ),
                    evidence=worst,
                    recommended_action="Complete missing ownership, cost, and relationship mappings for this capability.",
                    business_impact="Improves CIO and audit confidence in capability-level reporting.",
                    confidence=91,
                )
            )

        return insights

    @staticmethod
    def get_operational_insights(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = AIInsightService._context(organization_id)
        connectors = context["connector_health"].get("connectors", {})
        insights = []

        failing = {
            name: AIInsightService._connector_evidence(row)
            for name, row in connectors.items()
            if name != "SaaS" and row.get("status") == "Failed"
        }
        if failing:
            connector_word = "connector is" if len(failing) == 1 else "connectors are"
            insights.append(
                AIInsightService._insight(
                    category="Operational Intelligence",
                    severity="High",
                    title="One or more connectors are failing",
                    description=f"{len(failing)} {connector_word} currently failed: {', '.join(sorted(failing))}.",
                    evidence=failing,
                    recommended_action="Review connector credentials, permissions, and latest sync errors.",
                    business_impact="Connector failures reduce freshness and discovery completeness.",
                    confidence=96,
                )
            )

        incomplete = {
            name: AIInsightService._connector_evidence(row)
            for name, row in connectors.items()
            if name != "SaaS" and row.get("status") != "Connected"
        }
        if incomplete:
            insights.append(
                AIInsightService._insight(
                    category="Operational Intelligence",
                    severity="Medium",
                    title="Discovery coverage is incomplete across providers",
                    description=f"{len(incomplete)} connectors are not connected or are failing.",
                    evidence=incomplete,
                    recommended_action="Complete onboarding for not configured connectors and repair failed syncs.",
                    business_impact="Improves enterprise asset coverage and AI context completeness.",
                    confidence=93,
                )
            )

        stale_assets = AIInsightService._stale_assets(context["assets"])
        if stale_assets:
            insights.append(
                AIInsightService._insight(
                    category="Operational Intelligence",
                    severity="Medium",
                    title="Some assets have not refreshed recently",
                    description=f"{len(stale_assets)} enterprise assets are older than the freshness threshold.",
                    evidence={"assets": stale_assets[:10]},
                    recommended_action="Run scheduled discovery and verify connector sync cadence.",
                    business_impact="Keeps the Digital Twin aligned with the current cloud estate.",
                    confidence=86,
                )
            )

        return insights

    @staticmethod
    def get_business_insights(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = AIInsightService._context(organization_id)
        insights = []

        risky = sorted(
            context["capabilities"],
            key=lambda row: (
                AIInsightService._risk_rank(row.get("risk")),
                float(row.get("health") or 100),
            ),
        )
        if risky:
            capability = risky[0]
            insights.append(
                AIInsightService._insight(
                    category="Business Intelligence",
                    severity="High" if AIInsightService._risk_rank(capability.get("risk")) <= 1 else "Medium",
                    title=f"{capability.get('name')} is the highest operational risk capability",
                    description=(
                        f"{capability.get('name')} has risk '{capability.get('risk')}' and health "
                        f"{float(capability.get('health') or 0):.1f}%."
                    ),
                    evidence=capability,
                    recommended_action="Review dependencies, governance gaps, and cost concentration for this capability.",
                    business_impact="Highlights where service disruption would matter most to leadership.",
                    confidence=90,
                )
            )

        largest_app = AIInsightService._top(context["applications"], "cost")
        if largest_app:
            insights.append(
                AIInsightService._insight(
                    category="Business Intelligence",
                    severity="Medium",
                    title=f"{largest_app.get('name')} has the largest blast radius by spend",
                    description=(
                        f"If {largest_app.get('name')} fails, it affects "
                        f"{largest_app.get('asset_count')} enterprise assets and "
                        f"{AIInsightService._money(largest_app.get('cost'))} of attributed cloud spend."
                    ),
                    evidence=largest_app,
                    recommended_action="Validate resilience, ownership, and recovery plans for this application.",
                    business_impact="Connects application reliability to business cost exposure.",
                    confidence=92,
                )
            )

        return insights

    @staticmethod
    def get_executive_summary(organization_id: str | None = None) -> dict[str, Any]:
        context = AIInsightService._context(organization_id)
        capability = AIInsightService._top(context["capabilities"], "cost") or {}
        application = AIInsightService._top(context["applications"], "cost") or {}
        cost = context["cost"].get("summary", {})
        quality = context["quality"].get("scores", {})
        connectors = context["connector_health"].get("summary", {})
        primary_provider = AIInsightService._primary_provider(context)
        narrative = (
            f"{capability.get('name', 'The primary capability')} is currently the highest-value business capability "
            f"with {AIInsightService._money(capability.get('cost'))} of attributed cloud spend. "
            f"Ownership coverage is {float(quality.get('ownership') or 0):.1f}%, "
            f"Digital Twin quality is {float(quality.get('overall_quality') or 0):.1f}%, while "
            f"{int(cost.get('unattributed_rows') or 0)} cost records remain unattributed, representing an optimization opportunity. "
            f"{primary_provider} remains the primary technology platform supporting the "
            f"{application.get('name', 'mapped application')} application."
        )
        return {
            "title": "Executive AI Summary",
            "narrative": narrative,
            "evidence": {
                "primary_capability": capability,
                "primary_application": application,
                "cost_summary": cost,
                "quality": quality,
                "connector_summary": connectors,
            },
        }

    @staticmethod
    def get_priority_actions(organization_id: str | None = None) -> list[dict[str, Any]]:
        insights = AIInsightService.get_all_insights(organization_id, include_summary=False)
        return sorted(
            insights,
            key=lambda row: (
                AIInsightService.SEVERITY_ORDER.get(row.get("severity"), 99),
                -int(row.get("confidence") or 0),
            ),
        )[:10]

    @staticmethod
    def get_all_insights(
        organization_id: str | None = None,
        include_summary: bool = True,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        insights = (
            AIInsightService.get_cost_insights(organization_id)
            + AIInsightService.get_governance_insights(organization_id)
            + AIInsightService.get_operational_insights(organization_id)
            + AIInsightService.get_business_insights(organization_id)
        )
        insights = sorted(
            insights,
            key=lambda row: (
                AIInsightService.SEVERITY_ORDER.get(row.get("severity"), 99),
                -int(row.get("confidence") or 0),
            ),
        )
        if not include_summary:
            return insights
        return {
            "executive_summary": AIInsightService.get_executive_summary(organization_id),
            "priority_actions": insights[:10],
            "insights": insights,
        }

    @staticmethod
    def _context(organization_id: str | None = None) -> dict[str, Any]:
        return AIContextService.build_enterprise_context(organization_id)

    @staticmethod
    def _insight(
        category: str,
        severity: str,
        title: str,
        description: str,
        evidence: dict[str, Any],
        recommended_action: str,
        business_impact: str,
        confidence: int,
    ) -> dict[str, Any]:
        return {
            "category": category,
            "severity": severity,
            "title": title,
            "description": description,
            "evidence": evidence,
            "recommended_action": recommended_action,
            "business_impact": business_impact,
            "confidence": max(0, min(100, int(confidence))),
        }

    @staticmethod
    def _applications_without_executive_sponsor(context: dict[str, Any]) -> list[dict[str, Any]]:
        output = []
        for app in context["applications"]:
            assets = [
                row
                for row in context["assets"]
                if AIInsightService._norm(row.get("application")) == AIInsightService._norm(app.get("name"))
            ]
            if assets and not any(row.get("executive_owner") for row in assets):
                output.append(app)
        return output

    @staticmethod
    def _stale_assets(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        threshold = datetime.now(timezone.utc) - timedelta(hours=72)
        stale = []
        for asset in assets:
            parsed = AIInsightService._parse_datetime(asset.get("last_seen"))
            if parsed and parsed < threshold:
                stale.append(asset)
        return stale

    @staticmethod
    def _primary_provider(context: dict[str, Any]) -> str:
        totals: dict[str, float] = {}
        for asset in context["assets"]:
            provider = asset.get("cloud_provider") or "Unknown"
            totals[provider] = totals.get(provider, 0.0) + float(asset.get("cost") or 0)
        if not totals:
            return "No cloud provider"
        return sorted(totals.items(), key=lambda item: item[1], reverse=True)[0][0]

    @staticmethod
    def _connector_evidence(row: dict[str, Any]) -> dict[str, Any]:
        last_error = str(row.get("last_error") or "")
        if len(last_error) > 240:
            last_error = last_error[:237] + "..."
        return {
            "status": row.get("status"),
            "health": row.get("health"),
            "last_sync": row.get("last_sync"),
            "failures": row.get("failures"),
            "coverage": row.get("coverage"),
            "last_error": last_error,
            "recommended_action": row.get("recommended_action"),
        }

    @staticmethod
    def _top(rows: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
        if not rows:
            return None
        return sorted(rows, key=lambda row: float(row.get(field) or 0), reverse=True)[0]

    @staticmethod
    def _risk_rank(risk: Any) -> int:
        return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(AIInsightService._norm(risk), 2)

    @staticmethod
    def _money(value: Any) -> str:
        return f"${float(value or 0):,.2f}"

    @staticmethod
    def _percent(numerator: float, denominator: float) -> float:
        if not denominator:
            return 0.0
        return round((float(numerator) / float(denominator)) * 100, 1)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()
