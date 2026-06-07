import streamlit as st

# Shared logout utility for all pages

def logout(supabase=None):
    """
    Logs out the user from Supabase Auth and clears session state.
    Optionally pass the supabase client if available.
    """
    if supabase is not None:
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.success("You have been logged out.")
    st.rerun()


def logout_button(supabase=None, location="sidebar"):
    """
    Renders a logout button in the sidebar or main area.
    """
    if location == "sidebar":
        if st.sidebar.button("Logout", key="logout_btn"):
            logout(supabase)
    else:
        if st.button("Logout", key="logout_btn_main"):
            logout(supabase)

