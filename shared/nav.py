import streamlit as st

# Maps menu label -> (page path relative to Dev/, icon)
_PAGE_MAP = {
    "CEO Dashboard":      ("pages/ceo_dashboard.py",      "👑"),
    "CTO Dashboard":      ("pages/cto_dashboard.py",      "🧑‍💻"),
    "FinOps Dashboard":   ("pages/finops_dashboard.py",   "💼"),
    "Cloud Accounts":     ("pages/cloud_accounts.py",     "☁️"),
    "Cost Explorer":      ("pages/cost_explorer.py",      "💰"),
    "Recommendations":    ("pages/recommendations.py",    "💡"),
    "Multi-Cloud Compare":("pages/multi_cloud_compare.py", "🌐"),
    "Multi-Cloud Advisor":("pages/multi_cloud_advisor.py", "🚀"),
    "Compliance":         ("pages/compliance.py",         "🔒"),
    "Privacy":            ("pages/privacy.py",            "🔒"),
}

_ROLE_PAGES = {
    "CEO": [
        "CEO Dashboard",
        "Recommendations",
        "Multi-Cloud Compare",
        "Multi-Cloud Advisor",
        "Compliance",
    ],
    "CTO": [
        "CTO Dashboard",
        "Cloud Accounts",
        "Cost Explorer",
        "Recommendations",
        "Multi-Cloud Compare",
        "Multi-Cloud Advisor",
    ],
    "FinOps": [
        "FinOps Dashboard",
        "Cost Explorer",
        "Recommendations",
        "Multi-Cloud Compare",
        "Multi-Cloud Advisor",
    ],
}


def render_global_styles() -> None:
    st.markdown("""
    <style>
    .main {
        background-color: #f5f7fb;
    }

    section[data-testid="stSidebar"] {
        background: #111827;
        color: white;
    }

    section[data-testid="stSidebar"] * {
        color: white !important;
    }

    .header-bar {
        background: white;
        padding: 15px 25px;
        border-radius: 10px;
        margin-bottom: 15px;
        box-shadow: 0px 2px 8px rgba(0,0,0,0.05);
    }

    .profile-box {
        background: white;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
    }

    .kpi-card {
        padding: 18px;
        border-radius: 12px;
        color: white;
        font-weight: 600;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.08);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        cursor: pointer;
    }

    .kpi-card:hover {
        transform: translateY(-4px);
        box-shadow: 0px 8px 20px rgba(0,0,0,0.15);
    }

    .kpi-blue { background: linear-gradient(135deg, #4facfe, #00f2fe); }
    .kpi-purple { background: linear-gradient(135deg, #667eea, #764ba2); }
    .kpi-green { background: linear-gradient(135deg, #43e97b, #38f9d7); }
    .kpi-orange { background: linear-gradient(135deg, #f7971e, #ffd200); }

    .section-card {
        background: white;
        padding: 20px;
        border-radius: 12px;
        margin-top: 20px;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.06);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .section-card:hover {
        transform: translateY(-2px);
        box-shadow: 0px 8px 18px rgba(0,0,0,0.10);
    }
    </style>
    """, unsafe_allow_html=True)


def render_header_bar() -> None:
    import pandas as pd

    st.markdown(f"""
    <div class="header-bar">
        <b>📅 {pd.Timestamp.today().strftime("%B %d, %Y")}</b>
        <span style="float:right;">👤 {st.session_state.get("user_email", "")}</span>
    </div>
    """, unsafe_allow_html=True)


def require_role(required_role: str) -> None:
    if st.session_state.get("role") != required_role:
        st.error("⛔ Access Denied")
        st.stop()


