from __future__ import annotations

# ruff: noqa: E402, I001

import os
import sys

import pandas as pd
import streamlit as st

from shared.session import init_session
from shared.styles import configure_page
from components.sidebar_navigation import render_sidebar_navigation

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

configure_page(
    page_title="Audit Timeline | Nexora",
    page_icon=":spiral_calendar:",
)

init_session()

from shared.auth import require_role

require_role([
    "executive",
    "technical",
    "finance",
    "auditor",
    "operations",
    "super_admin",
])

role = st.session_state.get("role", "Unknown")
render_sidebar_navigation(role)

from components.layout import render_page_header, render_section
from components.tables import data_table
from services.audit_timeline_service import (
    get_approvals_assignments_timeline,
    get_governance_changes_timeline,
    get_workflow_transitions_timeline,
    get_ai_recommendation_actions_timeline,
    get_kpi_changes_timeline,
    get_alerts_reports_timeline,
)

org_id = st.session_state.get("organization_id")
current_role = st.session_state.get("role", "").lower()
is_ceo_view = current_role == "executive"


def _extract_rows(response):
    if not response or not response.get("success"):
        return []
    return response.get("data") or []


def _pick(row, *keys, default=""):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _to_business_event(row, category, default_event):
    return {
        "Event": _pick(
            row,
            "event",
            "action",
            "event_type",
            "title",
            "description",
            default=default_event,
        ),
        "Category": category,
        "Impact": _pick(
            row,
            "impact",
            "severity",
            "priority",
            default="Medium",
        ),
        "Status": _pick(
            row,
            "status",
            "state",
            default="Recorded",
        ),
        "Date": _pick(
            row,
            "created_at",
            "recorded_at",
            "updated_at",
            "timestamp",
            default="",
        ),
    }


if is_ceo_view:

    render_page_header(
        "Governance Timeline",
        "Major governance, approval, risk and reporting events"
    )

    timeline_rows = []

    approval_rows = _extract_rows(
        get_approvals_assignments_timeline(org_id)
    )
    governance_rows = _extract_rows(
        get_governance_changes_timeline(org_id)
    )
    workflow_rows = _extract_rows(
        get_workflow_transitions_timeline(org_id)
    )
    ai_rows = _extract_rows(
        get_ai_recommendation_actions_timeline(org_id)
    )
    kpi_rows = _extract_rows(
        get_kpi_changes_timeline(org_id)
    )
    alert_rows = _extract_rows(
        get_alerts_reports_timeline(org_id)
    )

    for row in approval_rows:
        timeline_rows.append(
            _to_business_event(
                row,
                "Approval",
                "Approval activity recorded",
            )
        )

    for row in governance_rows:
        timeline_rows.append(
            _to_business_event(
                row,
                "Governance",
                "Governance change recorded",
            )
        )

    for row in workflow_rows:
        timeline_rows.append(
            _to_business_event(
                row,
                "Workflow",
                "Workflow transition recorded",
            )
        )

    for row in ai_rows:
        timeline_rows.append(
            _to_business_event(
                row,
                "Optimization",
                "AI recommendation action recorded",
            )
        )

    for row in kpi_rows:
        timeline_rows.append(
            _to_business_event(
                row,
                "Performance",
                "KPI change recorded",
            )
        )

    for row in alert_rows:
        timeline_rows.append(
            _to_business_event(
                row,
                "Risk",
                "Alert or report event recorded",
            )
        )

    render_section("Major Governance Events")

    if timeline_rows:
        timeline_df = pd.DataFrame(timeline_rows)

        if "Date" in timeline_df.columns:
            timeline_df["Date"] = timeline_df["Date"].astype(str).str[:19]
            timeline_df = timeline_df.sort_values(
                "Date",
                ascending=False,
            )

        st.dataframe(
            timeline_df[
                [
                    "Event",
                    "Category",
                    "Impact",
                    "Status",
                    "Date",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No governance events available yet.")

else:

    render_page_header(
        "Audit Timeline",
        "Track approvals, assignments, governance, and AI actions",
    )

    render_section("Approvals & Assignments")
    approvals_assignments_resp = get_approvals_assignments_timeline(org_id)
    if not approvals_assignments_resp["success"]:
        st.warning(f"Error: {approvals_assignments_resp.get('errors', 'Unknown error')}")
    data_table(approvals_assignments_resp["data"])

    render_section("Governance Changes")
    governance_changes_resp = get_governance_changes_timeline(org_id)
    if not governance_changes_resp["success"]:
        st.warning(f"Error: {governance_changes_resp.get('errors', 'Unknown error')}")
    data_table(governance_changes_resp["data"])

    render_section("Workflow Transitions")
    workflow_transitions_resp = get_workflow_transitions_timeline(org_id)
    if not workflow_transitions_resp["success"]:
        st.warning(f"Error: {workflow_transitions_resp.get('errors', 'Unknown error')}")
    data_table(workflow_transitions_resp["data"])

    render_section("AI Recommendation Actions")
    ai_actions_resp = get_ai_recommendation_actions_timeline(org_id)
    if not ai_actions_resp["success"]:
        st.warning(f"Error: {ai_actions_resp.get('errors', 'Unknown error')}")
    data_table(ai_actions_resp["data"])

    render_section("KPI Changes")
    kpi_changes_resp = get_kpi_changes_timeline(org_id)
    if not kpi_changes_resp["success"]:
        st.warning(f"Error: {kpi_changes_resp.get('errors', 'Unknown error')}")
    data_table(kpi_changes_resp["data"])

    render_section("Alerts & Reports")
    alerts_reports_resp = get_alerts_reports_timeline(org_id)
    if not alerts_reports_resp["success"]:
        st.warning(f"Error: {alerts_reports_resp.get('errors', 'Unknown error')}")
    data_table(alerts_reports_resp["data"])
