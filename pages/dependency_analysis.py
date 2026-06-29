from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.enterprise_intelligence import render_common_asset_search, render_empty_state, render_intelligence_workspace
from components.sidebar_navigation import render_sidebar_navigation
from services.dependency_analysis_service import DependencyAnalysisService
from services.enterprise_graph_service import EnterpriseGraphService


st.set_page_config(page_title="Dependency Analysis", layout="wide")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical", "finance"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Dependency Analysis is available to leadership, operations, governance, and finance roles.")
        st.stop()


def _show_table(rows: list[dict[str, Any]], empty_message: str) -> None:
    if not rows:
        st.info(empty_message)
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    dashboard = DependencyAnalysisService.get_dashboard(organization_id)
    summary = dashboard["summary"]
    graph = EnterpriseGraphService.build_graph(organization_id)

    st.title("Dependency Analysis")
    st.caption("Impact, upstream/downstream dependency, provider concentration, and single-point-of-failure analysis from the Enterprise Graph.")
    render_intelligence_workspace("Dependency Analysis")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Dependencies", f"{int(summary.get('Total Dependencies') or 0):,}")
    k2.metric("Critical Paths", f"{int(summary.get('Critical Paths') or 0):,}")
    k3.metric("Single Points", f"{int(summary.get('Single Points of Failure') or 0):,}")
    k4.metric("High-Risk Apps", f"{int(summary.get('High-Risk Applications') or 0):,}")

    k5, k6, k7 = st.columns(3)
    k5.metric("Provider Concentration", summary.get("Provider Concentration") or "Unknown")
    k6.metric("Avg Dependency Depth", f"{float(summary.get('Average Dependency Depth') or 0):.1f}")
    k7.metric("Most Connected Node", summary.get("Most Connected Node") or "Unknown")

    st.divider()
    st.subheader("Dependency Map")
    selected_node, _selected_type = render_common_asset_search(organization_id, "dependency_map", default="Checkout")
    dependency_map = DependencyAnalysisService.get_dependency_map(selected_node, organization_id)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Upstream", f"{dependency_map['summary']['upstream_count']:,}")
    m2.metric("Downstream", f"{dependency_map['summary']['downstream_count']:,}")
    m3.metric("Upstream Depth", f"{dependency_map['summary']['max_upstream_depth']:,}")
    m4.metric("Downstream Depth", f"{dependency_map['summary']['max_downstream_depth']:,}")

    left, right = st.columns(2)
    with left:
        st.subheader("Upstream Dependencies")
        if dependency_map["upstream"]:
            _show_table(dependency_map["upstream"], "No upstream dependencies found.")
        else:
            render_empty_state("No upstream dependencies found.", "This asset has no mapped prerequisites in the enterprise graph.")
    with right:
        st.subheader("Downstream Impacts")
        if dependency_map["downstream"]:
            _show_table(dependency_map["downstream"], "No downstream impacts found.")
        else:
            render_empty_state("No downstream impacts found.", "This asset has no mapped consumers or business impacts yet.")

    st.divider()
    st.subheader("Critical Dependency Paths")
    _show_table(dashboard["critical_dependency_paths"], "No critical dependency paths are available.")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Single Points of Failure")
        _show_table(dashboard["single_points_of_failure"], "No single points of failure were detected.")

        st.subheader("Provider Dependency Summary")
        _show_table(dashboard["provider_dependency_summary"], "No provider dependency summary is available.")

    with c2:
        st.subheader("Application Dependency Summary")
        _show_table(dashboard["application_dependency_summary"], "No application dependency summary is available.")

        st.subheader("Reasoning Examples")
        ea_impact = DependencyAnalysisService.get_downstream_impacts("EA-000001", organization_id)
        checkout_map = DependencyAnalysisService.get_dependency_map("Checkout", organization_id)
        st.code(
            "EA-000001 impacts: "
            + " -> ".join(row["node"] for row in ea_impact if row["node_type"] in {"Application", "Business Service", "Business Capability"}),
            language="text",
        )
        st.code(
            "Checkout depends on: "
            + ", ".join(row["node"] for row in checkout_map["upstream"][:10]),
            language="text",
        )


if __name__ == "__main__":
    main()
