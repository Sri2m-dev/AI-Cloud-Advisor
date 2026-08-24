from __future__ import annotations

import logging
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except ImportError:
    letter = None
    canvas = None

from backend.services.alert_service import send_email_alert
from backend.services.cost_service import fetch_cost_data
from backend.services.governance_service import get_governance_summary
from backend.services.recommendation_service import get_recommendations
from backend.services.tenant_scope import scoped_query
from data.supabase_client import supabase

REPORT_HISTORY_TABLE = "report_history"
REPORT_RECIPIENTS_TABLE = "report_distribution_lists"
REPORT_SCHEDULE_TABLE = "report_schedule"
logger = logging.getLogger(__name__)


def _require_reportlab() -> None:
    if canvas is None or letter is None:
        logger.warning("PDF reporting unavailable: install reportlab to enable PDF generation")
        raise RuntimeError("PDF reporting requires the optional dependency 'reportlab'")


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


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fetch_rows(
    table_name: str,
    tenant_id: str,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    try:
        rows = scoped_query(supabase, table_name, tenant_id).limit(limit).execute().data or []
        return rows
    except Exception:
        logger.exception("report_table_fetch_failed table=%s", table_name)
        return []


def _fetch_one(table_name: str, tenant_id: str) -> dict[str, Any]:
    rows = _fetch_rows(table_name, tenant_id, limit=1)
    return rows[0] if rows else {}


def _first_number(row: dict[str, Any], *keys: str) -> float:
    for key in keys:
        if key in row:
            return _safe_float(row.get(key))
    return 0.0


def _sum_rows(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> float:
    total = 0.0
    for row in rows:
        total += _first_number(row, *keys)
    return total


def _get_spend_breakdown(tenant_id: str) -> dict[str, float]:
    row = _fetch_one("mart_enterprise_spend_v2", tenant_id)
    return {
        "cloud_spend": _first_number(row, "cloud_spend", "cloud_cost"),
        "saas_spend": _first_number(row, "saas_spend", "saas_cost"),
        "msp_spend": _first_number(row, "msp_spend", "msp_cost"),
        "license_spend": _first_number(row, "license_spend", "license_cost"),
        "total_spend": _first_number(row, "total_spend"),
    }


def _get_budget_actual(tenant_id: str) -> dict[str, float]:
    rows = _fetch_rows("mart_budget_vs_actual", tenant_id)
    budget = _sum_rows(rows, ("budget", "budget_amount", "planned_cost"))
    actual = _sum_rows(rows, ("actual", "actual_cost", "total_cost", "cost"))
    return {
        "budget": budget,
        "actual": actual,
        "variance": actual - budget,
    }


def _get_forecast_total(tenant_id: str) -> float:
    return _sum_rows(
        _fetch_rows("mart_enterprise_forecast", tenant_id),
        ("projected_monthly_spend", "forecast_spend", "forecast_cost", "amount"),
    )


def _get_recommendation_summary(tenant_id: str) -> dict[str, Any]:
    recommendations = get_recommendations(tenant_id=tenant_id)
    realized_statuses = {"APPROVED", "IMPLEMENTED", "COMPLETED", "RESOLVED"}
    realized = 0.0
    pending = 0.0

    for rec in recommendations:
        savings = _safe_float(rec.get("estimated_savings"))
        status = str(rec.get("status") or "").upper()
        if status in realized_statuses:
            realized += savings
        else:
            pending += savings

    return {
        "items": recommendations,
        "count": len(recommendations),
        "realized_savings": realized,
        "pending_savings": pending,
        "total_savings": realized + pending,
    }


def _get_saas_summary(tenant_id: str) -> dict[str, float]:
    saas_costs = _fetch_rows("saas_cost", tenant_id, limit=1000)
    license_costs = _fetch_rows("license_cost", tenant_id, limit=1000)
    renewals = _fetch_rows("saas_renewals", tenant_id, limit=1000)
    saas_waste = _sum_rows(saas_costs, ("estimated_waste", "waste", "unused_cost"))
    license_waste = _sum_rows(license_costs, ("estimated_waste", "waste", "unused_cost"))
    now = datetime.utcnow()
    renewal_risk = 0.0

    for renewal in renewals:
        renewal_date = _parse_datetime(
            renewal.get("renewal_date")
            or renewal.get("contract_end_date")
            or renewal.get("expires_at")
            or renewal.get("current_period_end")
        )

        if not renewal_date:
            continue

        days_until = (renewal_date - now).days
        if days_until <= 90:
            renewal_risk += _first_number(
                renewal,
                "annual_cost",
                "contract_value",
                "yearly_cost",
            )

    return {
        "saas_spend": _sum_rows(saas_costs, ("cost", "amount", "spend", "total_cost")),
        "license_spend": _sum_rows(license_costs, ("cost", "amount", "spend", "total_cost")),
        "saas_waste": saas_waste,
        "license_waste": license_waste,
        "renewal_risk": renewal_risk,
    }


def _get_approval_metrics(tenant_id: str) -> dict[str, int]:
    rows = _fetch_rows("approval_requests", tenant_id, limit=1000)
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "UNKNOWN").upper()
        counts[status] = counts.get(status, 0) + 1
    counts["TOTAL"] = len(rows)
    return counts


def _get_audit_summary(tenant_id: str) -> dict[str, int]:
    rows = _fetch_rows("audit_events", tenant_id, limit=1000)
    event_types = {str(row.get("event_type") or "UNKNOWN") for row in rows}
    return {
        "events": len(rows),
        "event_types": len(event_types),
    }


def _parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _classify_report_type(report_name: str) -> str:
    name = report_name.lower()

    if "board" in name:
        return "board_pack"
    if any(term in name for term in ["saas", "license"]):
        return "saas_license"
    if "financial" in name or "budget" in name or "forecast" in name:
        return "financial_review"
    if any(term in name for term in ["governance", "risk", "audit"]):
        return "governance_review"
    if any(term in name for term in ["optimization", "saving", "cost intelligence"]):
        return "optimization_review"
    if any(
        term in name
        for term in [
            "financial",
            "budget",
            "forecast",
            "spend",
            "cloud strategy",
            "technology spend",
            "inventory",
            "resource",
        ]
    ):
        return "cost_spend"
    if any(term in name for term in ["board", "executive", "summary"]):
        return "executive_summary"

    return "executive_summary"


def _draw_report_shell(
    report_name: str,
    tenant_id: str,
    requested_by: str,
) -> tuple[BytesIO, canvas.Canvas, int]:
    _require_reportlab()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    pdf.setTitle(report_name)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, 760, f"Nexora - {report_name}")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 740, f"Tenant: {tenant_id}")
    pdf.drawString(40, 726, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    pdf.drawString(40, 712, f"Requested by: {requested_by}")

    return buffer, pdf, 686


def _finish_pdf(buffer: BytesIO, pdf: canvas.Canvas) -> bytes:
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()


def _draw_executive_summary_section(
    pdf: canvas.Canvas,
    y: int,
    tenant_id: str,
    requested_by: str,
) -> int:
    payload = fetch_cost_data(tenant_id=tenant_id, requested_by=requested_by)
    recommendations = get_recommendations(tenant_id=tenant_id)
    governance = get_governance_summary(tenant_id=tenant_id)
    anomaly_summary = _get_anomaly_summary(tenant_id=tenant_id)

    y = _draw_heading(pdf, "Executive Summary", y)
    return _draw_text_lines(
        pdf,
        [
            f"Total cost: {_safe_float(payload.get('total_cost')):,.2f}",
            f"Records: {payload.get('record_count', 0)}",
            f"Governance findings: {governance.get('anomaly_count', 0)}",
            f"Anomalies detected: {anomaly_summary.get('count', 0)}",
            f"Recommendations: {len(recommendations)}",
        ],
        y,
    )


def _draw_cost_spend_section(pdf: canvas.Canvas, y: int, tenant_id: str, requested_by: str) -> int:
    payload = fetch_cost_data(tenant_id=tenant_id, requested_by=requested_by)
    spend_breakdown = _get_spend_breakdown(tenant_id)
    forecast_rows = _fetch_rows("mart_enterprise_forecast", tenant_id)
    monthly_cloud_spend = _get_monthly_cloud_spend(tenant_id=tenant_id)

    forecast_total = 0.0
    for row in forecast_rows:
        for key in ("projected_monthly_spend", "forecast_spend", "forecast_cost", "amount"):
            if key in row:
                forecast_total += _safe_float(row.get(key))
                break

    y = _draw_heading(pdf, "Cost / Spend Report", y)
    y = _draw_text_lines(
        pdf,
        [
            f"Total cloud cost: {_safe_float(payload.get('total_cost')):,.2f}",
            f"Cloud spend: {_safe_float(spend_breakdown.get('cloud_spend')):,.2f}",
            f"SaaS spend: {_safe_float(spend_breakdown.get('saas_spend')):,.2f}",
            f"MSP spend: {_safe_float(spend_breakdown.get('msp_spend')):,.2f}",
            f"License spend: {_safe_float(spend_breakdown.get('license_spend')):,.2f}",
            f"Forecast total: {forecast_total:,.2f}",
        ],
        y,
    )

    y -= 6
    y = _draw_heading(pdf, "Monthly Cloud Spend", y)
    if monthly_cloud_spend:
        lines = [
            f"{row.get('month', 'unknown')} - {row.get('cloud', 'Unknown')}: "
            f"{_safe_float(row.get('cost')):,.2f}"
            for row in monthly_cloud_spend[:15]
        ]
    else:
        lines = ["No monthly spend data available for this report."]
    return _draw_text_lines(pdf, lines, y)


def _draw_savings_section(pdf: canvas.Canvas, y: int, tenant_id: str) -> int:
    recommendations = get_recommendations(tenant_id=tenant_id)

    y = _draw_heading(pdf, "Savings / Optimization Report", y)
    if not recommendations:
        return _draw_text_lines(
            pdf,
            ["No optimization recommendation data is available yet."],
            y,
        )

    total_savings = sum(_safe_float(rec.get("estimated_savings")) for rec in recommendations)
    lines = [f"Estimated savings identified: {total_savings:,.2f}"]
    for rec in recommendations[:15]:
        service = rec.get("service") or rec.get("service_name") or "Unknown"
        status = rec.get("status") or rec.get("impact") or "Unclassified"
        savings = _safe_float(rec.get("estimated_savings"))
        message = rec.get("message") or rec.get("title") or "Optimization opportunity"
        lines.append(f"- [{status}] {service}: {message} (Est. savings {savings:,.2f})")

    return _draw_text_lines(pdf, lines, y)


def _draw_governance_section(pdf: canvas.Canvas, y: int, tenant_id: str) -> int:
    governance = get_governance_summary(tenant_id=tenant_id)
    anomaly_summary = _get_anomaly_summary(tenant_id=tenant_id)

    y = _draw_heading(pdf, "Governance / Risk Report", y)
    lines = [
        f"Total governance findings: {governance.get('anomaly_count', 0)}",
        f"Total anomalies: {anomaly_summary.get('count', 0)}",
    ]

    for sev in governance.get("severity_distribution", [])[:5]:
        lines.append(
            f"- Governance severity {sev.get('severity_bucket', 'Unknown')}: {sev.get('count', 0)}"
        )
    for sev in anomaly_summary.get("severity", [])[:5]:
        name = sev.get("severity") or sev.get("index") or "Unknown"
        lines.append(f"- Anomaly severity {name}: {sev.get('count', 0)}")

    if len(lines) == 2:
        lines.append(
            "Limited governance/risk detail is available; this section is "
            "intentionally scoped to current data."
        )

    return _draw_text_lines(pdf, lines, y)


def _draw_saas_license_section(pdf: canvas.Canvas, y: int, tenant_id: str) -> int:
    saas_users = _fetch_rows("saas_users", tenant_id, limit=1000)
    saas_costs = _fetch_rows("saas_cost", tenant_id, limit=1000)
    spend_breakdown = _get_spend_breakdown(tenant_id)
    total_saas_cost = sum(_safe_float(row.get("cost")) for row in saas_costs)

    y = _draw_heading(pdf, "SaaS / License Report", y)
    lines = [
        f"SaaS users: {len(saas_users)}",
        f"SaaS cost: {total_saas_cost or _safe_float(spend_breakdown.get('saas_spend')):,.2f}",
        f"License spend: {_safe_float(spend_breakdown.get('license_spend')):,.2f}",
    ]

    if not saas_users and not saas_costs:
        lines.append(
            "Limited SaaS/license detail is available; this section is a labeled "
            "placeholder, not an executive summary."
        )

    return _draw_text_lines(pdf, lines, y)


def _get_monthly_cloud_spend(tenant_id: str) -> list[dict[str, Any]]:
    try:
        rows = scoped_query(supabase, "unified_cloud_costs", tenant_id).execute().data or []
    except Exception:
        logger.exception("monthly_cloud_spend_fetch_failed")
        return []

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
    try:
        rows = scoped_query(supabase, "anomalies", tenant_id).execute().data or []
    except Exception:
        logger.exception("anomaly_summary_fetch_failed")
        return {"count": 0, "severity": [], "top": []}

    if not rows:
        return {"count": 0, "severity": [], "top": []}

    df = pd.DataFrame(rows)
    sev_col = "severity" if "severity" in df.columns else None
    score_col = "score" if "score" in df.columns else None
    svc_col = (
        "service_name"
        if "service_name" in df.columns
        else ("service" if "service" in df.columns else None)
    )

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


def _build_email_body(
    tenant_id: str,
    cost_payload: dict[str, Any],
    governance: dict[str, Any],
    anomaly_summary: dict[str, Any],
) -> str:
    return (
        "Executive cloud report attached.\n\n"
        f"Tenant: {tenant_id}\n"
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"Total spend: {cost_payload.get('total_cost', 0):,.2f}\n"
        f"Governance findings: {governance.get('anomaly_count', 0)}\n"
        f"Anomalies detected: {anomaly_summary.get('count', 0)}\n\n"
        "Includes: monthly cloud spend, optimization findings, governance scorecard, "
        "and anomaly summary."
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
    history_id = str(uuid.uuid4())
    payload = {
        "id": history_id,
        "org_id": tenant_id,
        "report_name": report_name,
        "requested_by": requested_by,
        "delivery_channel": delivery_channel,
        "status": status,
        "file_name": file_name,
        "notes": notes,
        "created_at": datetime.utcnow().isoformat(),
    }
    try:
        supabase.table(REPORT_HISTORY_TABLE).insert(payload).execute()
    except Exception as exc:
        logger.exception("report_history_insert_failed")
        payload["saved"] = False
        payload["error"] = str(exc)
        return payload
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
    return {
        "organization_id": tenant_id,
        "org_id": tenant_id,
        "tenant_id": tenant_id,
        "recipients": [],
        "active": False,
    }


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
        supabase.table(REPORT_RECIPIENTS_TABLE).upsert(
            payload, on_conflict="org_id,report_name"
        ).execute()
    except Exception:
        logger.exception("report_distribution_upsert_failed tenant_id=%s", tenant_id)
        return {"saved": False, **payload}
    return {"saved": True, **payload}


def list_report_schedules(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
    try:
        rows = (
            supabase.table(REPORT_SCHEDULE_TABLE)
            .select("*")
            .eq("organization_id", tenant_id)
            .order("next_run", desc=False)
            .limit(limit)
            .execute()
            .data
            or []
        )
        return rows
    except Exception:
        logger.exception("report_schedule_load_failed tenant_id=%s", tenant_id)
        return []


def _is_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False


def save_report_schedule(
    tenant_id: str,
    report_type: str,
    frequency: str,
    recipient: str,
    active: bool,
    next_run: str | None = None,
    last_run: str | None = None,
    schedule_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.utcnow()
    next_run_value = (
        next_run.isoformat() if hasattr(next_run, "isoformat") else str(next_run or now.isoformat())
    )

    payload = {
        "id": str(uuid.uuid4()),
        "organization_id": tenant_id if _is_uuid(tenant_id) else None,
        "report_type": report_type,
        "frequency": frequency,
        "recipient_email": recipient,
        "enabled": True,
        "next_run": next_run_value,
        "created_at": now.isoformat(),
    }

    try:
        supabase.table(REPORT_SCHEDULE_TABLE).insert(payload).execute()
    except Exception as e:
        logger.exception(
            "report_schedule_insert_failed tenant_id=%s report_type=%s",
            tenant_id,
            report_type,
        )

        return {
            "saved": False,
            "error": str(e),
            **payload,
        }
    return {"saved": True, **payload}


def build_executive_pdf(tenant_id: str, requested_by: str = "api") -> bytes:
    _require_reportlab()
    payload = fetch_cost_data(tenant_id=tenant_id, requested_by=requested_by)
    recommendations = get_recommendations(tenant_id=tenant_id)
    governance = get_governance_summary(tenant_id=tenant_id)
    monthly_cloud_spend = _get_monthly_cloud_spend(tenant_id=tenant_id)
    anomaly_summary = _get_anomaly_summary(tenant_id=tenant_id)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    pdf.setTitle("Cloud Executive Report")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, 760, "Nexora - Executive Cost Report")

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
                month_lines.append(
                    f"  - {item.get('cloud', 'Unknown')}: {float(item.get('cost', 0) or 0):,.2f}"
                )
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


def _draw_board_pack(pdf: canvas.Canvas, y: int, tenant_id: str, requested_by: str) -> int:
    summary = _fetch_one("mart_executive_summary", tenant_id)
    spend = _get_spend_breakdown(tenant_id)
    budget = _get_budget_actual(tenant_id)
    forecast = _get_forecast_total(tenant_id)
    recommendations = _get_recommendation_summary(tenant_id)
    governance = get_governance_summary(tenant_id=tenant_id)
    saas = _get_saas_summary(tenant_id)
    optimization = summary.get("optimization_savings") or summary.get("optimization")

    y = _draw_heading(pdf, "Executive Summary", y)
    y = _draw_text_lines(
        pdf,
        [
            "Enterprise spend: "
            f"{_safe_float(summary.get('total_spend') or spend.get('total_spend')):,.2f}",
            "Optimization savings: "
            f"{_safe_float(optimization):,.2f}",
            f"Governance score: {_safe_float(summary.get('governance_score')):,.0f}%",
        ],
        y,
    )

    y -= 6
    y = _draw_heading(pdf, "Enterprise Spend", y)
    y = _draw_text_lines(
        pdf,
        [
            f"Cloud spend: {spend['cloud_spend']:,.2f}",
            f"SaaS spend: {spend['saas_spend']:,.2f}",
            f"MSP spend: {spend['msp_spend']:,.2f}",
            f"License spend: {spend['license_spend']:,.2f}",
        ],
        y,
    )

    y -= 6
    y = _draw_heading(pdf, "Budget vs Actual", y)
    y = _draw_text_lines(
        pdf,
        [
            f"Budget: {budget['budget']:,.2f}",
            f"Actual: {budget['actual']:,.2f}",
            f"Variance: {budget['variance']:,.2f}",
        ],
        y,
    )

    y -= 6
    y = _draw_heading(pdf, "Forecast", y)
    y = _draw_text_lines(pdf, [f"Projected spend: {forecast:,.2f}"], y)

    y -= 6
    y = _draw_heading(pdf, "Savings", y)
    y = _draw_text_lines(
        pdf,
        [
            f"Realized savings: {recommendations['realized_savings']:,.2f}",
            f"Pending savings: {recommendations['pending_savings']:,.2f}",
        ],
        y,
    )

    y -= 6
    y = _draw_heading(pdf, "Governance", y)
    y = _draw_text_lines(
        pdf,
        [
            f"Governance findings: {governance.get('anomaly_count', 0)}",
            f"Risks: {_get_anomaly_summary(tenant_id).get('count', 0)}",
        ],
        y,
    )

    y -= 6
    y = _draw_heading(pdf, "SaaS Renewal Risks", y)
    y = _draw_text_lines(
        pdf,
        [f"Contract renewals at risk: {saas['renewal_risk']:,.2f}"],
        y,
    )

    y -= 6
    y = _draw_heading(pdf, "Key Recommendations", y)
    lines = []
    for rec in recommendations["items"][:8]:
        title = rec.get("title") or rec.get("message") or "Optimization recommendation"
        savings = _safe_float(rec.get("estimated_savings"))
        lines.append(f"- {title} (Est. savings {savings:,.2f})")
    return _draw_text_lines(pdf, lines or ["No key recommendations available."], y)


def _draw_financial_review(pdf: canvas.Canvas, y: int, tenant_id: str, requested_by: str) -> int:
    spend = _get_spend_breakdown(tenant_id)
    budget = _get_budget_actual(tenant_id)
    forecast = _get_forecast_total(tenant_id)
    recommendations = _get_recommendation_summary(tenant_id)

    y = _draw_heading(pdf, "Financial Review", y)
    return _draw_text_lines(
        pdf,
        [
            f"Cloud spend: {spend['cloud_spend']:,.2f}",
            f"SaaS spend: {spend['saas_spend']:,.2f}",
            f"MSP spend: {spend['msp_spend']:,.2f}",
            f"License spend: {spend['license_spend']:,.2f}",
            f"Budget variance: {budget['variance']:,.2f}",
            f"Forecast: {forecast:,.2f}",
            f"Savings opportunity: {recommendations['pending_savings']:,.2f}",
        ],
        y,
    )


def _draw_governance_review(pdf: canvas.Canvas, y: int, tenant_id: str) -> int:
    summary = _fetch_one("mart_executive_summary", tenant_id)
    governance = get_governance_summary(tenant_id=tenant_id)
    anomaly_summary = _get_anomaly_summary(tenant_id=tenant_id)
    approvals = _get_approval_metrics(tenant_id)
    audit = _get_audit_summary(tenant_id)

    y = _draw_heading(pdf, "Governance Review", y)
    lines = [
        f"Governance score: {_safe_float(summary.get('governance_score')):,.0f}%",
        f"Risks: {anomaly_summary.get('count', 0)}",
        f"Approval metrics: {approvals.get('PENDING', 0)} pending, "
        f"{approvals.get('APPROVED', 0)} approved, "
        f"{approvals.get('REJECTED', 0)} rejected",
        f"Audit summary: {audit['events']} events across {audit['event_types']} event types",
        f"Compliance: {_safe_float(summary.get('governance_score')):,.0f}%",
    ]
    for sev in governance.get("severity_distribution", [])[:5]:
        lines.append(f"- {sev.get('severity_bucket', 'Unknown')}: {sev.get('count', 0)}")
    return _draw_text_lines(pdf, lines, y)


def _draw_optimization_review(pdf: canvas.Canvas, y: int, tenant_id: str) -> int:
    recommendations = _get_recommendation_summary(tenant_id)
    saas = _get_saas_summary(tenant_id)

    y = _draw_heading(pdf, "Optimization Review", y)
    lines = [
        f"Recommendations: {recommendations['count']}",
        f"Realized savings: {recommendations['realized_savings']:,.2f}",
        f"Pending savings: {recommendations['pending_savings']:,.2f}",
        f"SaaS waste: {saas['saas_waste']:,.2f}",
        f"License waste: {saas['license_waste']:,.2f}",
    ]
    for rec in recommendations["items"][:10]:
        title = rec.get("title") or rec.get("message") or "Optimization recommendation"
        status = rec.get("status") or rec.get("impact") or "Unclassified"
        savings = _safe_float(rec.get("estimated_savings"))
        lines.append(f"- [{status}] {title} (Est. savings {savings:,.2f})")
    return _draw_text_lines(pdf, lines, y)


def build_report_pdf(
    report_name: str,
    tenant_id: str,
    requested_by: str = "api",
) -> bytes:
    report_type = _classify_report_type(report_name)

    if report_type == "executive_summary":
        return build_executive_pdf(
            tenant_id=tenant_id,
            requested_by=requested_by,
        )

    buffer, pdf, y = _draw_report_shell(
        report_name=report_name,
        tenant_id=tenant_id,
        requested_by=requested_by,
    )

    if report_type == "board_pack":
        y = _draw_board_pack(
            pdf=pdf,
            y=y,
            tenant_id=tenant_id,
            requested_by=requested_by,
        )
    elif report_type == "financial_review":
        y = _draw_financial_review(
            pdf=pdf,
            y=y,
            tenant_id=tenant_id,
            requested_by=requested_by,
        )
    elif report_type == "governance_review":
        y = _draw_governance_review(
            pdf=pdf,
            y=y,
            tenant_id=tenant_id,
        )
    elif report_type == "optimization_review":
        y = _draw_optimization_review(
            pdf=pdf,
            y=y,
            tenant_id=tenant_id,
        )
    elif report_type == "cost_spend":
        y = _draw_cost_spend_section(
            pdf=pdf,
            y=y,
            tenant_id=tenant_id,
            requested_by=requested_by,
        )
    elif report_type == "saas_license":
        y = _draw_saas_license_section(
            pdf=pdf,
            y=y,
            tenant_id=tenant_id,
        )
    else:
        return build_executive_pdf(
            tenant_id=tenant_id,
            requested_by=requested_by,
        )

    y -= 6
    y = _draw_heading(pdf, "Report Scope", y)
    _draw_text_lines(
        pdf,
        [
            f"Report type: {report_type.replace('_', ' ').title()}",
            "Sections are generated from currently available Nexora data sources.",
            "If source detail is limited, the PDF includes a labeled placeholder section "
            "instead of reusing the wrong report body.",
        ],
        y,
    )

    return _finish_pdf(buffer, pdf)


def _executive_export_payload(tenant_id: str) -> dict[str, Any]:
    """Collect tenant-scoped evidence once for governed office exports."""
    return {
        "spend": _get_spend_breakdown(tenant_id),
        "budget": _get_budget_actual(tenant_id),
        "forecast": _get_forecast_total(tenant_id),
        "recommendations": _get_recommendation_summary(tenant_id),
        "saas": _get_saas_summary(tenant_id),
        "approvals": _get_approval_metrics(tenant_id),
        "audit": _get_audit_summary(tenant_id),
    }


def build_report_xlsx(
    report_name: str,
    tenant_id: str,
    requested_by: str = "api",
) -> bytes:
    """Build an evidence workbook without introducing a second reporting engine."""
    from services.impact_analysis_service import _minimal_xlsx

    payload = _executive_export_payload(tenant_id)
    metadata = [{
        "report_name": report_name,
        "tenant_id": tenant_id,
        "requested_by": requested_by,
        "generated_at_utc": datetime.utcnow().isoformat(),
        "classification": "CERTIFIED_TENANT_SCOPED_DATA",
    }]
    recommendations = payload["recommendations"]["items"] or [{"status": "UNKNOWN"}]
    return _minimal_xlsx({
        "Report Metadata": metadata,
        "Enterprise Spend": [payload["spend"]],
        "Budget and Forecast": [{**payload["budget"], "forecast": payload["forecast"]}],
        "Recommendations": recommendations,
        "SaaS": [payload["saas"]],
        "Approvals": [payload["approvals"]],
        "Audit": [payload["audit"]],
    })


def build_board_pack_pptx(
    tenant_id: str,
    requested_by: str = "api",
) -> bytes:
    """Build a board-ready presentation from the same tenant-scoped evidence."""
    from services.impact_analysis_service import _minimal_pptx

    payload = _executive_export_payload(tenant_id)
    spend = payload["spend"]
    budget = payload["budget"]
    recommendations = payload["recommendations"]
    approvals = payload["approvals"]
    top_recommendations = [
        str(item.get("title") or item.get("message") or "Recommendation")
        for item in recommendations["items"][:5]
    ] or ["No certified recommendations are currently available"]
    return _minimal_pptx([
        (
            "Nexora Executive Board Pack",
            [
                f"Tenant: {tenant_id}",
                f"Prepared for: {requested_by}",
                "Classification: certified tenant-scoped data",
            ],
        ),
        (
            "Financial posture",
            [
                f"Enterprise spend: {spend['total_spend']:,.2f}",
                f"Budget: {budget['budget']:,.2f}",
                f"Actual: {budget['actual']:,.2f}",
                f"Forecast: {payload['forecast']:,.2f}",
            ],
        ),
        ("Priority decisions", top_recommendations),
        (
            "Governance and action",
            [
                f"Pending approvals: {approvals.get('PENDING', 0)}",
                f"Certified recommendations: {recommendations['count']}",
                f"Audit events: {payload['audit']['events']}",
            ],
        ),
    ])


def send_executive_report_email(
    tenant_id: str,
    recipients: list[str],
    requested_by: str = "api",
    report_name: str = "Executive Summary",
) -> dict[str, Any]:
    pdf_bytes = build_report_pdf(
        report_name=report_name,
        tenant_id=tenant_id,
        requested_by=requested_by,
    )
    cost_payload = fetch_cost_data(tenant_id=tenant_id, requested_by=requested_by)
    governance = get_governance_summary(tenant_id=tenant_id)
    anomaly_summary = _get_anomaly_summary(tenant_id=tenant_id)
    subject = f"{report_name} - {tenant_id}"
    body = _build_email_body(tenant_id, cost_payload, governance, anomaly_summary)
    file_name = report_name.lower().replace("&", "and").replace("/", "_").replace(" ", "-")

    result = send_email_alert(
        subject=subject,
        body=body,
        recipients=recipients,
        attachments=[
            {
                "filename": f"{file_name}-{tenant_id}.pdf",
                "content": pdf_bytes,
                "mime_type": "application/pdf",
            }
        ],
    )
    record_report_history(
        tenant_id=tenant_id,
        report_name=report_name,
        requested_by=requested_by,
        delivery_channel="email",
        status="sent" if result.get("sent") else "failed",
        recipients=recipients,
        file_name=f"{file_name}-{tenant_id}.pdf",
        notes=result.get("reason"),
    )
    return result
