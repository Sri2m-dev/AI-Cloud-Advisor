import streamlit as st
import os

# Remove yagmail import if present
# import yagmail   # ❌ REMOVED

ENV = os.getenv("APP_ENV", "demo")

st.write("ENV VALUE:", ENV)

if ENV == "demo":
    from demo_ceo.app import main
    main()
else:
    from dashboards.ceo import show_dashboard
    show_dashboard()

    # Top N
    st.markdown("### Top 10 Days by Cost")
    top_days = filtered.groupby('date')['cost'].sum().reset_index().sort_values('cost', ascending=False).head(10)
    st.dataframe(top_days.rename(columns={'date': 'Date', 'cost': 'Total Cost'}))

    # Anomaly highlight
    st.markdown("### Anomaly/Spike Detection")
    mean = trend['cost'].mean()
    std = trend['cost'].std()
    spikes = trend[trend['cost'] > mean + 2*std]
    if not spikes.empty:
        st.error(f"Spikes detected on: {', '.join(spikes['date'].dt.strftime('%Y-%m-%d'))}")
    else:
        st.success("No major cost spikes detected.")

    # Download/export
    st.markdown("---")
    st.download_button("Download Filtered Data (CSV)", filtered.to_csv(index=False).encode('utf-8'), file_name="filtered_cost_data.csv", mime="text/csv")

def ai_advisor_page():
    st.write("Preview the types of AI-generated optimization opportunities that will be managed in Recommendations.")

    recommendation_preview = pd.DataFrame(
        [
            {"Recommendation": "Downsize underutilized EC2 instances", "Potential Savings": "$840/month", "Priority": "High"},
            {"Recommendation": "Evaluate Savings Plans coverage gaps", "Potential Savings": "$1,260/month", "Priority": "High"},
            {"Recommendation": "Archive stale snapshots and cold backups", "Potential Savings": "$430/month", "Priority": "Medium"},
        ]
    )
    st.dataframe(recommendation_preview, width="stretch", hide_index=True)
    st.markdown('''
**AI Advisor role**

- Explains the kinds of optimization opportunities the system can identify
- Previews likely savings themes before workflow tracking begins
- Leaves generation and status management to Recommendations
''')
    if st.button("Open AI Recommendations", key="ai_advisor_open_recommendations", width="stretch"):
        st.session_state["selected_page"] = "AI Recommendations"
        st.rerun()

