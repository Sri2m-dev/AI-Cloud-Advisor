import streamlit as st

from components.navigation.v1_page_link import v1_page_link
from shared.auth import require_role
from shared.styles import configure_page

_CUSTOMER_ROLES = ["client_admin", "executive", "cio", "finance", "operations", "auditor"]

configure_page(page_title="Reports | NEXORA", page_icon=":bar_chart:", layout="wide")
require_role(_CUSTOMER_ROLES)

st.title("Evidence-linked Exports")
st.info(
    "Customer exports are generated from the canonical workflow only after the Finance, CIO, "
    "and CEO approval sequence is complete. Legacy report and schedule endpoints are not part "
    "of the V1 customer route."
)
v1_page_link(
    "pages/customer_workspace.py",
    label="Open Customer Workspace",
    icon=":material/workspace_premium:",
)
