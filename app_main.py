import streamlit as st

from auth.role_constants import normalize_role
from auth.v1_route_policy import allowed_page_specs
from components.sidebar_navigation import DEFAULT_ROLE_PAGE, PAGE_PATHS, ROLE_PAGES
from services.universal_evidence_runtime_service import initialize_universal_evidence_runtime

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login_page = st.Page("pages/login.py", title="Login", url_path="login", default=True)
    st.navigation([login_page], position="hidden").run()
else:
    role = normalize_role(st.session_state.get("role", ""))
    page_specs = allowed_page_specs(
        role,
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
    )
    default_path = (
        PAGE_PATHS.get("Customer Workspace")
        if role in {"client_admin", "executive", "cio", "finance", "operations", "auditor"}
        else DEFAULT_ROLE_PAGE.get(role)
    )
    if default_path not in {page_path for _, page_path in page_specs}:
        default_path = page_specs[0][1] if page_specs else None
    pages = []
    for title, page_path in page_specs:
        page_arguments = {
            "title": title,
            "url_path": page_path[6:-3],
        }
        if page_path == default_path:
            page_arguments["default"] = True
        pages.append(st.Page(page_path, **page_arguments))
    selected_page = st.navigation(pages, position="hidden")

    if selected_page.title != "Logout":
        try:
            from services.enterprise_spend_composition import authenticated_tenant_context

            context = authenticated_tenant_context(st.session_state)
        except PermissionError as error:
            st.error(f"Authenticated tenant scope is unavailable: {error}")
            st.stop()
        if context.role != role:
            st.session_state["role"] = context.role
            st.rerun()
        initialize_universal_evidence_runtime()

    selected_page.run()
