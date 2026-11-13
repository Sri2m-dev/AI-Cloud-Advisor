import streamlit as st

from components.navigation.v1_page_link import v1_page_link
from shared.auth import require_role
from shared.styles import configure_page

_CUSTOMER_ROLES = ["client_admin", "executive", "cio", "finance", "operations", "auditor"]

configure_page(page_title="Approvals | NEXORA", page_icon=":white_check_mark:", layout="wide")
require_role(_CUSTOMER_ROLES)

st.title("Customer Approvals")
st.info(
    "Approval requests, Finance → CIO → CEO decisions, history, and evidence-linked exports "
    "are managed in the authenticated Customer Workspace."
)
v1_page_link(
    "pages/customer_workspace.py",
    label="Open Customer Workspace",
    icon=":material/workspace_premium:",
)