def cost_explorer_page():

    st.title("Cost Explorer")

    def _compact_metric_value(value):
        text = str(value or "N/A")
        compact_map = {
            "Virtual Machines": "VMs",
            "SQL Database": "SQL DB",
            "Compute Engine": "Compute Eng.",
            "Cloud Functions": "Functions",
            "Cloud Storage": "Storage",
            "Data Transfer": "Transfer",
        }
        if text in compact_map:
            return compact_map[text]
        return text if len(text) <= 18 else f"{text[:15]}..."

    username = st.session_state.get("username", "guest")
    active_demo = st.session_state.get("active_demo_environment")
    billing_df, account_scope, plan_scope = _load_dashboard_billing_scope(username, active_demo=active_demo)

    if billing_df.empty:
        latest_sync_runs = list_sync_runs(username=username, limit=1)
        if latest_sync_runs:
            latest_run = latest_sync_runs[0]
            latest_status = str(latest_run.get("status") or "unknown").lower()
            status_icon = "✅" if latest_status == "success" else "⚠️" if latest_status in {"failed", "error"} else "ℹ️"
            started_at = latest_run.get("started_at") or "n/a"
            st.caption(f"{status_icon} Last sync: {started_at} | Status: {latest_status.title()}")
        else:
            st.caption("ℹ️ Last sync: never")
        clicked = render_empty_state(
            icon="📊",
            title="No billing data available yet",
            message="Connect a cloud account to sync real cost data, or activate a demo scenario from the Dashboard to explore Cost Explorer with sample data.",
            cta_label="Go to Cloud Accounts",
            cta_key="cost_explorer_empty_connect",
        )
        if clicked:
            st.session_state["selected_page"] = "Cloud Accounts"
            st.rerun()
        return

    if plan_scope["history_days"] not in {None, float("inf")}:
        st.caption(
            f"{plan_scope['plan_name']} plan access is limited to {plan_scope['history_label'].lower()} for Cost Explorer and CSV export."
        )

    explorer_df = billing_df.copy()
    explorer_df["date"] = pd.to_datetime(explorer_df["date"], errors="coerce")
    explorer_df["cost"] = pd.to_numeric(explorer_df["cost"], errors="coerce").fillna(0.0)
    explorer_df = explorer_df.dropna(subset=["date"])

    if explorer_df.empty:
        st.info("Billing data exists, but it does not contain usable dates for exploration.")
        return

    explorer_df["provider"] = explorer_df["account"].fillna("").astype(str).str.extract(r"^(aws|azure|gcp)", expand=False).fillna("other").str.upper()

    min_date = explorer_df["date"].min().date()
    max_date = explorer_df["date"].max().date()

    provider_options = sorted(provider for provider in explorer_df["provider"].dropna().unique().tolist() if provider)
    account_options = sorted(account for account in explorer_df["account"].dropna().unique().tolist() if account)
    service_options = sorted(service for service in explorer_df["service"].dropna().unique().tolist() if service)
    provider_filter_options = ["All Providers", *provider_options]
    account_filter_options = ["All Accounts", *account_options]
    service_filter_options = ["All Services", *service_options]

    metric_container = st.container()

    st.markdown("#### Filters")
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1.1, 1.35, 1.35, 1.5])
    with filter_col1:
        selected_provider = st.selectbox("Provider", provider_filter_options, index=0)
    with filter_col2:
        selected_account = st.selectbox(
            "Account",
            account_filter_options,
            index=0,
        )
    with filter_col3:
        selected_service = st.selectbox("Service", service_filter_options, index=0)
    with filter_col4:
        date_range = st.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

    selected_providers = provider_options if selected_provider == "All Providers" else [selected_provider]
    selected_accounts = account_options if selected_account == "All Accounts" else [selected_account]
    selected_services = service_options if selected_service == "All Services" else [selected_service]
    start_date, end_date = (date_range if isinstance(date_range, tuple) and len(date_range) == 2 else (min_date, max_date))
    filtered_df = explorer_df[
        explorer_df["provider"].isin(selected_providers or provider_options)
        & explorer_df["account"].isin(selected_accounts or account_options)
        & explorer_df["service"].isin(selected_services or service_options)
        & (explorer_df["date"].dt.date >= start_date)
        & (explorer_df["date"].dt.date <= end_date)
    ].copy()

    if filtered_df.empty:
        st.warning("No billing rows match the current Cost Explorer filters.")
        return

    filter_summary_col1, filter_summary_col2, filter_summary_col3 = st.columns([1.1, 1.4, 2.2])
    filter_summary_col1.caption(f"Provider: {selected_provider}")
    filter_summary_col2.caption(f"Account: {selected_account}")
    filter_summary_col3.caption(f"Service: {selected_service} | Window: {start_date.isoformat()} to {end_date.isoformat()}")

    total_spend = float(filtered_df["cost"].sum())
    day_count = max((end_date - start_date).days + 1, 1)
    avg_daily_spend = total_spend / day_count
    top_service_row = filtered_df.groupby("service", as_index=False)["cost"].sum().sort_values("cost", ascending=False).head(1)
    top_account_row = filtered_df.groupby("account", as_index=False)["cost"].sum().sort_values("cost", ascending=False).head(1)

    with metric_container:
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        metric_col1.metric("Filtered Spend", f"${total_spend:,.0f}")
        metric_col2.metric("Avg Daily Spend", f"${avg_daily_spend:,.0f}")
        metric_col3.metric(
            "Top Service",
            _compact_metric_value(top_service_row.iloc[0]["service"] if not top_service_row.empty else "N/A"),
        )
        metric_col4.metric(
            "Top Account",
            _compact_metric_value(top_account_row.iloc[0]["account"] if not top_account_row.empty else "N/A"),
        )

    daily_trend = (
        filtered_df.assign(Date=filtered_df["date"].dt.date)
        .groupby("Date", as_index=False)["cost"]
        .sum()
        .rename(columns={"cost": "Cost"})
    )
    service_breakdown = (
        filtered_df.groupby("service", as_index=False)["cost"]
        .sum()
        .sort_values("cost", ascending=False)
        .head(10)
        .rename(columns={"service": "Service", "cost": "Cost"})
    )
    account_breakdown = (
        filtered_df.groupby("account", as_index=False)["cost"]
        .sum()
        .sort_values("cost", ascending=False)
        .rename(columns={"account": "Account", "cost": "Cost"})
    )
    service_breakdown_display = service_breakdown.copy()
    service_breakdown_display["Cost"] = service_breakdown_display["Cost"].map(lambda value: f"${value:,.0f}")
    account_breakdown_display = account_breakdown.copy()
    account_breakdown_display["Cost"] = account_breakdown_display["Cost"].map(lambda value: f"${value:,.0f}")
    provider_breakdown = (
        filtered_df.groupby("provider", as_index=False)["cost"]
        .sum()
        .sort_values("cost", ascending=False)
        .rename(columns={"provider": "Provider", "cost": "Cost"})
    )
    overview_tab, breakdown_tab, data_tab = st.tabs(["Overview", "Breakdowns", "Raw Data"])

    with overview_tab:
        trend_col, breakdown_col = st.columns([1.6, 1])
        with trend_col:
            trend_fig = px.line(daily_trend, x="Date", y="Cost", markers=True, title="Daily spend trend")
            trend_fig.update_layout(margin=dict(l=10, r=10, t=45, b=10), height=340)
            st.plotly_chart(trend_fig, width="stretch")
        with breakdown_col:
            service_fig = px.bar(service_breakdown, x="Service", y="Cost", title="Top services")
            service_fig.update_layout(margin=dict(l=10, r=10, t=45, b=10), height=340)
            st.plotly_chart(service_fig, width="stretch")

        summary_col1, summary_col2 = st.columns([1.1, 1.1])
        with summary_col1:
            st.markdown("#### Service Summary")
            st.dataframe(service_breakdown_display, width="stretch", hide_index=True)
        with summary_col2:
            st.markdown("#### Account Summary")
            st.dataframe(account_breakdown_display.head(10), width="stretch", hide_index=True)

    with breakdown_tab:
        lower_col1, lower_col2 = st.columns([1.1, 1.1])
        with lower_col1:
            account_fig = px.bar(account_breakdown.head(10), x="Cost", y="Account", orientation="h", title="Top accounts")
            account_fig.update_layout(margin=dict(l=10, r=10, t=45, b=10), height=320, yaxis=dict(categoryorder="total ascending"))
            st.plotly_chart(account_fig, width="stretch")
        with lower_col2:
            provider_fig = px.pie(provider_breakdown, names="Provider", values="Cost", title="Provider mix")
            provider_fig.update_layout(margin=dict(l=10, r=10, t=45, b=10), height=320)
            st.plotly_chart(provider_fig, width="stretch")

    with data_tab:
        st.subheader("Filtered Cost Details")
        detail_scope = filtered_df[["date", "account", "provider", "service", "cost"]].copy()
        detail_scope["date"] = detail_scope["date"].dt.date.astype(str)
        detail_scope = detail_scope.sort_values(["date", "account", "service"], ascending=[False, True, True])
        csv_bytes = detail_scope.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Filtered CSV",
            data=csv_bytes,
            file_name="cost_explorer_filtered.csv",
            mime="text/csv",
            width="content",
        )
        st.dataframe(detail_scope, width="stretch", hide_index=True)

