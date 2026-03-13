import sqlite3
import pandas as pd
import numpy as np
from prophet import Prophet
from statsmodels.tsa.arima.model import ARIMA
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
import streamlit as st
from database.db import save_forecast_note, load_forecast_note, log_audit_event

def predict_cost(cost_history):
    return predict_cost_months(cost_history, months_ahead=1)

def predict_cost_months(cost_history, months_ahead=1):
    X = np.arange(len(cost_history)).reshape(-1,1)
    y = np.array(cost_history)
    model = LinearRegression()
    model.fit(X, y)
    next_month = model.predict([[len(cost_history) + months_ahead - 1]])
    return next_month[0]

def cost_forecast_page():
    st.title("Cost Forecast (Premium)")
    conn = sqlite3.connect("cloud_advisor.db")
    df = None
    try:
        df = pd.read_sql_query("SELECT date, SUM(cost) as total_cost FROM billing_data GROUP BY date ORDER BY date", conn)
    except Exception as e:
        st.error(f"Error loading cost history: {e}")
    finally:
        conn.close()
    if df is not None and not df.empty:
        st.markdown("## 📊 Cost History Trend")
        with st.expander("Show/Hide Cost History Chart", expanded=True):
            st.line_chart(df.set_index("date")["total_cost"])
        st.markdown("---")
        st.markdown("## 🔮 Forecast Settings")
        col1, col2 = st.columns([2,1])
        with col1:
            model_choice = st.selectbox("Select Forecast Model", ["Linear Regression", "Prophet", "ARIMA"], help="Choose a forecasting algorithm. Prophet is best for seasonality, ARIMA for trends, Linear Regression for simplicity.")
        with col2:
            forecast_period = st.number_input("Months to Forecast Ahead", min_value=1, max_value=12, value=1, help="How many months into the future to predict.")
        st.markdown("---")
        st.markdown("## 🧮 Forecast Result")
        forecast_value = None
        forecast_data = pd.DataFrame()
        with st.spinner("Calculating forecast..."):
            if model_choice == "Linear Regression":
                X = np.arange(len(df["total_cost"]))[:, None]
                y = df["total_cost"].values
                model = LinearRegression()
                model.fit(X, y)
                forecast = model.predict([[len(df["total_cost"]) + forecast_period - 1]])[0]
                forecast_value = forecast
                st.metric(label=f"Linear Regression Forecast ({forecast_period} month(s) ahead)", value=f"${forecast:,.0f}", help="Simple trend-based forecast.")
                forecast_data = pd.DataFrame({
                    "Month Ahead": [forecast_period],
                    "Forecast": [forecast]
                })
            elif model_choice == "Prophet":
                prophet_df = df.rename(columns={"date": "ds", "total_cost": "y"})
                m = Prophet()
                m.fit(prophet_df)
                future = m.make_future_dataframe(periods=forecast_period, freq='M')
                forecast_prophet = m.predict(future)
                next_month_prophet = forecast_prophet.iloc[-1]["yhat"]
                forecast_value = next_month_prophet
                st.metric(label=f"Prophet Forecast ({forecast_period} month(s) ahead)", value=f"${next_month_prophet:,.0f}", help="Handles seasonality and holidays.")
                # Prophet confidence interval visualization
                import plotly.graph_objs as go
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=forecast_prophet['ds'], y=forecast_prophet['yhat'], mode='lines', name='Forecast', line=dict(color='royalblue')))
                fig.add_trace(go.Scatter(x=forecast_prophet['ds'], y=forecast_prophet['yhat_upper'], mode='lines', name='Upper CI', line=dict(dash='dash', color='lightgreen')))
                fig.add_trace(go.Scatter(x=forecast_prophet['ds'], y=forecast_prophet['yhat_lower'], mode='lines', name='Lower CI', line=dict(dash='dash', color='salmon')))
                fig.update_layout(title='Prophet Forecast with Confidence Interval', xaxis_title='Date', yaxis_title='Cost')
                with st.expander("Show/Hide Prophet Confidence Interval Chart", expanded=True):
                    st.plotly_chart(fig, use_container_width=True)
                forecast_data = forecast_prophet[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(forecast_period)
            elif model_choice == "ARIMA":
                try:
                    arima_model = ARIMA(df["total_cost"], order=(1,1,1))
                    arima_fit = arima_model.fit()
                    arima_forecast = arima_fit.forecast(steps=forecast_period)
                    forecast_value = arima_forecast.iloc[-1]
                    st.metric(label=f"ARIMA Forecast ({forecast_period} month(s) ahead)", value=f"${forecast_value:,.0f}", help="Best for stationary time series.")
                    forecast_data = pd.DataFrame({
                        "Month Ahead": list(range(1, forecast_period+1)),
                        "Forecast": arima_forecast
                    })
                except Exception as e:
                    st.warning(f"ARIMA model error: {e}")
                    forecast_data = pd.DataFrame()
        # Model performance metrics
        st.markdown("---")
        metrics_text = ""
        y_true = df["total_cost"].values
        y_pred_lr = np.repeat(forecast_value, len(y_true)) if forecast_value is not None else np.zeros_like(y_true)
        mae_lr = mean_absolute_error(y_true, y_pred_lr)
        rmse_lr = np.sqrt(mean_squared_error(y_true, y_pred_lr))
        metrics_text += f"Linear Regression MAE: {mae_lr:.2f}, RMSE: {rmse_lr:.2f}\n"
        # Prophet metrics
        try:
            prophet_df = df.rename(columns={"date": "ds", "total_cost": "y"})
            m = Prophet()
            m.fit(prophet_df)
            forecast_hist = m.predict(prophet_df)
            y_pred_prophet = forecast_hist["yhat"].values
            mae_prophet = mean_absolute_error(y_true, y_pred_prophet)
            rmse_prophet = np.sqrt(mean_squared_error(y_true, y_pred_prophet))
            metrics_text += f"Prophet MAE: {mae_prophet:.2f}, RMSE: {rmse_prophet:.2f}\n"
        except Exception:
            metrics_text += "Prophet metrics: error\n"
        # ARIMA metrics
        try:
            arima_model = ARIMA(df["total_cost"], order=(1,1,1))
            arima_fit = arima_model.fit()
            y_pred_arima = arima_fit.fittedvalues
            mae_arima = mean_absolute_error(y_true[1:], y_pred_arima)
            rmse_arima = np.sqrt(mean_squared_error(y_true[1:], y_pred_arima))
            metrics_text += f"ARIMA MAE: {mae_arima:.2f}, RMSE: {rmse_arima:.2f}"
        except Exception:
            metrics_text += "ARIMA metrics: error"
        st.info(f"Model Performance (on history):\n{metrics_text}")
        # Downloadable forecast report
        if not forecast_data.empty:
            csv = forecast_data.to_csv(index=False).encode('utf-8')
            download = st.download_button(
                label="Download Forecast CSV",
                data=csv,
                file_name="cost_forecast.csv",
                mime="text/csv"
            )
            if download:
                log_audit_event(st.session_state.get("username", "guest"), "download_forecast_csv", f"model={model_choice}, period={forecast_period}")
                st.success("Forecast CSV downloaded!")
                st.snow()
        # Persistent user notes/annotations
        st.markdown("---")
        st.subheader("Add Notes or Annotations")
        username = st.session_state.get("username", "guest")
        forecast_key = f"{model_choice}_{forecast_period}m"
        loaded_note = load_forecast_note(username, forecast_key)
        notes = st.text_area("Your notes for this forecast (saved across sessions)", value=loaded_note, key=f"forecast_notes_{forecast_key}")
        if st.session_state.get("authenticated", False):
            if st.button("Save Notes"):
                save_forecast_note(username, forecast_key, notes)
                log_audit_event(username, "save_note", f"forecast={forecast_key}")
                st.success("Notes saved and will persist across sessions.")
                st.balloons()
        else:
            st.info("Login to save notes.")
        loaded_note = load_forecast_note(username, forecast_key)
        if loaded_note:
            st.info(f"**Saved Notes:**\n{loaded_note}")
        # Placeholder for future AI/ML models
        st.markdown("---")
        st.subheader("Coming Soon: Advanced AI/ML Forecasting")
        st.caption("We are working on integrating deep learning and advanced AI models for even more accurate forecasts. Stay tuned!")
    else:
        st.info("Not enough data for forecast.")

import streamlit as st
def inject_custom_css():
    with open(".streamlit/custom.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
inject_custom_css()

st.set_page_config(
    page_title="Cloud Advisory Platform",
    layout="wide"
)

# -------------------
# SESSION STATE
# -------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# -------------------
# LOGIN PAGE
# -------------------
def login_page():

    st.title("☁️ Cloud Advisory Platform")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        from database.db import get_user, log_audit_event
        user = get_user(username)
        if user and password == user[1]:
            st.session_state["authenticated"] = True
            st.session_state["username"] = user[0]
            st.session_state["role"] = user[2]
            log_audit_event(user[0], "login")
            st.rerun()
        else:
            st.error("Invalid credentials")
    user_role = st.session_state.get("role", "user")
    if user_role not in ["admin", "premium", "user"]:
        st.warning("You do not have access to this feature.")
        st.stop()

    def logout_action():
        from database.db import log_audit_event
        log_audit_event(st.session_state.get("username", "guest"), "logout")
        st.session_state.update(authenticated=False)
    st.button("Logout", on_click=logout_action)

# -------------------
# PAGE FUNCTIONS
# -------------------
def dashboard_page():
    st.title("Dashboard")
    st.write("Welcome to the Cloud Advisory Platform 🚀")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Monthly Cost", "$12,450", "5%")
    col2.metric("Forecast", "$13,100", "2%")
    col3.metric("Savings Opportunity", "$3,200")
    col4.metric("Idle Resources", "17")

    st.divider()

    st.subheader("Cost Trend")

    from services.aws_connector import get_aws_cost
    import pandas as pd
    cost_data = get_aws_cost()
    if cost_data:
        df = pd.DataFrame(cost_data)
        st.line_chart(df.set_index("month"))
    else:
        st.warning("No AWS cost data available.")

def ai_advisor_page():
    st.title("AI FinOps Advisor")

    st.write("AI-driven cloud cost optimization recommendations")

    if st.button("Generate AI Recommendations"):
        st.success("Recommendations Generated")
        st.markdown("""
        **EC2 Optimization**

        • 3 EC2 instances are underutilized  
        • Recommended: downgrade from m5.large → t3.medium  

        **Estimated Monthly Savings:** $840
        """)

def cost_explorer_page():
    st.title("Cost Explorer")

    import pandas as pd

    data = {
        "Service": ["EC2","S3","RDS","Lambda"],
        "Cost": [5000,2000,3000,450]
    }

    df = pd.DataFrame(data)

    st.subheader("Service Cost Breakdown")

    st.dataframe(df)

    st.bar_chart(df.set_index("Service"))

def finops_insights_page():
    st.title("FinOps Insights")

    st.subheader("Cost Allocation by Team")

    import pandas as pd

    data = {
        "Team":["Platform","Data","DevOps","AI"],
        "Cost":[4000,3500,2800,2150]
    }

    df = pd.DataFrame(data)

    st.bar_chart(df.set_index("Team"))

def optimization_page():
    st.title("Optimization Opportunities")

    st.warning("Idle resources detected")

    st.write("""
    • 5 unattached EBS volumes  
    • 2 idle load balancers  
    • 3 underutilized EC2 instances
    """)

    st.metric("Potential Savings", "$1,750 / month")

def optimization_insights_page():
    st.title("Optimization Insights")

    st.info("Top Cost Drivers")

    import pandas as pd

    data = {
        "Service":["EC2","RDS","S3","Data Transfer"],
        "Cost":[5000,3000,2000,900]
    }

    df = pd.DataFrame(data)

    st.bar_chart(df.set_index("Service"))

def reports_page():
    st.title("Reports")
    st.write("Generate FinOps reports")
    if st.session_state.get("role", "user") == "admin":
        if st.button("Generate Monthly Report"):
            st.success("Report generated successfully")
    else:
        st.info("Only admins can generate monthly reports.")
    if st.button("Download CSV"):
        st.info("Download feature coming soon")

def cost_sync_history_page():
    st.title("Cost Sync History")
    conn = sqlite3.connect("cloud_advisor.db")
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

def audit_log_page():
    st.title("Audit Log")
    if st.session_state.get("role", "user") != "admin":
        st.warning("Only admins can view the audit log.")
        return
    conn = sqlite3.connect("cloud_advisor.db")
    try:
        df = pd.read_sql_query("SELECT username, action, details, timestamp FROM audit_log ORDER BY timestamp DESC LIMIT 500", conn)
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
    except Exception as e:
        st.error(f"Error loading audit log: {e}")
    finally:
        conn.close()

# -------------------
# APP FLOW
# -------------------

if not st.session_state.authenticated:
    login_page()
    st.stop()



# Sidebar enhancements: theme toggle, navigation, avatar, help, and logout
with st.sidebar:
    st.markdown("# 🌥️ Cloud Advisor")
    # User avatar (placeholder)
    avatar_url = "https://ui-avatars.com/api/?name=" + st.session_state.get("username", "Guest") + "&background=0D8ABC&color=fff&size=128"
    st.image(avatar_url, width=64)
    st.caption(f"Signed in as: {st.session_state.get('username', 'Guest')}")
    st.markdown("---")
    st.markdown("## 🧭 Quick Navigation")
    nav_pages = [
        ("Dashboard", "🏠"),
        ("AI Advisor", "🤖"),
        ("Cost Explorer", "💸"),
        ("FinOps Insights", "📊"),
        ("Optimization", "⚡"),
        ("Optimization Insights", "🔍"),
        ("Reports", "📑"),
        ("Cloud Accounts", "☁️"),
        ("Cost Sync History", "🕒"),
        ("Audit Log", "📝"),
        ("Cost Forecast (Premium)", "🔮")
    ]
    nav_labels = [f"{icon} {page}" for page, icon in nav_pages]
    default_index = nav_labels.index(f"🏠 Dashboard") if f"🏠 Dashboard" in nav_labels else 0
    selected = st.radio("Go to:", nav_labels, index=default_index)
    st.session_state["selected_page"] = nav_pages[nav_labels.index(selected)][0]
    st.markdown("---")
    with st.expander("❓ Help & FAQ", expanded=False):
        st.markdown("""
**How do I use the Cost Forecast?**  
Select a model, choose how many months to forecast, and view the results. You can download the forecast and add notes.

**What do the models mean?**  
- **Linear Regression:** Simple trend-based forecast.  
- **Prophet:** Handles seasonality and holidays.  
- **ARIMA:** Best for stationary time series.

**How do I save notes?**  
Type your notes and click 'Save Notes'. Notes are saved per user and forecast.
        """)
    st.button("Logout", on_click=lambda: st.session_state.update(authenticated=False))

# Main page routing logic
selected_page = st.session_state.get("selected_page", "Dashboard")
if selected_page == "Dashboard":
    dashboard_page()
elif selected_page == "AI Advisor":
    ai_advisor_page()
elif selected_page == "Cost Explorer":
    cost_explorer_page()
elif selected_page == "FinOps Insights":
    finops_insights_page()
elif selected_page == "Optimization":
    optimization_page()
elif selected_page == "Optimization Insights":
    optimization_insights_page()
elif selected_page == "Reports":
    reports_page()
elif selected_page == "Cloud Accounts":
    from pages.cloud_accounts import cloud_accounts_page
    cloud_accounts_page()
elif selected_page == "Cost Sync History":
    cost_sync_history_page()
elif selected_page == "Audit Log":
    audit_log_page()
elif selected_page == "Cost Forecast (Premium)":
    cost_forecast_page()
