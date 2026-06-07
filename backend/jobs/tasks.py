import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from backend.services.alert_service import dispatch_alert_channels
from backend.services.alerting_engine import (
    evaluate_alerts,
    get_alert_config,
    record_alert_event,
)
from backend.services.report_service import (
    build_executive_pdf,
    get_report_distribution_list,
    record_report_history,
    send_executive_report_email,
)
from data.supabase_client import supabase
from scripts.generate_recommendations import generate_recommendations
from services.escalation_service import batch_escalate_stale, get_aging_summary, get_escalation_report
from services.alert_processor import process_alerts, get_alert_configs

LOGGER = logging.getLogger("background-jobs")
ROOT_DIR = Path(__file__).resolve().parents[2]


def _run_python_script(script_name: str) -> None:
    script_path = ROOT_DIR / script_name
    if not script_path.exists():
        LOGGER.warning("Script not found: %s", script_path)
        return

    LOGGER.info("Running script: %s", script_path)
    completed = subprocess.run([sys.executable, str(script_path)], cwd=str(ROOT_DIR), check=False)
    if completed.returncode != 0:
        LOGGER.error("Script failed (%s): exit code %s", script_name, completed.returncode)


def _get_tenant_ids() -> list[str]:
    try:
        rows = supabase.table("unified_cloud_costs").select("organization_id").execute().data or []
        tenants = sorted({str(r.get("organization_id")) for r in rows if r.get("organization_id")})
        return tenants
    except Exception as exc:
        LOGGER.exception("Failed to resolve tenant ids: %s", exc)
        return []


def job_cost_ingestion_hourly() -> None:
    LOGGER.info("[job] cost_ingestion_hourly started")
    _run_python_script("aws_cost_sync.py")
    _run_python_script("azure_cost_sync.py")
    _run_python_script("gcp_cost_sync.py")
    LOGGER.info("[job] cost_ingestion_hourly completed")


def job_anomaly_scan_hourly() -> None:
    LOGGER.info("[job] anomaly_scan_hourly started")
    _run_python_script("anomaly_detection_engine.py")
    LOGGER.info("[job] anomaly_scan_hourly completed")


def job_alert_engine_hourly() -> None:
    LOGGER.info("[job] alert_engine_hourly started")
    tenants = _get_tenant_ids()
    if not tenants:
        LOGGER.warning("No tenants found for alert evaluation")
        return

    for tenant in tenants:
        try:
            config = get_alert_config(tenant_id=tenant)
            alerts = evaluate_alerts(tenant_id=tenant)
            if not alerts:
                continue
            for alert in alerts:
                results = dispatch_alert_channels(alert, config)
                successful_channels = [name for name, result in results.items() if result.get("sent")]
                status = "sent" if successful_channels else "pending"
                record_alert_event(
                    tenant_id=tenant,
                    alert_type=str(alert.get("alert_type")),
                    severity=str(alert.get("severity", "info")),
                    message=str(alert.get("message", "")),
                    channels=list(results.keys()),
                    status=status,
                    payload={"alert": alert.get("payload") or {}, "delivery": results},
                )
        except Exception as exc:
            LOGGER.exception("Failed alert evaluation for tenant %s: %s", tenant, exc)

    LOGGER.info("[job] alert_engine_hourly completed")


def job_optimization_engine_daily() -> None:
    LOGGER.info("[job] optimization_engine_daily started")
    tenants = _get_tenant_ids()
    if not tenants:
        generate_recommendations()
    else:
        for tenant in tenants:
            generate_recommendations(org_id=tenant)
    LOGGER.info("[job] optimization_engine_daily completed")


def job_kpi_refresh_15m() -> None:
    LOGGER.info("[job] kpi_refresh_15m started")
    try:
        # Optional DB-side refresh hook (create this function in Supabase for fast KPI materialization).
        supabase.rpc("refresh_kpis").execute()
        LOGGER.info("refresh_kpis RPC executed")
    except Exception as exc:
        LOGGER.warning("refresh_kpis RPC unavailable/skipped: %s", exc)
    LOGGER.info("[job] kpi_refresh_15m completed")


