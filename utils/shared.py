def _format_plan_history_label(plan_def):
    history_days = plan_def.get("data_history_days")
    if history_days in {None, float("inf")}:
        return "Unlimited"
    return f"Last {int(history_days)} days"

def _query_param_value(name, default=None):
    import streamlit as st
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value

def _render_workspace_header(selected_page, plan_name):
    plan_label = str(plan_name or "Starter")
    selected_page_name = str(selected_page or "")
    header_class = (
        "saas-workspace-header saas-workspace-header--tight"
        if selected_page_name == "AI Recommendations"
        else "saas-workspace-header"
    )
    html_content = (
        "<style>"
        ".saas-workspace-header {display: flex; flex-direction: row; justify-content: space-between; align-items: center; width: 100%;}"
        ".saas-workspace-title {font-size: 2.8rem; font-weight: 700; margin-bottom: 0.5rem;}"
        ".saas-workspace-meta {font-size: 1.1rem; color: #444; margin-left: auto;}"
        "</style>"
    )
    html_content += f"<div class='{header_class}'>"
    html_content += f"<div class='saas-workspace-title'>{selected_page_name}</div>"
    html_content += f"<div class='saas-workspace-meta'>Plan: {plan_label}</div>"
    html_content += "</div>"
    import streamlit as st
    st.markdown(html_content, unsafe_allow_html=True)

TERMS_OF_SERVICE_TEXT = """
By using this platform:

- You agree to data processing for cost optimization.
- You are responsible for your cloud credentials.
- We provide insights, not financial guarantees.
"""

def can_manage_recommendation(item, username, action="view"):
    # Placeholder logic, replace with actual permission logic as needed
    return True

def login_page():
    import streamlit as st
    st.markdown("## Login")
    st.info("Demo Credentials:  \n\nCEO → ceo / ceo123 \nCTO → cto / cto123")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    username = username.strip()
    password = password.strip()
    if st.button("Login"):
        # Demo users
        if username == "ceo" and password == "ceo123":
            st.session_state["logged_in"] = True
            st.session_state["role"] = "CEO"
            st.rerun()
        elif username == "cto" and password == "cto123":
            st.session_state["logged_in"] = True
            st.session_state["role"] = "CTO"
            st.rerun()
        elif username.strip() == "admin" and password.strip() == "admin123":
            st.session_state["logged_in"] = True
            st.session_state["role"] = "admin"
            st.rerun()
        else:
            st.error("Invalid credentials")
