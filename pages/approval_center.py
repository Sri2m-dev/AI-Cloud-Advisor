from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page
from components.cards import render_approval_card, render_insight_card, render_kpi_card, render_metric_card
from components.layout import render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES

from services.approval_service import (
    ApprovalService
)
from services.approval_center_certification_service import (
    ApprovalCenterCertificationService,
)

configure_page(
    page_title="Approvals",
    page_icon="✅",
)

init_session()

require_role([
    "executive",
    "cio",
    "finance",
    "technical",
    "super_admin",
])

role = st.session_state.get("role", "cio")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Approvals"],
)

current_role = st.session_state.get("role", "").lower()
is_ceo_view = current_role == "executive"

def approval_table(rows):
    df = pd.DataFrame(rows)
    visible_columns = ApprovalCenterCertificationService.visible_columns(rows)

    return df[visible_columns]


def render_workflow_timeline(history_rows):
    for index, row in enumerate(history_rows):
        action = row.get("action", "Workflow Update")
        from_stage = row.get("from_stage", "Submitted")
        to_stage = row.get("to_stage", "Pending")
        created_at = row.get("created_at", "Time unavailable")

        st.markdown(
            f"""
            ✅ **{action}**

            {from_stage} → {to_stage}

            ({created_at})
            """
        )

        if index < len(history_rows) - 1:
            st.markdown("↓")

