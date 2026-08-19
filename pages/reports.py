import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

try:
    import fitz
except ImportError:  # Optional renderer; report generation remains unchanged.
    fitz = None

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.cards import render_insight_card, render_metric_card
from components.layout import render_page, render_section, render_status_badge
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services import audit_service
from services.reporting_service import (
    get_approval_summary,
    get_executive_summary,
    get_recommendation_summary,
    get_report_history,
    get_saas_summary,
)
from services.reports_certification_service import ReportsCertificationService
from services.supabase_client import supabase
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page


def get_report_backend():
    try:
        from backend.services.report_service import (
            build_board_pack_pptx,
            build_report_pdf,
            build_report_xlsx,
            list_report_schedules,
            save_report_schedule,
        )

        return {
            "available": True,
            "build_board_pack_pptx": build_board_pack_pptx,
            "build_report_pdf": build_report_pdf,
            "build_report_xlsx": build_report_xlsx,
            "list_report_schedules": list_report_schedules,
            "save_report_schedule": save_report_schedule,
            "error": None,
        }
    except Exception as exc:
        return {
            "available": False,
            "build_board_pack_pptx": None,
            "build_report_pdf": None,
            "build_report_xlsx": None,
            "list_report_schedules": None,
            "save_report_schedule": None,
            "error": str(exc),
        }


def report_backend_warning(action, error):
    st.warning(
        f"Report {action} is unavailable in this environment. "
        "The Reports page remains available, but PDF and schedule actions require the report backend configuration."
    )
    if error:
        st.caption(f"Backend detail: {error}")


def format_currency(value):
    if value is None or value == "":
        return "UNKNOWN"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "UNKNOWN"


def format_number(value):
    if value is None or value == "":
        return "UNKNOWN"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "UNKNOWN"


def format_percent(value):
    if value is None or value == "":
        return "UNKNOWN"
    try:
        return f"{float(value):.0f}%"
    except (TypeError, ValueError):
        return "UNKNOWN"


def spend_value(row, new_key, old_key):
    return row.get(new_key, row.get(old_key))


def calculate_next_run(frequency):
    now = datetime.utcnow()
    frequency_key = str(frequency or "").lower()

    if frequency_key == "daily":
        return now + timedelta(days=1)
    if frequency_key == "weekly":
        return now + timedelta(weeks=1)
    if frequency_key == "quarterly":
        return now + timedelta(days=90)

    return now + timedelta(days=30)


