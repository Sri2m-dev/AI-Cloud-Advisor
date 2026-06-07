import os
import sys
import streamlit as st
from shared.session import init_session
from shared.styles import configure_page
from components.sidebar import render_sidebar

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

configure_page(page_title="SaaS Governance | AI Cloud Advisor", page_icon=":cloud:")

init_session()

from shared.auth import require_role

require_role([
    "executive",
    "technical",
    "finance",
    "super_admin",
])

render_sidebar(role=st.session_state.get("role", "Unknown"))

from components.layout import render_page_header, render_section

from services.saas_service import (
    get_saas_license_utilization,
    get_inactive_saas_users,
    get_duplicate_saas_tools,
    get_renewal_forecasting,
    get_vendor_cost_trends,
)
from components.tables import data_table

render_page_header("SaaS Governance", "Optimize SaaS spend, utilization, and vendor management")

org_id = st.session_state.get("organization_id")

render_section("License Utilization")
license_util_resp = get_saas_license_utilization(org_id)
if not license_util_resp["success"]:
    st.warning(f"Error: {license_util_resp.get('errors', 'Unknown error')}")
data_table(license_util_resp["data"])

render_section("Inactive Users")
inactive_users_resp = get_inactive_saas_users(org_id)
if not inactive_users_resp["success"]:
    st.warning(f"Error: {inactive_users_resp.get('errors', 'Unknown error')}")
data_table(inactive_users_resp["data"])

render_section("Duplicate SaaS Tools")
duplicates_resp = get_duplicate_saas_tools(org_id)
if not duplicates_resp["success"]:
    st.warning(f"Error: {duplicates_resp.get('errors', 'Unknown error')}")
data_table(duplicates_resp["data"])

render_section("Renewal Forecasting")
renewals_resp = get_renewal_forecasting(org_id)
if not renewals_resp["success"]:
    st.warning(f"Error: {renewals_resp.get('errors', 'Unknown error')}")
data_table(renewals_resp["data"])

render_section("Vendor Cost Trends")
vendor_trends_resp = get_vendor_cost_trends(org_id)
if not vendor_trends_resp["success"]:
    st.warning(f"Error: {vendor_trends_resp.get('errors', 'Unknown error')}")
data_table(vendor_trends_resp["data"])

