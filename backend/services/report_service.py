from datetime import datetime
from io import BytesIO
from typing import Any
import uuid
import logging

import pandas as pd

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.services.cost_service import fetch_cost_data
from backend.services.governance_service import get_governance_summary
from backend.services.recommendation_service import get_recommendations
from backend.services.alert_service import send_email_alert
from backend.services.tenant_scope import scoped_query
from data.supabase_client import supabase

REPORT_HISTORY_TABLE = "report_history"
REPORT_RECIPIENTS_TABLE = "report_distribution_lists"
logger = logging.getLogger(__name__)


def _draw_heading(pdf: canvas.Canvas, text: str, y: int) -> int:
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, y, text)
    return y - 16


def _draw_text_lines(pdf: canvas.Canvas, lines: list[str], y: int) -> int:
    pdf.setFont("Helvetica", 10)
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 14
        if y < 70:
            pdf.showPage()
            y = 760
            pdf.setFont("Helvetica", 10)
    return y


def _get_monthly_cloud_spend(tenant_id: str) -> list[dict[str, Any]]:
    rows = scoped_query(supabase, "unified_cloud_costs", tenant_id).select("cloud,cost,usage_date").execute().data or []
    if not rows:
        return []

    df = pd.DataFrame(rows)
    if "usage_date" not in df.columns:
        return []

    df["usage_date"] = pd.to_datetime(df["usage_date"], errors="coerce")
    df["cost"] = pd.to_numeric(df.get("cost"), errors="coerce").fillna(0)
    df = df.dropna(subset=["usage_date"]).copy()
    if df.empty:
        return []

    df["month"] = df["usage_date"].dt.to_period("M").astype(str)
    monthly = (
        df.groupby(["month", "cloud"], dropna=False)["cost"]
        .sum()
        .reset_index()
        .sort_values(["month", "cost"], ascending=[False, False])
    )
    return monthly.to_dict("records")


def _get_anomaly_summary(tenant_id: str) -> dict[str, Any]:
    rows = scoped_query(supabase, "anomalies", tenant_id).execute().data or []
    if not rows:
        return {"count": 0, "severity": [], "top": []}

    df = pd.DataFrame(rows)
    sev_col = "severity" if "severity" in df.columns else None
    score_col = "score" if "score" in df.columns else None
    svc_col = "service_name" if "service_name" in df.columns else ("service" if "service" in df.columns else None)

    severity = []
    if sev_col:
        severity = (
            df.groupby(sev_col)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .to_dict("records")
        )

    top = []
    if svc_col:
        ranked = df.copy()
        if score_col:
            ranked[score_col] = pd.to_numeric(ranked[score_col], errors="coerce").fillna(0)
            ranked = ranked.sort_values(score_col, ascending=False)
        top = ranked[[svc_col] + ([score_col] if score_col else [])].head(10).to_dict("records")

    return {"count": len(rows), "severity": severity, "top": top}


def _build_email_body(tenant_id: str, cost_payload: dict[str, Any], governance: dict[str, Any], anomaly_summary: dict[str, Any]) -> str:
    return (
        "Executive cloud report attached.\n\n"
        f"Tenant: {tenant_id}\n"
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"Total spend: {cost_payload.get('total_cost', 0):,.2f}\n"
        f"Governance findings: {governance.get('anomaly_count', 0)}\n"
        f"Anomalies detected: {anomaly_summary.get('count', 0)}\n\n"
        "Includes: monthly cloud spend, optimization findings, governance scorecard, anomaly summary."
    )