def log_report_request(report_name):
    report_backend = get_report_backend()
    if not report_backend["available"]:
        report_backend_warning("generation", report_backend["error"])
        return False

    org_id = st.session_state.get("organization_id")
    requested_by = st.session_state.get("user") or st.session_state.get("email") or "unknown"

    report_id = str(uuid.uuid4())
    safe_name = report_name.lower().replace("&", "and").replace(" ", "_").replace("/", "_")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_name = f"{safe_name}_{timestamp}.pdf"

    output_dir = Path("exports") / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / file_name

    payload = {
        "id": report_id,
        "org_id": org_id,
        "tenant_id": org_id,
        "report_name": report_name,
        "requested_by": requested_by,
        "delivery_channel": "ui",
        "status": "queued",
        "recipients": [],
        "notes": "Report generation requested from Reports Center.",
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        supabase.table("report_history").insert(payload).execute()

        pdf_bytes = report_backend["build_report_pdf"](
            report_name=report_name,
            tenant_id=org_id,
            requested_by=requested_by,
        )

        file_path.write_bytes(pdf_bytes)

        supabase.table("report_history").update(
            {
                "status": "generated",
                "file_name": file_name,
                "notes": f"{report_name} generated successfully from Reports Center.",
            }
        ).eq("id", report_id).execute()

        audit_service.log_report_generated(
            report_id=report_id,
            generated_by=requested_by,
            org_id=org_id,
            report_type=report_name,
            file_name=file_name,
        )

        return True

    except Exception as e:
        st.error(f"REPORT ERROR: {e}")

        try:
            supabase.table("report_history").update(
                {
                    "status": "failed",
                    "notes": str(e),
                }
            ).eq("id", report_id).execute()
        except Exception:
            pass

        return False


report_data_freshness = ReportsCertificationService.report_data_freshness
scheduled_indicator = ReportsCertificationService.scheduled_indicator
report_coverage_label = ReportsCertificationService.report_coverage_label


def get_report_schedule_rows(org_id):
    if not org_id:
        return []

    report_backend = get_report_backend()
    if not report_backend["available"]:
        return []

    try:
        return report_backend["list_report_schedules"](org_id)
    except Exception:
        return []


def save_report_schedule_safe(
    tenant_id,
    report_type,
    frequency,
    recipient,
    active,
    next_run,
):
    report_backend = get_report_backend()
    if not report_backend["available"]:
        return {
            "saved": False,
            "error": report_backend["error"] or "Report backend is unavailable.",
        }

    try:
        return report_backend["save_report_schedule"](
            tenant_id=tenant_id,
            report_type=report_type,
            frequency=frequency,
            recipient=recipient,
            active=active,
            next_run=next_run,
        )
    except Exception as exc:
        return {
            "saved": False,
            "error": str(exc),
        }


def get_enterprise_spend_breakdown():
    try:
        response = supabase.table("mart_enterprise_spend_v2").select("*").limit(1).execute()
        return response.data[0] if response.data else {}
    except Exception:
        return {}


def get_enterprise_forecast_total():
    try:
        response = supabase.table("mart_enterprise_forecast").select("*").execute()
        rows = response.data or []
    except Exception:
        rows = []

    total = 0
    for row in rows:
        for key in (
            "projected_monthly_spend",
            "forecast_spend",
            "forecast_cost",
            "amount",
        ):
            if key in row:
                total += float(row.get(key) or 0)
                break

    return total if rows else None


def report_card(title, items, button_label, key):
    with st.container():
        render_insight_card(
            title=title,
            value=button_label.replace("Generate ", ""),
            description=report_coverage_label(title),
            icon="intelligence",
            status="ready",
        )
        for label, value in items:
            render_metric_card(
                title=label,
                value=value,
                icon="reports",
                status="info",
            )

        metadata_cols = st.columns(2)
        metadata_cols[0].caption(f"Last Generated: {last_generated_for(title, report_history_all)}")
        metadata_cols[1].caption(f"Delivery: {scheduled_indicator(title, schedule_rows)}")
        st.caption(f"Data Freshness: {report_data_freshness()}")
        st.caption("Export Format: PDF")

        if st.button(
            button_label,
            key=key,
            use_container_width=True,
        ):
            saved = log_report_request(title)

            if saved:
                st.success(f"{title} generated successfully.")
                st.rerun()
            else:
                st.error(f"{title} generation could not be queued.")


def last_generated_for(report_name, rows):
    for row in rows:
        if (
            row.get("report_name") == report_name
            and str(row.get("status", "")).lower() == "generated"
        ):
            return str(row.get("created_at", ""))[:19] or "Generated"
    return "Not generated"


def generated_report_thumbnail(report_name: str) -> bytes | None:
    """Render the first page of an existing governed PDF output for preview."""
    if fitz is None:
        return None
    for row in globals().get("report_history_all", []):
        if row.get("report_name") != report_name:
            continue
        if str(row.get("status", "")).lower() != "generated":
            continue
        file_name = Path(str(row.get("file_name") or "")).name
        if not file_name.lower().endswith(".pdf"):
            continue
        report_path = Path("exports") / "reports" / file_name
        if not report_path.is_file():
            continue
        with fitz.open(report_path) as document:
            if not document.page_count:
                continue
            pixmap = document.load_page(0).get_pixmap(matrix=fitz.Matrix(0.75, 0.75))
            return pixmap.tobytes("png")
    return None


def render_report_catalog_card(
    report_name,
    audience,
    purpose,
    frequency,
    last_generated,
    button_key,
    schedule_rows,
    backend_report_name=None,
):
    safe_report_name = str(report_name)
    generation_name = str(backend_report_name or report_name)
    delivery_mode = scheduled_indicator(generation_name, schedule_rows)
    coverage = report_coverage_label(safe_report_name)
    with st.container():
        actual_preview = generated_report_thumbnail(generation_name)
        if actual_preview:
            st.image(
                actual_preview,
                caption="Generated report · first-page preview",
                use_container_width=True,
            )
        st.markdown(
            f"""
            <div class="nexora-card" style="
                min-height: 238px;
                padding: 1rem;
                margin-bottom: 0.5rem;
            ">
                <div aria-label="Report preview" style="
                    width:92px;height:116px;float:right;margin:0 0 0.75rem 1rem;
                    border:1px solid #d9e1ec;border-radius:6px;background:#fff;
                    box-shadow:0 8px 20px rgba(15,23,42,.08);padding:10px;
                ">
                    <div style="height:8px;width:55%;background:#1d4ed8;margin-bottom:12px;"></div>
                    <div style="height:4px;background:#d9e1ec;margin-bottom:6px;"></div>
                    <div style="height:4px;background:#e8edf4;margin-bottom:6px;"></div>
                    <div style="height:36px;background:#eff6ff;margin:10px 0;"></div>
                    <div style="font-size:8px;color:#607087;text-align:center;">GENERATE TO PREVIEW</div>
                </div>
                <div style="font-size:1.05rem;font-weight:700;color:var(--nexora-text);margin-bottom:0.65rem;">
                    {safe_report_name}
                </div>
                <div style="display:grid;gap:0.35rem;font-size:0.9rem;color:var(--nexora-text-muted);">
                    <div><strong style="color:var(--nexora-text);">Audience:</strong> {audience}</div>
                    <div><strong style="color:var(--nexora-text);">Purpose:</strong> {purpose}</div>
                    <div><strong style="color:var(--nexora-text);">Coverage:</strong> {coverage}</div>
                    <div><strong style="color:var(--nexora-text);">Frequency:</strong> {frequency}</div>
                    <div><strong style="color:var(--nexora-text);">Last Generated:</strong> {last_generated}</div>
                    <div><strong style="color:var(--nexora-text);">Data Freshness:</strong> {report_data_freshness()}</div>
                    <div><strong style="color:var(--nexora-text);">Export Format:</strong> PDF</div>
                    <div><strong style="color:var(--nexora-text);">Delivery:</strong> {delivery_mode}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Generate",
            key=button_key,
            use_container_width=True,
        ):
            saved = log_report_request(generation_name)

            if saved:
                st.success(f"{safe_report_name} generated successfully.")
                st.rerun()
            else:
                st.error(f"{safe_report_name} generation could not be queued.")


def render_simple_report_catalog_card(
    report_name, description, last_generated, button_key, schedule_rows, backend_report_name=None
):
    safe_report_name = str(report_name)
    generation_name = str(backend_report_name or report_name)
    delivery_mode = scheduled_indicator(generation_name, schedule_rows)
    coverage = report_coverage_label(safe_report_name)
    with st.container():
        st.markdown(
            f"""
            <div class="nexora-card" style="
                min-height: 220px;
                padding: 1rem;
                margin-bottom: 0.5rem;
            ">
                <div style="font-size:1.05rem;font-weight:700;color:var(--nexora-text);margin-bottom:0.6rem;">
                    {safe_report_name}
                </div>
                <div style="font-size:0.92rem;color:var(--nexora-text-muted);line-height:1.45;margin-bottom:0.75rem;">
                    {description}
                </div>
                <div style="font-size:0.88rem;color:var(--nexora-text-muted);">
                    <strong style="color:var(--nexora-text);">Last Generated:</strong> {last_generated}
                </div>
                <div style="font-size:0.88rem;color:var(--nexora-text-muted);">
                    <strong style="color:var(--nexora-text);">Coverage:</strong> {coverage}
                </div>
                <div style="font-size:0.88rem;color:var(--nexora-text-muted);">
                    <strong style="color:var(--nexora-text);">Data Freshness:</strong> {report_data_freshness()}
                </div>
                <div style="font-size:0.88rem;color:var(--nexora-text-muted);">
                    <strong style="color:var(--nexora-text);">Export Format:</strong> PDF
                </div>
                <div style="font-size:0.88rem;color:var(--nexora-text-muted);">
                    <strong style="color:var(--nexora-text);">Delivery:</strong> {delivery_mode}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Generate",
            key=button_key,
            use_container_width=True,
        ):
            saved = log_report_request(generation_name)

            if saved:
                st.success(f"{safe_report_name} generated successfully.")
                st.rerun()
            else:
                st.error(f"{safe_report_name} generation could not be queued.")


configure_page(
    page_title="Executive Reports Center",
    page_icon=":bar_chart:",
    layout="wide",
)

init_session()

require_role(
    [
        "executive",
        "cio",
        "technical",
        "finance",
        "super_admin",
    ]
)

role = st.session_state.get("role", "cio")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Reports"],
)