def finops_insights_page(embedded=False):
    if embedded:
        st.subheader("FinOps Insights")
    else:
        st.subheader("Cost Allocation by Team")
        import pandas as pd
        data = {
            "Team":["Platform","Data","DevOps","AI"],
            "Cost":[4000,3500,2800,2150]
        }
        df = pd.DataFrame(data)
        st.bar_chart(df.set_index("Team"))

def optimization_page(embedded=False):
    if embedded:
        st.subheader("Optimization Opportunities")
    else:
        st.warning("Idle resources detected")
        st.markdown('''
- 5 unattached EBS volumes  
- 2 idle load balancers  
- 3 underutilized EC2 instances
''')
        st.metric("Potential Savings", "$1,750 / month")

def optimization_insights_page():
    from views.optimization_insights import render_optimization_insights_page
    render_optimization_insights_page()


def insights_page():
    st.caption("Explore analytical views and optimization signals. Use Reports for downloadable artifacts.")
    insight_tab1, insight_tab2 = st.tabs(["FinOps Insights", "Optimization Insights"])
    with insight_tab1:
        finops_insights_page(embedded=True)
    with insight_tab2:
        optimization_insights_page()


def operations_page():
    st.title("Operations")
    st.caption("Review platform operations, sync activity, and audit events.")
    operations_tab1, operations_tab2 = st.tabs(["Cost Sync History", "Audit Log"])
    with operations_tab1:
        cost_sync_history_page(embedded=True)
    with operations_tab2:
        audit_log_page(embedded=True)

