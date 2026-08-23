from __future__ import annotations

import html
from dataclasses import asdict

import streamlit as st

from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.prospect_data_intake_service import (
    DEFAULT_RETENTION_DAYS,
    PROSPECT_WATERMARK,
    SUPPORTED_PROFILES,
    ProspectIntakeError,
    confirm_analysis_currency,
    create_prospect_tenant,
    ingest_upload,
    prospect_encryption_key,
    record_activity,
)
from shared.currency import SUPPORTED_CURRENCIES, format_currency_amount
from shared.session import init_session
from shared.styles import configure_page

configure_page(page_title="Prospect Data Intake | Nexora", page_icon="PI")
init_session()
role = normalize_role(st.session_state.get("role"))
if role not in {"sales_engineer", "finance"}:
    st.error("Prospect Data Intake is restricted to Sales Engineers and Finance Operators.")
    st.stop()
render_sidebar_navigation(role)


def _board_pack_html(prospect_name: str, analysis) -> str:
    metadata = asdict(analysis)
    monetary_fields = {
        "total_spend",
        "cloud_spend",
        "saas_spend",
        "other_spend",
        "unclassified_spend",
        "opportunity_identified",
        "opportunity_evidence_qualified",
        "opportunity_recommended",
        "opportunity_approved",
        "opportunity_realized",
    }
    rows = "".join(
        f"<tr><th>{html.escape(key.replace('_', ' ').title())}</th>"
        f"<td>{html.escape(format_currency_amount(value, analysis.currency) if key in monetary_fields else str(value))}</td></tr>"  # noqa: E501
        for key, value in metadata.items()
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Prospect Board Pack</title>"
        "<style>body{font-family:Arial;margin:48px;color:#172033}"
        "h1{margin-bottom:4px}.watermark{color:#9a6700;font-weight:700}"
        "table{border-collapse:collapse;width:100%}th,td{padding:10px;border-bottom:1px solid #ddd;"
        "text-align:left}</style></head><body>"
        f"<p class='watermark'>{html.escape(PROSPECT_WATERMARK)}</p>"
        f"<h1>{html.escape(prospect_name)} &mdash; Prospect Analysis</h1>"
        "<p>Evidence-backed temporary analysis. Human review is required.</p>"
        f"<table>{rows}</table></body></html>"
    )


def _audit_board_pack_download() -> None:
    tenant = st.session_state.get("prospect_tenant")
    if not tenant:
        return
    record_activity(
        tenant,
        event="PROSPECT_BOARD_PACK_EXPORTED",
        actor=str(st.session_state.get("user_email") or "unknown"),
        role=role,
        details={"format": "html", "watermarked": True},
        key=prospect_encryption_key(),
    )


st.markdown(
    """
    <section class="nexora-welcome-hero">
      <p class="nexora-eyebrow">SECURE PROSPECT ANALYSIS</p>
      <h1>Drop in evidence. Walk out with an executive brief.</h1>
      <p>Nexora scans, validates, normalizes, and analyzes supported cost evidence inside
      an encrypted temporary tenant. Missing attribution remains UNKNOWN.</p>
    </section>
    """,
    unsafe_allow_html=True,
)
st.warning(PROSPECT_WATERMARK)

current_analysis = st.session_state.get("prospect_analysis")
if current_analysis:
    progress_steps = (
        "Uploaded",
        "Validated",
        "Normalized",
        "Mapped",
        "Analyzed",
        "Executive intelligence ready",
    )
    progress_class = "ready"
elif st.session_state.get("prospect_analysis_error"):
    progress_steps = ("Needs attention",)
    progress_class = ""
else:
    progress_steps = ("Awaiting governed upload",)
    progress_class = ""
st.markdown(
    '<div class="nexora-process">'
    + "".join(
        f'<div class="nexora-process-step {progress_class}">{step}</div>'
        for step in progress_steps
    )
    + "</div>",
    unsafe_allow_html=True,
)

with st.container(border=True):
    st.subheader("1. Consent and temporary tenant")
    prospect_name = st.text_input("Prospect organization name")
    consent = st.checkbox(
        "I confirm the prospect authorized this temporary analysis and 30-day encrypted retention."
    )
    st.caption(
        "Uploaded data is isolated, encrypted, excluded from logs and Git, and automatically "
        "eligible for purge after 30 days. It is never used for model training."
    )

with st.container(border=True):
    st.subheader("2. Add business data")
    profile = st.selectbox("Input profile", SUPPORTED_PROFILES)
    upload = st.file_uploader(
        "Drop CSV or Excel evidence here, or browse files",
        type=["csv", "xlsx"],
        help="Supported schemas are validated before analysis. Unsupported files are rejected.",
    )
    st.caption("Supported now: CSV and XLSX · PDF invoices are not yet supported")