render_page(
    title="Executive Reports Center",
    description="Board, financial, governance, and optimization reporting.",
    breadcrumbs=["Home", "Administration", "Reports"],
    content=None,
    show_footer=False,
)

summary = get_executive_summary()
recommendations = get_recommendation_summary()
approvals = get_approval_summary()
saas = get_saas_summary()
spend_breakdown = get_enterprise_spend_breakdown()
forecast_total = get_enterprise_forecast_total()
recommendations_available = bool(recommendations)
approvals_available = bool(approvals)

current_role = st.session_state.get("role", "").lower()
org_id = st.session_state.get("organization_id")
report_history_all = get_report_history()
report_backend_status = get_report_backend()
schedule_rows = get_report_schedule_rows(org_id)

approved_recommendations = recommendations.get("APPROVED", 0) + recommendations.get("approved", 0)

implemented_recommendations = (
    recommendations.get("IMPLEMENTED", 0)
    + recommendations.get("COMPLETED", 0)
    + recommendations.get("implemented", 0)
    + recommendations.get("completed", 0)
)

approved_approvals = approvals.get("APPROVED", 0) + approvals.get("approved", 0)

pending_approvals = (
    approvals.get("PENDING", 0) + approvals.get("PENDING_APPROVAL", 0) + approvals.get("pending", 0)
)

