"""Authoritative, tenant-scoped multi-cloud account registry."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from repositories.cloud_account_registry_repository import CloudAccountRegistryRepository
from services.cloud_account_registry_service import (
    CloudAccountRegistryService,
    RegistryValidationError,
)
from services.enterprise_spend_composition import (
    authenticated_tenant_context,
    enterprise_spend_service,
)
from services.supabase_client import supabase
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

configure_page(page_title="Cloud Account Registry | Nexora", page_icon="cloud")
init_session()
require_role(
    ["super_admin", "client_admin", "executive", "cio", "finance", "operations", "auditor"]
)
context = authenticated_tenant_context(st.session_state)
service = CloudAccountRegistryService(
    CloudAccountRegistryRepository(supabase), enterprise_spend_service()
)
permissions = service.permissions(context)
role = st.session_state.get("role", "viewer")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Cloud Account Registry"],
)


def content():
    data = service.dashboard(context)
    rows = data["accounts"]
    st.caption(f"Organization: {context.organization_name}")
    cols = st.columns(8)
    for col, label, key in zip(
        cols,
        [
            "Total Accounts",
            "AWS Accounts",
            "Azure Subscriptions",
            "GCP Projects",
            "Active Accounts",
            "Pending Mapping",
            "Unknown Accounts",
            "Average Governance Score",
        ],
        ["total", "aws", "azure", "gcp", "active", "pending", "unknown", "average_governance"],
    ):
        col.metric(label, data[key])
    render_section("Registry", "Search, filter, govern, and inspect tenant-owned cloud accounts.")
    search = st.text_input("Search")
    filters = st.columns(4)
    provider = filters[0].selectbox("Cloud", ["All", "aws", "azure", "gcp"])
    environment = filters[1].selectbox(
        "Environment",
        ["All"] + sorted({str(r.get("environment")) for r in rows if r.get("environment")}),
    )
    status = filters[2].selectbox(
        "Status", ["All"] + sorted({str(r.get("status")) for r in rows if r.get("status")})
    )
    minimum = filters[3].slider("Minimum governance", 0, 100, 0)
    mapping_filters = st.columns(4)
    business_unit_filter = mapping_filters[0].selectbox(
        "Business Unit",
        ["All"] + sorted({str(r.get("business_unit")) for r in rows if r.get("business_unit")}),
    )
    department_filter = mapping_filters[1].selectbox(
        "Department",
        ["All"] + sorted({str(r.get("department")) for r in rows if r.get("department")}),
    )
    owner_filter = mapping_filters[2].selectbox(
        "Owner", ["All"] + sorted({str(r.get("owner")) for r in rows if r.get("owner")})
    )
    application_filter = mapping_filters[3].selectbox(
        "Application",
        ["All"] + sorted({str(r.get("application")) for r in rows if r.get("application")}),
    )
    shown = [
        r
        for r in rows
        if (provider == "All" or r.get("provider") == provider)
        and (environment == "All" or r.get("environment") == environment)
        and (status == "All" or r.get("status") == status)
        and (business_unit_filter == "All" or r.get("business_unit") == business_unit_filter)
        and (department_filter == "All" or r.get("department") == department_filter)
        and (owner_filter == "All" or r.get("owner") == owner_filter)
        and (application_filter == "All" or r.get("application") == application_filter)
        and int(r.get("governance_score") or 0) >= minimum
        and (not search or search.lower() in " ".join(str(v) for v in r.values()).lower())
    ]
    table_controls = st.columns(3)
    sort_by = table_controls[0].selectbox(
        "Sort by",
        ["provider", "account_id", "account_name", "governance_score", "status", "updated_at"],
    )
    descending = table_controls[1].checkbox(
        "Descending", value=sort_by in {"governance_score", "updated_at"}
    )
    page_size = table_controls[2].selectbox("Rows per page", [10, 25, 50, 100])
    shown = sorted(
        shown, key=lambda row: (row.get(sort_by) is None, row.get(sort_by)), reverse=descending
    )
    page_count = max(1, (len(shown) + page_size - 1) // page_size)
    page = st.number_input("Page", min_value=1, max_value=page_count, value=1)
    visible = shown[(page - 1) * page_size : page * page_size]
    st.caption(f"Page {page} of {page_count} · {len(shown)} accounts")
    display_columns = [
        "provider",
        "account_id",
        "mapping_status",
        "ownership_status",
        "source",
        "billing_period",
        "quarantined_spend",
        "currency",
        "first_seen_at",
        "last_seen_at",
        "governance_state",
        "review_action",
    ]
    st.dataframe(
        pd.DataFrame(visible).reindex(columns=display_columns),
        use_container_width=True,
        hide_index=True,
    )
    export = st.columns(2)
    export[0].download_button(
        "Export CSV", service.export_csv(shown), "cloud-account-registry.csv", "text/csv"
    )
    export[1].download_button(
        "Export Excel", service.export_excel(shown), "cloud-account-registry.xlsx"
    )
    if permissions["edit"]:
        with st.expander("Create pending mapping or edit governed account"):
            governed_rows = [row for row in rows if row.get("id")]
            edit_target = st.selectbox(
                "Record",
                [None] + governed_rows,
                format_func=lambda r: "Create pending mapping"
                if r is None
                else f"Edit {r.get('provider','').upper()} {r.get('account_id')}",
            )
            with st.form("registry-form"):
                provider_value = st.selectbox("Provider", ["aws", "azure", "gcp"])
                account_id = st.text_input("Account ID")
                account_name = st.text_input("Account Name")
                owner = st.text_input("Owner")
                business_unit = st.text_input("Business Unit")
                department = st.text_input("Department")
                application = st.text_input("Application")
                environment_value = st.text_input("Environment")
                budget = st.number_input("Budget", min_value=0.0)
                reason = st.text_input("Reason")
                if st.form_submit_button("Save"):
                    try:
                        service.save(
                            context,
                            {
                                "provider": provider_value,
                                "account_id": account_id,
                                "account_name": account_name,
                                "owner": owner,
                                "business_unit": business_unit,
                                "department": department,
                                "application": application,
                                "environment": environment_value,
                                "budget": budget,
                            },
                            registry_id=str(edit_target["id"]) if edit_target else None,
                            reason=reason,
                        )
                        st.success("Account saved")
                        st.rerun()
                    except (RegistryValidationError, PermissionError) as exc:
                        st.error(str(exc))
        uploaded = st.file_uploader("Import CSV", type=["csv"])
        if uploaded:
            try:
                preview = service.preview_csv(context, uploaded.getvalue())
                st.write(
                    {"Valid rows": preview["valid"], "Duplicate rows": len(preview["duplicates"])}
                )
                st.dataframe(preview["rows"])
                import_reason = st.text_input("Import reason")
                if st.button("Commit import", disabled=not preview["can_commit"]):
                    service.commit_preview(context, preview, reason=import_reason)
                    st.success("Import committed")
                    st.rerun()
            except RegistryValidationError as exc:
                st.error(str(exc))
    if rows:
        selected = st.selectbox(
            "Account details",
            rows,
            format_func=lambda r: (
                f"{r.get('provider', '').upper()} · {r.get('account_id')} · "
                f"{r.get('account_name', '')}"
            ),
        )
        tabs = st.tabs(
            [
                "Overview",
                "Financial",
                "Ownership",
                "Business Mapping",
                "Applications",
                "Technology",
                "Synchronization",
                "Audit History",
            ]
        )
        tabs[0].json(selected)
        tabs[1].write(
            {
                k: selected.get(k)
                for k in (
                    "quarantined_spend",
                    "currency",
                    "billing_period",
                    "source_import_id",
                    "payer_account_id",
                )
            }
        )
        tabs[2].write(
            {
                k: selected.get(k)
                for k in ("ownership_status", "owner", "technical_owner", "finance_owner")
            }
        )
        tabs[3].write(
            {
                k: selected.get(k)
                for k in (
                    "mapping_status",
                    "business_unit",
                    "department",
                    "business_service",
                    "project",
                )
            }
        )
        tabs[4].write(selected.get("application") or "Not mapped")
        tabs[5].write(
            {
                "landing_zone": selected.get("landing_zone"),
                "health_score": selected.get("health_score"),
            }
        )
        tabs[6].write(
            {
                "source": selected.get("source"),
                "first_seen_at": selected.get("first_seen_at"),
                "last_seen_at": selected.get("last_seen_at"),
            }
        )
        tabs[7].dataframe(
            service.repository.audit_history(context, selected["id"]) if selected.get("id") else []
        )
        if selected.get("id") is None:
            st.info(
                "Discovered from AWS CUR. Review and create a pending mapping before "
                "ownership or lifecycle governance can begin."
            )
        if permissions["full"] and selected.get("id"):
            lifecycle_reason = st.text_input("Lifecycle reason")
            lifecycle = st.columns(2)
            if lifecycle[0].button("Deactivate"):
                service.transition(context, str(selected["id"]), "inactive", lifecycle_reason)
                st.rerun()
            if lifecycle[1].button("Archive"):
                service.transition(context, str(selected["id"]), "archived", lifecycle_reason)
                st.rerun()


render_page(
    title="Cloud Account Registry",
    description=(
        "Authoritative governed inventory for AWS accounts, Azure subscriptions, "
        "and GCP projects."
    ),
    content=content,
)