def reports_page():
    # --- Variable assignments (must come first) ---
    username = st.session_state.get("username", "guest")
    active_demo = st.session_state.get("active_demo_environment")
    summary_metrics = _dashboard_summary_metrics(username, active_demo=active_demo)
    billing_df, account_scope, plan_scope = _load_dashboard_billing_scope(username, active_demo=active_demo)
    operations_snapshot = _cloud_operations_snapshot(username)

    service_cost = pd.DataFrame(columns=["Service", "Cost"])
    if not billing_df.empty:
        service_cost = (
            billing_df.groupby("service", as_index=False)["cost"]
            .sum()
            .sort_values("cost", ascending=False)
            .rename(columns={"service": "Service", "cost": "Cost"})
        )

    client_name = "Cloud Advisory Client"
    if active_demo:
        client_name = active_demo.get("label") or active_demo.get("name") or client_name
    elif len(account_scope) == 1:
        client_name = account_scope[0]
    elif username and username != "guest":
        client_name = f"{username.title()} Portfolio"

    top_service = service_cost.iloc[0]["Service"] if not service_cost.empty else "N/A"
    maturity_score = int(operations_snapshot.get("avg_health_score") or 78)
    readiness_adjustment = 8 if operations_snapshot.get("accounts_in_error", 0) == 0 else -5
    readiness_score = max(40, min(100, maturity_score + readiness_adjustment))

    # --- Executive Summary Cards (KPI style) ---
    st.markdown("## Executive Summary")
    st.caption(f"Client: {client_name} | Date: {datetime.datetime.now().strftime('%Y-%m-%d')}")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            """
            <div style='background-color:#0066cc; color:white; border-radius:16px; padding:18px; box-shadow:2px 2px 6px #ccc; text-align:center;'>
            <b>Monthly Cloud Spend</b><br>
            <span style='font-size:2rem; font-weight:700;'>${:,.0f}</span>
            </div>
            """.format(summary_metrics['total_monthly_cost']), unsafe_allow_html=True)
    with col2:
        percent_savings = (summary_metrics['potential_savings']/summary_metrics['total_monthly_cost']*100) if summary_metrics['total_monthly_cost'] else 0
        st.markdown(
            """
            <div style='background-color:#00994c; color:white; border-radius:16px; padding:18px; box-shadow:2px 2px 6px #ccc; text-align:center;'>
            <b>Estimated Savings</b><br>
            <span style='font-size:2rem; font-weight:700;'>${:,.0f} ({:.1f}%)</span>
            </div>
            """.format(summary_metrics['potential_savings'], percent_savings), unsafe_allow_html=True)
    with col3:
        st.markdown(
            """
            <div style='background-color:#ff9900; color:white; border-radius:16px; padding:18px; box-shadow:2px 2px 6px #ccc; text-align:center;'>
            <b>Cloud Maturity</b><br>
            <span style='font-size:2rem; font-weight:700;'>{}/100</span>
            </div>
            """.format(maturity_score), unsafe_allow_html=True)
    with col4:
        st.markdown(
            """
            <div style='background-color:#6600cc; color:white; border-radius:16px; padding:18px; box-shadow:2px 2px 6px #ccc; text-align:center;'>
            <b>Focus</b><br>
            <span style='font-size:1.5rem; font-weight:700;'>Cost optimization and modernization</span>
            </div>
            """, unsafe_allow_html=True)

    # Now define summary_df after all variables are set and before any code that uses it
    summary_df = pd.DataFrame(
        {
            "Metric": [
                "Client",
                "Accounts in Scope",
                "Monthly Spend",
                "Forecast Next Month",
                "Potential Savings",
                "Top Service",
                "Healthy Accounts",
                "Accounts in Error",
                "Cloud Maturity",
                "Transformation Readiness",
            ],
            "Value": [
                client_name,
                len(account_scope),
                f"${summary_metrics['total_monthly_cost']:,.0f}",
                f"${summary_metrics['forecast_next_month']:,.0f}",
                f"${summary_metrics['potential_savings']:,.0f}",
                top_service,
                operations_snapshot.get("healthy_accounts", 0),
                operations_snapshot.get("accounts_in_error", 0),
                f"{maturity_score}/100",
                f"{readiness_score}/100",
            ],
        }
    )

    def _render_download(state_key, label, mime):
        report_path = st.session_state.get(state_key)
        if report_path and os.path.exists(report_path):
            with open(report_path, "rb") as report_file:
                st.download_button(label, report_file.read(), file_name=os.path.basename(report_path), mime=mime)

    def _prepare_report(state_key, generator, success_message):
        try:
            report_path = generator()
        except Exception as exc:
            st.error(f"Could not prepare report: {exc}")
            return
        st.session_state[state_key] = report_path
        st.success(success_message)

    finance_tab, leadership_tab, board_tab = st.tabs(["Finance", "Leadership", "Board Packs"])

    with finance_tab:
        finance_col1, finance_col2 = st.columns(2)
        with finance_col1:
            st.markdown("#### Finance Summary PDF")
            st.caption("Compact PDF with current spend, forecast, savings, service concentration, and account health.")
            if st.button("Prepare Finance PDF", key="prepare_finance_pdf", width="stretch"):
                _prepare_report(
                    "report_finance_pdf",
                    lambda: create_pdf_report(summary_df, "Finance Summary Report"),
                    "Finance PDF is ready.",
                )
            _render_download("report_finance_pdf", "Download Finance PDF", "application/pdf")

        with finance_col2:
            st.markdown("#### Cost Workbook (Excel)")
            st.caption("Excel workbook with executive summary, service-cost breakdown, and detailed spend tabs.")
            if st.button("Prepare Excel Workbook", key="prepare_finance_excel", width="stretch"):
                from cloud_report_generator import generate_excel_report
                _prepare_report(
                    "report_finance_excel",
                    lambda: generate_excel_report(
                        client_name,
                        monthly_spend=summary_metrics["total_monthly_cost"],
                        savings_monthly=summary_metrics["potential_savings"],
                        top_service_name=top_service,
                        maturity_score=maturity_score,
                        service_cost=service_cost,
                        df=billing_df,
                    ),
                    "Excel workbook is ready.",
                )
            _render_download(
                "report_finance_excel",
                "Download Excel Workbook",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with leadership_tab:
        st.markdown("#### Executive PPTX Presentation")
        st.caption("Management-ready PPTX with KPIs, cost distribution, and recommended next steps.")
        if st.button("Prepare Executive PPTX", key="prepare_executive_pptx", width="stretch"):
            from ppt_report_generator import generate_executive_ppt
            _prepare_report(
                "report_executive_pptx",
                lambda: generate_executive_ppt(
                    client_name,
                    monthly_spend=summary_metrics["total_monthly_cost"],
                    savings_monthly=summary_metrics["potential_savings"],
                    maturity_score=maturity_score,
                    readiness_score=readiness_score,
                    service_cost=service_cost,
                ),
                "Executive PPTX is ready.",
            )
        _render_download("report_executive_pptx", "Download Executive PPTX", "application/vnd.openxmlformats-officedocument.presentationml.presentation")

    st.caption("Use Cost Explorer and Audit Log for interactive analysis. Reports is reserved for exportable outputs.")

def cost_sync_history_page(embedded=False):
    if embedded:
        st.subheader("Cost Sync History")
    else:
        conn, _ = _get_analytics_connection()
        df = None
        try:
            df = pd.read_sql_query("SELECT account, service, cost FROM billing_data ORDER BY rowid DESC LIMIT 100", conn)
        except Exception as e:
            st.error(f"Error loading cost history: {e}")
        finally:
            conn.close()
        if df is not None and not df.empty:
            st.dataframe(df)
        else:
            st.info("No cost sync history available.")

def audit_log_page(embedded=False):
    if embedded:
        st.subheader("Audit Log")
    else:
        if not is_global_admin_role(st.session_state.get("role", "user")):
            st.warning("Only admins can view the audit log.")
            return
        conn, _ = _get_analytics_connection()
        try:
            df = pd.read_sql_query("SELECT username, action, details, timestamp FROM audit_log ORDER BY timestamp DESC LIMIT 500", conn)
        except Exception as e:
            st.error(f"Error loading audit log: {e}")
            df = None
        finally:
            conn.close()
        if df is not None:
            if df.empty:
                st.info("No audit log entries found.")
            else:
                # Filter controls
                col1, col2, col3 = st.columns(3)
                with col1:
                    user_filter = st.text_input("Filter by Username", "")
                with col2:
                    action_filter = st.text_input("Filter by Action", "")
                with col3:
                    date_range = st.date_input("Date Range (UTC)", [])
                filtered_df = df
                if user_filter:
                    filtered_df = filtered_df[filtered_df['username'].str.contains(user_filter, case=False, na=False)]
                if action_filter:
                    filtered_df = filtered_df[filtered_df['action'].str.contains(action_filter, case=False, na=False)]
                if date_range:
                    if isinstance(date_range, list) and len(date_range) == 2:
                        start_date, end_date = date_range
                    else:
                        start_date = end_date = date_range[0] if isinstance(date_range, list) and date_range else date_range
                    filtered_df = filtered_df[filtered_df['timestamp'].str[:10].between(str(start_date), str(end_date))]
                st.dataframe(filtered_df)
                # Simple analytics
                st.markdown("---")
                st.subheader("Audit Log Analytics")
                st.write(f"Total Events: {len(filtered_df)}")
                st.write("**Top Actions:**")
                st.dataframe(filtered_df['action'].value_counts().head(10).rename_axis('action').reset_index(name='count'))
                st.write("**Top Users:**")
                st.dataframe(filtered_df['username'].value_counts().head(10).rename_axis('username').reset_index(name='count'))
                # Time series chart
                st.write("**Events Over Time:**")
                time_series = filtered_df.copy()
                time_series['date'] = time_series['timestamp'].str[:10]
                ts_counts = time_series.groupby('date').size().reset_index(name='events')
                st.line_chart(ts_counts.set_index('date'))
                csv = filtered_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Filtered Audit Log CSV",
                    data=csv,
                    file_name="audit_log.csv",
                    mime="text/csv"
                )


