from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.ai_decision_service import AIDecisionService
from services.ai_recommendation_service import AIRecommendationService
from services.ai_workflow_service import AIWorkflowService
from services.digital_twin_quality_service import DigitalTwinQualityService
from services.enterprise_digital_twin_dashboard_service import EnterpriseDigitalTwinDashboardService
from services.execution_runner import ExecutionRunner
from services.workflow_execution_service import WorkflowExecutionService


st.set_page_config(page_title="Enterprise Twin Dashboard", layout="wide")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Enterprise Twin Dashboard is available to Super Admins, Client Admins, CIOs, and Executives.")
        st.stop()


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"${amount:,.2f}"


def _percent(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:.1f}%"


def _format_money_columns(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for column in columns:
        if column in df.columns:
            df[column] = df[column].apply(_money)
    return df


def _show_table(rows: list[dict[str, Any]], empty_message: str, money_columns: list[str] | None = None) -> None:
    if not rows:
        st.info(empty_message)
        return
    df = _format_money_columns(rows, money_columns or [])
    st.dataframe(df, use_container_width=True, hide_index=True)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    dashboard = EnterpriseDigitalTwinDashboardService.get_dashboard(organization_id)
    quality_dashboard = DigitalTwinQualityService.get_dashboard(organization_id)
    recommendation_dashboard = AIRecommendationService.get_all_recommendations(organization_id)
    decision_dashboard = AIDecisionService.get_dashboard(organization_id)
    workflow_dashboard = AIWorkflowService.get_dashboard(organization_id)
    execution_dashboard = WorkflowExecutionService.get_dashboard(organization_id)
    automation_dashboard = ExecutionRunner.get_dashboard(organization_id)
    summary = dashboard["summary"]
    quality_scores = quality_dashboard["scores"]
    health = quality_dashboard["health"]

    st.title("Enterprise Twin Dashboard")
    st.caption("Business capability to cloud resource intelligence for CIO and executive review.")

    st.subheader("Enterprise Twin Summary")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Capabilities", f"{int(summary.get('Total Capabilities') or 0):,}")
    k2.metric("Applications", f"{int(summary.get('Applications') or 0):,}")
    k3.metric("Enterprise Assets", f"{int(summary.get('Enterprise Assets') or 0):,}")
    k4.metric("Attributed Cost", _money(summary.get("Attributed Cost")))

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Cost Coverage", _percent(summary.get("Cost Coverage %")))
    k6.metric("Avg Capability Health", _percent(summary.get("Average Capability Health")))
    k7.metric("Ownership Quality", _percent(summary.get("Ownership Quality")))
    k8.metric("Relationship Quality", _percent(summary.get("Relationship Quality")))

    st.divider()
    st.subheader("Digital Twin Quality")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Digital Twin Health", _percent(health.get("score")))
    q2.metric("Overall Quality", _percent(quality_scores.get("overall_quality")))
    q3.metric("Auto-Fix Candidates", f"{len(quality_dashboard['auto_fix_recommendations']):,}")
    q4.metric("Connector Success", _percent(health.get("connector_success")))

    q5, q6, q7, q8, q9, q10 = st.columns(6)
    q5.metric("Ownership", _percent(quality_scores.get("ownership")))
    q6.metric("Relationship", _percent(quality_scores.get("relationship")))
    q7.metric("Mapping", _percent(quality_scores.get("mapping")))
    q8.metric("Cost", _percent(quality_scores.get("cost")))
    q9.metric("Capability", _percent(quality_scores.get("capability")))
    q10.metric("Freshness", _percent(quality_scores.get("freshness")))

    trend = quality_dashboard["quality_trend"]
    if trend:
        st.line_chart(pd.DataFrame(trend).set_index("Date"))

    tq1, tq2 = st.columns(2)
    with tq1:
        st.subheader("Top 10 Issues")
        _show_table(quality_dashboard["top_issues"], "No digital twin quality issues are currently open.", ["Cost"])

    with tq2:
        st.subheader("Auto-Fix Recommendations")
        _show_table(
            quality_dashboard["auto_fix_recommendations"],
            "No automatic remediation candidates are currently available.",
        )

    st.subheader("Relationship Confidence")
    _show_table(
        quality_dashboard["relationship_confidence"],
        "No relationship confidence records are available yet.",
    )

    st.divider()
    st.subheader("AI Recommendations")
    recommendation_summary = recommendation_dashboard["summary"]
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Total Recommendations", f"{int(recommendation_summary.get('total_recommendations') or 0):,}")
    r2.metric("Critical", f"{int(recommendation_summary.get('critical') or 0):,}")
    r3.metric("High", f"{int(recommendation_summary.get('high') or 0):,}")
    r4.metric("Medium", f"{int(recommendation_summary.get('medium') or 0):,}")

    r5, r6, r7 = st.columns(3)
    r5.metric("Estimated Savings", _money(recommendation_summary.get("estimated_savings")))
    r6.metric("Risk Reduction", _percent(recommendation_summary.get("estimated_risk_reduction")))
    r7.metric("Avg Confidence", _percent(recommendation_summary.get("average_confidence")))

    rec_left, rec_right = st.columns(2)
    with rec_left:
        st.subheader("Priority Distribution")
        _show_table(
            recommendation_summary["priority_distribution"],
            "No recommendation priorities are available yet.",
        )

        st.subheader("Recommendation Categories")
        _show_table(
            recommendation_summary["category_distribution"],
            "No recommendation categories are available yet.",
        )

    with rec_right:
        st.subheader("Owner Workload")
        _show_table(
            recommendation_summary["owner_workload"],
            "No recommendation owners are available yet.",
        )

        st.subheader("Persistence")
        persistence = recommendation_dashboard.get("persistence", {})
        st.caption(f"{persistence.get('status')} | rows: {persistence.get('rows', 0)}")

    st.subheader("Priority Actions")
    priority_rows = [
        {
            "ID": row.get("recommendation_id"),
            "Priority": row.get("priority"),
            "Category": row.get("category"),
            "Title": row.get("title"),
            "Owner": row.get("owner"),
            "Score": row.get("overall_score"),
            "Confidence": row.get("confidence"),
            "Savings": row.get("estimated_savings"),
            "Status": row.get("status"),
        }
        for row in recommendation_dashboard["priority_actions"]
    ]
    _show_table(priority_rows, "No AI recommendations are currently open.", ["Savings"])

    st.divider()
    st.subheader("AI Decisions")
    decision_summary = decision_dashboard["summary"]
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Total Decisions", f"{int(decision_summary.get('total_decisions') or 0):,}")
    d2.metric("Auto Approved", f"{int(decision_summary.get('auto_approved') or 0):,}")
    d3.metric("Pending Approval", f"{int(decision_summary.get('pending_approval') or 0):,}")
    d4.metric("Critical", f"{int(decision_summary.get('critical') or 0):,}")

    d5, d6, d7 = st.columns(3)
    d5.metric("Automated", f"{int(decision_summary.get('automated') or 0):,}")
    d6.metric("Manual", f"{int(decision_summary.get('manual') or 0):,}")
    d7.metric("Avg Confidence", _percent(decision_summary.get("average_confidence")))

    dec_left, dec_right = st.columns(2)
    with dec_left:
        st.subheader("Decision Distribution")
        _show_table(decision_summary["decision_distribution"], "No decision distribution is available yet.")

        st.subheader("Automation Readiness")
        _show_table(decision_summary["automation_readiness"], "No automation readiness data is available yet.")

        st.subheader("Business Impact")
        _show_table(decision_summary["business_impact"], "No business impact data is available yet.")

    with dec_right:
        st.subheader("Risk Reduction")
        _show_table(decision_summary["risk_reduction"], "No risk reduction data is available yet.")

        st.subheader("Decision Timeline")
        _show_table(decision_summary["decision_timeline"], "No decision timeline is available yet.")

        st.subheader("Owner Workload")
        _show_table(decision_summary["owner_workload"], "No decision owner workload is available yet.")

    st.subheader("Decision Queue")
    decision_rows = [
        {
            "ID": row.get("decision_id"),
            "Recommendation": row.get("recommendation_id"),
            "Decision": row.get("decision"),
            "Priority": row.get("priority"),
            "Automation": row.get("automation"),
            "Approval": row.get("approval_required"),
            "Owner": row.get("owner"),
            "Confidence": row.get("confidence"),
            "Score": row.get("overall_score"),
            "Status": row.get("status"),
        }
        for row in decision_dashboard["decisions"][:15]
    ]
    _show_table(decision_rows, "No AI decisions are currently available.")

    st.caption(
        f"Decision persistence: {decision_dashboard.get('persistence', {}).get('status')} | "
        f"rows: {decision_dashboard.get('persistence', {}).get('rows', 0)}"
    )

    st.divider()
    st.subheader("AI Workflow Actions")
    workflow_summary = workflow_dashboard["summary"]
    w1, w2, w3, w4 = st.columns(4)
    w1.metric("Total Actions", f"{int(workflow_summary.get('total_actions') or 0):,}")
    w2.metric("Pending Approval", f"{int(workflow_summary.get('pending_approval') or 0):,}")
    w3.metric("Approved", f"{int(workflow_summary.get('approved') or 0):,}")
    w4.metric("Executed", f"{int(workflow_summary.get('executed') or 0):,}")

    w5, w6, w7 = st.columns(3)
    w5.metric("Automation Eligible", f"{int(workflow_summary.get('automation_eligible') or 0):,}")
    w6.metric("Expected Savings", _money(workflow_summary.get("expected_savings")))
    w7.metric("Risk Reduction", _percent(workflow_summary.get("expected_risk_reduction")))

    wf_left, wf_right = st.columns(2)
    with wf_left:
        st.subheader("Pending Approval Queue")
        pending_workflow_rows = [
            {
                "Action": row.get("action_id"),
                "Decision": row.get("decision_id"),
                "Type": row.get("action_type"),
                "Title": row.get("title"),
                "Owner": row.get("owner"),
                "Risk": row.get("risk_level"),
                "Confidence": row.get("confidence"),
                "Savings": row.get("expected_savings"),
            }
            for row in workflow_dashboard["pending_approval_queue"][:10]
        ]
        _show_table(pending_workflow_rows, "No workflow actions are pending approval.", ["Savings"])

    with wf_right:
        st.subheader("Auto-Remediation Candidates")
        automation_rows = [
            {
                "Action": row.get("action_id"),
                "Type": row.get("action_type"),
                "Title": row.get("title"),
                "Owner": row.get("owner"),
                "Approval": row.get("approval_status"),
                "Execution": row.get("execution_status"),
                "Confidence": row.get("confidence"),
            }
            for row in workflow_dashboard["auto_remediation_candidates"][:10]
        ]
        _show_table(automation_rows, "No auto-remediation candidates are currently available.")

    st.subheader("Workflow Audit Trail")
    _show_table(workflow_dashboard["audit_trail"][:15], "No workflow audit events are available yet.")

    st.divider()
    st.subheader("AI Execution Lifecycle")
    execution_summary = execution_dashboard["summary"]
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Pending Execution", f"{int(execution_summary.get('pending_execution') or 0):,}")
    e2.metric("Assigned", f"{int(execution_summary.get('assigned') or 0):,}")
    e3.metric("In Progress", f"{int(execution_summary.get('in_progress') or 0):,}")
    e4.metric("Waiting Validation", f"{int(execution_summary.get('waiting_validation') or 0):,}")

    e5, e6, e7, e8 = st.columns(4)
    e5.metric("Completed Today", f"{int(execution_summary.get('completed_today') or 0):,}")
    e6.metric("Automation", _percent(execution_summary.get("automation_percent")))
    e7.metric("Realized Savings", _money(execution_summary.get("realized_savings")))
    e8.metric("Risk Reduction", _percent(execution_summary.get("risk_reduction")))

    execution_rows = [
        {
            "Action": row.get("action_id"),
            "Status": row.get("execution_status"),
            "Title": row.get("title"),
            "Team": row.get("assigned_team"),
            "Readiness": row.get("automation_readiness"),
            "Progress": f"{int(row.get('execution_progress') or 0)}%",
            "Expected": row.get("expected_savings"),
            "Actual": row.get("actual_savings"),
        }
        for row in execution_dashboard["actions"][:10]
    ]
    _show_table(execution_rows, "No execution lifecycle actions are available yet.", ["Expected", "Actual"])

    st.divider()
    st.subheader("Safe Automation Runner")
    automation_summary = automation_dashboard["summary"]
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Simulation Queue", f"{int(automation_summary.get('simulation_queue') or 0):,}")
    a2.metric("Ready for Execution", f"{int(automation_summary.get('ready_for_execution') or 0):,}")
    a3.metric("Running", f"{int(automation_summary.get('running_executions') or 0):,}")
    a4.metric("Failed", f"{int(automation_summary.get('failed_executions') or 0):,}")

    a5, a6, a7, a8 = st.columns(4)
    a5.metric("Projected Savings", _money(automation_summary.get("projected_savings")))
    a6.metric("Verified Savings", _money(automation_summary.get("verified_savings")))
    a7.metric("Success Rate", _percent(automation_summary.get("success_rate")))
    a8.metric("Policy Compliance", _percent(automation_summary.get("policy_compliance")))

    automation_rows = [
        {
            "Workflow": row.get("workflow_id"),
            "Status": row.get("status"),
            "Provider": row.get("provider"),
            "Projected": row.get("projected_savings"),
            "Actual": row.get("actual_savings"),
            "Variance": row.get("savings_variance_percent"),
            "Confidence": row.get("confidence"),
        }
        for row in automation_dashboard["logs"][:10]
    ]
    _show_table(automation_rows, "No safe automation execution logs are available yet.", ["Projected", "Actual"])

    st.divider()
    st.subheader("Executive Narrative")
    st.info(dashboard["executive_narrative"])

    paths = dashboard["impact_paths"]
    if paths:
        st.subheader("Impact Path")
        st.code(paths[0], language="text")

    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("Capability Twin")
        _show_table(
            dashboard["capability_twin"],
            "No capability twin data is available yet.",
            ["Cost"],
        )

        st.subheader("Application Twin")
        _show_table(
            dashboard["application_twin"],
            "No application twin data is available yet.",
            ["Cost"],
        )

    with right:
        st.subheader("Asset Twin")
        _show_table(
            dashboard["asset_twin"],
            "No asset twin data is available yet.",
            ["Cost"],
        )

    st.divider()
    st.subheader("Risk & Governance Gaps")
    gaps = dashboard["risk_governance_gaps"]
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Missing Owners")
        _show_table(gaps["missing_owners"], "No missing owner gaps are currently open.")

        st.subheader("Low-Confidence Correlations")
        _show_table(gaps["low_confidence_correlations"], "No low-confidence correlations are currently open.")

    with g2:
        st.subheader("Unattributed Cost")
        _show_table(gaps["unattributed_cost"], "No unattributed cost is currently open.", ["cost"])

        st.subheader("Unmapped Assets")
        _show_table(gaps["unmapped_assets"], "No unmapped asset gaps are currently open.")


if __name__ == "__main__":
    main()