def render_approval_content():
    # --------------------------------------------------
    # KPI SECTION
    # --------------------------------------------------

    metrics = ApprovalService.get_dashboard_metrics()
    stage_metrics = (
        ApprovalService
        .get_workflow_stage_metrics()
    )
    overdue_approvals = (
        ApprovalService
        .get_overdue_approvals()
    )
    sla = ApprovalService.get_sla_metrics()
    approval_register = ApprovalService.get_all_approvals()
    pending = (
        ApprovalService
        .get_pending_approvals(current_role)
    )

    certification = ApprovalCenterCertificationService.get_dashboard(
        metrics=metrics,
        stage_metrics=stage_metrics,
        overdue_approvals=overdue_approvals,
        sla=sla,
        approval_register=approval_register,
        pending=pending,
        current_role=current_role,
    )

    overdue_count = certification["overdue_count"]
    due_today_count = certification["due_today_count"]
    evidence = certification["evidence"]

    render_section(
        "Executive Summary",
        "Approval posture, SLA health, and executive decision readiness.",
        divider=False,
    )

    render_insight_card(
        title="Executive Summary",
        value="Approval Governance",
        description=certification["executive_summary"],
        icon="executive",
        status="warning" if overdue_count else "healthy",
    )

    render_section(
        "Approval Overview",
        "Decision queue status across pending, approved, rejected, and total approval requests.",
        divider=True,
    )

    metric_columns = st.columns(4)

    with metric_columns[0]:
        render_kpi_card(
            "Pending",
            metrics["pending"],
            icon="approval",
            status="watch" if metrics["pending"] else "healthy",
        )

    with metric_columns[1]:
        render_kpi_card(
            "Approved",
            metrics["approved"],
            icon="success",
            status="healthy",
        )

    with metric_columns[2]:
        render_kpi_card(
            "Rejected",
            metrics["rejected"],
            icon="error",
            status="warning" if metrics["rejected"] else "healthy",
        )

    with metric_columns[3]:
        render_kpi_card(
            "Total",
            metrics["total"],
            icon="governance",
            status="info",
        )

    if not is_ceo_view:

        render_section(
            "Workflow Queue",
            "Approval volume by workflow stage.",
            divider=True,
        )

        workflow_cols = st.columns(5)

        with workflow_cols[0]:
            render_metric_card("PMO", stage_metrics["pmo"], icon="governance", status="info")

        with workflow_cols[1]:
            render_metric_card("Finance", stage_metrics["finance"], icon="finance", status="info")

        with workflow_cols[2]:
            render_metric_card("CIO", stage_metrics["cio"], icon="technology", status="info")

        with workflow_cols[3]:
            render_metric_card("CEO", stage_metrics["ceo"], icon="executive", status="info")

        with workflow_cols[4]:
            render_metric_card("Completed", stage_metrics["completed"], icon="success", status="healthy")

        render_section(
            "SLA",
            "Approval aging and service-level posture.",
            divider=True,
        )

        sla_cols = st.columns(3)

        with sla_cols[0]:
            render_metric_card("Overdue", overdue_count, icon="warning", status="critical" if overdue_count else "healthy")

        with sla_cols[1]:
            render_metric_card("Due Today", due_today_count, icon="info", status="watch" if due_today_count else "healthy")

        with sla_cols[2]:
            render_metric_card(
                "SLA %",
                sla.get(
                    "sla_compliance_percent",
                    sla.get("sla_compliance", 100)
                ),
                icon="success",
                status="healthy",
            )

    # --------------------------------------------------
    # PENDING APPROVALS
    # --------------------------------------------------

    render_section(
        "Pending Approvals",
        "Approval requests awaiting action for the current role.",
        divider=True,
    )

    if pending:

        pending_card_columns = st.columns(2)
        for index, row in enumerate(pending[:4]):
            with pending_card_columns[index % 2]:
                render_approval_card(
                    title=row.get("title") or row.get("request_type") or "Approval Request",
                    value=row.get("priority") or row.get("status") or "Pending",
                    description=row.get("description"),
                    status="watch",
                    footer=f"Stage: {row.get('workflow_stage', '-')} | Created: {str(row.get('created_at', '-'))[:19]}",
                )

        pending_df = approval_table(pending)

        st.dataframe(
            pending_df,
            use_container_width=True,
            hide_index=True
        )

        approval_ids = [
            row["id"]
            for row in pending
        ]

        selected_id = st.selectbox(
            "Select Approval",
            approval_ids
        )

        history_rows = ApprovalService.get_approval_history(selected_id)

        if history_rows:
            render_section("Approval Timeline", divider=True)
            render_workflow_timeline(history_rows)

        comments = st.text_area(
            "Comments"
        )

        action_columns = st.columns(2 if is_ceo_view else 3)

        with action_columns[0]:

            if st.button(
                "Approve",
                use_container_width=True
            ):

                ApprovalService.approve_request(
                    approval_id=selected_id,
                    approver_id=1,
                    comments=comments,
                )

                st.success(
                    "Request Approved"
                )

                st.rerun()

        with action_columns[1]:

            if st.button(
                "Reject",
                use_container_width=True
            ):

                ApprovalService.reject_request(
                    approval_id=selected_id,
                    approver_id=1,
                    comments=comments,
                )

                st.warning(
                    "Request Rejected"
                )

                st.rerun()

        if not is_ceo_view:

            with action_columns[2]:

                if st.button(
                    "Escalate",
                    use_container_width=True
                ):

                    ApprovalService.escalate_request(
                        approval_id=selected_id,
                        escalated_to=999,
                        comments=comments,
                    )

                    st.info(
                        "Request Escalated"
                    )

                    st.rerun()

    else:

        render_insight_card(
            title="No Pending Approvals",
            description="There are no executive decisions awaiting approval.",
            status="healthy",
        )

    # --------------------------------------------------
    # ALL APPROVALS
    # --------------------------------------------------

    render_section(
        "Recent Decisions",
        "Approval register and recent governance decisions.",
        divider=True,
    )

    if not is_ceo_view:

        history = approval_register

        if history:

            history_df = approval_table(history)

            st.dataframe(
                history_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            render_insight_card(
                title="No Approval History",
                description="No completed approval decisions are available yet.",
                status="info",
            )
    else:
        render_insight_card(
            title="Executive View",
            description="Recent decision history is available to operational approver roles.",
            status="info",
        )

    render_section(
        "Approval Governance Insight",
        "Approval queue health, SLA compliance, and governance posture.",
        divider=True,
    )

    render_insight_card(
        title="Approval Governance",
        value=f"{metrics['pending']} Pending",
        description=(
            f"{overdue_count} approvals are overdue, {due_today_count} are due today, "
            f"and SLA compliance is {sla.get('sla_compliance_percent', sla.get('sla_compliance', 100))}."
        ),
        status="warning" if overdue_count else "healthy",
    )

    render_section(
        "Evidence",
        "Source data, coverage, AI interpretation, and raw evidence supporting Approval Center.",
        divider=True,
    )

    evidence_tabs = st.tabs([
        "Source Data",
        "Data Coverage",
        "AI Interpretation",
        "Raw Evidence",
    ])

    with evidence_tabs[0]:
        st.dataframe(pd.DataFrame(evidence["source_data"]), use_container_width=True, hide_index=True)
    with evidence_tabs[1]:
        st.dataframe(pd.DataFrame(evidence["data_coverage"]), use_container_width=True, hide_index=True)
    with evidence_tabs[2]:
        st.write(evidence["ai_interpretation"])
    with evidence_tabs[3]:
        st.caption("Approval Metrics")
        st.dataframe(
            pd.DataFrame(evidence["raw_evidence"]["Approval Metrics"]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Workflow Stages")
        st.dataframe(
            pd.DataFrame(evidence["raw_evidence"]["Workflow Stages"]),
            use_container_width=True,
            hide_index=True,
        )


render_page(
    title="Approvals",
    description=(
        "CEO approval queue and governance decisions"
        if is_ceo_view
        else "Executive approval queue and governance decisions"
    ),
    breadcrumbs=["Home", "Governance", "Approvals"],
    content=render_approval_content,
)