def access_management_page():
    current_plan = get_user_plan(st.session_state.get("username", "guest"))
    st.markdown(f"""
        <style>
        .access-header-row {{display: flex; flex-direction: row; justify-content: space-between; align-items: center; width: 100%;}}
        .access-header-title {{font-size: 2.8rem; font-weight: 700; margin-bottom: 0.2em;}}
        .access-header-plan {{font-size: 1.1rem; color: #444; margin-left: auto;}}
        </style>
        <div class='access-header-row'>
            <div class='access-header-title'>Access Management</div>
            <div class='access-header-plan'>Plan: {current_plan}</div>
        </div>
    """, unsafe_allow_html=True)
    # Plan label is only shown in the custom header row above. Remove any other Plan label rendering here.
    username = st.session_state.get("username", "guest")
    current_role = st.session_state.get("role", "user")
    current_company = st.session_state.get("company") or get_user_company(username)
    current_plan = get_user_plan(username)
    plan_names = get_plan_names()
    is_global_admin = is_global_admin_role(current_role)
    is_company_admin = is_company_admin_role(current_role)

    if not (is_global_admin or is_company_admin):
        st.warning("You do not have access to user or tenant administration.")
        return

    st.caption("Manage internal users, client organizations, company users, and password resets separately from commercial plans.")



    # --- Ensure all variables needed for Board Pack generation are defined ---
    # Use similar logic as in reports_page
    username = st.session_state.get("username", "guest")
    active_demo = st.session_state.get("active_demo_environment")
    billing_df = pd.DataFrame()
    account_scope = []
    plan_scope = {}
    operations_snapshot = {}
    # Try to load billing_df and account_scope if possible
    try:
        billing_df, account_scope, plan_scope = _load_dashboard_billing_scope(username, active_demo=active_demo)
    except Exception:
        billing_df = pd.DataFrame()
        account_scope = []
        plan_scope = {}
    try:
        operations_snapshot = _cloud_operations_snapshot(username)
    except Exception:
        operations_snapshot = {}
    service_cost = pd.DataFrame(columns=["Service", "Cost"])
    if not billing_df.empty:
        service_cost = (
            billing_df.groupby("service", as_index=False)["cost"]
            .sum()
            .sort_values("cost", ascending=False)
            .rename(columns={"service": "Service", "cost": "Cost"})
        )
    client_name = "Cloud Advisory Client"
    if active_demo:
        client_name = active_demo.get("label") or active_demo.get("name") or client_name
    elif len(account_scope) == 1:
        client_name = account_scope[0]
    elif username and username != "guest":
        client_name = f"{username.title()} Portfolio"
    top_service = service_cost.iloc[0]["Service"] if not service_cost.empty else "N/A"
    maturity_score = int(operations_snapshot.get("avg_health_score") or 78)
    readiness_adjustment = 8 if operations_snapshot.get("accounts_in_error", 0) == 0 else -5
    readiness_score = max(40, min(100, maturity_score + readiness_adjustment))
    summary_metrics = {
        "total_monthly_cost": float(billing_df["cost"].sum()) if not billing_df.empty else 0,
        "potential_savings": 0,
        "forecast_next_month": 0,
    }
    # Use the same _prepare_report and _render_download as in reports_page
    def _prepare_report(state_key, generator, success_message):
        try:
            report_path = generator()
        except Exception as exc:
            st.error(f"Could not prepare report: {exc}")
            return
        st.session_state[state_key] = report_path
        st.success(success_message)
    def _render_download(state_key, label, mime):
        report_path = st.session_state.get(state_key)
        if report_path and os.path.exists(report_path):
            with open(report_path, "rb") as report_file:
                st.download_button(label, report_file.read(), file_name=os.path.basename(report_path), mime=mime)
    # Ensure board_tab is defined for the tab context
    finance_tab, leadership_tab, board_tab = st.tabs(["Finance", "Leadership", "Board Packs"])
    # Placeholders for client org creation logic
    normalized_admin = "admin"
    client_admin_password = "password"
    normalized_company = "company"
    client_plan = "Starter"

    if is_global_admin:
        internal_tab, client_tab = st.tabs(["Internal Workspace", "Client Organizations"])

        with internal_tab:
            st.markdown("**Internal Users**")
            internal_users = list_users(company=current_company)
            st.caption("Use internal users for testing, product validation, and presentation-only access.")
            internal_col1, internal_col2, internal_col3 = st.columns([1.1, 1.1, 0.8])
            internal_username = internal_col1.text_input("Internal Username", key="internal_username")
            internal_password = internal_col2.text_input("Temporary Password", type="password", key="internal_password")
            internal_role = internal_col3.selectbox("Access Type", ["internal_user", "presenter"], key="internal_role")
            if st.button("Create Internal User"):
                normalized_username = internal_username.strip()
                if not normalized_username or not internal_password:
                    st.error("Enter both a username and a temporary password.")
                elif any(item.get("username") == normalized_username for item in list_users()):
                    st.error("That username already exists.")
                else:
                    add_user(
                        normalized_username,
                        internal_password,
                        internal_role,
                        company=current_company,
                        user_type="internal",
                        created_by=username,
                    )
                    st.success(f"Internal user '{normalized_username}' created successfully.")
                    st.rerun()

            if internal_users:
                st.dataframe(pd.DataFrame(internal_users), width="stretch", hide_index=True)
                reset_internal_user = st.selectbox(
                    "Reset Internal User Password",
                    [item["username"] for item in internal_users],
                    key="reset_internal_user",
                )
                reset_internal_password = st.text_input(
                    "New Temporary Password",
                    type="password",
                    key="reset_internal_password",
                )
                if st.button("Reset Internal Password"):
                    if not reset_internal_password:
                        st.error("Enter a new temporary password.")
                    elif update_user_password(reset_internal_user, reset_internal_password, acting_username=username):
                        st.success(f"Password reset for '{reset_internal_user}'.")
                    else:
                        st.error("Could not reset the password for that user.")

    with board_tab:
        st.markdown("#### Board Pack PPTX")
        st.caption("Board-style PPTX covering spend concentration, risks, ROI, and transformation roadmap.")
        if st.button("Prepare Board Pack PPTX", key="prepare_board_pack_pptx", width="stretch"):
            from cloud_report_generator import generate_powerpoint_report
            _prepare_report(
                "report_board_pack_pptx",
                lambda: generate_powerpoint_report(
                    client_name,
                    monthly_spend=summary_metrics["total_monthly_cost"],
                    savings_monthly=summary_metrics["potential_savings"],
                    top_service_name=top_service,
                    maturity_score=maturity_score,
                    readiness_score=readiness_score,
                ),
                "Board Pack PPTX is ready.",
            )
        _render_download("report_board_pack_pptx", "Download Board Pack PPTX", "application/vnd.openxmlformats-officedocument.presentationml.presentation")

        # Client organization creation logic (correct indentation)
        if st.button("Create Client Organization"):
            add_user(
                normalized_admin,
                client_admin_password,
                "client_admin",
                company=normalized_company,
                user_type="client",
                created_by=username,
            )
            update_company_plan(normalized_company, client_plan)
            st.success(f"Client organization '{normalized_company}' and local admin '{normalized_admin}' created successfully.")
            st.rerun()

            client_companies = [company for company in list_companies(viewer_username=username) if company.get("company_name") != current_company]

            if client_companies:
                st.dataframe(pd.DataFrame(client_companies), width="stretch", hide_index=True)
                selected_company_name = st.selectbox(
                    "Manage Client Organization",
                    [company["company_name"] for company in client_companies],
                    key="manage_client_company",
                )
                selected_company = get_company(selected_company_name)
                selected_plan = st.selectbox(
                    "Selected Company Plan",
                    plan_names,
                    index=plan_names.index(selected_company.get("plan", "Starter")),
                    key="selected_client_plan",
                )
                if st.button("Update Client Plan"):
                    update_company_plan(selected_company_name, selected_plan)
                    st.success(f"Plan updated for {selected_company_name}.")
                    st.rerun()

                client_users = list_users(company=selected_company_name)
                if client_users:
                    st.dataframe(pd.DataFrame(client_users), width="stretch", hide_index=True)
                    reset_client_user = st.selectbox(
                        "Reset Client User Password",
                        [item["username"] for item in client_users],
                        key="reset_client_user",
                    )
                    reset_client_password = st.text_input(
                        "New Client Temporary Password",
                        type="password",
                        key="reset_client_password",
                    )
                    if st.button("Reset Client Password"):
                        if not reset_client_password:
                            st.error("Enter a new temporary password.")
                        elif update_user_password(reset_client_user, reset_client_password, acting_username=username):
                            st.success(f"Password reset for '{reset_client_user}'.")
                        else:
                            st.error("Could not reset the password for that user.")

        else:
            st.markdown("**Company Users**")
            company_users = list_users(viewer_username=username)
            seat_limit = get_user_seat_limit(current_plan)
            seat_text = "Unlimited" if seat_limit == float("inf") else seat_limit
            st.caption(f"{current_company} user licenses in use: {len(company_users)} / {seat_text}")

            company_col1, company_col2, company_col3 = st.columns([1.1, 1.1, 0.8])
            company_username = company_col1.text_input("Username", key="company_user_username")
            company_password = company_col2.text_input("Temporary Password", type="password", key="company_user_password")
            company_role = company_col3.selectbox("Role", ["user", "premium"], key="company_user_role")
            seats_available = seat_limit == float("inf") or len(company_users) < seat_limit
            if st.button("Create Company User"):
                normalized_username = company_username.strip()
                if not normalized_username or not company_password:
                    st.error("Enter both a username and a temporary password.")
                elif any(item.get("username") == normalized_username for item in list_users(viewer_username=username)):
                    st.error("That username already exists in your company.")
                elif not seats_available:
                    st.error("No user licenses are available on the current plan.")
                else:
                    add_user(
                        normalized_username,
                        company_password,
                        company_role,
                        company=current_company,
                        user_type="client",
                        created_by=username,
                    )
                    st.success(f"Company user '{normalized_username}' created successfully.")
                    st.rerun()

            if company_users:
                st.dataframe(pd.DataFrame(company_users), width="stretch", hide_index=True)
                reset_company_user = st.selectbox(
                    "Reset Company User Password",
                    [item["username"] for item in company_users],
                    key="reset_company_user",
                )
                reset_company_password = st.text_input(
                    "New Temporary Password",
                    type="password",
                    key="reset_company_password",
                )
                if st.button("Reset Company Password"):
                    if not reset_company_password:
                        st.error("Enter a new temporary password.")
                    elif update_user_password(reset_company_user, reset_company_password, acting_username=username):
                        st.success(f"Password reset for '{reset_company_user}'.")
                    else:
                        st.error("Could not reset the password for that user.")

        st.info("You can manage only your company users here. Client admins do not have Global Admin access.")

