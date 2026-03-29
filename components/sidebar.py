import streamlit as st

def render_sidebar(user_role="CEO"):
    with st.sidebar:
        st.markdown("## Cloud Advisory")

        st.markdown("""
        <div style="
            background:#2F80ED;
            color:white;
            width:50px;
            height:50px;
            display:flex;
            align-items:center;
            justify-content:center;
            border-radius:10px;
            font-weight:bold;
        ">
        AD
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"**Signed in as:** {user_role}")
        st.markdown("Company: Cloud Advisor Internal")

        st.markdown("🔒 All data stored in EU region (GDPR compliant)")

        st.markdown("---")

        st.markdown("### Go to:")
        st.radio(
            "",
            [
                "Dashboard",
                "Privacy Policy",
                "Terms of Service",
                    page = st.radio(
            ],
            key="nav_radio"
        )

        st.markdown("---")

        st.markdown("### 📊 Data Controls")

        st.button("🗑️ Delete My Data")
                    return page
        st.button("📤 Export My Data")
