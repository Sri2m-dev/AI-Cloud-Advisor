from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.connector_context import (
    get_current_organization_id,
    get_current_user_id,
    require_connector_admin,
)
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.aws_connector_service import AWSConnectorService

st.set_page_config(page_title="AWS Connector Setup", layout="wide")


def _show_result(result: dict) -> None:
    if result.get("status") == "CONNECTED":
        st.success("AWS connection verified.")
    elif result.get("status") == "FAILED":
        st.error("AWS connection failed.")
    st.dataframe(pd.DataFrame([result]), use_container_width=True, hide_index=True)


def _mask_secret(value: str | None) -> str:
    if not value:
        return ""
    suffix = str(value)[-4:]
    return "*" * 16 + suffix


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

    st.title("AWS Connector Setup")
    st.caption("Connect AWS using the default runtime credentials or an assumed IAM role.")

    config = AWSConnectorService.get_config(organization_id)
    saved_region = config.get("region") or "us-east-1"
    regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"]
    region_index = regions.index(saved_region) if saved_region in regions else 0

    with st.form("aws_connector_setup"):
        st.subheader("Save Connector Config")
        role_arn = st.text_input(
            "Role ARN",
            value=_mask_secret(config.get("role_arn")),
            placeholder="arn:aws:iam::123456789012:role/NexoraConnectorRole",
        )
        external_id = st.text_input("External ID", value=_mask_secret(config.get("external_id")), type="password")
        region = st.selectbox("Region", regions, index=region_index)
        sync_frequency = st.selectbox(
            "Sync Frequency",
            ["DAILY", "WEEKLY", "MONTHLY"],
            index=["DAILY", "WEEKLY", "MONTHLY"].index(config.get("sync_frequency", "DAILY"))
            if config.get("sync_frequency", "DAILY") in {"DAILY", "WEEKLY", "MONTHLY"}
            else 0,
        )
        enabled = st.checkbox("Enabled", value=bool(config.get("enabled", True)))
        form_cols = st.columns(2)
        test_submitted = form_cols[0].form_submit_button("Test Connection", use_container_width=True)
        save_submitted = form_cols[1].form_submit_button("Save Config", use_container_width=True)

    if test_submitted:
        effective_role_arn = _resolve_secret(role_arn, config.get("role_arn"))
        effective_external_id = _resolve_secret(external_id, config.get("external_id"))
        with st.spinner("Testing AWS connection..."):
            result = AWSConnectorService.test_connection(
                effective_role_arn,
                effective_external_id,
                region,
                organization_id=organization_id,
            )
        _show_result(result)

    if save_submitted:
        effective_role_arn = _resolve_secret(role_arn, config.get("role_arn"))
        effective_external_id = _resolve_secret(external_id, config.get("external_id"))
        result = AWSConnectorService.save_config(
            organization_id=organization_id,
            configured_by=configured_by,
            role_arn=effective_role_arn,
            external_id=effective_external_id,
            region=region,
            sync_frequency=sync_frequency,
            enabled=enabled,
        )
        if result.get("status") == "SAVED":
            st.success("AWS connector config saved.")
        else:
            st.error("AWS connector config could not be saved.")
        st.json(result)

    st.divider()
    st.subheader("Enable / Disable Connector")
    enable_cols = st.columns(2)
    with enable_cols[0]:
        if st.button("Enable Connector", use_container_width=True):
            st.json(AWSConnectorService.enable_connector(organization_id))
    with enable_cols[1]:
        if st.button("Disable Connector", use_container_width=True):
            st.json(AWSConnectorService.disable_connector(organization_id))

    st.divider()
    st.subheader("Run Sync")
    sync_cols = st.columns(3)
    with sync_cols[0]:
        if st.button("Preview AWS Sync", use_container_width=True):
            effective_role_arn = _resolve_secret(role_arn, config.get("role_arn"))
            effective_external_id = _resolve_secret(external_id, config.get("external_id"))
            with st.spinner("Previewing AWS accounts and seven days of Cost Explorer data..."):
                preview = AWSConnectorService.preview_live_sync(
                    role_arn=effective_role_arn,
                    external_id=effective_external_id,
                    region=region,
                )
            st.success("AWS sync preview completed.")
            st.json(preview)

    with sync_cols[1]:
        if st.button("Run AWS Sync with Manual Values", use_container_width=True):
            effective_role_arn = _resolve_secret(role_arn, config.get("role_arn"))
            effective_external_id = _resolve_secret(external_id, config.get("external_id"))
            with st.spinner("Syncing AWS accounts, costs, resources, and recommendations..."):
                result = AWSConnectorService.sync_all(
                    role_arn=effective_role_arn,
                    external_id=effective_external_id,
                    region=region,
                    organization_id=organization_id,
                )
            st.json(result)

    with sync_cols[2]:
        if st.button("Run Sync from Saved Config", use_container_width=True):
            with st.spinner("Syncing AWS using saved connector config..."):
                result = AWSConnectorService.sync_all(organization_id=organization_id)
            st.json(result)

    st.divider()
    st.subheader("AWS IAM Readiness")

    if st.button("Validate AWS Permissions", use_container_width=True):
        with st.spinner("Checking AWS IAM permissions..."):
            effective_role_arn = _resolve_secret(role_arn, config.get("role_arn"))
            effective_external_id = _resolve_secret(external_id, config.get("external_id"))
            permission_rows = AWSConnectorService.validate_permissions(
                role_arn=effective_role_arn,
                external_id=effective_external_id,
                region=region,
            )
        readiness_df = pd.DataFrame(permission_rows)
        if not readiness_df.empty:
            passed = int((readiness_df["status"] == "PASSED").sum()) if "status" in readiness_df else 0
            failed = int((readiness_df["status"] == "FAILED").sum()) if "status" in readiness_df else 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Permissions Checked", len(readiness_df))
            c2.metric("Ready", passed)
            c3.metric("Blocked", failed)
        st.dataframe(readiness_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Tables Populated")
    st.dataframe(
        pd.DataFrame(
            [
                {"Table": "cloud_accounts", "Source": "AWS Organizations / STS", "Purpose": "Account inventory"},
                {"Table": "unified_cloud_costs", "Source": "AWS Cost Explorer / CUR", "Purpose": "Cost propagation"},
                {"Table": "technology_inventory", "Source": "EC2 / resource APIs", "Purpose": "Technology portfolio"},
                {"Table": "recommendations", "Source": "Compute Optimizer", "Purpose": "Optimization workflow"},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader("Connector Status")

    status = AWSConnectorService.get_status(organization_id)

    if status:
        st.dataframe(
            [
                {
                    "Connector": status.get("connector_name"),
                    "Status": status.get("status"),
                    "Last Sync": status.get("last_sync_at"),
                    "Last Success": status.get("last_success_at"),
                    "Last Failure": status.get("last_failure_at"),
                    "Objects Synced": status.get("objects_synced"),
                    "Last Error": status.get("last_error"),
                }
            ],
            use_container_width=True,
        )
    else:
        st.info("No AWS connector status has been recorded yet.")

    st.subheader("Recent Sync History")

    history = AWSConnectorService.get_sync_history(organization_id=organization_id)

    if history:
        st.dataframe(
            history,
            use_container_width=True,
        )
    else:
        st.info("No AWS sync history is available yet.")

    st.divider()
    st.subheader("AWS Discovery Status")

    discovery = AWSConnectorService.get_discovery_summary(organization_id)
    relationships = AWSConnectorService.get_relationship_summary(organization_id)

    c1, c2, c3 = st.columns(3)
    c1.metric("Assets Discovered", discovery["assets_discovered"])
    c2.metric("Resource Types", discovery["resource_types"])
    c3.metric("Relationship Edges", relationships["relationship_edges"])

    if discovery["resources_by_type"]:
        st.write("Resources by Type")
        st.dataframe(
            [{"Resource Type": k, "Count": v} for k, v in discovery["resources_by_type"].items()],
            use_container_width=True,
        )
    else:
        st.info(
            "No AWS resources discovered yet. Cost sync can work even when resource discovery is blocked by IAM permissions."
        )

    if discovery["latest_assets"]:
        st.write("Latest Discovered Assets")
        st.dataframe(discovery["latest_assets"], use_container_width=True)

    if relationships["latest_relationships"]:
        st.write("Latest AWS Relationship Edges")
        st.dataframe(relationships["latest_relationships"], use_container_width=True)


if __name__ == "__main__":
    main()