# --- Supabase Sign Up Page ---
try:
    from importlib import import_module
    supabase_ = import_module("supabase")
except ImportError:
    supabase_ = None

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase = None

if supabase_ and SUPABASE_URL and SUPABASE_KEY:
    supabase = supabase_.create_client(SUPABASE_URL, SUPABASE_KEY)

def supabase_signup_page():
    if supabase_ is None:
        st.warning("Supabase support is unavailable because the supabase package is not installed in this Python environment.")
        return
    if supabase is None:
        st.warning("Supabase support is not configured. Set SUPABASE_URL and SUPABASE_KEY to enable sign-up.")
        return
    email = st.text_input("Email", key="sb_email")
    password = st.text_input("Password", type="password", key="sb_password")
    company = st.text_input("Company", key="sb_company")
    if st.button("Sign Up (Supabase)", key="sb_signup_btn"):
        result = supabase.auth.sign_up({"email": email, "password": password})
        if result.get("user"):
            st.success("Sign up successful! Please check your email to verify your account.")
            user_id = result["user"]["id"]
            supabase.table("profiles").insert({"id": user_id, "email": email, "company": company}).execute()
            st.info("Company info saved to your profile.")
        else:
            st.error(result.get("error", {}).get("message", "Sign up failed."))

# -------------------
# APP FLOW
# -------------------

