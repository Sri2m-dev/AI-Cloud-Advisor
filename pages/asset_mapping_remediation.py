from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.asset_mapping_remediation_service import AssetMappingRemediationService


st.set_page_config(page_title="Asset Mapping Remediation", layout="wide")


ALLOWED_ROLES = {"super_admin", "client_admin", "cio"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Asset Mapping Remediation is available to Super Admins, Client Admins, and CIO read-only users.")
        st.stop()


def _asset_options(queue: list[dict]) -> list[str]:
    return [
        f"{row['Enterprise Asset ID']} | {row['Asset']}"
        for row in queue
    ]


def _selected_asset_uid(selected: str) -> str:
    return selected.split("|", 1)[0].strip()


def _application_names(applications: list[dict]) -> list[str]:
    names = sorted({str(row.get("app_name") or "").strip() for row in applications if row.get("app_name")})
    return names


def _cost_centers(applications: list[dict]) -> list[str]:
    centers = sorted({str(row.get("cost_center") or "").strip() for row in applications if row.get("cost_center")})
    return centers


def _owners(applications: list[dict]) -> list[str]:
    owners = sorted({str(row.get("owner_name") or "").strip() for row in applications if row.get("owner_name")})
    return owners


def _show_result(result: dict) -> None:
    if result.get("status") == "SUCCESS":
        st.success(result.get("message") or "Remediation applied.")
    else:
        st.error(result.get("message") or "Remediation failed.")

    quality = result.get("quality") or {}
    st.info(f"Updated Relationship Quality Score: {float(quality.get('score') or 0):.1f}%")


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    is_read_only = role == "cio"
    dashboard = AssetMappingRemediationService.get_dashboard(organization_id)
    queue = dashboard["queue"]
    applications = dashboard["applications"]
    quality = dashboard["quality"]
    coverage = dashboard["coverage"]

    st.title("Asset Mapping Remediation")
    st.caption("Governance workflow for closing discovery, ownership, application, and cost mapping gaps.")
    if is_read_only:
        st.info("Read-only view. Remediation actions are restricted to Client Admins and Super Admins.")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Relationship Quality", f"{float(quality.get('score') or 0):.1f}%")
    k2.metric("Relationship Coverage", f"{float(coverage.get('coverage_percent') or 0):.1f}%")
    k3.metric("Open Mapping Tasks", f"{len(queue):,}")
    k4.metric("Assets in Gate", f"{int(quality.get('total_assets') or 0):,}")

    st.divider()
    st.subheader("Unmapped Asset Queue")
    if queue:
        st.dataframe(pd.DataFrame(queue), use_container_width=True, hide_index=True)
    else:
        st.success("No mapping remediation tasks are currently open.")
        return

    st.divider()
    st.subheader("Remediate Selected Asset")
    selected = st.selectbox("Asset", _asset_options(queue))
    asset_uid = _selected_asset_uid(selected)
    app_names = _application_names(applications)
    cost_centers = _cost_centers(applications)
    owner_names = _owners(applications)

    app_col, cost_col = st.columns(2)
    with app_col:
        st.markdown("#### Assign Asset to Application")
        with st.form("assign_application_form"):
            application_name = st.selectbox("Application", app_names) if app_names else st.text_input("Application")
            submitted = st.form_submit_button("Assign Application", disabled=is_read_only)
            if submitted:
                result = AssetMappingRemediationService.assign_asset_to_application(
                    asset_uid,
                    application_name,
                    organization_id,
                )
                _show_result(result)

    with cost_col:
        st.markdown("#### Assign Asset to Cost Center")
        with st.form("assign_cost_center_form"):
            cost_center_default = cost_centers[0] if cost_centers else ""
            cost_center = st.text_input("Cost Center", value=cost_center_default)
            cost_application = st.selectbox("Update Application", [""] + app_names) if app_names else ""
            submitted = st.form_submit_button("Assign Cost Center", disabled=is_read_only)
            if submitted:
                result = AssetMappingRemediationService.assign_asset_to_cost_center(
                    asset_uid,
                    cost_center,
                    organization_id,
                    application_name=cost_application or None,
                )
                _show_result(result)

    owner_col, review_col = st.columns(2)
    with owner_col:
        st.markdown("#### Assign Owner")
        with st.form("assign_owner_form"):
            owner_default = owner_names[0] if owner_names else ""
            owner_name = st.text_input("Owner Name", value=owner_default)
            owner_email = st.text_input("Owner Email")
            owner_department = st.text_input("Owner Department")
            submitted = st.form_submit_button("Assign Owner", disabled=is_read_only)
            if submitted:
                result = AssetMappingRemediationService.assign_owner(
                    asset_uid,
                    owner_name,
                    organization_id,
                    owner_email=owner_email or None,
                    owner_department=owner_department or None,
                )
                _show_result(result)

    with review_col:
        st.markdown("#### Review")
        st.write("Mark the selected asset as reviewed after all required mappings have been evaluated.")
        if st.button("Mark Reviewed", disabled=is_read_only):
            result = AssetMappingRemediationService.mark_reviewed(asset_uid, organization_id)
            _show_result(result)

    st.divider()
    latest_quality = AssetMappingRemediationService.get_quality_score(organization_id)
    st.subheader("Quality Score After Remediation")
    q1, q2, q3, q4, q5 = st.columns(5)
    q1.metric("Overall", f"{float(latest_quality.get('score') or 0):.1f}%")
    q2.metric("Relationships", f"{float(latest_quality.get('relationship_score') or 0):.1f}%")
    q3.metric("Owners", f"{float(latest_quality.get('owner_score') or 0):.1f}%")
    q4.metric("Applications", f"{float(latest_quality.get('application_mapping_score') or 0):.1f}%")
    q5.metric("Costs", f"{float(latest_quality.get('cost_mapping_score') or 0):.1f}%")


if __name__ == "__main__":
    main()
