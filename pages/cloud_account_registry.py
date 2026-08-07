"""Authoritative, tenant-scoped multi-cloud account registry."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.cloud_account_registry_composition import cloud_account_registry_service
from services.cloud_account_registry_service import RegistryValidationError
from services.enterprise_spend_composition import authenticated_tenant_context
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

configure_page(page_title="Cloud Account Registry | Nexora", page_icon="cloud")
init_session()
require_role(
    ["super_admin", "client_admin", "executive", "cio", "finance", "operations", "auditor"]
)
context = authenticated_tenant_context(st.session_state)
service = cloud_account_registry_service()
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
            "Unknown Accounts",
            "Pending Review",
            "Partially Mapped",
            "Ready for Approval",
            "Approved",
            "Quarantined Spend",
            "Resolved Spend",
            "Allocation Coverage",
        ],
        [
            "unknown",
            "pending_review",
            "partially_mapped",
            "ready_for_approval",
            "approved",
            "quarantined_spend",
            "resolved_spend",
            "allocation_coverage",
        ],
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
        unresolved = [
            row for row in rows if row.get("mapping_status") == "unknown" and not row.get("id")
        ]
        if permissions["resolve"] and unresolved:
            with st.expander("Account Resolution", expanded=True):
                target = st.selectbox(
                    "Discovered account",
                    unresolved,
                    format_func=lambda row: (
                        f"AWS {row.get('account_id')} · "
                        f"{row.get('quarantined_spend')} {row.get('currency')}"
                    ),
                )
                st.json(
                    {
                        key: target.get(key)
                        for key in (
                            "provider",
                            "account_id",
                            "payer_account_id",
                            "source_import_id",
                            "first_seen_at",
                            "last_seen_at",
                            "billing_period",
                            "quarantined_spend",
                            "currency",
                        )
                    }
                )
                with st.form("account-resolution-form"):
                    account_name = st.text_input("Account Name")
                    alias = st.text_input("Alias")
                    environment_resolution = st.text_input("Environment")
                    business_unit_resolution = st.text_input("Business Unit")
                    department_resolution = st.text_input("Department")
                    application_resolution = st.text_input("Application")
                    business_service_resolution = st.text_input("Business Service")
                    owner_resolution = st.text_input("Owner")
                    technical_owner_resolution = st.text_input("Technical Owner")
                    finance_owner_resolution = st.text_input("Finance Owner")
                    cost_center_resolution = st.text_input("Cost Center")
                    project_code = st.text_input("Project Code")
                    criticality = st.selectbox(
                        "Criticality", ["", "low", "medium", "high", "critical"]
                    )
                    resolution_states = ["PENDING_REVIEW", "PARTIALLY_MAPPED", "READY_FOR_APPROVAL"]
                    if permissions["approve"]:
                        resolution_states += ["APPROVED", "ACTIVE", "REJECTED"]
                    resolution_status = st.selectbox("Resolution Status", resolution_states)
                    effective_date = st.date_input("Effective Date")
                    resolution_reason = st.text_input("Resolution Reason")
                    resolution_confirmed = st.checkbox(
                        "I explicitly confirm this governed account resolution"
                    )
                    if st.form_submit_button("Resolve Account"):
                        try:
                            service.resolve_discovered(
                                context,
                                target,
                                {
                                    "account_name": account_name,
                                    "alias": alias,
                                    "environment": environment_resolution,
                                    "business_unit": business_unit_resolution,
                                    "department": department_resolution,
                                    "application": application_resolution,
                                    "business_service": business_service_resolution,
                                    "owner": owner_resolution,
                                    "technical_owner": technical_owner_resolution,
                                    "finance_owner": finance_owner_resolution,
                                    "cost_center": cost_center_resolution,
                                    "project_code": project_code,
                                    "criticality": criticality,
                                    "effective_date": effective_date.isoformat(),
                                    "resolution_status": resolution_status,
                                },
                                reason=resolution_reason,
                                confirmed=resolution_confirmed,
                            )
                            st.success("Account resolution committed")
                            st.rerun()
                        except (RegistryValidationError, PermissionError) as exc:
                            st.error(str(exc))

                bulk_targets = st.multiselect(
                    "Bulk review accounts",
                    unresolved,
                    format_func=lambda row: f"AWS {row.get('account_id')}",
                )
                bulk_business_unit = st.text_input("Bulk Business Unit")
                bulk_environment = st.text_input("Bulk Environment")
                bulk_reason = st.text_input("Bulk Resolution Reason")
                bulk_confirmed = st.checkbox("I confirm the previewed bulk changes")
                if bulk_targets:
                    bulk_preview = service.preview_bulk_resolution(
                        context,
                        bulk_targets,
                        {
                            "business_unit": bulk_business_unit,
                            "environment": bulk_environment,
                            "resolution_status": "PENDING_REVIEW",
                        },
                    )
                    st.write(
                        {
                            "Affected accounts": bulk_preview["count"],
                            "Affected spend": bulk_preview["quarantined_spend"],
                            "Changes": bulk_preview["changes"],
                        }
                    )
                    if st.button("Commit Bulk Review"):
                        try:
                            service.commit_bulk_resolution(
                                context, bulk_preview, reason=bulk_reason, confirmed=bulk_confirmed
                            )
                            st.success("Bulk review committed atomically")
                            st.rerun()
                        except (RegistryValidationError, PermissionError) as exc:
                            st.error(str(exc))
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
            (
                service.repository.version_history(context, selected["id"])
                if selected.get("id") and hasattr(service.repository, "version_history")
                else service.repository.audit_history(context, selected["id"])
                if selected.get("id")
                else []
            )
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
        if permissions["resolve"] and selected.get("id"):
            with st.expander("Correct, suspend, or reopen mapping"):
                correction_owner = st.text_input(
                    "Corrected Owner", value=str(selected.get("owner") or "")
                )
                correction_cost_center = st.text_input(
                    "Corrected Cost Center", value=str(selected.get("cost_center") or "")
                )
                correction_reason = st.text_input("Correction Reason")
                correction_confirmed = st.checkbox("I confirm this governed lifecycle change")
                lifecycle_action = st.selectbox("Governed Action", ["Correct", "Suspend", "Reopen"])
                if st.button("Apply Governed Change"):
                    requested_state = {
                        "Correct": selected.get("resolution_status") or "PENDING_REVIEW",
                        "Suspend": "SUSPENDED",
                        "Reopen": "PENDING_REVIEW",
                    }[lifecycle_action]
                    corrected = {
                        key: selected.get(key)
                        for key in (
                            "account_name",
                            "alias",
                            "environment",
                            "business_unit",
                            "department",
                            "application",
                            "business_service",
                            "technical_owner",
                            "finance_owner",
                            "project_code",
                            "criticality",
                        )
                    }
                    corrected.update(
                        owner=correction_owner,
                        cost_center=correction_cost_center,
                        resolution_status=requested_state,
                    )
                    try:
                        service.resolve_discovered(
                            context,
                            selected,
                            corrected,
                            reason=correction_reason,
                            confirmed=correction_confirmed,
                            expected_state=str(selected.get("resolution_status") or "DISCOVERED"),
                        )
                        st.success("Governed lifecycle change committed")
                        st.rerun()
                    except (RegistryValidationError, PermissionError) as exc:
                        st.error(str(exc))


render_page(
    title="Cloud Account Registry",
    description=(
        "Authoritative governed inventory for AWS accounts, Azure subscriptions, "
        "and GCP projects."
    ),
    content=content,
)