if st.button("Create temporary analysis", type="primary", use_container_width=True):
    if upload is None:
        st.error("Select a CSV or XLSX file before creating the analysis.")
    else:
        try:
            key = prospect_encryption_key()
            actor = str(st.session_state.get("user_email") or "unknown")
            tenant = create_prospect_tenant(
                prospect_name,
                consent=consent,
                actor=actor,
                role=role,
                retention_days=DEFAULT_RETENTION_DAYS,
                key=key,
            )
            analysis = ingest_upload(
                tenant,
                profile=profile,
                filename=upload.name,
                content=upload.getvalue(),
                actor=actor,
                role=role,
                key=key,
            )
            st.session_state["prospect_tenant"] = tenant
            st.session_state["prospect_analysis"] = analysis
            st.session_state["prospect_name"] = prospect_name.strip()
            st.session_state.pop("prospect_analysis_error", None)
            st.success("Prospect evidence was scanned, normalized, encrypted, and analyzed.")
        except ProspectIntakeError as exc:
            st.session_state["prospect_analysis_error"] = str(exc)
            st.error(str(exc))

analysis = st.session_state.get("prospect_analysis")
if analysis:
    if analysis.currency_resolution_required:
        st.divider()
        if analysis.currency_source == "MIXED_EVIDENCE":
            st.error(
                "Multiple currencies were detected: "
                + ", ".join(analysis.detected_currencies)
                + ". Monetary values have not been aggregated. FX conversion is not supported."
            )
        else:
            st.warning("Currency could not be determined from the uploaded evidence.")
            selected_currency = st.selectbox(
                "Currency", SUPPORTED_CURRENCIES, key="intake_currency_selection"
            )
            confirmed = st.checkbox(
                "I confirm that the selected currency applies to the uploaded evidence.",
                key="intake_currency_confirmation",
            )
            if st.button("Confirm currency", type="primary", use_container_width=True):
                try:
                    analysis = confirm_analysis_currency(
                        st.session_state["prospect_tenant"],
                        analysis=analysis,
                        selected_currency=selected_currency,
                        confirmed=confirmed,
                        actor=str(st.session_state.get("user_email") or "unknown"),
                        role=role,
                        key=prospect_encryption_key(),
                    )
                    st.session_state["prospect_analysis"] = analysis
                    st.rerun()
                except ProspectIntakeError as exc:
                    st.error(str(exc))
        st.stop()
    st.divider()
    st.caption(PROSPECT_WATERMARK.upper())
    st.header(f"{st.session_state['prospect_name']} — Prospect Analysis")
    primary = st.columns(4)
    primary[0].metric("Technology spend", format_currency_amount(analysis.total_spend, analysis.currency))
    primary[1].metric("Cloud", format_currency_amount(analysis.cloud_spend, analysis.currency))
    primary[2].metric("SaaS", format_currency_amount(analysis.saas_spend, analysis.currency))
    primary[3].metric("Other technology", format_currency_amount(analysis.other_spend, analysis.currency))
    quality = st.columns(4)
    quality[0].metric(
        "Evidence-qualified opportunity",
        format_currency_amount(analysis.opportunity_evidence_qualified, analysis.currency),
    )
    quality[1].metric("Evidence coverage", f"{analysis.evidence_coverage:.1f}%")
    quality[2].metric("Unclassified spend", format_currency_amount(analysis.unclassified_spend, analysis.currency))
    quality[3].metric("Confidence", f"{analysis.confidence:.1f}%")

    st.subheader("Value maturity")
    maturity = st.columns(5)
    for column, (label, value) in zip(
        maturity,
        (
            ("Identified", analysis.opportunity_identified),
            ("Evidence Qualified", analysis.opportunity_evidence_qualified),
            ("Recommended", analysis.opportunity_recommended),
            ("Approved", analysis.opportunity_approved),
            ("Realized", analysis.opportunity_realized),
        ),
        strict=True,
    ):
        column.metric(label, format_currency_amount(value, analysis.currency))

    st.subheader("Ask Nexora")
    question = st.selectbox(
        "Executive question",
        (
            "Where can I reduce cost?",
            "How reliable is this analysis?",
            "What remains unknown?",
        ),
        key="prospect_question",
    )
    if question == "Where can I reduce cost?":
        st.info(
            f"{format_currency_amount(analysis.opportunity_identified, analysis.currency)} is identified and "
            f"{format_currency_amount(analysis.opportunity_evidence_qualified, analysis.currency)} is evidence "
            "qualified. No amount is called recommended, approved, or realized without the "
            "corresponding evidence and authority."
        )
    elif question == "How reliable is this analysis?":
        st.info(
            f"Evidence coverage is {analysis.evidence_coverage:.1f}% and confidence is "
            f"{analysis.confidence:.1f}%. This is temporary prospect analysis, not certified "
            "production reporting."
        )
    else:
        st.info(
            f"{format_currency_amount(analysis.unclassified_spend, analysis.currency)} remains unclassified. "
            "Business-service, application, ownership, and risk attribution remain UNKNOWN "
            "unless those evidence fields were supplied."
        )

    st.download_button(
        "Download watermarked prospect Board Pack",
        data=_board_pack_html(st.session_state["prospect_name"], analysis),
        file_name="nexora-prospect-board-pack.html",
        mime="text/html",
        use_container_width=True,
        on_click=_audit_board_pack_download,
    )
    st.caption(
        f"Tenant ID: {analysis.tenant_id} · Audit ID: {analysis.audit_id} · "
        f"Analysis: {analysis.analysis_timestamp} · Expires: {analysis.expires_at}"
    )