generated_count = sum(
    1 for row in report_history_all if str(row.get("status", "")).lower() == "generated"
)
failed_count = sum(
    1 for row in report_history_all if str(row.get("status", "")).lower() == "failed"
)
queued_count = sum(
    1 for row in report_history_all if str(row.get("status", "")).lower() == "queued"
)
scheduled_count = len(schedule_rows)

certification = ReportsCertificationService.get_dashboard(
    report_history=report_history_all,
    schedule_rows=schedule_rows,
    backend_status=report_backend_status,
    current_role=current_role,
)
reporting_health = certification["health"]
evidence = certification["evidence"]

st.markdown(
    """
    <section class="nexora-executive-hero">
      <p class="nexora-eyebrow">BOARD-READY OUTPUT</p>
      <h2>Turn the current decision story into an executive Board Pack.</h2>
    </section>
    """,
    unsafe_allow_html=True,
)
preview, action = st.columns([1.7, 1])
with preview:
    st.markdown("### Executive Board Pack preview")
    preview_pages = st.columns(3)
    preview_pages[0].markdown("**01 · Executive summary**\n\n**02 · Financial position**")
    preview_pages[1].markdown("**03 · Technology estate**\n\n**04 · Business services**")
    preview_pages[2].markdown("**05 · Risk and savings**\n\n**06 · Recommendations**")
    st.caption(
        "Generated from the existing tenant-scoped reporting engine and governed evidence."
    )
with action:
    st.markdown("### Ready when you are")
    if st.button(
        "Generate Executive Board Pack",
        key="hero_prepare_board_pack",
        type="primary",
        use_container_width=True,
        disabled=not report_backend_status["available"],
    ):
        st.session_state["ga_board_pack_pptx"] = report_backend_status[
            "build_board_pack_pptx"
        ](
            tenant_id=org_id,
            requested_by=st.session_state.get("user")
            or st.session_state.get("email")
            or "unknown",
        )
    if st.session_state.get("ga_board_pack_pptx"):
        st.download_button(
            "Download Board Pack",
            data=st.session_state["ga_board_pack_pptx"],
            file_name="nexora-executive-board-pack.pptx",
            mime=(
                "application/vnd.openxmlformats-officedocument.presentationml."
                "presentation"
            ),
            use_container_width=True,
        )
    st.caption("Scheduling remains available below through the existing report workflow.")

render_section(
    "Executive Summary",
    "Reporting posture, export readiness, latest activity, and data freshness.",
    divider=True,
)

render_insight_card(
    "Executive Summary",
    value="Executive Reports Center",
    description=certification["executive_summary"],
    icon="reports",
    status=reporting_health["status"],
)

health_cols = st.columns(4)
with health_cols[0]:
    render_metric_card(
        "Reporting Health",
        reporting_health["status"].title(),
        "Overall reporting posture",
        icon="reports",
        status=reporting_health["status"],
    )
with health_cols[1]:
    render_metric_card(
        "Report Domains",
        f"{reporting_health['domain_count']} Domains",
        "Executive reporting coverage",
        icon="reports",
        status="info",
    )
with health_cols[2]:
    render_metric_card(
        "Latest Activity",
        reporting_health["latest_activity"],
        "Most recent report event",
        icon="info",
        status="info",
    )
with health_cols[3]:
    render_metric_card(
        "PDF Backend",
        reporting_health["pdf_backend"],
        "Report export readiness",
        icon="download",
        status="healthy" if reporting_health["pdf_backend"] == "Available" else "warning",
    )

render_section(
    "Governed Executive Exports",
    "Create board and evidence packages from the same tenant-scoped certified sources.",
    divider=True,
)
export_cols = st.columns(2)
requested_by = st.session_state.get("user") or st.session_state.get("email") or "unknown"

if export_cols[0].button(
    "Prepare Board Pack (PowerPoint)",
    use_container_width=True,
    disabled=not report_backend_status["available"],
):
    st.session_state["ga_board_pack_pptx"] = report_backend_status[
        "build_board_pack_pptx"
    ](tenant_id=org_id, requested_by=requested_by)