if not st.session_state.authenticated:
    login_page()
    st.stop()

# --- Onboarding gate ---
# Show the first-login wizard to any authenticated non-global-admin user
# who has not yet completed onboarding.
_onboard_username = st.session_state.get("username", "")
_onboard_role = st.session_state.get("role", "user")
if _onboard_username and not is_global_admin_role(_onboard_role) and not is_onboarding_complete(_onboard_username):
    from views.onboarding import render_onboarding_wizard
    render_onboarding_wizard()
    st.stop()

active_username = st.session_state.get("username", "guest")
effective_plan = get_user_plan(active_username)
st.session_state["plan"] = effective_plan
st.session_state["company"] = st.session_state.get("company") or get_user_company(active_username)
st.session_state["user_type"] = st.session_state.get("user_type") or get_user_type(active_username)
requested_page = _query_param_value("selected_page")
if _query_param_value("billing_result") or requested_page == "Plans & Billing":
    st.session_state["selected_page"] = "Plans & Billing"
elif requested_page:
    st.session_state["selected_page"] = requested_page



# Sidebar enhancements: theme toggle, navigation, avatar, help, and logout

with st.sidebar:
    st.markdown("# Cloud Advisory")
    current_plan = get_user_plan(st.session_state.get("username", "guest"))
    st.session_state["plan"] = current_plan
    allowed_pages = set(get_plan_pages(current_plan))
    allowed_pages.add("Dashboard")
    current_role = st.session_state.get("role", "user")
    avatar_url = "https://ui-avatars.com/api/?name=" + st.session_state.get("username", "Guest") + "&background=0D8ABC&color=fff&size=128"
    st.image(avatar_url, width=64)
    st.caption(f"Signed in as: {st.session_state.get('username', 'Guest')}")
    st.caption(f"Company: {st.session_state.get('company') or get_user_company(st.session_state.get('username', 'guest')) or 'Unassigned'}")
    st.caption("🔒 All data stored in EU region (GDPR compliant)")
    all_nav_pages = [
        ("Dashboard", "🏠"),
        ("AI Recommendations", "RI"),
        ("Cost Explorer", "💸"),
        ("Reports", "📑"),
        ("Operations", "🛠️"),
        ("Optimization Insights", "chart_with_upward_trend"),
        ("Cost Forecast (Premium)", "🔮"),
        ("Cloud Accounts", "☁️"),
        ("Plans & Billing", "💳"),
        ("Privacy Policy", "🔒"),
        ("Terms of Service", "📃"),
    ]
    if is_company_admin_role(current_role) or is_global_admin_role(current_role):
        all_nav_pages.append(("Access Management", "🔐"))
    admin_pages = {"Access Management"}
    visible_nav_pages = [p for p in all_nav_pages if p[0] in allowed_pages or (p[0] in admin_pages and (is_company_admin_role(current_role) or is_global_admin_role(current_role))) or p[0] in {"Privacy Policy", "Terms of Service"}]
    nav_labels = [page for page, _ in visible_nav_pages]
    current_page = st.session_state.get("selected_page", "Dashboard")
    default_index = nav_labels.index(current_page) if current_page in nav_labels else 0
    selected = st.radio("Go to:", nav_labels, index=default_index)
    st.session_state["selected_page"] = visible_nav_pages[nav_labels.index(selected)][0]
    st.markdown("---")
    # --- Data Controls (GDPR Right to Erasure & Export) ---
    st.markdown("### 📤 Data Controls")
    if st.button("🗑️ Delete My Data"):
        st.session_state.confirm_delete = True
    if st.session_state.get("confirm_delete"):
        st.warning("This will permanently delete your data. This action cannot be undone.")
        col1, col2 = st.columns(2)
        if col1.button("Confirm Delete"):
            from database.delete_user import delete_user_data
            delete_user_data(st.session_state.get("username"))
            st.success("Your data has been deleted.")
            st.session_state.clear()
            st.rerun()
        if col2.button("Cancel"):
            st.session_state.confirm_delete = False

    # Export My Data (GDPR)
    if st.button("📥 Export My Data"):
        from database.export_user import export_user_data
        data = export_user_data(st.session_state.get("username"))
        st.download_button(
            label="Download My Data",
            data=data,
            file_name="my_data.json",
            mime="application/json"
        )
    with st.expander("Help & FAQ", expanded=False):
        st.markdown('''
**How do I use the Cost Forecast?**  
Select a model, choose how many months to forecast, and view the results. You can download the forecast and add notes.

**What do the models mean?**  
- **Linear Regression:** Simple trend-based forecast.  
- **Prophet:** Handles seasonality and holidays.  
- **ARIMA:** Best for stationary time series.

**How do I save notes?**  
Type your notes and click 'Save Notes'. Notes are saved per user and forecast.
        ''')
    st.button("Logout", on_click=_perform_logout)



