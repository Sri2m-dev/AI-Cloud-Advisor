from __future__ import annotations

# ruff: noqa: E402
import os
import sys
from dataclasses import asdict

import pandas as pd
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.sidebar_navigation import render_sidebar_navigation
from decision_intelligence import DecisionIntelligenceService
from enterprise_intelligence import enterprise_intelligence_service
from services.demo_tenant_service import (
    demo_mode_enabled,
    is_demo_tenant,
    load_demo_tenant,
)
from services.enterprise_spend_composition import authenticated_tenant_context
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

ROLES = ["super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"]
configure_page(page_title="Decision Intelligence | Nexora", page_icon="DI")
init_session()
require_role(ROLES)
role = str(st.session_state.get("role") or "")
render_sidebar_navigation(role)
authenticated = authenticated_tenant_context(st.session_state)
organization_id = str(st.session_state.get("organization_id") or "")

if demo_mode_enabled() and is_demo_tenant(organization_id):
    payload = load_demo_tenant(organization_id)
    decisions = payload.get("decisions") or []
    journeys = {item["decision_id"]: item for item in payload.get("journeys") or []}

    st.markdown(
        """
        <section class="nexora-executive-hero">
          <p class="nexora-eyebrow">EXECUTIVE DECISION CENTER</p>
          <h2>Three decisions can materially change enterprise outcomes.</h2>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Prioritized by impact, authority, confidence, and governed evidence.")
    st.warning(
        "SYNTHETIC DEMONSTRATION DATA — isolated from customer and production records."
    )
    summary = st.columns(4)
    summary[0].metric("Decisions requiring action", len(decisions))
    summary[1].metric(
        "Known financial impact",
        f"${sum(item.get('financial_impact') or 0 for item in decisions) / 1_000_000:.1f}M",
    )
    summary[2].metric(
        "Average confidence",
        f"{sum(item['confidence'] for item in decisions) / len(decisions):.0f}%",
    )
    summary[3].metric(
        "Average evidence coverage",
        f"{sum(item['evidence_coverage'] for item in decisions) / len(decisions):.0f}%",
    )

    st.subheader("Decisions requiring leadership attention")
    for decision in decisions:
        journey = journeys[decision["id"]]
        with st.container(border=True):
            st.caption(f"{decision['id']} · {decision['status'].replace('_', ' ').title()}")
            st.markdown(f"## {decision['title']}")
            impact = decision.get("financial_impact")
            columns = st.columns(4)
            columns[0].metric("Business service", decision["business_service"])
            columns[1].metric(
                "Financial impact", f"${impact / 1_000_000:.1f}M" if impact else "UNKNOWN"
            )
            columns[2].metric("Confidence", f"{decision['confidence']}%")
            columns[3].metric("Evidence coverage", f"{decision['evidence_coverage']}%")
            st.markdown(f"**Why it matters:** {journey['impact']}")
            st.markdown(f"**Recommended decision:** {journey['recommendation']}")
            st.info(f"Accountable next step — {journey['next_step']}")
            path = journey.get("twin_path") or []
            if path:
                st.caption("Decision context · " + " → ".join(item["entity"] for item in path))
            actions = st.columns(3)
            with actions[0]:
                st.page_link("pages/business_services.py", label="View Impact")
            with actions[1]:
                st.page_link(
                    "pages/twin_explorer.py",
                    label="Trace Evidence",
                    help=(
                        "Trace business, application, technology, cost, risk, "
                        "and decision context."
                    ),
                )
            with actions[2]:
                st.page_link("pages/approval_center.py", label="Review Approval")
            with st.expander("Show evidence and assumptions"):
                st.write(journey["evidence"])
                st.write(journey["change"])
    st.stop()

intelligence = enterprise_intelligence_service(
    authenticated.fabric_context, role=authenticated.role
)
service = DecisionIntelligenceService(
    authenticated.fabric_context, role=authenticated.role, intelligence=intelligence
)
findings = service.findings()

st.title("Decision Intelligence")
st.caption("Governed findings and recommendation proposals · human authority remains required")
metrics = st.columns(4)
metrics[0].metric("Open Findings", len(findings))
metrics[1].metric("High Priority", sum(item.severity == "high" for item in findings))
metrics[2].metric(
    "Potential Financial Impact", f"${sum(item.financial_exposure for item in findings):,.2f}"
)
metrics[3].metric("Verified Realized Value", "$0.00")
tabs = st.tabs(["Findings", "Recommendations", "Decisions", "Evidence", "Policy", "Outcomes"])
with tabs[0]:
    if findings:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Finding": item.title,
                        "Subject": item.subject_canonical_id,
                        "Type": item.finding_type.value,
                        "Severity": item.severity,
                        "Priority": item.priority.score,
                        "Financial exposure": item.financial_exposure,
                        "Confidence": item.confidence,
                        "Freshness": item.freshness,
                    }
                    for item in findings
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
        selected = st.selectbox("Finding detail", [item.finding_id for item in findings])
        finding = next(item for item in findings if item.finding_id == selected)
        st.json(asdict(finding))
        st.subheader("Recommendation proposal")
        st.json(asdict(service.proposal(finding)))
    else:
        st.info(
            "No deterministic tenant-scoped findings are currently supported by governed evidence."
        )
with tabs[1]:
    st.info(
        "Recommendation lifecycle is governed by WP-011. Proposals require an "
        "approved WP-010 evidence package."
    )
with tabs[2]:
    st.info("Human Decisions are created and reconstructed only through WP-011.")
with tabs[3]:
    st.info("Immutable approved evidence packages are governed by WP-010.")
with tabs[4]:
    st.info("Policy Preview is simulation only. It is not authorization.")
with tabs[5]:
    st.info("Verified realized value is authoritative only after WP-013 outcome verification.")
