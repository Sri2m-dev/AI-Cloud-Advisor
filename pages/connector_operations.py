from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.business_capability_service import BusinessCapabilityService
from services.connector_operations_service import ConnectorOperationsService
from services.enterprise_cost_attribution_service import EnterpriseCostAttributionService
from services.enterprise_correlation_service import EnterpriseCorrelationService
from services.enterprise_ownership_service import EnterpriseOwnershipService
from services.enterprise_relationship_intelligence_service import EnterpriseRelationshipIntelligenceService


st.set_page_config(page_title="Connector Operations", layout="wide")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio"}


def _require_connector_operations_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Connector Operations is available to Super Admins, Client Admins, and CIO read-only users.")
        st.stop()


def _status_badge(status: str) -> str:
    if status == "Connected":
        return "Connected"
    if status == "Failed":
        return "Failed"
    return "Not Configured"


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_connector_operations_access(role)

    organization_id = get_current_organization_id()
    is_read_only = role == "cio"

    st.title("Connector Operations")
    st.caption("Operational command center for connector health, sync activity, discovery coverage, and recommended actions.")
    if is_read_only:
        st.info("Read-only view. Connector configuration changes are restricted to Client Admins and Super Admins.")

    kpis = ConnectorOperationsService.get_kpis(organization_id)
    identity_dashboard = ConnectorOperationsService.get_asset_identity_dashboard(organization_id)
    identity_metrics = identity_dashboard["metrics"]
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Connectors", kpis["Total Connectors"])
    c2.metric("Connected", kpis["Connected"])
    c3.metric("Failed", kpis["Failed"])
    c4.metric("Not Configured", kpis["Not Configured"])
    c5.metric("Assets", f"{kpis['Assets Discovered']:,}")
    c6.metric("Avg Health", f"{kpis['Average Health']}%")

    st.divider()
    st.subheader("Organization Connector Health")
    rows = ConnectorOperationsService.get_connector_operations(organization_id)
    if not rows:
        st.info("No connector operations data is available yet.")
        return

    df = pd.DataFrame(rows)
    df["Status"] = df["Status"].apply(_status_badge)
    st.dataframe(
        df[
            [
                "Connector",
                "Status",
                "Last Sync",
                "Objects Synced",
                "Costs Synced",
                "Resources Synced",
                "Assets Discovered",
                "Health Score",
                "Recommended Action",
                "Last Error",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Connectors Requiring Attention")
        attention = [
            row
            for row in rows
            if row["Status"] != "Connected" or int(row["Health Score"] or 0) < 80
        ]
        if attention:
            st.dataframe(
                pd.DataFrame(attention)[["Connector", "Status", "Health Score", "Recommended Action", "Last Error"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("All configured connectors are healthy.")

    with right:
        st.subheader("Executive Narrative")
        st.info(ConnectorOperationsService.get_executive_narrative(organization_id))

    st.divider()
    st.subheader("Asset Identity Coverage")
    i1, i2, i3 = st.columns(3)
    i1.metric("Identified Assets", f"{int(identity_metrics.get('identified_assets') or 0):,}")
    i2.metric("Discovered Assets", f"{int(identity_metrics.get('discovered_assets') or 0):,}")
    i3.metric("Identity Coverage", f"{float(identity_metrics.get('coverage_percent') or 0):.1f}%")

    provider_rows = identity_dashboard["coverage_by_provider"]
    latest_asset_ids = identity_dashboard["latest_asset_ids"]
    provider_col, asset_col = st.columns([1, 2])
    with provider_col:
        st.subheader("Coverage by Provider")
        if provider_rows:
            st.dataframe(
                pd.DataFrame(provider_rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No provider-level identity coverage is available yet.")

    with asset_col:
        st.subheader("Latest Enterprise Asset IDs")
        if latest_asset_ids:
            st.dataframe(
                pd.DataFrame(latest_asset_ids),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No enterprise asset IDs have been created yet.")

    st.divider()
    st.subheader("Enterprise Relationship Intelligence")
    relationship_dashboard = EnterpriseRelationshipIntelligenceService.get_dashboard(organization_id)
    relationship_coverage = relationship_dashboard["coverage"]
    relationship_quality = relationship_dashboard["quality"]

    r1, r2, r3, r4, r5, r6 = st.columns(6)
    r1.metric("Relationship Coverage", f"{float(relationship_coverage.get('coverage_percent') or 0):.1f}%")
    r2.metric("Orphan Assets", f"{len(relationship_dashboard['orphan_assets']):,}")
    r3.metric("Assets without Owner", f"{len(relationship_dashboard['assets_without_owners']):,}")
    r4.metric(
        "Without App Mapping",
        f"{len(relationship_dashboard['assets_without_application_mapping']):,}",
    )
    r5.metric("Without Cost Mapping", f"{len(relationship_dashboard['assets_without_cost_mapping']):,}")
    r6.metric("Quality Score", f"{float(relationship_quality.get('score') or 0):.1f}%")

    remediation_rows = relationship_dashboard["remediation"]
    st.subheader("Remediation")
    if remediation_rows:
        st.dataframe(
            pd.DataFrame(remediation_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("Relationship quality gate is clear for the current asset set.")

    st.divider()
    st.subheader("Enterprise Correlation")
    correlation_dashboard = EnterpriseCorrelationService.get_dashboard(organization_id)
    correlation_summary = correlation_dashboard["summary"]
    top_applications = correlation_dashboard["top_applications"]
    top_business_services = correlation_dashboard["top_business_services"]
    low_confidence = correlation_dashboard["low_confidence"]

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Assets Correlated", f"{int(correlation_summary.get('correlated') or 0):,}")
    e2.metric("Correlation", f"{float(correlation_summary.get('correlation_percent') or 0):.1f}%")
    e3.metric("Uncorrelated Assets", f"{int(correlation_summary.get('uncorrelated') or 0):,}")
    e4.metric("Low Confidence", f"{len(low_confidence):,}")

    app_dist_col, service_dist_col = st.columns([1, 1])
    with app_dist_col:
        st.subheader("Top Applications")
        if top_applications:
            st.dataframe(
                pd.DataFrame(top_applications),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No correlated application distribution is available yet.")

    with service_dist_col:
        st.subheader("Top Business Services")
        if top_business_services:
            st.dataframe(
                pd.DataFrame(top_business_services),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No correlated business service distribution is available yet.")

    if low_confidence:
        st.subheader("Low Confidence Correlations")
        st.dataframe(
            pd.DataFrame(low_confidence)[
                [
                    "enterprise_asset_id",
                    "application",
                    "business_service",
                    "confidence",
                    "correlation_source",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.subheader("Enterprise Ownership Intelligence")
    ownership_dashboard = EnterpriseOwnershipService.get_dashboard(organization_id)
    ownership_summary = ownership_dashboard["summary"]
    ownership_rows = ownership_summary.get("ownership", [])
    owned_assets = int(ownership_summary.get("owned_assets") or 0)
    total_assets = int(ownership_summary.get("assets_processed") or 0)

    o1, o2, o3, o4, o5 = st.columns(5)
    o1.metric("Total Assets", f"{total_assets:,}")
    o2.metric("Owned Assets", f"{owned_assets:,}")
    o3.metric("Ownership Coverage", f"{float(ownership_summary.get('ownership_coverage_percent') or 0):.1f}%")
    o4.metric("Ownership Quality", f"{float(ownership_summary.get('ownership_quality_score') or 0):.1f}%")
    o5.metric("Manual Review Queue", f"{len(ownership_dashboard['manual_review_queue']):,}")

    o6, o7, o8, o9 = st.columns(4)
    o6.metric("Departments", f"{len([row for row in ownership_dashboard['department_distribution'] if row['Department'] != 'Unassigned']):,}")
    o7.metric("Teams", f"{len([row for row in ownership_dashboard['team_distribution'] if row['Team'] != 'Unassigned']):,}")
    o8.metric("Technical Owners", f"{len([row for row in ownership_dashboard['owner_workload'] if row['Technical Owner'] != 'Unassigned']):,}")
    o9.metric("Executive Owners", f"{len([row for row in ownership_dashboard['executive_owner_distribution'] if row['Executive Owner'] != 'Unassigned']):,}")

    dist_a, dist_b = st.columns(2)
    with dist_a:
        st.subheader("Ownership by Department")
        st.dataframe(pd.DataFrame(ownership_dashboard["department_distribution"]), use_container_width=True, hide_index=True)
        st.subheader("Ownership by Team")
        st.dataframe(pd.DataFrame(ownership_dashboard["team_distribution"]), use_container_width=True, hide_index=True)
        st.subheader("Assets per Technical Owner")
        st.dataframe(pd.DataFrame(ownership_dashboard["owner_workload"]), use_container_width=True, hide_index=True)

    with dist_b:
        st.subheader("Ownership by Business Capability")
        st.dataframe(pd.DataFrame(ownership_dashboard["business_capability_distribution"]), use_container_width=True, hide_index=True)
        st.subheader("Ownership by Cost Center")
        st.dataframe(pd.DataFrame(ownership_dashboard["cost_center_distribution"]), use_container_width=True, hide_index=True)
        st.subheader("Executive Ownership Heatmap")
        st.dataframe(pd.DataFrame(ownership_dashboard["executive_owner_distribution"]), use_container_width=True, hide_index=True)

    table_a, table_b = st.columns(2)
    with table_a:
        st.subheader("Unowned Assets")
        unowned = ownership_dashboard["assets_without_owner"]
        if unowned:
            st.dataframe(pd.DataFrame(unowned), use_container_width=True, hide_index=True)
        else:
            st.success("All assets have ownership coverage.")

        st.subheader("Missing Executive Owner")
        missing_exec = ownership_dashboard["missing_executive_owner"]
        if missing_exec:
            st.dataframe(pd.DataFrame(missing_exec), use_container_width=True, hide_index=True)
        else:
            st.success("Executive owners are assigned.")

    with table_b:
        st.subheader("Largest Owner Workloads")
        st.dataframe(pd.DataFrame(ownership_dashboard["owner_workload"][:10]), use_container_width=True, hide_index=True)
        st.subheader("Missing Cost Center")
        missing_cost = ownership_dashboard["missing_cost_center"]
        if missing_cost:
            st.dataframe(pd.DataFrame(missing_cost), use_container_width=True, hide_index=True)
        else:
            st.success("Cost centers are assigned.")

    st.subheader("Manual Review Queue")
    review_queue = ownership_dashboard["manual_review_queue"]
    if review_queue:
        st.dataframe(pd.DataFrame(review_queue), use_container_width=True, hide_index=True)
    else:
        st.success("No ownership records require manual review.")

    if not is_read_only and ownership_rows:
        st.subheader("Ownership Governance Workflow")
        asset_options = [
            f"{row.get('enterprise_asset_id')} | {row.get('application') or row.get('business_service') or 'Unmapped'}"
            for row in ownership_rows
            if row.get("enterprise_asset_id")
        ]
        selected_asset = st.selectbox("Ownership Asset", asset_options)
        selected_asset_id = selected_asset.split("|", 1)[0].strip()

        with st.form("ownership_update_form"):
            f1, f2, f3 = st.columns(3)
            technical_owner = f1.text_input("Technical Owner")
            business_owner = f2.text_input("Business Owner")
            executive_owner = f3.text_input("Executive Owner")
            f4, f5, f6 = st.columns(3)
            department = f4.text_input("Department")
            team = f5.text_input("Team")
            cost_center = f6.text_input("Cost Center")
            f7, f8 = st.columns(2)
            criticality = f7.selectbox("Criticality", ["", "Critical", "High", "Medium", "Low", "Standard"])
            lifecycle = f8.selectbox("Lifecycle", ["", "Active", "Planned", "Deprecated", "Retired"])
            reviewed = st.checkbox("Mark as Reviewed")
            submitted = st.form_submit_button("Update Ownership")
            if submitted:
                result = EnterpriseOwnershipService.update_ownership(
                    selected_asset_id,
                    {
                        "technical_owner": technical_owner,
                        "business_owner": business_owner,
                        "executive_owner": executive_owner,
                        "department": department,
                        "team": team,
                        "cost_center": cost_center,
                        "criticality": criticality,
                        "lifecycle": lifecycle,
                        "reviewed": reviewed,
                    },
                    organization_id,
                    reviewed_by=user.get("email") or st.session_state.get("email") or "system",
                )
                if result.get("status") == "SUCCESS":
                    st.success(result.get("message"))
                else:
                    st.error(result.get("message") or "Ownership update failed.")

        with st.form("ownership_bulk_update_form"):
            st.caption("Bulk update applies only non-empty fields to selected assets.")
            bulk_assets = st.multiselect("Bulk Assets", asset_options)
            b1, b2, b3 = st.columns(3)
            bulk_department = b1.text_input("Bulk Department")
            bulk_team = b2.text_input("Bulk Team")
            bulk_cost_center = b3.text_input("Bulk Cost Center")
            b4, b5, b6 = st.columns(3)
            bulk_technical_owner = b4.text_input("Bulk Technical Owner")
            bulk_business_owner = b5.text_input("Bulk Business Owner")
            bulk_executive_owner = b6.text_input("Bulk Executive Owner")
            bulk_reviewed = st.checkbox("Bulk Mark Reviewed")
            bulk_submitted = st.form_submit_button("Bulk Update Ownership")
            if bulk_submitted:
                result = EnterpriseOwnershipService.bulk_update_ownership(
                    [item.split("|", 1)[0].strip() for item in bulk_assets],
                    {
                        "department": bulk_department,
                        "team": bulk_team,
                        "cost_center": bulk_cost_center,
                        "technical_owner": bulk_technical_owner,
                        "business_owner": bulk_business_owner,
                        "executive_owner": bulk_executive_owner,
                        "reviewed": bulk_reviewed,
                    },
                    organization_id,
                    reviewed_by=user.get("email") or st.session_state.get("email") or "system",
                )
                st.info(f"Bulk update result: {result.get('updated', 0)} updated, {result.get('failed', 0)} failed.")

    st.divider()
    st.subheader("Business Capability Intelligence")
    capability_dashboard = BusinessCapabilityService.get_dashboard(organization_id)
    capability_summary = capability_dashboard["summary"]

    bc1, bc2, bc3, bc4, bc5, bc6 = st.columns(6)
    bc1.metric("Total Capabilities", f"{int(capability_summary.get('capabilities_synced') or 0):,}")
    bc2.metric("Critical", f"{int(capability_summary.get('critical_capabilities') or 0):,}")
    bc3.metric("Avg Health", f"{float(capability_summary.get('average_health') or 0):.1f}%")
    bc4.metric("Capability Spend", f"${float(capability_summary.get('total_capability_spend') or 0):,.0f}")
    bc5.metric("Optimization", f"${float(capability_summary.get('optimization_opportunity') or 0):,.0f}")
    bc6.metric("Governance", f"{float(capability_summary.get('governance_score') or 0):.1f}%")

    cap_left, cap_right = st.columns(2)
    with cap_left:
        st.subheader("Capability Health Matrix")
        health_matrix = capability_dashboard["health_matrix"]
        if health_matrix:
            st.dataframe(pd.DataFrame(health_matrix), use_container_width=True, hide_index=True)
        else:
            st.info("No business capability health data is available yet.")

        st.subheader("Spend by Capability")
        spend_by_capability = capability_dashboard["spend_by_capability"]
        if spend_by_capability:
            st.dataframe(pd.DataFrame(spend_by_capability), use_container_width=True, hide_index=True)
        else:
            st.info("No capability spend data is available yet.")

        st.subheader("Assets by Capability")
        assets_by_capability = capability_dashboard["assets_by_capability"]
        if assets_by_capability:
            st.dataframe(pd.DataFrame(assets_by_capability), use_container_width=True, hide_index=True)
        else:
            st.info("No capability asset data is available yet.")

    with cap_right:
        st.subheader("Applications by Capability")
        applications_by_capability = capability_dashboard["applications_by_capability"]
        if applications_by_capability:
            st.dataframe(pd.DataFrame(applications_by_capability), use_container_width=True, hide_index=True)
        else:
            st.info("No capability application data is available yet.")

        st.subheader("Risk Heatmap")
        risk_heatmap = capability_dashboard["risk_heatmap"]
        if risk_heatmap:
            st.dataframe(pd.DataFrame(risk_heatmap), use_container_width=True, hide_index=True)
        else:
            st.info("No capability risk data is available yet.")

        st.subheader("Dependency Graph")
        dependency_graph = capability_dashboard["dependency_graph"]
        if dependency_graph:
            st.dataframe(pd.DataFrame(dependency_graph).head(25), use_container_width=True, hide_index=True)
        else:
            st.info("No capability dependencies are available yet.")

    cap_t1, cap_t2 = st.columns(2)
    with cap_t1:
        st.subheader("Critical Capabilities")
        critical_capabilities = capability_dashboard["critical_capabilities"]
        if critical_capabilities:
            st.dataframe(pd.DataFrame(critical_capabilities), use_container_width=True, hide_index=True)
        else:
            st.success("No critical capability risks are currently identified.")

        st.subheader("Lowest Health")
        lowest_health = capability_dashboard["lowest_health"]
        if lowest_health:
            st.dataframe(pd.DataFrame(lowest_health), use_container_width=True, hide_index=True)

    with cap_t2:
        st.subheader("Highest Spend")
        highest_spend = capability_dashboard["highest_spend"]
        if highest_spend:
            st.dataframe(pd.DataFrame(highest_spend), use_container_width=True, hide_index=True)

        st.subheader("Missing Executive Owner")
        missing_capability_owner = capability_dashboard["missing_executive_owner"]
        if missing_capability_owner:
            st.dataframe(pd.DataFrame(missing_capability_owner), use_container_width=True, hide_index=True)
        else:
            st.success("All capabilities have executive ownership.")

    st.subheader("Improvement Recommendations")
    recommendations = capability_dashboard["improvement_recommendations"]
    if recommendations:
        st.dataframe(pd.DataFrame(recommendations), use_container_width=True, hide_index=True)
    else:
        st.success("No capability improvement recommendations are currently open.")

    st.divider()
    st.subheader("Enterprise Cost Attribution")
    cost_dashboard = EnterpriseCostAttributionService.get_dashboard(organization_id)
    cost_summary = cost_dashboard["summary"]

    ca1, ca2, ca3, ca4 = st.columns(4)
    ca1.metric("Total Attributed Cost", f"${float(cost_summary.get('attributed_cost') or 0):,.2f}")
    ca2.metric("Attribution Coverage", f"{float(cost_summary.get('attribution_coverage_percent') or 0):.1f}%")
    ca3.metric("Unattributed Cost", f"${float(cost_summary.get('unattributed_cost') or 0):,.2f}")
    ca4.metric("Rows Attributed", f"{int(cost_summary.get('attributed_rows') or 0):,}")

    cost_left, cost_right = st.columns(2)
    with cost_left:
        st.subheader("Cost by Application")
        cost_by_application = cost_dashboard["cost_by_application"]
        if cost_by_application:
            st.dataframe(pd.DataFrame(cost_by_application), use_container_width=True, hide_index=True)
        else:
            st.info("No application-level cost attribution is available yet.")

        st.subheader("Cost by Business Capability")
        cost_by_capability = cost_dashboard["cost_by_business_capability"]
        if cost_by_capability:
            st.dataframe(pd.DataFrame(cost_by_capability), use_container_width=True, hide_index=True)
        else:
            st.info("No business capability cost attribution is available yet.")

    with cost_right:
        st.subheader("Cost by Department")
        cost_by_department = cost_dashboard["cost_by_department"]
        if cost_by_department:
            st.dataframe(pd.DataFrame(cost_by_department), use_container_width=True, hide_index=True)
        else:
            st.info("No department cost attribution is available yet.")

        st.subheader("Cost by Cost Center")
        cost_by_cost_center = cost_dashboard["cost_by_cost_center"]
        if cost_by_cost_center:
            st.dataframe(pd.DataFrame(cost_by_cost_center), use_container_width=True, hide_index=True)
        else:
            st.info("No cost center attribution is available yet.")

    st.subheader("Unattributed Cost Queue")
    unattributed_costs = cost_dashboard["unattributed_costs"]
    if unattributed_costs:
        st.dataframe(pd.DataFrame(unattributed_costs), use_container_width=True, hide_index=True)
    else:
        st.success("All eligible cloud costs have business attribution.")


if __name__ == "__main__":
    main()
