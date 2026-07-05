from __future__ import annotations

from typing import Any

from services.cio_dashboard_certification_service import CioDashboardCertificationService


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value if value is not None else fallback))
    except (TypeError, ValueError):
        return fallback


class CIOWorkspaceService:
    """Workspace orchestration facade for the CIO Dashboard.

    Domain and certification data still comes from existing services. This
    facade shapes the model expected by the shared platform renderers.
    """

    @staticmethod
    def get_workspace() -> dict[str, Any]:
        dashboard = CioDashboardCertificationService.get_dashboard()
        metrics = dashboard.get("metrics") or {}
        evidence = dashboard.get("evidence") or {}
        business_architecture = dashboard.get("business_architecture") or {}
        financial_model = dashboard.get("financial_model") or {}
        reconciliation_cards = dashboard.get("reconciliation_cards") or {}

        return {
            **dashboard,
            "dashboard": dashboard,
            "summary": CIOWorkspaceService._summary(dashboard),
            "business_context": CIOWorkspaceService._business_context(metrics, business_architecture),
            "reconciliation_cards": {
                **reconciliation_cards,
                "allocated_spend_display": CioDashboardCertificationService.format_compact_currency(
                    financial_model.get("allocated_spend")
                ),
                "variance_status": reconciliation_cards.get("status", "Unknown"),
            },
            "ai_narrative": evidence.get("ai_interpretation")
            or "CIO workspace interpretation is unavailable.",
        }

    @staticmethod
    def _summary(dashboard: dict[str, Any]) -> dict[str, Any]:
        metrics = dashboard.get("metrics") or {}
        business_architecture = dashboard.get("business_architecture") or {}

        return {
            "title": "Executive Summary",
            "description": "Certified CIO overview of technology posture, financial reconciliation, and business architecture context.",
            "narrative": dashboard.get("executive_summary")
            or "CIO workspace executive summary is unavailable.",
            "metrics": [
                {
                    "label": "Technology Spend",
                    "value": CioDashboardCertificationService.format_compact_currency(metrics.get("total_spend")),
                    "description": "Total technology investment",
                    "icon": "cost",
                    "status": "info",
                },
                {
                    "label": "Optimization Potential",
                    "value": CioDashboardCertificationService.format_compact_currency(metrics.get("potential_savings")),
                    "description": "Identified savings pipeline",
                    "icon": "savings",
                    "status": "warning" if _safe_float(metrics.get("potential_savings")) else "healthy",
                },
                {
                    "label": "Technology Health",
                    "value": f"{_safe_int(metrics.get('technology_health'))}%",
                    "description": "Overall platform health",
                    "icon": "health",
                    "status": CIOWorkspaceService._health_status(metrics.get("technology_health")),
                },
                {
                    "label": "Critical Risks",
                    "value": f"{_safe_int(metrics.get('open_risks')):,}",
                    "description": "Open technology risks",
                    "icon": "risk",
                    "status": "critical" if _safe_int(metrics.get("open_risks")) else "healthy",
                },
                {
                    "label": "Applications",
                    "value": f"{_safe_int(metrics.get('applications')):,}",
                    "description": "Application records in scope",
                    "icon": "application",
                    "status": "info",
                },
                {
                    "label": "Business Services",
                    "value": f"{_safe_int(metrics.get('business_services')):,}",
                    "description": "Critical service signals tracked",
                    "icon": "enterprise",
                    "status": "info",
                },
                {
                    "label": "AI Tools",
                    "value": f"{_safe_int(metrics.get('ai_tools')):,}",
                    "description": "Detected AI platform signals",
                    "icon": "intelligence",
                    "status": "info",
                },
                {
                    "label": "Automation Candidates",
                    "value": f"{_safe_int(business_architecture.get('automation_candidates')):,}",
                    "description": "Business architecture automation signal",
                    "icon": "workflow",
                    "status": "info",
                },
            ],
        }

    @staticmethod
    def _business_context(metrics: dict[str, Any], business_architecture: dict[str, Any]) -> dict[str, Any]:
        return {
            "business_units": _safe_int(business_architecture.get("business_units")),
            "capabilities": _safe_int(business_architecture.get("capabilities")),
            "business_services": _safe_int(business_architecture.get("services")),
            "business_processes": _safe_int(business_architecture.get("processes")),
            "applications": _safe_int(business_architecture.get("applications") or metrics.get("applications")),
            "technologies": _safe_int(business_architecture.get("technologies") or metrics.get("resources")),
            "mapping_coverage": _safe_float(business_architecture.get("mapping_coverage")),
        }

    @staticmethod
    def _health_status(value: Any) -> str:
        score = _safe_float(value)
        if score >= 85:
            return "healthy"
        if score >= 70:
            return "warning"
        return "critical"
