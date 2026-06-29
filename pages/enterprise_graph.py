from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.enterprise_intelligence import render_common_asset_search, render_empty_state, render_intelligence_workspace
from components.sidebar_navigation import render_sidebar_navigation
from services.enterprise_graph_service import EnterpriseGraphService


st.set_page_config(page_title="Enterprise Graph", layout="wide")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical", "finance"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Enterprise Graph is available to leadership, operations, and governance roles.")
        st.stop()


def _show_table(rows: list[dict[str, Any]], empty_message: str) -> None:
    if not rows:
        st.info(empty_message)
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _sankey(edges: list[dict[str, Any]]) -> go.Figure | None:
    if not edges:
        return None
    labels = pd.unique(pd.DataFrame(edges)[["source_name", "target_name"]].values.ravel("K")).tolist()
    index = {label: i for i, label in enumerate(labels)}
    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node={"label": labels, "pad": 16, "thickness": 14},
                link={
                    "source": [index[row["source_name"]] for row in edges],
                    "target": [index[row["target_name"]] for row in edges],
                    "value": [1 for _ in edges],
                    "label": [row["relationship_type"] for row in edges],
                },
            )
        ]
    )
    fig.update_layout(height=430, margin={"l": 10, "r": 10, "t": 20, "b": 10})
    return fig


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    if st.button("Refresh Graph Cache"):
        EnterpriseGraphService.build_graph(organization_id, refresh=True)
        st.success("Enterprise graph cache refreshed.")

    dashboard = EnterpriseGraphService.get_dashboard(organization_id)
    summary = dashboard["summary"]
    nodes = dashboard["nodes"]
    edges = dashboard["edges"]

    st.title("Enterprise Knowledge Graph")
    st.caption("Unified graph across capabilities, applications, assets, technologies, owners, cost, AI decisions, workflows, and execution.")
    render_intelligence_workspace("Knowledge Graph")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Graph Nodes", f"{int(summary.get('Graph Nodes') or 0):,}")
    k2.metric("Relationships", f"{int(summary.get('Graph Relationships') or 0):,}")
    k3.metric("Components", f"{int(summary.get('Connected Components') or 0):,}")
    k4.metric("Orphan Nodes", f"{int(summary.get('Orphan Nodes') or 0):,}")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Critical Nodes", f"{int(summary.get('Critical Nodes') or 0):,}")
    k6.metric("Dependency Depth", f"{int(summary.get('Dependency Depth') or 0):,}")
    k7.metric("Graph Health", f"{float(summary.get('Graph Health Score') or 0):.1f}%")
    k8.metric("Reasoning Readiness", f"{float(summary.get('Reasoning Readiness %') or 0):.1f}%")

    st.divider()
    st.subheader("Graph Explorer")
    selected_node, _selected_type = render_common_asset_search(organization_id, "graph_explorer", default="AWS")
    node_names = sorted({node["name"] for node in nodes})
    node_types = ["All", *sorted({node["type"] for node in nodes})]
    edge_types = ["All", *sorted({edge["relationship_type"] for edge in edges})]

    f2, f3 = st.columns(2)
    selected_node_type = f2.selectbox("Node Type", node_types)
    selected_edge_type = f3.selectbox("Edge Type", edge_types)

    subgraph = EnterpriseGraphService.subgraph(
        node=selected_node,
        node_type=None if selected_node_type == "All" else selected_node_type,
        edge_type=None if selected_edge_type == "All" else selected_edge_type,
        organization_id=organization_id,
        depth=2,
    )
    fig = _sankey(subgraph["edges"])
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        render_empty_state(
            "No graph relationships match the selected filters.",
            "The selected asset may not have mapped relationships yet.",
            "Refresh graph cache or add relationship mappings.",
        )

    n1, n2 = st.columns(2)
    with n1:
        st.subheader("Connected Nodes")
        neighbors = EnterpriseGraphService.get_neighbors(selected_node, organization_id)
        _show_table(
            [
                {
                    "Direction": row["direction"],
                    "Relationship": row["relationship"],
                    "Node": row["node"]["name"],
                    "Type": row["node"]["type"],
                }
                for row in neighbors
            ],
            "No connected nodes are available for this entity.",
        )

    with n2:
        st.subheader("Critical Nodes")
        _show_table(dashboard["critical_nodes"], "No critical graph nodes are currently identified.")

    st.divider()
    st.subheader("Reasoning Path")
    p1, p2 = st.columns(2)
    source = p1.text_input("From", value="Revenue Services")
    target = p2.text_input("To", value="AWS")
    path = EnterpriseGraphService.find_path(source, target, organization_id)
    if path:
        st.code(" -> ".join(row["node"] for row in path), language="text")
        _show_table(path, "No path details are available.")
    else:
        st.info("No path found between those entities.")

    st.divider()
    d1, d2 = st.columns(2)
    with d1:
        st.subheader("Dependencies")
        dependency_node = st.text_input("Dependency Node", value="Checkout")
        dependencies = EnterpriseGraphService.find_dependencies(dependency_node, organization_id)
        _show_table(
            [
                {
                    "Depth": row["depth"],
                    "Relationship": row["relationship"],
                    "Node": row["node"]["name"],
                    "Type": row["node"]["type"],
                }
                for row in dependencies
            ],
            "No dependencies were found.",
        )

    with d2:
        st.subheader("Impact Analysis")
        impact_node = st.text_input("Impact Node", value="EA-000001")
        impacted = EnterpriseGraphService.find_impacted_nodes(impact_node, organization_id)
        _show_table(
            [
                {
                    "Depth": row["depth"],
                    "Relationship": row["relationship"],
                    "Node": row["node"]["name"],
                    "Type": row["node"]["type"],
                }
                for row in impacted
            ],
            "No impacted nodes were found.",
        )

    st.divider()
    t1, t2, t3 = st.columns(3)
    with t1:
        st.subheader("Node Types")
        _show_table(dashboard["node_types"], "No node type distribution is available.")
    with t2:
        st.subheader("Edge Types")
        _show_table(dashboard["edge_types"], "No edge type distribution is available.")
    with t3:
        st.subheader("Orphan Nodes")
        _show_table(
            [{"Node": row["name"], "Type": row["type"]} for row in dashboard["orphan_nodes"]],
            "No orphan nodes are currently present.",
        )


if __name__ == "__main__":
    main()