# Main page routing logic
selected_page = st.session_state.get("selected_page", "Dashboard")
st.session_state["plan"] = current_plan
current_role = st.session_state.get("role", "user")
admin_pages = {"Access Management"}
# Restrict access to admin pages for non-admins
if selected_page in admin_pages and not (is_company_admin_role(current_role) or is_global_admin_role(current_role)):
    st.warning("You do not have access to this page.")
    st.session_state["selected_page"] = "Dashboard"
# Restrict access to plan pages (except Privacy Policy/Terms of Service)
elif selected_page not in set(get_plan_pages(current_plan)).union(admin_pages, {"Privacy Policy", "Terms of Service"}):
    st.warning(f"{selected_page} is not included in the {current_plan} plan.")
    st.session_state["selected_page"] = "Plans & Billing"
    st.rerun()

# Always render the workspace header at the top of the main content area
_render_workspace_header(selected_page, current_plan)

if selected_page == "Dashboard":
    dashboard_page()
elif selected_page == "AI Recommendations":
    from views.recommendations import render_recommendations_page
    render_recommendations_page()
elif selected_page == "AI Advisor":
    st.session_state["selected_page"] = "AI Recommendations"
    st.rerun()
elif selected_page == "Cost Explorer":
    cost_explorer_page()
elif selected_page == "Insights":
    st.session_state["selected_page"] = "AI Recommendations"
    st.rerun()
elif selected_page == "Reports":
    reports_page()
elif selected_page == "Operations":
    operations_page()
elif selected_page == "Optimization Insights":
    optimization_insights_page()
elif selected_page == "Cost Forecast (Premium)":
    cost_forecast_page()
elif selected_page == "Cloud Accounts":
    from pages.cloud_accounts import cloud_accounts_page
    cloud_accounts_page()
elif selected_page == "Plans & Billing":
    # ...existing code for Plans & Billing page...
    # (No change to this block)
    import streamlit as st
    import os
    import datetime
    import pandas as pd
    import numpy as np
    # ...existing imports...

    # --- Cookie Consent Banner (CRITICAL for EU) ---
    if "cookie_consent" not in st.session_state:
        st.session_state.cookie_consent = False

    if not st.session_state.cookie_consent:
        st.warning("We use cookies to improve experience.")
        if st.button("Accept Cookies"):
            st.session_state.cookie_consent = True
            st.rerun()

    # ...existing code...
elif selected_page == "Privacy Policy":
    st.title("Privacy Policy")
    st.markdown("""
## 1. Introduction
We value your privacy and are committed to protecting your personal and business data. This Privacy Policy explains how Cloud Advisory Platform ("we", "our", "us") collects, processes, and protects your data in compliance with the General Data Protection Regulation (GDPR).

---

## 2. Data Controller
Cloud Advisory Platform  
Email: support@yourcompany.com  

We act as the Data Controller for all data processed through this platform.

---

## 3. Data We Collect
We collect and process the following types of data:

- Account Information: Username, role, company name
- Cloud Data: Cost, usage, billing, and optimization data from connected cloud providers (AWS, Azure, GCP)
- System Logs: Audit logs, user activity, timestamps
- Technical Data: IP address, browser type (for security and monitoring)

We **do NOT store sensitive personal data** or payment card details.

---

## 4. Purpose of Data Processing
We process your data to:

- Provide cloud cost analytics and optimization recommendations
- Improve system performance and user experience
- Ensure platform security and auditability
- Generate reports and insights

---

## 5. Legal Basis for Processing (GDPR Article 6)
We process data based on:

- Contractual necessity (to deliver the service)
- Legitimate interest (to improve and secure the platform)

---

## 6. Data Retention
We retain data only as long as necessary:

- Account data: Until account deletion
- Audit logs: Up to 90 days (configurable)
- Analytics data: Aggregated and anonymized where possible

---

## 7. Data Sharing & Subprocessors
We may share data with trusted third-party providers:

- Cloud Providers: AWS / Azure / GCP (for infrastructure)
- AI Services: OpenAI (for recommendations)
- Payment Providers: Stripe (for billing, if applicable)

All subprocessors are GDPR-compliant.

---

## 8. Data Security
We implement strong security controls:

- Encryption in transit (HTTPS/TLS)
- Secure credential storage
- Role-based access control (RBAC)
- Audit logging and monitoring

---

## 9. Data Residency
All customer data is stored and processed within **EU data centers** (e.g., AWS Frankfurt / Azure Germany), ensuring GDPR compliance.

---

## 10. Your Rights Under GDPR
You have the right to:

- Access your data
- Correct inaccurate data
- Request deletion ("Right to be forgotten")
- Request data portability
- Object to processing

To exercise your rights, contact: support@yourcompany.com

---

## 11. Cookies
We use cookies to:

- Maintain user sessions
- Improve user experience

You can accept or reject cookies via our consent banner.

---

## 12. Data Breach Notification
In case of a data breach, we will notify affected users and relevant authorities within 72 hours, as required by GDPR.

---

## 13. Updates to this Policy
We may update this policy periodically. Continued use of the platform implies acceptance of updates.

---

## 14. Contact
For any privacy-related concerns, contact:  
support@ai-cloudadvisor.com
    """)
elif selected_page == "Terms of Service":
    st.title("Terms of Service")
    st.write(TERMS_OF_SERVICE_TEXT)
elif selected_page == "Access Management":
    access_management_page()
elif selected_page == "Access Management":
    access_management_page()
