from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


class ReportsCertificationService:
    """Certification metadata for the Reports page.

    This service intentionally avoids report generation and scheduling writes.
    Those operational actions remain in the Reports page/backend path.
    """

    REPORT_DOMAINS = [
        "Executive",
        "Cost Optimization",
        "Governance",
        "Technology Intelligence",
        "SaaS Intelligence",
        "Digital Twin",
        "AI Insights",
    ]

    @staticmethod
    def report_data_freshness() -> str:
        return f"Live data as of {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"

    @staticmethod
    def scheduled_indicator(report_name: str, rows: list[dict[str, Any]]) -> str:
        for row in rows:
            is_active = row.get("enabled", row.get("active"))
            if str(row.get("report_type", "")).lower() == str(report_name).lower() and is_active:
                return "Scheduled"
        return "Manual"

    @staticmethod
    def report_coverage_label(report_name: str) -> str:
        name = str(report_name).lower()
        if any(token in name for token in ("board", "executive")):
            return "Executive, finance, governance, risk, optimization"
        if any(token in name for token in ("cost", "financial", "budget", "forecast", "savings")):
            return "Spend, forecast, savings, budget, optimization"
        if "saas" in name or "license" in name:
            return "SaaS, license, renewal, vendor, AI governance"
        if "technology" in name or "resource" in name or "inventory" in name:
            return "Technology, application, cloud, dependency evidence"
        if any(token in name for token in ("governance", "risk", "audit")):
            return "Governance, approvals, controls, risk evidence"
        if any(token in name for token in ("digital twin", "twin")):
            return "Digital twin, relationships, health, cost, risk"
        if "ai" in name:
            return "AI insights, optimization, risk, governance"
        return "Report package"

    @staticmethod
    def get_dashboard(
        *,
        report_history: list[dict[str, Any]],
        schedule_rows: list[dict[str, Any]],
        backend_status: dict[str, Any],
        current_role: str,
    ) -> dict[str, Any]:
        generated_count = sum(
            1 for row in report_history
            if str(row.get("status", "")).lower() == "generated"
        )
        failed_count = sum(
            1 for row in report_history
            if str(row.get("status", "")).lower() == "failed"
        )
        queued_count = sum(
            1 for row in report_history
            if str(row.get("status", "")).lower() == "queued"
        )
        scheduled_count = len(schedule_rows)
        download_available_count = ReportsCertificationService._download_available_count(report_history)
        latest_activity = ReportsCertificationService._latest_activity(report_history)
        backend_available = bool(backend_status.get("available"))
        schedule_available = backend_available
        health_status = "healthy" if failed_count == 0 and backend_available else "warning"

        health = {
            "generated_count": generated_count,
            "failed_count": failed_count,
            "queued_count": queued_count,
            "scheduled_count": scheduled_count,
            "domain_count": len(ReportsCertificationService.REPORT_DOMAINS),
            "latest_activity": latest_activity,
            "data_freshness": ReportsCertificationService.report_data_freshness(),
            "pdf_backend": "Available" if backend_available else "Unavailable",
            "schedule_backend": "Available" if schedule_available else "Unavailable",
            "download_available_count": download_available_count,
            "status": health_status,
            "current_role": current_role or "unknown",
        }

        return {
            "health": health,
            "executive_summary": ReportsCertificationService._executive_summary(health),
            "evidence": ReportsCertificationService._evidence(
                health=health,
                backend_status=backend_status,
            ),
        }

    @staticmethod
    def _latest_activity(report_history: list[dict[str, Any]]) -> str:
        if not report_history:
            return "No report activity"
        latest = max(str(row.get("created_at", "")) for row in report_history)
        return latest[:19] if latest else "No report activity"

    @staticmethod
    def _download_available_count(report_history: list[dict[str, Any]]) -> int:
        count = 0
        for row in report_history:
            file_name = row.get("file_name")
            if file_name and (Path("exports") / "reports" / str(file_name)).exists():
                count += 1
        return count

    @staticmethod
    def _executive_summary(health: dict[str, Any]) -> str:
        sentences = [
            f"Reports Center tracks {health['generated_count']} generated report package(s) across {health['domain_count']} reporting domains.",
            f"Latest activity is {health['latest_activity']}, with {health['queued_count']} queued and {health['failed_count']} failed report(s).",
            f"PDF backend is {health['pdf_backend']} and schedule backend is {health['schedule_backend']}.",
            f"Data freshness is {health['data_freshness']}.",
        ]
        return " ".join(sentences)

    @staticmethod
    def _evidence(
        *,
        health: dict[str, Any],
        backend_status: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "source_data": [
                {"Section": "Executive Summary", "Source": "services.reporting_service", "Mode": "Service"},
                {"Section": "Recommendations", "Source": "services.reporting_service", "Mode": "Service"},
                {"Section": "Approvals", "Source": "services.reporting_service", "Mode": "Service"},
                {"Section": "SaaS", "Source": "services.reporting_service", "Mode": "Service"},
                {"Section": "Report History", "Source": "report_history", "Mode": "Live"},
                {"Section": "Report Backend", "Source": "backend.services.report_service", "Mode": "Optional/Lazy"},
                {"Section": "Schedules", "Source": "report backend schedule APIs", "Mode": "Optional/Lazy"},
            ],
            "data_coverage": [
                {"Coverage Area": "Report Domains", "Value": f"{health['domain_count']} domains", "Status": "Tracked"},
                {"Coverage Area": "Generated Reports", "Value": str(health["generated_count"]), "Status": "Tracked"},
                {"Coverage Area": "Scheduled Reports", "Value": str(health["scheduled_count"]), "Status": "Tracked"},
                {"Coverage Area": "Download Availability", "Value": str(health["download_available_count"]), "Status": "Tracked"},
                {"Coverage Area": "PDF Backend", "Value": health["pdf_backend"], "Status": health["pdf_backend"]},
                {"Coverage Area": "Schedule Backend", "Value": health["schedule_backend"], "Status": health["schedule_backend"]},
            ],
            "ai_interpretation": (
                "Reports Center is organized as an executive reporting portal with guarded optional PDF and schedule backends. "
                "When backend configuration is unavailable, the page remains usable and evidence still explains report coverage, history, and operational readiness."
            ),
            "raw_evidence": {
                "Reporting Health": [
                    {"Metric": "Generated Reports", "Value": health["generated_count"]},
                    {"Metric": "Scheduled Reports", "Value": health["scheduled_count"]},
                    {"Metric": "Queued Reports", "Value": health["queued_count"]},
                    {"Metric": "Failed Reports", "Value": health["failed_count"]},
                    {"Metric": "Latest Activity", "Value": health["latest_activity"]},
                    {"Metric": "Data Freshness", "Value": health["data_freshness"]},
                    {"Metric": "PDF Backend", "Value": health["pdf_backend"]},
                    {"Metric": "Schedule Backend", "Value": health["schedule_backend"]},
                ],
                "Backend Detail": [
                    {
                        "Backend": "Report Service",
                        "Available": bool(backend_status.get("available")),
                        "Detail": backend_status.get("error") or "Available",
                    }
                ],
            },
        }
