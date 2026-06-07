from importlib import import_module, reload

from importlib import import_module, reload




PAGE_ROUTES = {
    "Admin Dashboard": ("Dev.views.admin_dashboard", "main"),
    "Account Management": ("Dev.views.account_management", "main"),
    "CEO Dashboard": ("Dev.views.ceo_dashboard", "main"),
    "CTO Dashboard": ("Dev.views.cto_dashboard", "main"),
    "FinOps Dashboard": ("Dev.views.finops_dashboard", "main"),
    "Service Detail": ("Dev.views.service_detail", "main"),
    "Cost Explorer": ("Dev.views.cost_explorer", "main"),
    "Cloud Accounts": ("Dev.views.cloud_accounts", "cloud_accounts_page"),
}



# -----------------------
# 🎯 ROUTER (CLEAN)
# -----------------------
import streamlit as st
try:
    from views.data_loader import load_cost_data, get_data_status, get_last_updated
except ImportError:
    def load_cost_data(*args, **kwargs):
        return {}
    def get_data_status(*args, **kwargs):
        return "Unavailable"
    def get_last_updated(*args, **kwargs):
        return "Not available"


def render_navigation():
    # Initialize variables from session state or set defaults
    client_id = st.session_state.get("client_id")
    user = st.session_state.get("user_email", "Guest")
    role = st.session_state.get("role", "Guest")

    data_payload = load_cost_data(client_id, as_frame=False) if client_id else {}
    data_status = get_data_status(data_payload) if data_payload else "Unavailable"
    last_updated = get_last_updated(data_payload) if data_payload else "Not available"

    # Header
    # All sidebar code removed. Only keep non-sidebar logic here.


# --- PAGE ROUTER ---
def route_selected_page(page_name):
    """
    Dynamically import and run the main function for the selected page.
    """
    if page_name not in PAGE_ROUTES:
        st.error(f"Page '{page_name}' not found.")
        return
    module_name, func_name = PAGE_ROUTES[page_name]
    try:
        module = import_module(module_name)
        func = getattr(module, func_name)
        func()
    except Exception as e:
        st.error(f"Failed to load page '{page_name}': {e}")
    # (Removed duplicate logout and routing code)

