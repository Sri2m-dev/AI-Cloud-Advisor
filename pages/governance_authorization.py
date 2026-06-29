from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from repositories.governance_repository import GovernanceRepository
from services.governance_authorization_service import GovernanceAuthorizationService


st.set_page_config(page_title="Governance & Authorization", layout="wide")

EXAMPLES = [
    "Is this migration ready for execution?",
    "Build implementation plan for Oracle migration.",
    "Authorize Azure spend reduction workflow.",
    "Review CAB readiness for SaaS license optimization.",
]


def _show_table(rows: list[dict[str, Any]], empty: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    organization_id = get_current_organization_id()

    st.title("Governance & Authorization")
    st.caption("Policy validation, approvals, CAB readiness, digital sign-off, and execution lock state. No execution is performed.")

    left, right = st.columns([1.1, 0.9])
    with left:
        goal = st.text_area("Workflow or Goal", value=st.session_state.get("governance_goal", EXAMPLES[1]), height=100)
        cols = st.columns(2)
        for index, example in enumerate(EXAMPLES):
            if cols[index % 2].button(example[:42], key=f"gov_example_{index}", use_container_width=True):
                st.session_state["governance_goal"] = example
                st.rerun()
        evaluate = st.button("Evaluate Authorization", type="primary", use_container_width=True)
    with right:
        st.subheader("Governance Gates")
        st.write("- Policy validation")
        st.write("- Risk, security, compliance, finance, business, CAB, and executive review")
        st.write("- Digital sign-off evidence")
        st.write("- Execution remains locked until all gates pass")

    if evaluate:
        st.session_state["last_governance_review"] = GovernanceAuthorizationService.evaluate_goal(
            goal,
            organization_id=organization_id,
            created_by=user.get("email") or "governance_authorization",
            persist=True,
        )

    review = st.session_state.get("last_governance_review")
    existing = GovernanceRepository.list_governance_reviews(organization_id)
    pending = GovernanceRepository.list_approval_requests(organization_id)

    st.divider()
    if review:
        cab = review["cab_readiness"]
        lock = review["execution_lock"]
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Governance Score", f"{review['governance_score']:.1f}%")
        k2.metric("Execution Status", review["execution_status"])
        k3.metric("CAB Readiness", f"{cab['Score']:.1f}%")
        k4.metric("Required Approvals", len(review["required_approvals"]))
        k5.metric("Pending", len(review["pending_approvals"]))

        if review["execution_status"] == "AUTHORIZED":
            st.success(review["executive_summary"])
        else:
            st.warning(review["executive_summary"])
        st.write(f"Execution Lock: **{lock['State']}**")
        st.write(lock["Reason"])

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Required Approvals")
            _show_table(review["required_approvals"], "No approval requests were generated.")
            st.subheader("Policy Violations")
            _show_table(review["policy_violations"], "No policy violations were detected.")
        with c2:
            st.subheader("CAB Checklist")
            _show_table(cab["Checklist"], "No CAB checklist is available.")
            if cab["Missing Items"]:
                st.error("Missing: " + ", ".join(cab["Missing Items"]))

        st.subheader("Policy Validation")
        _show_table(review["policy_validation"], "No policy validation rows are available.")

        st.subheader("Risk Matrix")
        risk_df = pd.DataFrame(review["risk_matrix"])
        if not risk_df.empty:
            fig = px.bar(risk_df, x="Risk", y=[1] * len(risk_df), color="Level", text="Mitigation")
            fig.update_layout(showlegend=True, yaxis_visible=False)
            st.plotly_chart(fig, use_container_width=True)
        _show_table(review["risk_matrix"], "No risk matrix is available.")

        st.subheader("Executive Authorization")
        _show_table([review["executive_authorization"]], "No executive authorization state is available.")

        st.subheader("Audit Timeline")
        _show_table(review["audit_timeline"], "No audit timeline is available.")
    else:
        st.subheader("Recent Governance Reviews")
        _show_table(existing, "No governance reviews are available.")
        st.subheader("Pending Approvals")
        _show_table(pending, "No pending approvals are available.")


if __name__ == "__main__":
    main()