def show_ceo_dashboard() -> None:
    import pandas as pd
    from shared.queries import get_recommendations, get_usage_metrics

    render_global_styles()
    render_header_bar()

    st.title("👑 CEO Dashboard")
    st.caption("Executive Cloud Cost Overview")

    # -----------------------
    # FETCH DATA
    # -----------------------
    usage = st.session_state.get("usage_df", pd.DataFrame())
    reco = st.session_state.get("reco_df", pd.DataFrame())
    cost_df = st.session_state.get("cost_df", pd.DataFrame())

    if usage.empty and st.session_state.get("client_id"):
        usage = get_usage_metrics(st.session_state.get("client_id"))
        st.session_state["usage_df"] = usage

    if reco.empty:
        reco = get_recommendations(st.session_state.get("client_id"))
        st.session_state["reco_df"] = reco

    if not usage.empty and "cost" not in usage.columns and "utilization" in usage.columns:
        usage = usage.copy()
        usage["cost"] = usage["utilization"] * 0.5  # simple model

    # -----------------------
    # KPI CALCULATIONS
    # -----------------------
    avg_util = int(usage["utilization"].mean()) if not usage.empty and "utilization" in usage.columns else 0
    monthly_spend = float(usage["cost"].sum()) if not usage.empty and "cost" in usage.columns else 0
    yearly_projection = monthly_spend * 12
    savings = 3200 if not reco.empty else 0

    # -----------------------
    # KPI ROW
    # -----------------------
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="kpi-card kpi-blue">
            Monthly Spend<br><h2>${monthly_spend}</h2>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="kpi-card kpi-purple">
            Yearly Projection<br><h2>${yearly_projection}</h2>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="kpi-card kpi-green">
            Avg Utilization<br><h2>{avg_util}%</h2>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="kpi-card kpi-orange">
            Savings Opportunity<br><h2>${savings}</h2>
        </div>
        """, unsafe_allow_html=True)

    # -----------------------
    # INSIGHT BANNER
    # -----------------------
    st.info("⚠️ High cost detected in EC2 | 💡 Optimization opportunity available")

    # -----------------------
    # SPENDING TREND
    # -----------------------
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("### 📈 Spending Trend (Last 3 Months)")

    trend = pd.DataFrame({
        "Month": ["Jan", "Feb", "Mar"],
        "Actual Spend": [5000, 6500, 6000],
        "Optimized Spend": [4500, 5200, 4800]
    })

    st.line_chart(trend.set_index("Month"))

    if not usage.empty and {"service", "cost"}.issubset(usage.columns):
        top_service = usage.groupby("service")["cost"].sum().idxmax()
        st.info(f"💡 Highest cost contributor: {top_service}")

    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------
    # COST BY SERVICE
    # -----------------------
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("💰 Cost by Service")

    if not cost_df.empty and "service" in cost_df.columns:
        st.bar_chart(cost_df.set_index("service"))
    else:
        st.warning("No cost data available")

    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------
    # COST BY PROVIDER
    # -----------------------
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("🌐 Cost by Provider")

    if not cost_df.empty and {"provider", "cost"}.issubset(cost_df.columns):
        provider_data = cost_df.groupby("provider")["cost"].sum()
        st.bar_chart(provider_data)
    else:
        st.warning("No provider cost data available")

    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------
    # AI INSIGHTS
    # -----------------------
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("🧠 AI Insights")

    if not reco.empty:
        if "title" in reco.columns:
            for i, row in reco.iterrows():
                title = row.get("title", f"Recommendation {i + 1}")
                status = str(row.get("status", "Pending") or "Pending")
                normalized_status = status.strip().lower().replace(" ", "_")

                with st.container(border=True):
                    st.write(f"💡 {title}")

                    details = []
                    if "resource" in reco.columns and pd.notna(row.get("resource")):
                        details.append(f"Resource: {row.get('resource')}")
                    if "savings" in reco.columns and pd.notna(row.get("savings")):
                        try:
                            details.append(f"Estimated savings: ${float(row.get('savings')):,.0f}/mo")
                        except (TypeError, ValueError):
                            details.append(f"Estimated savings: {row.get('savings')}")
                    if details:
                        st.caption(" • ".join(details))

                    if normalized_status in {"pending", "open", "pending_approval"}:
                        st.warning("Status: Pending")
                    elif normalized_status == "approved":
                        st.info("Status: Approved")
                    elif normalized_status in {"completed", "success"}:
                        st.success("Status: Completed")
                    elif normalized_status in {"running", "queued"}:
                        st.info(f"Status: {status.replace('_', ' ').title()}")
                    else:
                        st.caption(f"Status: {status}")
        else:
            st.write(reco)
    else:
        st.write("No recommendations available")

    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------
    # UTILIZATION CHART
    # -----------------------
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("📊 Utilization Overview")

    if not usage.empty and "utilization" in usage.columns:
        st.line_chart(usage["utilization"])
    else:
        st.write("No data available")

    st.markdown('</div>', unsafe_allow_html=True)


def show_cto_dashboard() -> None:
    import pandas as pd

    render_global_styles()
    render_header_bar()

    usage = st.session_state.get("usage_df", pd.DataFrame())

    st.title("🛠 CTO Dashboard")
    st.caption("Infrastructure & System Overview")

    # -----------------------
    # KPI CARDS
    # -----------------------
    total = len(usage)
    avg = int(usage["utilization"].mean()) if not usage.empty and "utilization" in usage.columns else 0
    services = usage["service"].nunique() if not usage.empty and "service" in usage.columns else 0

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Resources", total)
    col2.metric("Avg Utilization", f"{avg}%")
    col3.metric("Services", services)

    # -----------------------
    # ALERT CARD
    # -----------------------
    st.markdown("### ⚠️ System Alerts")

    if not usage.empty and {"utilization", "resource"}.issubset(usage.columns):
        high = usage[usage["utilization"] > 80]
        if not high.empty:
            for _, row in high.iterrows():
                st.warning(f"{row['resource']} at {row['utilization']}%")
        else:
            st.success("All systems healthy")
    else:
        st.info("No alert data available")

    # -----------------------
    # INFRA TABLE
    # -----------------------
    st.markdown("### 🔍 Infrastructure Usage")

    if not usage.empty:
        st.dataframe(usage, use_container_width=True)
    else:
        st.info("No infrastructure data available")

    # -----------------------
    # SERVICE CHART
    # -----------------------
    st.markdown("### 📊 Service Distribution")

    if not usage.empty and "service" in usage.columns:
        st.bar_chart(usage["service"].value_counts())
    else:
        st.info("No service data available")


def show_finops_dashboard() -> None:
    import pandas as pd

    render_global_styles()
    render_header_bar()

    st.title("💰 FinOps Dashboard")
    st.caption("Cost Optimization & Financial Insights")

    usage = st.session_state.get("usage_df", pd.DataFrame())
    reco = st.session_state.get("reco_df", pd.DataFrame())

    # -----------------------
    # KPIs
    # -----------------------
    monthly_spend = 6500
    potential_savings = 3200 if not reco.empty else 0
    optimization_count = len(reco)

    col1, col2, col3 = st.columns(3)

    col1.metric("Monthly Spend", f"${monthly_spend}")
    col2.metric("Potential Savings", f"${potential_savings}")
    col3.metric("Optimization Actions", optimization_count)

    # -----------------------
    # COST BREAKDOWN
    # -----------------------
    st.subheader("📊 Cost Breakdown")

    if not usage.empty and {"service", "cost"}.issubset(usage.columns):
        cost_by_service = usage.groupby("service")["cost"].sum()
        st.bar_chart(cost_by_service)
    else:
        st.write("No data available")

    # -----------------------
    # COST ANOMALIES
    # -----------------------
    st.subheader("🚨 Cost Anomalies")

    if not usage.empty and "cost" in usage.columns:
        threshold = usage["cost"].mean() * 1.5
        anomalies = usage[usage["cost"] > threshold]

        if not anomalies.empty:
            for _, row in anomalies.iterrows():
                service_name = row["service"] if "service" in anomalies.columns else "Unknown Service"
                st.error(f"High cost anomaly in {service_name} ({row['cost']})")
        else:
            st.success("No anomalies detected")
    else:
        st.info("No cost data available")

    # -----------------------
    # SAVINGS OPPORTUNITIES
    # -----------------------
    st.subheader("💡 Optimization Opportunities")

    if not reco.empty:
        if "title" in reco.columns:
            for _, row in reco.iterrows():
                st.info(f"{row['title']}")
        else:
            st.write(reco)
    else:
        st.write("No recommendations available")

    # -----------------------
    # COST TREND (SIMULATED)
    # -----------------------
    st.subheader("📈 Cost Trend")

    trend_data = pd.DataFrame({
        "Month": ["Jan", "Feb", "Mar"],
        "Cost": [5000, 6500, 6000]
    })

    st.line_chart(trend_data.set_index("Month"))


def show_cloud_accounts() -> None:
    st.switch_page("pages/cloud_accounts.py")


def show_cost_explorer() -> None:
    st.switch_page("pages/cost_explorer.py")


def show_recommendations() -> None:
    st.switch_page("pages/recommendations.py")


def show_compliance() -> None:
    st.switch_page("pages/compliance.py")


def show_privacy() -> None:
    st.switch_page("pages/privacy.py")


def route_selected_page(selected_page: str) -> None:
    # -----------------------
    # PAGE ROUTING
    # -----------------------
    if selected_page == "CEO Dashboard":
        show_ceo_dashboard()

    elif selected_page == "CTO Dashboard":
        show_cto_dashboard()

    elif selected_page == "FinOps Dashboard":
        show_finops_dashboard()

    elif selected_page == "Cloud Accounts":
        show_cloud_accounts()

    elif selected_page == "Cost Explorer":
        show_cost_explorer()

    elif selected_page == "Recommendations":
        show_recommendations()

    elif selected_page == "Compliance":
        show_compliance()

    elif selected_page == "Privacy":
        show_privacy()


def render_sidebar(current_page: str) -> None:
    role = st.session_state.get("role", "")
    allowed_pages = _ROLE_PAGES.get(role, [])

    render_global_styles()

    with st.sidebar:
        st.image("https://via.placeholder.com/150", width=120)
        st.markdown("### ☁️ Cloud Advisory")
        st.markdown(
            f"""
            **👤 User:** {st.session_state.get('user_email', '')}  
            **🔐 Role:** {st.session_state.get('role', '')}
            """
        )

        ai_mode = st.toggle("🔐 AI Safety Mode", value=st.session_state.get("ai_safe_mode", True))
        st.session_state["ai_safe_mode"] = ai_mode

        auto_mode = st.toggle("⚙️ Autonomous Mode", value=st.session_state.get("auto_mode", False))
        st.session_state["auto_mode"] = auto_mode

        st.markdown("---")

        if not allowed_pages:
            st.warning("No pages available for this role.")
        else:
            pages = [current_page] + [page for page in allowed_pages if page != current_page]
            selected_page = st.radio(
                "Navigation",
                pages,
                index=0,
            )

            if selected_page != current_page:
                route_selected_page(selected_page)

        st.markdown("---")
        if st.button("🚪 Logout", key="nav_logout", use_container_width=True):
            st.session_state.clear()
            st.switch_page("app.py")
