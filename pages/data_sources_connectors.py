from __future__ import annotations

from uuid import uuid4

import pandas as pd
import streamlit as st

from auth.authenticated_tenant import AuthenticatedTenantContext
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from connector_orchestration.trigger import ConnectorTriggerType
from services.connector_service import ConnectorService
from services.live_source_service import live_source_service

st.set_page_config(page_title="Data Sources & Connectors", layout="wide")


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def _get_tenant_context() -> AuthenticatedTenantContext | None:
    org_id = str(
        st.session_state.get("organization_id")
        or st.session_state.get("org_id")
        or "bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c"
    ).strip()
    email = str(
        st.session_state.get("email") or st.session_state.get("user") or "admin@company.com"
    ).strip()
    role = normalize_role(st.session_state.get("role") or "client_admin")
    org_name = str(st.session_state.get("organization_name") or "Enterprise Workspace").strip()
    try:
        return AuthenticatedTenantContext(
            organization_id=org_id,
            organization_name=org_name,
            user_id=email,
            user_email=email,
            role=role,
            authorization_claims=frozenset(
                ["admin"] if role in {"super_admin", "client_admin"} else []
            ),
            tenant_id=org_id,
        )
    except Exception:
        return None


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)

    st.title("Data Sources & Connectors")
    st.caption("Governed live cloud connectivity and Data Fabric ingestion")

    ctx = _get_tenant_context()
    is_admin = role in {"super_admin", "client_admin", "admin"}

    tab_live, tab_overview = st.tabs(["Active Cloud Sources (AWS & Azure)", "Platform Overview"])

    with tab_live:
        st.subheader("Tenant Live Cloud Sources")
        st.caption("Direct cross-account role and service-principal connections to AWS and Azure")

        if ctx is None:
            st.error("No verified tenant context available for source management.")
        else:
            try:
                service = live_source_service()
                sources = service.list_sources(ctx)
            except Exception as e:
                sources = ()
                st.warning(f"Could not load live sources: {e}")

            if not sources:
                st.info("No live cloud sources configured for this tenant.")
            else:
                for src in sources:
                    with st.container():
                        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 3])
                        with c1:
                            st.markdown(f"**{src['display_name']}**")
                            st.caption(f"Provider: `{src['provider'].upper()}`")
                        with c2:
                            status_color = {
                                "ACTIVE": "green",
                                "READY": "blue",
                                "DRAFT": "orange",
                                "VALIDATING": "orange",
                                "ERROR": "red",
                                "DISABLED": "gray",
                            }.get(src["status"], "gray")
                            st.markdown(f"Status: :{status_color}[● {src['status']}]")
                            if src.get("safe_error_summary"):
                                st.caption(f"Error: {src['safe_error_summary']}")
                        with c3:
                            sync_st = src.get("sync_status", "NEVER_SYNCED")
                            sync_color = {
                                "SUCCEEDED": "green",
                                "RUNNING": "orange",
                                "QUEUED": "orange",
                                "FAILED": "red",
                                "NEVER_SYNCED": "gray",
                            }.get(sync_st, "gray")
                            st.markdown(f"Sync: :{sync_color}[{sync_st}]")
                            if src.get("last_success_at"):
                                st.caption(f"Last Success: {src['last_success_at'][:19]}")
                        with c4:
                            sched = "Daily" if src.get("schedule_enabled") else "Disabled"
                            st.write(f"Schedule: {sched}")
                        with c5:
                            if is_admin:
                                act_cols = st.columns(3)
                                with act_cols[0]:
                                    if st.button("Validate", key=f"val_{src['source_id']}"):
                                        with st.spinner("Validating..."):
                                            res = service.validate_connection(ctx, src["source_id"])
                                            if res.get("status") == "READY":
                                                st.success("Validated!")
                                            else:
                                                st.error("Validation failed.")
                                            st.rerun()
                                with act_cols[1]:
                                    if src["status"] == "READY":
                                        if st.button("Activate", key=f"act_{src['source_id']}"):
                                            service.set_active(ctx, src["source_id"], True)
                                            st.success("Activated!")
                                            st.rerun()
                                    elif src["status"] == "ACTIVE":
                                        if st.button("Disable", key=f"dis_{src['source_id']}"):
                                            service.set_active(ctx, src["source_id"], False)
                                            st.info("Disabled.")
                                            st.rerun()
                                with act_cols[2]:
                                    if src["status"] == "ACTIVE":
                                        if st.button("Sync Now", key=f"sync_{src['source_id']}"):
                                            with st.spinner("Ingesting from cloud API..."):
                                                sync_res = service.sync(
                                                    ctx,
                                                    src["source_id"],
                                                    request_key=f"manual:{uuid4()}",
                                                    trigger=ConnectorTriggerType.MANUAL,
                                                )
                                                if sync_res.get("status") == "SUCCEEDED":
                                                    st.success("Synced successfully!")
                                                else:
                                                    st.error("Sync failed.")
                                                st.rerun()
                        st.divider()

            if is_admin:
                st.subheader("Connect New Cloud or SaaS Source")
                with st.expander("➕ Add Data Source (AWS, Azure, M365)", expanded=False):
                    provider_choice = st.radio(
                        "Provider", ["AWS", "Azure", "Microsoft 365 / Entra ID"], horizontal=True
                    )

                    if provider_choice == "AWS":
                        with st.form("add_aws_source_form"):
                            st.caption("Configure AWS Cost Explorer access using IAM Role")
                            aws_name = st.text_input(
                                "Source Display Name", placeholder="Production AWS Account"
                            )
                            aws_account_id = st.text_input(
                                "AWS Account ID (12 digits)", placeholder="123456789012"
                            )
                            aws_role_arn = st.text_input(
                                "Role ARN",
                                placeholder="arn:aws:iam::123456789012:role/NexoraRole",
                            )
                            aws_region = st.selectbox(
                                "Region",
                                ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"],
                                index=0,
                            )
                            aws_ext_id = st.text_input(
                                "External ID (Optional)",
                                type="password",
                                placeholder="Enter external ID if configured",
                            )

                            aws_submit = st.form_submit_button(
                                "Register & Save AWS Source", type="primary"
                            )
                            if aws_submit:
                                try:
                                    service = live_source_service()
                                    new_src = service.create(
                                        ctx,
                                        provider="aws",
                                        display_name=aws_name,
                                        configuration={
                                            "account_id": aws_account_id.strip(),
                                            "role_arn": aws_role_arn.strip(),
                                            "region": aws_region.strip(),
                                        },
                                        secrets={"external_id": aws_ext_id.strip()}
                                        if aws_ext_id.strip()
                                        else {},
                                    )
                                    st.success(f"AWS source **{new_src['display_name']}** created.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Failed to create AWS source: {exc}")

                    elif provider_choice == "Azure":
                        with st.form("add_azure_source_form"):
                            st.caption("Configure Azure Cost Management access using SP")
                            az_name = st.text_input(
                                "Source Display Name", placeholder="Enterprise Azure"
                            )
                            az_tenant_id = st.text_input(
                                "Azure Tenant ID (UUID)",
                                placeholder="00000000-0000-0000-0000-000000000000",
                            )
                            az_sub_id = st.text_input(
                                "Subscription ID (UUID)",
                                placeholder="00000000-0000-0000-0000-000000000000",
                            )
                            az_client_id = st.text_input(
                                "Client ID (UUID)",
                                placeholder="00000000-0000-0000-0000-000000000000",
                            )
                            az_client_secret = st.text_input(
                                "Client Secret",
                                type="password",
                                placeholder="Enter client secret",
                            )

                            az_submit = st.form_submit_button(
                                "Register & Save Azure Source", type="primary"
                            )
                            if az_submit:
                                try:
                                    service = live_source_service()
                                    new_src = service.create(
                                        ctx,
                                        provider="azure",
                                        display_name=az_name,
                                        configuration={
                                            "tenant_id": az_tenant_id.strip(),
                                            "subscription_id": az_sub_id.strip(),
                                            "client_id": az_client_id.strip(),
                                        },
                                        secrets={"client_secret": az_client_secret.strip()},
                                    )
                                    st.success(f"Azure source **{new_src['display_name']}** added.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Failed to create Azure source: {exc}")

                    elif provider_choice == "Microsoft 365 / Entra ID":
                        with st.form("add_m365_source_form"):
                            st.caption("Configure M365 / Entra ID access using Service Principal")
                            m365_name = st.text_input(
                                "Source Display Name", placeholder="Corporate Microsoft 365"
                            )
                            m365_tenant_id = st.text_input(
                                "Microsoft Tenant ID (UUID)",
                                placeholder="00000000-0000-0000-0000-000000000000",
                            )
                            m365_client_id = st.text_input(
                                "Client / App ID (UUID)",
                                placeholder="00000000-0000-0000-0000-000000000000",
                            )
                            m365_client_secret = st.text_input(
                                "Client Secret",
                                type="password",
                                placeholder="Enter client secret",
                            )

                            m365_submit = st.form_submit_button(
                                "Register & Save M365 Source", type="primary"
                            )
                            if m365_submit:
                                try:
                                    service = live_source_service()
                                    new_src = service.create(
                                        ctx,
                                        provider="m365",
                                        display_name=m365_name,
                                        configuration={
                                            "tenant_id": m365_tenant_id.strip(),
                                            "client_id": m365_client_id.strip(),
                                        },
                                        secrets={"client_secret": m365_client_secret.strip()},
                                    )
                                    st.success(f"M365 source **{new_src['display_name']}** added.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Failed to create M365 source: {exc}")

    with tab_overview:
        kpis = ConnectorService.get_connector_kpis()
        cols = st.columns(4)
        cols[0].metric("Connected Connectors", kpis["Connected Connectors"])
        cols[1].metric("Assets Synced", f"{kpis['Assets Synced']:,}")
        cols[2].metric("Daily Syncs", kpis["Daily Syncs"])
        cols[3].metric("Product Readiness", kpis["Product Readiness"])

        st.divider()
        st.subheader("Connector Health")
        _show_dataframe(ConnectorService.connector_dataframe(), "No connectors are registered.")

        st.divider()
        left, right = st.columns([1, 1])
        with left:
            st.subheader("Customer Activation Flow")
            _show_dataframe(
                pd.DataFrame(ConnectorService.get_enablement_flow()),
                "No activation flow is available.",
            )

        with right:
            st.subheader("Executive Narrative")
            st.info(ConnectorService.get_executive_narrative())


if __name__ == "__main__":
    main()

