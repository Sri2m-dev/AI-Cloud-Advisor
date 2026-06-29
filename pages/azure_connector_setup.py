from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.guards import require_login
from auth.connector_context import get_current_organization_id, get_current_user_id, require_connector_admin
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.azure_connector_service import AzureConnectorService


st.set_page_config(page_title="Azure Connector Setup", layout="wide")


def _mask_secret(value: str | None) -> str:
    if not value:
        return ""
    return "*" * 16 + str(value)[-4:]


def _resolve_secret(input_value: str, saved_value: str | None) -> str | None:
    if input_value and set(input_value[:-4]) == {"*"}:
        return saved_value
    return input_value or None


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    require_connector_admin()
    organization_id = get_current_organization_id()
    configured_by = get_current_user_id()

    st.title("Azure Connector Setup")
    st.caption("Connect Azure using service-principal credentials or the runtime Azure identity.")

    config = AzureConnectorService.get_config(organization_id)
    with st.form("azure_connector_setup"):
        st.subheader("Save Connector Config")
        tenant_id = st.text_input("Tenant ID", value=_mask_secret(config.get("tenant_id")))
        client_id = st.text_input("Client ID", value=_mask_secret(config.get("client_id")))
        client_secret = st.text_input("Client Secret", value=_mask_secret(config.get("client_secret")), type="password")
        subscription_id = st.text_input("Subscription ID", value=config.get("subscription_id") or "")
        sync_frequency = st.selectbox("Sync Frequency", ["DAILY", "WEEKLY", "MONTHLY"], index=0)
        enabled = st.checkbox("Enabled", value=bool(config.get("enabled", True)))
        cols = st.columns(2)
        test_submitted = cols[0].form_submit_button("Test Connection", use_container_width=True)
        save_submitted = cols[1].form_submit_button("Save Config", use_container_width=True)

    if test_submitted:
        effective_tenant_id = _resolve_secret(tenant_id, config.get("tenant_id"))
        effective_client_id = _resolve_secret(client_id, config.get("client_id"))
        effective_client_secret = _resolve_secret(client_secret, config.get("client_secret"))
        with st.spinner("Testing Azure connection..."):
            result = AzureConnectorService.test_connection(
                effective_tenant_id,
                effective_client_id,
                effective_client_secret,
                subscription_id or None,
            )
        if result.get("status") == "CONNECTED":
            st.success("Azure connection verified.")
        else:
            st.error("Azure connection failed.")
        st.dataframe(pd.DataFrame([result]), use_container_width=True, hide_index=True)

    if save_submitted:
        effective_tenant_id = _resolve_secret(tenant_id, config.get("tenant_id"))
        effective_client_id = _resolve_secret(client_id, config.get("client_id"))
        effective_client_secret = _resolve_secret(client_secret, config.get("client_secret"))
        result = AzureConnectorService.save_config(
            organization_id,
            configured_by,
            effective_tenant_id,
            effective_client_id,
            effective_client_secret,
            subscription_id or None,
            sync_frequency,
            enabled,
        )
        st.json(result)

    st.divider()
    st.subheader("Run Sync")
    sync_cols = st.columns(2)
    with sync_cols[0]:
        if st.button("Preview Azure Sync", use_container_width=True):
            effective_tenant_id = _resolve_secret(tenant_id, config.get("tenant_id"))
            effective_client_id = _resolve_secret(client_id, config.get("client_id"))
            effective_client_secret = _resolve_secret(client_secret, config.get("client_secret"))
            with st.spinner("Previewing Azure accounts and seven days of Cost Management data..."):
                preview = AzureConnectorService.preview_live_sync(
                    effective_tenant_id,
                    effective_client_id,
                    effective_client_secret,
                    subscription_id or None,
                    organization_id=organization_id,
                )
            st.success("Azure sync preview completed.")
            st.json(preview)

    with sync_cols[1]:
        if st.button("Run Azure Sync", use_container_width=True):
            with st.spinner("Syncing Azure accounts, costs, resources, and recommendations..."):
                st.json(AzureConnectorService.sync_all(organization_id=organization_id))

    st.divider()
    st.subheader("Connector Status")
    status = AzureConnectorService.get_status(organization_id)
    if status:
        st.dataframe(pd.DataFrame([status]), use_container_width=True, hide_index=True)
    else:
        st.info("No Azure connector status has been recorded yet.")

    st.subheader("Recent Sync History")
    history = AzureConnectorService.get_sync_history(organization_id=organization_id)
    if history:
        st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
    else:
        st.info("No Azure sync history is available yet.")

    st.divider()
    st.subheader("Azure Discovery Status")

    discovery = AzureConnectorService.get_discovery_summary(organization_id)
    relationships = AzureConnectorService.get_relationship_summary(organization_id)

    c1, c2, c3 = st.columns(3)
    c1.metric("Assets Discovered", discovery["assets_discovered"])
    c2.metric("Resource Types", discovery["resource_types"])
    c3.metric("Relationship Edges", relationships["relationship_edges"])

    if discovery["resources_by_type"]:
        st.write("Resources by Type")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Resource Type": resource_type, "Count": count}
                    for resource_type, count in discovery["resources_by_type"].items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No Azure resources discovered yet. Cost sync can work even when resource discovery is blocked by RBAC permissions."
        )

    if discovery["latest_assets"]:
        st.write("Latest Azure Assets")
        st.dataframe(pd.DataFrame(discovery["latest_assets"]), use_container_width=True, hide_index=True)

    if relationships["latest_relationships"]:
        st.write("Latest Azure Relationship Edges")
        st.dataframe(pd.DataFrame(relationships["latest_relationships"]), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Tables Populated")
    st.dataframe(
        pd.DataFrame(
            [
                {"Table": "unified_cloud_costs", "Source": "Azure Cost Management", "Purpose": "Cost propagation"},
                {"Table": "discovered_assets", "Source": "Azure Resource Manager", "Purpose": "Connector asset inventory"},
                {"Table": "technology_inventory", "Source": "Azure Resource Manager", "Purpose": "Technology portfolio"},
                {"Table": "technology_relationships", "Source": "Azure Resource Manager", "Purpose": "Technology dependency graph"},
                {"Table": "relationship_graph", "Source": "Azure Resource Manager", "Purpose": "Digital Twin lineage"},
                {"Table": "recommendations", "Source": "Azure Advisor", "Purpose": "Optimization workflow"},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    main()