def list_report_history(tenant_id: str, limit: int = 20) -> list[dict[str, Any]]:
    try:
        rows = (
            scoped_query(supabase, REPORT_HISTORY_TABLE, tenant_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
        return rows
    except Exception:
        logger.exception("report_history_load_failed tenant_id=%s limit=%s", tenant_id, limit)
        return []


def record_report_history(
    tenant_id: str,
    report_name: str,
    requested_by: str,
    delivery_channel: str,
    status: str,
    recipients: list[str] | None = None,
    file_name: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    payload = {
        "id": str(uuid.uuid4()),
        "organization_id": tenant_id,
        "org_id": tenant_id,
        "tenant_id": tenant_id,
        "report_name": report_name,
        "requested_by": requested_by,
        "delivery_channel": delivery_channel,
        "status": status,
        "recipients": recipients or [],
        "file_name": file_name,
        "notes": notes,
        "created_at": datetime.utcnow().isoformat(),
    }
    try:
        supabase.table(REPORT_HISTORY_TABLE).insert(payload).execute()
    except Exception:
        logger.exception(
            "report_history_insert_failed tenant_id=%s report_name=%s channel=%s",
            tenant_id,
            report_name,
            delivery_channel,
        )
        return {"saved": False, **payload}
    return {"saved": True, **payload}


def get_report_distribution_list(tenant_id: str) -> dict[str, Any]:
    try:
        rows = (
            scoped_query(supabase, REPORT_RECIPIENTS_TABLE, tenant_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            return rows[0]
    except Exception:
        logger.exception("report_distribution_load_failed tenant_id=%s", tenant_id)
    return {"organization_id": tenant_id, "org_id": tenant_id, "tenant_id": tenant_id, "recipients": [], "active": False}


def save_report_distribution_list(
    tenant_id: str,
    recipients: list[str],
    updated_by: str,
    active: bool = True,
) -> dict[str, Any]:
    clean_recipients = sorted({str(item).strip() for item in recipients if str(item).strip()})
    payload = {
        "id": str(uuid.uuid4()),
        "organization_id": tenant_id,
        "org_id": tenant_id,
        "tenant_id": tenant_id,
        "report_name": "executive_pdf",
        "recipients": clean_recipients,
        "active": active,
        "updated_by": updated_by,
        "updated_at": datetime.utcnow().isoformat(),
    }
    try:
        supabase.table(REPORT_RECIPIENTS_TABLE).upsert(payload, on_conflict="org_id,report_name").execute()
    except Exception:
        logger.exception("report_distribution_upsert_failed tenant_id=%s", tenant_id)
        return {"saved": False, **payload}
    return {"saved": True, **payload}


def build_executive_pdf(tenant_id: str, requested_by: str = "api") -> bytes:
    payload = fetch_cost_data(tenant_id=tenant_id, requested_by=requested_by)
    recommendations = get_recommendations(tenant_id=tenant_id)
    governance = get_governance_summary(tenant_id=tenant_id)
    monthly_cloud_spend = _get_monthly_cloud_spend(tenant_id=tenant_id)
    anomaly_summary = _get_anomaly_summary(tenant_id=tenant_id)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    pdf.setTitle("Cloud Executive Report")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, 760, "AI Cloud Advisor - Executive Cost Report")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 740, f"Tenant: {tenant_id}")
    pdf.drawString(40, 726, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    pdf.drawString(40, 712, f"Requested by: {requested_by}")

    y = 686
    y = _draw_heading(pdf, "Executive Summary", y)
    y = _draw_text_lines(
        pdf,
        [
            f"Total cost: {payload.get('total_cost', 0):,.2f}",
            f"Records: {payload.get('record_count', 0)}",
            f"Governance findings: {governance.get('anomaly_count', 0)}",
            f"Anomalies detected: {anomaly_summary.get('count', 0)}",
            f"Recommendations: {len(recommendations)}",
        ],
        y,
    )

    y -= 6
    y = _draw_heading(pdf, "Monthly Cloud Spend Report", y)
    if monthly_cloud_spend:
        month_group = {}
        for row in monthly_cloud_spend[:24]:
            month_group.setdefault(row.get("month", "unknown"), []).append(row)
        month_lines: list[str] = []
        for month in sorted(month_group.keys(), reverse=True)[:3]:
            month_lines.append(f"{month}")
            for item in month_group[month][:5]:
                month_lines.append(f"  - {item.get('cloud', 'Unknown')}: {float(item.get('cost', 0) or 0):,.2f}")
        y = _draw_text_lines(pdf, month_lines, y)
    else:
        y = _draw_text_lines(pdf, ["No monthly spend data available."], y)

    y -= 6
    y = _draw_heading(pdf, "Optimization Findings", y)
    if recommendations:
        rec_lines = []
        for rec in recommendations[:10]:
            service = rec.get("service", "Unknown")
            impact = rec.get("impact", "N/A")
            savings = float(rec.get("estimated_savings", 0) or 0)
            message = str(rec.get("message", "Optimization opportunity"))
            rec_lines.append(f"- [{impact}] {service}: {message} (Est. savings {savings:,.2f})")
        y = _draw_text_lines(pdf, rec_lines, y)
    else:
        y = _draw_text_lines(pdf, ["No optimization findings available."], y)

    y -= 6
    y = _draw_heading(pdf, "Governance Scorecard", y)
    governance_lines = [f"Total governance findings: {governance.get('anomaly_count', 0)}"]
    for sev in governance.get("severity_distribution", [])[:5]:
        governance_lines.append(f"- {sev.get('severity_bucket', 'Unknown')}: {sev.get('count', 0)}")
    for finding in governance.get("top_findings", [])[:5]:
        service = finding.get("service") or finding.get("service_name") or "Unknown"
        bucket = finding.get("severity_bucket", "Unknown")
        governance_lines.append(f"- Top finding: {service} ({bucket})")
    y = _draw_text_lines(pdf, governance_lines, y)

    y -= 6
    y = _draw_heading(pdf, "Anomaly Summary", y)
    anomaly_lines = [f"Total anomalies: {anomaly_summary.get('count', 0)}"]
    for sev in anomaly_summary.get("severity", [])[:5]:
        name = sev.get("severity") or sev.get("index") or "Unknown"
        anomaly_lines.append(f"- {name}: {sev.get('count', 0)}")
    for item in anomaly_summary.get("top", [])[:5]:
        svc = item.get("service_name") or item.get("service") or "Unknown"
        score = item.get("score")
        if score is None:
            anomaly_lines.append(f"- {svc}")
        else:
            anomaly_lines.append(f"- {svc} (score {float(score):.2f})")
    y = _draw_text_lines(pdf, anomaly_lines, y)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()


def send_executive_report_email(
    tenant_id: str,
    recipients: list[str],
    requested_by: str = "api",
) -> dict[str, Any]:
    pdf_bytes = build_executive_pdf(tenant_id=tenant_id, requested_by=requested_by)
    cost_payload = fetch_cost_data(tenant_id=tenant_id, requested_by=requested_by)
    governance = get_governance_summary(tenant_id=tenant_id)
    anomaly_summary = _get_anomaly_summary(tenant_id=tenant_id)
    subject = f"Executive Cloud Report - {tenant_id}"
    body = _build_email_body(tenant_id, cost_payload, governance, anomaly_summary)

    result = send_email_alert(
        subject=subject,
        body=body,
        recipients=recipients,
        attachments=[
            {
                "filename": f"executive-report-{tenant_id}.pdf",
                "content": pdf_bytes,
                "mime_type": "application/pdf",
            }
        ],
    )
    record_report_history(
        tenant_id=tenant_id,
        report_name="executive_pdf",
        requested_by=requested_by,
        delivery_channel="email",
        status="sent" if result.get("sent") else "failed",
        recipients=recipients,
        file_name=f"executive-report-{tenant_id}.pdf",
        notes=result.get("reason"),
    )
    return result