if export_cols[1].button(
    "Prepare Evidence Workbook (Excel)",
    use_container_width=True,
    disabled=not report_backend_status["available"],
):
    st.session_state["ga_evidence_xlsx"] = report_backend_status["build_report_xlsx"](
        report_name="Executive Evidence Workbook",
        tenant_id=org_id,
        requested_by=requested_by,
    )

download_cols = st.columns(2)
if st.session_state.get("ga_board_pack_pptx"):
    download_cols[0].download_button(
        "Download Board Pack",
        data=st.session_state["ga_board_pack_pptx"],
        file_name="nexora-executive-board-pack.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        use_container_width=True,
    )
if st.session_state.get("ga_evidence_xlsx"):
    download_cols[1].download_button(
        "Download Evidence Workbook",
        data=st.session_state["ga_evidence_xlsx"],
        file_name="nexora-executive-evidence.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

render_section(
    "Executive Reporting Overview",
    "Enterprise reporting portal for executive, cost, governance, technology, SaaS, operational, and AI intelligence exports.",
    divider=True,
)
overview_cols = st.columns(4)
with overview_cols[0]:
    render_metric_card(
        "Generated Reports",
        generated_count,
        "Completed report packages",
        icon="success",
        status="healthy",
    )
with overview_cols[1]:
    render_metric_card(
        "Scheduled Reports",
        scheduled_count,
        "Recurring delivery definitions",
        icon="reports",
        status="info",
    )
with overview_cols[2]:
    render_metric_card(
        "Report Coverage",
        "7 Domains",
        "Executive, cost, governance, technology, SaaS, digital twin, AI",
        icon="reports",
        status="info",
    )
with overview_cols[3]:
    render_metric_card(
        "Export Format", "PDF", report_data_freshness(), icon="download", status="info"
    )

render_insight_card(
    "Executive Reporting Narrative",
    description=(
        "Reports are organized by decision domain so leaders can quickly generate board, financial, governance, "
        "technology intelligence, SaaS, operational, digital twin, and AI insight packages. Generated reports are "
        "tracked in history, while recurring delivery uses schedule metadata when the report backend is available."
    ),
    icon="reports",
    status="warning" if failed_count else "healthy",
)

if current_role in ["executive", "super_admin"]:
    render_section(
        "Executive Reports",
        "Board-ready reporting packages for financial performance, governance, risk, and optimization decisions.",
        divider=True,
    )

    executive_reports = [
        {
            "name": "Executive Board Pack",
            "backend_name": "Board Pack",
            "purpose": "Board Meeting",
            "audience": "Board / CEO",
            "frequency": "Monthly",
            "key": "generate_board_pack",
        },
        {
            "name": "Cost Optimization Report",
            "backend_name": "Financial Review",
            "purpose": "CFO Review",
            "audience": "CEO / CFO",
            "frequency": "Monthly",
            "key": "generate_financial_review",
        },
        {
            "name": "Governance Report",
            "backend_name": "Governance Review",
            "purpose": "Risk Committee",
            "audience": "CEO / Risk Committee",
            "frequency": "Quarterly",
            "key": "generate_governance_review",
        },
        {
            "name": "Operational Optimization Report",
            "backend_name": "Optimization Review",
            "purpose": "Cost Reduction",
            "audience": "CEO / CIO / CFO",
            "frequency": "Monthly",
            "key": "generate_optimization_review",
        },
    ]

    catalog_rows = [executive_reports[:2], executive_reports[2:]]
    for catalog_row in catalog_rows:
        cols = st.columns([1, 1], gap="large")
        for index, report in enumerate(catalog_row):
            with cols[index]:
                render_report_catalog_card(
                    report["name"],
                    report["audience"],
                    report["purpose"],
                    report["frequency"],
                    last_generated_for(
                        report.get("backend_name", report["name"]), report_history_all
                    ),
                    report["key"],
                    schedule_rows,
                    report.get("backend_name"),
                )

if current_role in ["cio", "super_admin"]:
    render_section(
        "Technology Intelligence Reports",
        "Technology, cloud, SaaS, governance, and risk reports for CIO decision-making.",
        divider=True,
    )

    cio_reports = [
        {
            "name": "Technology Intelligence Report",
            "backend_name": "Technology Spend Report",
            "description": "Application, platform, SaaS, license, MSP, cloud spend, and dependency package for CIO review.",
            "key": "generate_cio_technology_spend_report",
        },
        {
            "name": "Cost Optimization Report",
            "backend_name": "Cloud Strategy Report",
            "description": "Strategic view of enterprise cloud posture, forecast, savings opportunity, and active risk.",
            "key": "generate_cio_cloud_strategy_report",
        },
        {
            "name": "Governance Report",
            "backend_name": "Risk & Governance Report",
            "description": "Governance, policy, approval, and technology risk package for CIO decision-making.",
            "key": "generate_cio_risk_governance_report",
        },
        {
            "name": "SaaS Intelligence Report",
            "backend_name": "SaaS Governance Report",
            "description": "SaaS spend, license usage, renewal risk, vendor footprint, and optimization package.",
            "key": "generate_cio_saas_governance_report",
        },
    ]

    for report_row in [cio_reports[:2], cio_reports[2:]]:
        cols = st.columns([1, 1], gap="large")
        for index, report in enumerate(report_row):
            with cols[index]:
                render_simple_report_catalog_card(
                    report["name"],
                    report["description"],
                    last_generated_for(
                        report.get("backend_name", report["name"]), report_history_all
                    ),
                    report["key"],
                    schedule_rows,
                    report.get("backend_name"),
                )

if current_role in ["finance", "super_admin"]:
    render_section(
        "Cost Optimization Reports",
        "Budget, forecast, SaaS, license, savings, and financial performance reports.",
        divider=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        report_card(
            "Budget vs Actual Report",
            [
                ("Enterprise Spend", format_currency(summary.get("total_spend"))),
                ("Forecast", format_currency(forecast_total)),
                (
                    "Budget Performance",
                    format_percent(
                        summary.get("budget_performance", summary.get("budget_adherence"))
                    ),
                ),
            ],
            "Generate Budget Report",
            "generate_finance_budget_report",
        )

    with col2:
        report_card(
            "Forecast Report",
            [
                ("Forecast Spend", format_currency(forecast_total)),
                (
                    "Cloud Spend",
                    format_currency(spend_value(spend_breakdown, "cloud_spend", "cloud_cost")),
                ),
                (
                    "SaaS Spend",
                    format_currency(spend_value(spend_breakdown, "saas_spend", "saas_cost")),
                ),
            ],
            "Generate Forecast Report",
            "generate_finance_forecast_report",
        )

    col3, col4 = st.columns(2)

    with col3:
        report_card(
            "SaaS & License Report",
            [
                (
                    "SaaS Spend",
                    format_currency(
                        saas.get("total_cost")
                        if saas.get("data_available")
                        else spend_value(spend_breakdown, "saas_spend", "saas_cost")
                    ),
                ),
                (
                    "License Spend",
                    format_currency(spend_value(spend_breakdown, "license_spend", "license_cost")),
                ),
                (
                    "Users",
                    format_number(saas.get("total_users") if saas.get("data_available") else None),
                ),
            ],
            "Generate SaaS Report",
            "generate_finance_saas_report",
        )

    with col4:
        report_card(
            "Savings Report",
            [
                (
                    "Savings Identified",
                    format_currency(
                        summary.get("optimization_savings", summary.get("optimization"))
                    ),
                ),
                ("Savings Realized", format_currency(summary.get("savings_realized"))),
                (
                    "Approved Recommendations",
                    format_number(approved_recommendations if recommendations_available else None),
                ),
            ],
            "Generate Savings Report",
            "generate_finance_savings_report",
        )

if current_role in ["technical", "super_admin"]:
    render_section(
        "Operational Reports",
        "Resource inventory, cost intelligence, optimization, risk, and audit reports.",
        divider=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        report_card(
            "Resource Inventory Report",
            [
                ("Enterprise Spend", format_currency(summary.get("total_spend"))),
                ("Active Risks", format_number(summary.get("anomaly_count"))),
                ("Governance Score", format_percent(summary.get("governance_score"))),
            ],
            "Generate Resource Inventory Report",
            "generate_technical_inventory_report",
        )

    with col2:
        report_card(
            "Cost Intelligence Report",
            [
                (
                    "Optimization Opportunity",
                    format_currency(
                        summary.get("optimization_savings", summary.get("optimization"))
                    ),
                ),
                ("Forecast", format_currency(forecast_total)),
                (
                    "Cloud Spend",
                    format_currency(spend_value(spend_breakdown, "cloud_spend", "cloud_cost")),
                ),
            ],
            "Generate Cost Intelligence Report",
            "generate_technical_cost_report",
        )

    col3, col4 = st.columns(2)

    with col3:
        report_card(
            "Optimization Report",
            [
                (
                    "Savings Opportunity",
                    format_currency(
                        summary.get("optimization_savings", summary.get("optimization"))
                    ),
                ),
                (
                    "Approved Recommendations",
                    format_number(approved_recommendations if recommendations_available else None),
                ),
                (
                    "Implemented Recommendations",
                    format_number(
                        implemented_recommendations if recommendations_available else None
                    ),
                ),
            ],
            "Generate Optimization Report",
            "generate_technical_optimization_report",
        )

    with col4:
        report_card(
            "Risk & Audit Report",
            [
                ("Risks", format_number(summary.get("anomaly_count"))),
                (
                    "Approvals",
                    format_number(
                        pending_approvals + approved_approvals if approvals_available else None
                    ),
                ),
                ("Governance Score", format_percent(summary.get("governance_score"))),
            ],
            "Generate Risk & Audit Report",
            "generate_technical_risk_report",
        )

st.divider()
render_section("Generated Reports", "Generated report history and downloads.", divider=True)

report_history = report_history_all
report_history = sorted(
    report_history,
    key=lambda row: str(row.get("created_at", "")),
    reverse=True,
)

if current_role == "executive":
    executive_report_names = {
        "Board Pack",
        "Executive Board Pack",
        "Financial Review",
        "Cost Optimization Report",
        "Governance Review",
        "Governance Report",
        "Optimization Review",
        "Operational Optimization Report",
    }
    report_history = [
        row for row in report_history if row.get("report_name") in executive_report_names
    ]

history_status_options = [
    "All",
    "Generated",
    "Failed",
    "Queued",
]
default_history_index = 1 if current_role == "executive" else 0
history_status = st.selectbox(
    "Status Filter",
    history_status_options,
    index=default_history_index,
)

if history_status != "All":
    report_history = [
        row
        for row in report_history
        if str(row.get("status", "")).lower() == history_status.lower()
    ]

if report_history:
    header_cols = st.columns([2, 2, 2, 1, 1])
    header_cols[0].write("**Report**")
    header_cols[1].write("**Generated By**")
    header_cols[2].write("**Date**")
    header_cols[3].write("**Status**")
    header_cols[4].write("**Download**")

    for row in report_history:
        file_name = row.get("file_name")
        report_path = Path("exports") / "reports" / str(file_name)

        row_cols = st.columns([2, 2, 2, 1, 1])
        row_cols[0].write(row.get("report_name", "Report"))
        row_cols[1].write(row.get("requested_by", "unknown"))
        row_cols[2].write(str(row.get("created_at", ""))[:19] or "-")
        row_cols[3].write(row.get("status", "unknown"))

        if file_name and report_path.exists():
            with open(report_path, "rb") as f:
                row_cols[4].download_button(
                    "📄 Download",
                    data=f,
                    file_name=file_name,
                    mime="application/pdf",
                    key=row.get("id", file_name),
                )
        else:
            row_cols[4].write("-")
else:
    st.info(
        "No generated reports are available for the selected status. Generate a report package or change the status filter."
    )

st.divider()
render_section("Scheduled Reports", "Recurring report schedules and delivery status.", divider=True)

if not report_backend_status["available"]:
    report_backend_warning("scheduling", report_backend_status["error"])

schedule_header = st.columns([2, 1, 2, 2, 1])
schedule_header[0].write("**Report**")
schedule_header[1].write("**Frequency**")
schedule_header[2].write("**Recipient**")
schedule_header[3].write("**Next Run**")
schedule_header[4].write("**Status**")

if schedule_rows:
    for schedule in schedule_rows:
        schedule_cols = st.columns([2, 1, 2, 2, 1])
        schedule_cols[0].write(schedule.get("report_type", "Report"))
        schedule_cols[1].write(schedule.get("frequency", "-"))
        schedule_cols[2].write(schedule.get("recipient_email", "-"))
        schedule_cols[3].write(str(schedule.get("next_run", ""))[:19] or "-")
        with schedule_cols[4]:
            is_active = schedule.get("enabled", schedule.get("active"))
            render_status_badge(
                "healthy" if is_active else "unknown", label="Active" if is_active else "Inactive"
            )
else:
    st.info(
        "No scheduled reports are configured yet. Manual report generation remains available from the catalog above."
    )

if "show_report_schedule_form" not in st.session_state:
    st.session_state["show_report_schedule_form"] = False

if st.button(
    "Schedule Report",
    key="open_schedule_report_form",
    disabled=not report_backend_status["available"],
):
    st.session_state["show_report_schedule_form"] = True

if st.session_state.get("show_report_schedule_form"):
    with st.form("schedule_report_form"):
        schedule_report_options = {
            "Executive Board Pack": "Board Pack",
            "Cost Optimization Report": "Financial Review",
            "Governance Report": "Governance Review",
            "Operational Optimization Report": "Optimization Review",
        }
        report_type_display = st.selectbox(
            "Report Type",
            list(schedule_report_options),
        )
        frequency = st.selectbox(
            "Frequency",
            [
                "Daily",
                "Weekly",
                "Monthly",
                "Quarterly",
            ],
            index=2,
        )
        recipient = st.text_input(
            "Recipient",
            value="ceo@company.com",
        )

        submitted = st.form_submit_button(
            "Save Schedule",
            use_container_width=True,
        )

        if submitted:
            next_run = calculate_next_run(frequency)
            report_type = schedule_report_options[report_type_display]
            result = save_report_schedule_safe(
                tenant_id=org_id,
                report_type=report_type,
                frequency=frequency,
                recipient=recipient,
                active=True,
                next_run=next_run.isoformat(),
            )

            if result.get("saved"):
                st.session_state["show_report_schedule_form"] = False
                st.success(f"{report_type_display} scheduled.")
                st.rerun()
            else:
                st.error(
                    f"Report schedule could not be saved.\n\n"
                    f"{result.get('error', 'Unknown error')}"
                )

render_section(
    "Report Definitions", "Plain-language guide to executive reporting packages.", divider=True
)
definition_cols = st.columns(2)
definitions = [
    (
        "Executive Reports",
        "Board-ready packages summarizing spend, risk, governance, optimization, and executive decisions.",
    ),
    (
        "Cost Optimization Reports",
        "Finance-focused packages covering spend, forecast, savings, budget posture, and cost movement.",
    ),
    (
        "Governance Reports",
        "Risk and governance packages covering policy health, approvals, active risks, controls, and audit evidence.",
    ),
    (
        "Technology Intelligence Reports",
        "CIO packages covering applications, technologies, cloud, SaaS, dependencies, digital twin, and AI signals.",
    ),
    (
        "Operational Reports",
        "Technical packages covering resource inventory, cost intelligence, optimization, risk, and audit posture.",
    ),
    (
        "Scheduled Reports",
        "Recurring report deliveries configured for a recipient, cadence, and next run date.",
    ),
    (
        "Generated Reports",
        "Historical report packages generated through Nexora and available for download when files exist.",
    ),
]
for index, (title, description) in enumerate(definitions):
    with definition_cols[index % 2]:
        render_insight_card(
            title=title,
            description=description,
            icon="reports",
            status="info",
        )

render_section(
    "Report Governance Insight",
    "Report generation, scheduling, and governance posture.",
    divider=True,
)

governance_cols = st.columns(4)
with governance_cols[0]:
    render_metric_card("Generated Reports", generated_count, icon="success", status="healthy")
with governance_cols[1]:
    render_metric_card("Scheduled Reports", scheduled_count, icon="reports", status="info")
with governance_cols[2]:
    render_metric_card(
        "Queued Reports", queued_count, icon="info", status="watch" if queued_count else "healthy"
    )
with governance_cols[3]:
    render_metric_card(
        "Failed Reports",
        failed_count,
        icon="error",
        status="critical" if failed_count else "healthy",
    )

render_insight_card(
    title="Report Governance",
    value="Executive Reporting Control",
    description=(
        "Report generation is tracked through history records, scheduled delivery metadata, "
        "and audit logging. Generated packages remain available for download when the report file exists."
    ),
    icon="governance",
    status="warning" if failed_count else "healthy",
)

render_section(
    "Evidence",
    "Source data, coverage, AI interpretation, and raw evidence supporting Reports.",
    divider=True,
)

evidence_tabs = st.tabs(
    [
        "Source Data",
        "Data Coverage",
        "AI Interpretation",
        "Raw Evidence",
    ]
)

with evidence_tabs[0]:
    import pandas as pd

    st.dataframe(pd.DataFrame(evidence["source_data"]), use_container_width=True, hide_index=True)
with evidence_tabs[1]:
    import pandas as pd

    st.dataframe(pd.DataFrame(evidence["data_coverage"]), use_container_width=True, hide_index=True)
with evidence_tabs[2]:
    st.write(evidence["ai_interpretation"])
with evidence_tabs[3]:
    import pandas as pd

    st.caption("Reporting Health")
    st.dataframe(
        pd.DataFrame(evidence["raw_evidence"]["Reporting Health"]),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Backend Detail")
    st.dataframe(
        pd.DataFrame(evidence["raw_evidence"]["Backend Detail"]),
        use_container_width=True,
        hide_index=True,
    )
