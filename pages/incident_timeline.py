from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.enterprise_incident_timeline import EnterpriseIncidentTimeline


st.set_page_config(page_title="Incident Timeline", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical"}
CATEGORIES = ["All", "Cloud", "Monitoring", "Security", "DevOps", "ITSM", "Governance", "AI"]


def _table(rows: list[dict[str, Any]] | dict[str, Any], empty: str) -> None:
    if isinstance(rows, dict):
        rows = [{"Metric": key, "Value": value} for key, value in rows.items()]
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


def _metric_money(value: Any) -> str:
    return f"${float(value or 0):,.0f}"


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    if role not in ALLOWED_ROLES:
        st.error("Incident Timeline is available to enterprise technology roles.")
        st.stop()

    st.title("Enterprise Incident Timeline")
    st.caption("Unified incident reconstruction across DevOps, observability, ITSM, governance, AI, and recovery events.")

    controls = st.columns([1, 1, 2])
    incident_id = controls[0].text_input("Incident", "INC-CHECKOUT-2026-09")
    category = controls[1].selectbox("Category", CATEGORIES)
    search = controls[2].text_input("Search", placeholder="Incident, application, service, repository, change, user, CI")

    dashboard = EnterpriseIncidentTimeline.get_dashboard(
        get_current_organization_id(),
        incident_id=incident_id,
        search=search or None,
        category=category,
    )
    incident = dashboard["incident"]
    kpis = dashboard["kpis"]

    cols = st.columns(7)
    cols[0].metric("Severity", incident["severity"])
    cols[1].metric("Status", incident["status"])
    cols[2].metric("Events", kpis["Timeline Events"])
    cols[3].metric("Sources", kpis["Correlated Sources"])
    cols[4].metric("MTTR", f"{kpis['MTTR Minutes']} min")
    cols[5].metric("Revenue Impact", _metric_money(kpis["Revenue Impact"]))
    cols[6].metric("Confidence", f"{kpis['Confidence']}%")

    st.info(dashboard["executive_narrative"])

    summary_tab, timeline_tab, cause_tab, impact_tab, replay_tab, bus_tab = st.tabs(
        ["Summary", "Timeline", "Root Cause", "Impact", "Replay", "Event Bus"],
    )

    with summary_tab:
        left, right = st.columns([1, 1])
        with left:
            st.subheader("Incident Summary")
            _table(dashboard["incident_summary"], "No incident summary is available.")
        with right:
            st.subheader("Executive Timeline")
            _table(dashboard["executive_timeline"], "No executive timeline is available.")
        st.subheader("AI Recommendation")
        rec_rows = [
            {"Horizon": horizon, "Action": action}
            for horizon, actions in dashboard["recommendation"].items()
            for action in actions
        ]
        _table(rec_rows, "No recommendations are available.")

    with timeline_tab:
        st.subheader("Unified Timeline")
        _table(dashboard["timeline"], "No timeline events match the selected filters.")
        st.subheader("Timeline Graph")
        _table(dashboard["timeline_graph"], "No timeline graph is available.")
        st.subheader("Timeline Search Index")
        _table(dashboard["search_index"], "No search index is available.")

    with cause_tab:
        root = dashboard["root_cause"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Root Cause", root["summary"])
        c2.metric("Confidence", f"{root['confidence']}%")
        c3.metric("First Detection", f"{root['detected_first_by']['source']} {root['detected_first_by']['time']}")
        st.subheader("Contributing Factors")
        _table(root["contributing_factors"], "No contributing factors are available.")
        st.subheader("Evidence")
        _table(root["evidence"], "No root cause evidence is available.")

    with impact_tab:
        left, right = st.columns([1, 1])
        with left:
            st.subheader("Business Impact")
            _table(dashboard["business_impact"], "No business impact is available.")
        with right:
            st.subheader("Technical Impact")
            _table(dashboard["technical_impact"], "No technical impact is available.")
        st.subheader("Recovery Timeline")
        _table(dashboard["recovery_timeline"], "No recovery timeline is available.")

    with replay_tab:
        st.subheader("Executive Replay")
        frames = dashboard["executive_replay"]
        frame_count = len(frames)
        selected = st.slider("Replay Frame", 1, max(frame_count, 1), 1)
        frame = frames[selected - 1] if frames else {}
        st.metric("Replay Time", frame.get("time", "-"))
        st.write(f"**{frame.get('headline', 'No frame')}**")
        st.write(frame.get("narration", ""))
        _table(frames, "No replay frames are available.")

    with bus_tab:
        st.subheader("Enterprise Event Bus")
        _table(dashboard["event_bus"], "No event bus records are available.")
        st.subheader("Learning Feedback")
        _table(dashboard["learning_feedback"], "No learning feedback is available.")
        st.subheader("Gold Certification")
        _table(dashboard["certification"], "No certification metadata is available.")


if __name__ == "__main__":
    main()