def job_report_generation_daily() -> None:
    LOGGER.info("[job] report_generation_daily started")
    output_dir = ROOT_DIR / "exports" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    tenants = _get_tenant_ids()
    if not tenants:
        LOGGER.warning("No tenants found for report generation")
        return

    today = datetime.utcnow().strftime("%Y%m%d")
    for tenant in tenants:
        try:
            report = build_executive_pdf(tenant_id=tenant, requested_by="scheduler")
            out_file = output_dir / f"executive_{tenant}_{today}.pdf"
            out_file.write_bytes(report)
            record_report_history(
                tenant_id=tenant,
                report_name="executive_pdf",
                requested_by="scheduler",
                delivery_channel="scheduler",
                status="generated",
                file_name=out_file.name,
            )
            LOGGER.info("Generated report: %s", out_file)

            distribution = get_report_distribution_list(tenant_id=tenant)
            recipients = distribution.get("recipients") or []
            if distribution.get("active") and recipients:
                result = send_executive_report_email(
                    tenant_id=tenant,
                    recipients=[str(item) for item in recipients],
                    requested_by="scheduler",
                )
                LOGGER.info("Daily report email result for %s: %s", tenant, result)
        except Exception as exc:
            LOGGER.exception("Failed report generation for tenant %s: %s", tenant, exc)

    LOGGER.info("[job] report_generation_daily completed")


def job_escalation_hourly() -> None:
    """Check for stale approvals and escalate them based on SLA rules."""
    LOGGER.info("[job] escalation_hourly started")
    try:
        # Check PENDING_APPROVAL (48h SLA)
        result_pending = batch_escalate_stale(
            workflow_state="PENDING_APPROVAL",
            sla_hours=48,
            actor="escalation_engine",
            dry_run=False,
        )
        LOGGER.info(
            "Escalation results (PENDING_APPROVAL): escalated=%d, failed=%d",
            result_pending.get("escalated_count", 0),
            result_pending.get("failed_count", 0),
        )

        # Check APPROVED (72h SLA)
        result_approved = batch_escalate_stale(
            workflow_state="APPROVED",
            sla_hours=72,
            actor="escalation_engine",
            dry_run=False,
        )
        LOGGER.info(
            "Escalation results (APPROVED): escalated=%d, failed=%d",
            result_approved.get("escalated_count", 0),
            result_approved.get("failed_count", 0),
        )

        # Get aging summary for monitoring
        aging = get_aging_summary()
        if aging.get("ok"):
            summary = aging.get("summary", {})
            LOGGER.info(
                "Aging summary: total=%d, violations=%s",
                summary.get("total", 0),
                summary.get("sla_violations", {}),
            )

    except Exception as exc:
        LOGGER.exception("Escalation job failed: %s", exc)

    LOGGER.info("[job] escalation_hourly completed")


def job_alert_processor_hourly() -> None:
    """Process and send pending alerts across all configured channels."""
    LOGGER.info("[job] alert_processor_hourly started")
    try:
        configs = get_alert_configs(active_only=True)
        LOGGER.info("Found %d active alert configs", len(configs))

        # Example: Send a system health check alert if any escalations occurred in past hour
        # In production, this would be triggered by specific events
        from datetime import datetime, timedelta

        cutoff = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        try:
            recent_escalations = (
                supabase.table("recommendation_events")
                .select("*")
                .eq("action", "workflow_state_changed")
                .gte("created_at", cutoff)
                .execute()
            )
            escalation_count = len([e for e in recent_escalations.data or [] if str(e.get("new_value", "")).upper() == "ESCALATED"])

            if escalation_count > 0:
                result = process_alerts(
                    title="Recommendation Escalations Detected",
                    message=f"{escalation_count} recommendations were escalated in the past hour. Review the approval center for action.",
                    severity="warning",
                    channels=["email", "slack"],
                )
                LOGGER.info(
                    "Alert processing result: sent=%d, failed=%d",
                    result.get("total_sent", 0),
                    result.get("total_failed", 0),
                )
        except Exception as query_exc:
            LOGGER.warning("Could not query recent escalations: %s", query_exc)

    except Exception as exc:
        LOGGER.exception("Alert processor job failed: %s", exc)

    LOGGER.info("[job] alert_processor_hourly completed")

