from __future__ import annotations

from uuid import uuid4

import pandas as pd
import streamlit as st

from auth.authenticated_tenant import AuthenticatedTenantContext
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.data_source_control_tower_service import (
    DataSourceControlTowerService,
    SourceHealth,
)
from services.live_source_service import ADMIN_ROLES, live_source_service

st.set_page_config(page_title="Data Source Control Tower", layout="wide")


def _get_tenant_context() -> AuthenticatedTenantContext | None:
    try:
        from services.enterprise_spend_composition import authenticated_tenant_context

        return authenticated_tenant_context(st.session_state)
    except Exception:
        return None


def _safe_action(action, *args, **kwargs):
    """Never render raw service/provider exceptions, including unexpected failures."""
    try:
        return action(*args, **kwargs)
    except Exception:
        st.error("Source operation failed. Check authorization, validation and source state.")
        st.stop()


def main() -> None:
    require_login()
    role = normalize_role(st.session_state.get("role"))
    render_sidebar_navigation(role)

    st.title("Data Source Control Tower")
    st.caption("Operational monitoring, health governance, sync execution, and provenance")

    ctx = _get_tenant_context()
    is_admin = ctx is not None and ctx.role in ADMIN_ROLES
    is_operator = is_admin

    tab_tower, tab_connect = st.tabs(["Control Tower (Active Sources)", "Connect New Source"])

    with tab_tower:
        if ctx is None:
            st.error("No verified tenant context available.")
        else:
            control_service = DataSourceControlTowerService()
            try:
                sources = control_service.list_unified_sources(ctx)
            except Exception:
                sources = ()
                st.warning("Could not load sources. Check configuration and authorization.")

            # Top KPI metrics
            kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
            total_sources = len(sources)
            healthy_count = sum(1 for s in sources if s.health == SourceHealth.HEALTHY)
            failing_count = sum(1 for s in sources if s.health == SourceHealth.FAILED)
            total_records = sum(s.records_ingested for s in sources)

            kpi_c1.metric("Connected Sources", total_sources)
            kpi_c2.metric("Healthy Sources", healthy_count)
            kpi_c3.metric("Failing / Error", failing_count)
            kpi_c4.metric("Records Ingested", f"{total_records:,}")

            st.divider()

            if not sources:
                st.info("No data sources are registered for this tenant.")
            else:
                st.subheader("Data Source Inventory")
                for src in sources:
                    exp_title = (
                        f"**{src.display_name}** — Provider: `{src.provider.upper()}` "
                        f"| Health: `{src.health.value}`"
                    )
                    with st.expander(
                        exp_title,
                        expanded=(src.health in {SourceHealth.FAILED, SourceHealth.DEGRADED}),
                    ):
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            st.write(f"**Source ID:** `{src.source_id[:8]}...`")
                            st.write(f"**Type:** `{src.source_type}`")
                            st.write(f"**Active:** {'Yes' if src.active else 'No'}")
                        with c2:
                            health_color = {
                                SourceHealth.HEALTHY: "green",
                                SourceHealth.DEGRADED: "orange",
                                SourceHealth.FAILED: "red",
                                SourceHealth.NEVER_SYNCED: "gray",
                                SourceHealth.DISABLED: "gray",
                                SourceHealth.STALE: "orange",
                                SourceHealth.UNKNOWN: "gray",
                            }.get(src.health, "gray")
                            st.markdown(f"**Health:** :{health_color}[● {src.health.value}]")
                            st.write(f"**Freshness:** `{src.freshness.value}`")
                            if src.safe_error_summary:
                                st.caption(f"Error: {src.safe_error_summary}")
                        with c3:
                            sync_val = src.last_sync_at[:19] if src.last_sync_at else "Never"
                            succ_val = src.last_success_at[:19] if src.last_success_at else "Never"
                            st.write(f"**Last Sync:** {sync_val}")
                            st.write(f"**Last Success:** {succ_val}")
                            st.write(f"**Latest Status:** {src.last_sync_status}")
                            st.write(f"**Discovered:** {src.records_discovered:,}")
                            st.write(f"**Ingested:** {src.records_ingested:,} records")
                            st.write(f"**Rejected:** {src.records_rejected:,}")
                        with c4:
                            sched = (
                                f"Every {src.cadence_seconds // 60} minutes"
                                if src.schedule_enabled
                                else "Disabled"
                            )
                            next_val = src.next_run_at[:19] if src.next_run_at else "N/A"
                            st.write(f"Schedule: {sched}")
                            st.write(f"Next Run: {next_val}")
                            st.write(f"Provenance: `{src.provenance_reference}`")

                        # Actions Row
                        if is_operator:
                            st.markdown("##### Operational Actions")
                            btn_c1, btn_c2, btn_c3, _ = st.columns([1.5, 1.5, 2, 4])
                            with btn_c1:
                                if is_admin:
                                    if st.button(
                                        "Validate",
                                        key=f"val_{src.source_id}",
                                        disabled=src.connection_status in {"ACTIVE", "VALIDATING"},
                                    ):
                                        with st.spinner("Validating..."):
                                            svc = _safe_action(live_source_service)
                                            res = _safe_action(
                                                svc.validate_connection, ctx, src.source_id
                                            )
                                            if res.get("status") == "READY":
                                                st.success("Validated successfully!")
                                            else:
                                                st.error("Validation failed.")
                                            st.rerun()
                            with btn_c2:
                                if is_admin:
                                    if src.active:
                                        if st.button("Disable", key=f"dis_{src.source_id}"):
                                            _safe_action(
                                                control_service.toggle_source_active,
                                                ctx,
                                                src.source_id,
                                                False,
                                            )
                                            st.info("Source disabled.")
                                            st.rerun()
                                    else:
                                        if st.button(
                                            "Activate",
                                            key=f"act_{src.source_id}",
                                            disabled=src.connection_status != "READY",
                                        ):
                                            try:
                                                _safe_action(
                                                    control_service.toggle_source_active,
                                                    ctx,
                                                    src.source_id,
                                                    True,
                                                )
                                                st.success("Source activated!")
                                                st.rerun()
                                            except Exception:
                                                st.error(
                                                    "Activation failed. Validate the source first."
                                                )
                            with btn_c3:
                                if src.active:
                                    if st.button(
                                        "Sync Now", key=f"sync_{src.source_id}", type="primary"
                                    ):
                                        with st.spinner("Executing governed sync..."):
                                            sync_res = _safe_action(
                                                control_service.trigger_manual_sync,
                                                ctx,
                                                src.source_id,
                                                request_key=f"manual:{uuid4()}",
                                            )
                                            if sync_res.get("status") == "SUCCEEDED":
                                                st.success("Synced successfully!")
                                            else:
                                                st.error("Sync failed.")
                                            st.rerun()

                        # Recent Execution History
                        history = _safe_action(
                            control_service.get_execution_history, ctx, src.source_id
                        )
                        if history:
                            st.markdown("##### Recent Execution Runs")
                            hist_rows = [
                                {
                                    "Execution ID": h.execution_id[:8] + "...",
                                    "Trigger": h.trigger_type.upper(),
                                    "Status": h.status,
                                    "Discovered": h.records_discovered,
                                    "Ingested": h.records_ingested,
                                    "Rejected": h.records_rejected,
                                    "Started": h.started_at[:19] if h.started_at else "-",
                                    "Completed": h.completed_at[:19] if h.completed_at else "-",
                                    "Error": h.safe_error_summary or "None",
                                    "Evidence": h.evidence_reference or "None",
                                }
                                for h in history[:5]
                            ]
                            st.dataframe(
                                pd.DataFrame(hist_rows),
                                use_container_width=True,
                                hide_index=True,
                            )

    with tab_connect:
        if is_admin:
            st.subheader("Connect New Cloud or SaaS Source")
            with st.expander("➕ Add Data Source (AWS, Azure, M365)", expanded=False):
                provider_choice = st.radio(
                    "Provider", ["AWS", "Azure", "Microsoft 365 / Entra ID"], horizontal=True
                )

                if provider_choice == "AWS":
                    with st.form("add_aws_source_form", clear_on_submit=True):
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
                            except Exception:
                                st.error("AWS registration failed. Check configuration.")

                elif provider_choice == "Azure":
                    with st.form("add_azure_source_form", clear_on_submit=True):
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
                            except Exception:
                                st.error("Azure registration failed. Check configuration.")

                elif provider_choice == "Microsoft 365 / Entra ID":
                    with st.form("add_m365_source_form", clear_on_submit=True):
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
                            except Exception:
                                st.error("M365 registration failed. Check configuration.")


if __name__ == "__main__":
    main()
