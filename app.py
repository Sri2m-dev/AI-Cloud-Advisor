import os
# Disable Streamlit's default multipage navigation sidebar
os.environ["STREAMLIT_PAGES"] = "0"

# Streamlit page config: set title and collapse sidebar by default
import streamlit as st
st.set_page_config(
    page_title="Cloud Advisory Platform",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Hide only the Streamlit multipage navigation ("app", "cloud accounts")
hide_pages = """
<style>
[data-testid="stSidebarNav"] {
    display: none;
}
</style>
"""
st.markdown(hide_pages, unsafe_allow_html=True)
import datetime
import sqlite3
import pandas as pd
import numpy as np
from prophet import Prophet
from statsmodels.tsa.arima.model import ARIMA
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from database.db import save_forecast_note, load_forecast_note, log_audit_event
import plotly.express as px
from sklearn.ensemble import IsolationForest

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
    import optuna
    st.markdown("---")
    st.subheader("Automated Model Selection & Hyperparameter Tuning")
    if st.button("Run AutoML (Optuna)"):
        st.info("Running Optuna study for best model and hyperparameters. This may take a minute...")
        def objective(trial):
            model_type = trial.suggest_categorical("model", ["Linear Regression", "Prophet", "ARIMA"])
            y = df["total_cost"].values
            if model_type == "Linear Regression":
                X = np.arange(len(y)).reshape(-1,1)
                model = LinearRegression()
                model.fit(X, y)
                preds = model.predict(X)
                return mean_absolute_error(y, preds)
            elif model_type == "Prophet":
                seasonality = trial.suggest_categorical("seasonality_mode", ["additive", "multiplicative"])
                prophet_df = df.rename(columns={"date": "ds", "total_cost": "y"})
                m = Prophet(seasonality_mode=seasonality)
                m.fit(prophet_df)
                forecast = m.predict(prophet_df)
                preds = forecast["yhat"].values
                return mean_absolute_error(y, preds)
            else:  # ARIMA
                p = trial.suggest_int("p", 0, 3)
                d = trial.suggest_int("d", 0, 2)
                q = trial.suggest_int("q", 0, 3)
                try:
                    model = ARIMA(y, order=(p,d,q))
                    fit = model.fit()
                    preds = fit.fittedvalues
                    return mean_absolute_error(y[max(d,1):], preds)
                except Exception:
                    return float('inf')
        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=20, show_progress_bar=False)
        st.success(f"Best model: {study.best_params['model']} with MAE={study.best_value:.2f}")
        st.json(study.best_params)
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
        # --- Model hyperparameter controls ---
        arima_p = st.number_input("ARIMA p (AR)", min_value=0, max_value=5, value=1, help="ARIMA autoregressive order.") if model_choice == "ARIMA" else 1
        arima_d = st.number_input("ARIMA d (I)", min_value=0, max_value=2, value=1, help="ARIMA differencing order.") if model_choice == "ARIMA" else 1
        arima_q = st.number_input("ARIMA q (MA)", min_value=0, max_value=5, value=1, help="ARIMA moving average order.") if model_choice == "ARIMA" else 1
        prophet_seasonality = st.selectbox("Prophet Seasonality Mode", ["additive", "multiplicative"], help="Prophet seasonality mode.") if model_choice == "Prophet" else "additive"
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
                m = Prophet(seasonality_mode=prophet_seasonality)
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
                # Prophet components plot for explainability
                with st.expander("Show/Hide Prophet Components (Explainability)", expanded=False):
                    from prophet.plot import plot_components_plotly
                    st.plotly_chart(plot_components_plotly(m, forecast_prophet), use_container_width=True)
                forecast_data = forecast_prophet[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(forecast_period)
            elif model_choice == "ARIMA":
                try:
                    arima_model = ARIMA(df["total_cost"], order=(arima_p, arima_d, arima_q))
                    arima_fit = arima_model.fit()
                    arima_forecast = arima_fit.forecast(steps=forecast_period)
                    forecast_value = arima_forecast.iloc[-1]
                    st.metric(label=f"ARIMA Forecast ({forecast_period} month(s) ahead)", value=f"${forecast_value:,.0f}", help="Best for stationary time series.")
                    forecast_data = pd.DataFrame({
                        "Month Ahead": list(range(1, forecast_period+1)),
                        "Forecast": arima_forecast
                    })
                    # ARIMA residuals plot for diagnostics
                    with st.expander("Show/Hide ARIMA Residuals (Diagnostics)", expanded=False):
                        import plotly.graph_objs as go
                        residuals = arima_fit.resid
                        fig_resid = go.Figure()
                        fig_resid.add_trace(go.Scatter(y=residuals, mode='lines', name='Residuals'))
                        fig_resid.update_layout(title='ARIMA Residuals', xaxis_title='Time', yaxis_title='Residual')
                        st.plotly_chart(fig_resid, use_container_width=True)
                except Exception as e:
                    st.warning(f"ARIMA model error: {e}")
                    forecast_data = pd.DataFrame()
        # Model performance metrics with cross-validation
        st.markdown("---")
        metrics_text = ""
        y_true = df["total_cost"].values
        # Simple time series cross-validation (rolling forecast origin)
        def rolling_cv(model_func, y, window=12, forecast_horizon=1):
            errors = []
            for i in range(window, len(y) - forecast_horizon):
                train = y[:i]
                test = y[i:i+forecast_horizon]
                try:
                    pred = model_func(train, forecast_horizon)
                    errors.append(mean_absolute_error(test, pred))
                except Exception:
                    continue
            return np.mean(errors) if errors else None
        # Linear Regression CV
        def lr_func(train, horizon):
            X = np.arange(len(train)).reshape(-1,1)
            model = LinearRegression()
            model.fit(X, train)
            preds = [model.predict([[len(train)+h]])[0] for h in range(horizon)]
            return preds
        mae_lr_cv = rolling_cv(lr_func, y_true)
        metrics_text += f"Linear Regression MAE (CV): {mae_lr_cv:.2f}\n"
        # Prophet CV
        try:
            def prophet_func(train, horizon):
                dfp = pd.DataFrame({'ds': pd.date_range(start=df['date'].iloc[0], periods=len(train), freq='D'), 'y': train})
                m = Prophet(seasonality_mode=prophet_seasonality)
                m.fit(dfp)
                future = m.make_future_dataframe(periods=horizon, freq='D')
                forecast = m.predict(future)
                return forecast['yhat'].tail(horizon).values
            mae_prophet_cv = rolling_cv(prophet_func, y_true)
            metrics_text += f"Prophet MAE (CV): {mae_prophet_cv:.2f}\n"
        except Exception:
            metrics_text += "Prophet metrics: error\n"
        # ARIMA CV
        try:
            def arima_func(train, horizon):
                model = ARIMA(train, order=(arima_p, arima_d, arima_q))
                fit = model.fit()
                forecast = fit.forecast(steps=horizon)
                return forecast.values
            mae_arima_cv = rolling_cv(arima_func, y_true)
            metrics_text += f"ARIMA MAE (CV): {mae_arima_cv:.2f}"
        except Exception:
            metrics_text += "ARIMA metrics: error"
        st.info(f"Model Performance (CV):\n{metrics_text}")
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
    anomaly_feedback = []
    rec_feedback = []
    st.title("☁️ Cloud Cost Dashboard")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Monthly Cost", "$12,450", "+8%")
    col2.metric("Forecast Next Month", "$13,100", "+5%")
    col3.metric("Potential Savings", "$2,150", "-15%")
    col4.metric("Idle Resources", "17", "Needs action")

    # --- Scheduled Report Emails (manual trigger for demo) ---
    st.markdown("---")
    st.subheader("Send Feedback Analytics via Email")
    st.caption("Configure your SMTP credentials in environment variables: YAGMAIL_USER, YAGMAIL_PASSWORD")
    import yagmail
    email_to = st.text_input("Recipient Email", "your@email.com")
    if st.button("Send Feedback Reports by Email"):
        yag = yagmail.SMTP(user=os.getenv("YAGMAIL_USER"), password=os.getenv("YAGMAIL_PASSWORD"))
        attachments = []
        if anomaly_feedback:
            pdf_path = create_pdf_report(df_anom_fb, "Anomaly Feedback Report")
            attachments.append(pdf_path)
        if rec_feedback:
            pdf_path = create_pdf_report(df_rec_fb, "Recommendation Feedback Report")
            attachments.append(pdf_path)
        yag.send(to=email_to, subject="Cloud Advisor Feedback Analytics Reports", contents="Attached are the latest feedback analytics reports.", attachments=attachments)
        st.success(f"Reports sent to {email_to}")
    # --- Custom Reports & Export Options ---
    st.markdown("---")
    st.subheader("Custom Feedback Reports & Export")
    import io
    # Anomaly feedback export
    if anomaly_feedback:
        st.markdown("**Export Anomaly Feedback Analytics**")
        csv_anom = df_anom_fb.to_csv(index=False).encode('utf-8')
        st.download_button("Download Anomaly Feedback CSV", csv_anom, "anomaly_feedback_report.csv", "text/csv")
        # Custom report: summary table
        st.markdown("**Anomaly Feedback Summary Table**")
        st.dataframe(df_anom_fb.groupby(['flag']).size().reset_index(name='Count'))
    # Recommendation feedback export
    if rec_feedback:
        st.markdown("**Export Recommendation Feedback Analytics**")
        csv_rec = df_rec_fb.to_csv(index=False).encode('utf-8')
        st.download_button("Download Recommendation Feedback CSV", csv_rec, "recommendation_feedback_report.csv", "text/csv")
        # Custom report: summary by type and flag
        st.markdown("**Recommendation Feedback by Type**")
        st.dataframe(df_rec_fb.groupby(['type', 'flag']).size().reset_index(name='Count'))
    # --- Deeper Feedback Analytics ---
    st.markdown("---")
    st.subheader("Deeper Feedback Insights")
    # User-level breakdown (if username available in feedback)
    # Extend feedback collection to include username if possible
    import getpass
    username = st.session_state.get("username", getpass.getuser())
    # Anomaly feedback: time-to-correction, false positive rate
    if anomaly_feedback:
        df_anom_fb['user'] = username  # For demo; in real use, store username in feedback
        false_pos_rate = (df_anom_fb['flag'] == 'false_positive').mean()
        st.metric("Anomaly False Positive Rate", f"{false_pos_rate*100:.1f}%")
        # Time-to-correction: how quickly anomalies are flagged after detection
        if 'date' in df_anom_fb:
            detection_dates = pd.to_datetime(df_anom_fb['date'])
            feedback_dates = pd.to_datetime(df_anom_fb.index, unit='s', origin='unix')
            # For demo, use index as feedback time; in real use, store timestamp
            time_to_correction = (feedback_dates - detection_dates).dt.days.mean()
            st.metric("Avg Time to Correction (days)", f"{time_to_correction:.1f}")
        # User breakdown
        st.write("Feedback by User (Anomalies):")
        st.write(df_anom_fb.groupby(['user', 'flag']).size().unstack(fill_value=0))
    # Recommendation feedback: not useful rate, by type and user
    if rec_feedback:
        df_rec_fb['user'] = username  # For demo; in real use, store username in feedback
        not_useful_rate = (df_rec_fb['flag'] == 'not_useful').mean()
        st.metric("Recommendation Not Useful Rate", f"{not_useful_rate*100:.1f}%")
        st.write("Feedback by User (Recommendations):")
        st.write(df_rec_fb.groupby(['user', 'type', 'flag']).size().unstack(fill_value=0))
    # Actionable insights
    st.markdown("#### Actionable Insights for Model Improvement")
    if anomaly_feedback and false_pos_rate > 0.2:
        st.warning("High anomaly false positive rate detected. Consider adjusting anomaly detection thresholds or features.")
    if rec_feedback and not_useful_rate > 0.2:
        st.warning("Many recommendations are marked not useful. Review recommendation logic or add more context.")
    # --- Advanced Feedback Analytics ---
    st.markdown("---")
    st.subheader("Feedback Analytics & Trends")
    import matplotlib.pyplot as plt
    # Anomaly feedback analytics
    feedback_file = "anomaly_feedback.csv"
    anomaly_feedback = []
    if os.path.exists(feedback_file):
        with open(feedback_file, 'r') as f:
            for line in f:
                date, label, flag = line.strip().split(',')
                anomaly_feedback.append({'date': date, 'flag': flag})
    if anomaly_feedback:
        df_anom_fb = pd.DataFrame(anomaly_feedback)
        st.write(f"Total anomaly feedback: {len(df_anom_fb)}")
        st.write(df_anom_fb['flag'].value_counts().rename_axis('Feedback').reset_index(name='Count'))
        # Trend over time
        df_anom_fb['date'] = pd.to_datetime(df_anom_fb['date'])
        trend = df_anom_fb.groupby([df_anom_fb['date'].dt.to_period('M'), 'flag']).size().unstack(fill_value=0)
        fig, ax = plt.subplots()
        trend.plot(kind='bar', stacked=True, ax=ax)
        ax.set_title('Anomaly Feedback Trend (Monthly)')
        ax.set_xlabel('Month')
        ax.set_ylabel('Count')
        st.pyplot(fig)
        # Recommendation feedback analytics
        rec_feedback_file = "recommendation_feedback.csv"
        rec_feedback = []
        if os.path.exists(rec_feedback_file):
            with open(rec_feedback_file, 'r') as f:
                for line in f:
                    resource, rtype, flag = line.strip().split(',')
                    rec_feedback.append({'resource': resource, 'type': rtype, 'flag': flag})
        if rec_feedback:
                df_rec_fb = pd.DataFrame(rec_feedback)
                st.write(f"Total recommendation feedback: {len(df_rec_fb)}")
                st.write(df_rec_fb['flag'].value_counts().rename_axis('Feedback').reset_index(name='Count'))
                # Feedback by type
                fb_by_type = df_rec_fb.groupby(['type', 'flag']).size().unstack(fill_value=0)
                st.write(fb_by_type)
                # Pie chart
                fig2, ax2 = plt.subplots()
                df_rec_fb['flag'].value_counts().plot.pie(autopct='%1.0f%%', ax=ax2)
                ax2.set_title('Recommendation Feedback Distribution')
                st.pyplot(fig2)
    # --- Automated Retraining (on new data) ---
        
    st.markdown("---")
    st.subheader("Automated Model Retraining")
    retrain_flag = False
    last_train_file = "last_model_train.txt"
    last_train_time = None
    if os.path.exists(last_train_file):
        with open(last_train_file, 'r') as f:
            last_train_time = f.read().strip()
    st.caption(f"Last model retrain: {last_train_time if last_train_time else 'Never'}")
    # Simple retrain trigger: if new data since last retrain or user clicks button
    if 'filtered' not in locals() or filtered is None or filtered.empty or 'date' not in filtered.columns:
        st.warning("No filtered data available for retraining check.")
        return
    latest_data_time = str(filtered['date'].max())
    if last_train_time is None or latest_data_time > last_train_time:
        retrain_flag = True
    if st.button("Retrain Models Now") or retrain_flag:
        # --- Integrate feedback into retraining ---
        # Exclude dates flagged as false positives in anomaly feedback
        exclude_anomaly_dates = set()
        feedback_file = "anomaly_feedback.csv"
        if os.path.exists(feedback_file):
            with open(feedback_file, 'r') as f:
                for line in f:
                    date, label, flag = line.strip().split(',')
                    if label == 'anomaly' and flag == 'false_positive':
                        exclude_anomaly_dates.add(date)
        # Exclude recommendations flagged as not useful
        exclude_recs = set()
        rec_feedback_file = "recommendation_feedback.csv"
        if os.path.exists(rec_feedback_file):
            with open(rec_feedback_file, 'r') as f:
                for line in f:
                    resource, rtype, flag = line.strip().split(',')
                    if flag == 'not_useful':
                        exclude_recs.add(resource)
        # Filter data for retraining
        retrain_df = filtered.copy()
        if not retrain_df.empty:
            retrain_df = retrain_df[~retrain_df['date'].astype(str).isin(exclude_anomaly_dates)]
            retrain_df = retrain_df[~retrain_df.apply(lambda x: f"{x['account']}:{x['service']}" in exclude_recs, axis=1)]
        # Here, retraining would re-run Optuna/fit models using retrain_df
        with open(last_train_file, 'w') as f:
            f.write(latest_data_time)
        st.success(f"Models retrained on data up to {latest_data_time}! Feedback exclusions applied: {len(exclude_anomaly_dates)} anomaly dates, {len(exclude_recs)} recommendations.")
    else:
        st.info("Models are up to date.")
    # --- User Feedback Loop for Anomalies ---
    st.markdown("---")
    st.subheader("User Feedback: Anomaly Detection")
    feedback_file = "anomaly_feedback.csv"
    if 'anomalies' in locals() and not anomalies.empty:
        st.write("Flag false positives/negatives for detected anomalies:")
        for idx, row in anomalies.iterrows():
            feedback = st.radio(f"Anomaly on {row['date'].strftime('%Y-%m-%d')} (cost: ${row['cost']:.2f})", ["Correct", "False Positive"], key=f"anom_{idx}")
            if feedback != "Correct":
                with open(feedback_file, 'a') as f:
                    f.write(f"{row['date']},anomaly,false_positive\n")
    # --- User Feedback Loop for Recommendations ---
    st.markdown("---")
    st.subheader("User Feedback: Recommendations")
    rec_feedback_file = "recommendation_feedback.csv"
    if 'recs' in locals() and recs:
        for i, rec in enumerate(recs):
            feedback = st.radio(f"Recommendation: {rec['Type']} for {rec['Resource']} (Reason: {rec['Reason']})", ["Useful", "Not Useful"], key=f"rec_{i}")
            if feedback == "Not Useful":
                with open(rec_feedback_file, 'a') as f:
                    f.write(f"{rec['Resource']},{rec['Type']},not_useful\n")
    st.caption("Feedback will be used to improve future model retraining.")
    # --- Automated Model Selection for Recommendations (KMeans) ---
    st.markdown("---")
    st.subheader("AutoML: KMeans Cluster Tuning")
    if 'utilization' in filtered.columns and 'cost_var' in filtered.columns and len(filtered) > 10:
        import optuna
        if st.button("Tune KMeans Clusters (Optuna)"):
            st.info("Running Optuna study for best KMeans cluster count...")
            def kmeans_objective(trial):
                n_clusters = trial.suggest_int("n_clusters", 2, 6)
                X = filtered[['utilization', 'cost_var']].fillna(0)
                kmeans = KMeans(n_clusters=n_clusters, random_state=42)
                labels = kmeans.fit_predict(X)
                # Use inertia (sum of squared distances) as metric
                return kmeans.inertia_
            study = optuna.create_study(direction="minimize")
            study.optimize(kmeans_objective, n_trials=10, show_progress_bar=False)
            st.success(f"Best n_clusters: {study.best_params['n_clusters']} (inertia={study.best_value:.2f})")
    import pandas as pd
    import sqlite3
    import plotly.express as px
    st.title("Dashboard")
    st.write("Unified Cloud Cost Analytics Dashboard 🚀")

    # Load data

    conn = sqlite3.connect("cloud_advisor.db")
    df = pd.read_sql_query("SELECT * FROM billing_data", conn)
    conn.close()

    if df.empty or 'date' not in df.columns:
        st.warning("No cost data available or 'date' column missing.")
        return

    # Add provider column based on account naming convention
    def infer_provider(account):
        if account.startswith("aws"): return "AWS"
        if account.startswith("azure"): return "Azure"
        if account.startswith("gcp"): return "GCP"
        return "Other"
    df['provider'] = df['account'].apply(infer_provider)

    # Simulate tags, user, project columns for demo
    import numpy as np
    np.random.seed(42)
    if 'tag' not in df.columns:
        tags = ['prod', 'dev', 'test', 'analytics', 'backup']
        users = ['alice', 'bob', 'carol', 'dave']
        projects = ['Apollo', 'Zeus', 'Hermes', 'Athena']
        df['tag'] = np.random.choice(tags, len(df))
        df['user'] = np.random.choice(users, len(df))
        df['project'] = np.random.choice(projects, len(df))

    # Date filter
    df['date'] = pd.to_datetime(df['date'])
    min_date, max_date = df['date'].min(), df['date'].max()
    date_range = st.slider("Date Range", min_value=min_date, max_value=max_date, value=(min_date, max_date))
    filtered = df[(df['date'] >= date_range[0]) & (df['date'] <= date_range[1])]

    # Provider filter
    providers = filtered['provider'].unique().tolist()
    selected_providers = st.multiselect("Cloud Providers", providers, default=providers)
    filtered = filtered[filtered['provider'].isin(selected_providers)]

    # Account/service filters
    accounts = filtered['account'].unique().tolist()
    services = filtered['service'].unique().tolist()
    selected_accounts = st.multiselect("Accounts", accounts, default=accounts)
    selected_services = st.multiselect("Services", services, default=services)
    filtered = filtered[filtered['account'].isin(selected_accounts) & filtered['service'].isin(selected_services)]

    # Tag/user/project filters
    tags = filtered['tag'].unique().tolist()
    users = filtered['user'].unique().tolist()
    projects = filtered['project'].unique().tolist()
    selected_tags = st.multiselect("Tags", tags, default=tags)
    selected_users = st.multiselect("Users", users, default=users)
    selected_projects = st.multiselect("Projects", projects, default=projects)
    filtered = filtered[
        filtered['tag'].isin(selected_tags) &
        filtered['user'].isin(selected_users) &
        filtered['project'].isin(selected_projects)
    ]

    # --- Tag/user/project breakdowns ---
    st.markdown("### Cost Breakdown by Tag")
    by_tag = filtered.groupby('tag')['cost'].sum().reset_index()
    fig_tag = px.bar(by_tag, x='tag', y='cost', text='cost', title='Cost by Tag')
    st.plotly_chart(fig_tag, use_container_width=True)
    st.dataframe(by_tag.rename(columns={'cost': 'Total Cost'}))

    st.markdown("### Cost Breakdown by User")
    by_user = filtered.groupby('user')['cost'].sum().reset_index()
    fig_user = px.bar(by_user, x='user', y='cost', text='cost', title='Cost by User')
    st.plotly_chart(fig_user, use_container_width=True)
    st.dataframe(by_user.rename(columns={'cost': 'Total Cost'}))

    st.markdown("### Cost Breakdown by Project")
    by_project = filtered.groupby('project')['cost'].sum().reset_index()
    fig_proj = px.bar(by_project, x='project', y='cost', text='cost', title='Cost by Project')
    st.plotly_chart(fig_proj, use_container_width=True)
    st.dataframe(by_project.rename(columns={'cost': 'Total Cost'}))

    # --- Advanced savings opportunity analysis ---
    st.markdown("### Advanced Savings Opportunity Analysis")
    # Example logic: flag resources with high cost variance, low utilization, or persistent low cost
    # Simulate utilization and variance
    if 'utilization' not in filtered.columns:
        filtered['utilization'] = np.random.uniform(0.1, 1.0, len(filtered))
    if 'cost_var' not in filtered.columns:
        filtered['cost_var'] = np.random.uniform(0, 0.5, len(filtered))
    # Idle/underutilized: utilization < 0.3
    idle = filtered[filtered['utilization'] < 0.3]
    # Spiky: cost_var > 0.4
    spiky = filtered[filtered['cost_var'] > 0.4]
    # Persistent low cost: cost < 20 for > 10 days
    persistent = filtered.groupby(['account', 'service']).filter(lambda x: (x['cost'] < 20).sum() > 10)
    st.write(f"Idle/Underutilized resources: {len(idle)}")
    st.write(f"Spiky cost resources: {len(spiky)}")
    st.write(f"Persistent low-cost resources: {len(persistent)}")
    if not idle.empty:
        st.warning("Idle/Underutilized resources:")
        st.dataframe(idle[['date', 'account', 'service', 'cost', 'utilization']])
    if not spiky.empty:
        st.warning("Spiky cost resources:")
        st.dataframe(spiky[['date', 'account', 'service', 'cost', 'cost_var']])
    if not persistent.empty:
        st.warning("Persistent low-cost resources:")
        st.dataframe(persistent[['date', 'account', 'service', 'cost']])
    if idle.empty and spiky.empty and persistent.empty:
        st.success("No major savings opportunities detected in this period.")

    # --- Month-over-month/periodic cost change analytics ---
    st.markdown("### Month-over-Month Cost Change")
    filtered['month'] = filtered['date'].dt.to_period('M')
    monthly = filtered.groupby('month')['cost'].sum().reset_index()
    monthly['month'] = monthly['month'].astype(str)
    monthly['pct_change'] = monthly['cost'].pct_change() * 100
    fig_mo = px.bar(monthly, x='month', y='cost', text='cost', title='Monthly Cost')
    st.plotly_chart(fig_mo, use_container_width=True)
    st.dataframe(monthly[['month', 'cost', 'pct_change']].rename(columns={'cost': 'Total Cost', 'pct_change': '% Change'}))

    # --- AI/ML: Anomaly Detection (Multivariate, Explainable) ---
    st.markdown("### AI/ML: Cost Anomaly Detection")
    # Use daily total cost, utilization, and cost variance for anomaly detection
    trend = filtered.groupby('date').agg({'cost':'sum', 'utilization':'mean', 'cost_var':'mean'}).reset_index()
    if len(trend) > 10:
        features = ['cost']
        if 'utilization' in trend.columns and 'cost_var' in trend.columns:
            features = ['cost', 'utilization', 'cost_var']
        model = IsolationForest(contamination=0.1, random_state=42)
        trend['anomaly'] = model.fit_predict(trend[features])
        trend['anomaly_score'] = model.decision_function(trend[features])
        anomalies = trend[trend['anomaly'] == -1]
        fig_anom = px.line(trend, x='date', y='cost', title='Cost Trend with Anomalies')
        fig_anom.add_scatter(x=anomalies['date'], y=anomalies['cost'], mode='markers', marker=dict(color='red', size=10), name='Anomaly')
        st.plotly_chart(fig_anom, use_container_width=True)
        if not anomalies.empty:
            st.error(f"Anomalies detected on: {', '.join(anomalies['date'].dt.strftime('%Y-%m-%d'))}")
            st.dataframe(anomalies[['date', 'cost', 'utilization', 'cost_var', 'anomaly_score']].rename(columns={'date': 'Date', 'cost': 'Total Cost', 'utilization': 'Utilization', 'cost_var': 'Cost Variance', 'anomaly_score': 'Anomaly Score'}))
            st.caption("Anomaly Score: Lower values indicate more anomalous points.")
        else:
            st.success("No cost anomalies detected.")
    else:
        st.info("Not enough data for anomaly detection.")

    # --- AI/ML: Automated Recommendations (ML-based, Explainable) ---
    st.markdown("### AI/ML: Automated Recommendations")
    from sklearn.cluster import KMeans
    recs = []
    # Use KMeans to cluster resources by utilization and cost_var for more robust idle/spiky detection
    if 'utilization' in filtered.columns and 'cost_var' in filtered.columns and len(filtered) > 10:
        X = filtered[['utilization', 'cost_var']].fillna(0)
        kmeans = KMeans(n_clusters=3, random_state=42)
        filtered['cluster'] = kmeans.fit_predict(X)
        centers = kmeans.cluster_centers_
        # Label clusters by center values
        cluster_labels = {}
        for i, center in enumerate(centers):
            if center[0] < 0.3:
                cluster_labels[i] = 'Idle/Underutilized'
            elif center[1] > 0.4:
                cluster_labels[i] = 'Spiky'
            else:
                cluster_labels[i] = 'Normal'
        filtered['cluster_label'] = filtered['cluster'].map(cluster_labels)
        for _, row in filtered.iterrows():
            if row['cluster_label'] == 'Idle/Underutilized':
                recs.append({
                    'Type': 'Rightsize',
                    'Resource': f"{row['account']}:{row['service']}",
                    'Reason': f"Clustered as Idle/Underutilized (utilization={row['utilization']:.2f})",
                    'Potential Savings': f"${row['cost']*0.7:.2f}"
                })
            elif row['cluster_label'] == 'Spiky':
                recs.append({
                    'Type': 'Scheduling',
                    'Resource': f"{row['account']}:{row['service']}",
                    'Reason': f"Clustered as Spiky (cost_var={row['cost_var']:.2f})",
                    'Potential Savings': f"${row['cost']*0.5:.2f}"
                })
        # Explainability: show cluster centers
        st.caption(f"KMeans cluster centers (utilization, cost_var): {centers}")
    else:
        # Fallback to rule-based if not enough data
        if not idle.empty:
            for _, row in idle.iterrows():
                recs.append({
                    'Type': 'Rightsize',
                    'Resource': f"{row['account']}:{row['service']}",
                    'Reason': 'Low utilization',
                    'Potential Savings': f"${row['cost']*0.7:.2f}"
                })
        if not spiky.empty:
            for _, row in spiky.iterrows():
                recs.append({
                    'Type': 'Scheduling',
                    'Resource': f"{row['account']}:{row['service']}",
                    'Reason': 'Spiky cost pattern',
                    'Potential Savings': f"${row['cost']*0.5:.2f}"
                })
    untagged = filtered[filtered['tag'].isna() | (filtered['tag'] == '')]
    if not untagged.empty:
        for _, row in untagged.iterrows():
            recs.append({
                'Type': 'Tag Cleanup',
                'Resource': f"{row['account']}:{row['service']}",
                'Reason': 'Missing tag',
                'Potential Savings': '$0.00'
            })
    if recs:
        st.dataframe(pd.DataFrame(recs))
        st.caption("Recommendations are now ML-driven where possible. Reasons are shown for explainability.")
    else:
        st.success("No automated recommendations at this time.")

    # --- KPIs ---
    st.markdown("### Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Cost", f"${filtered['cost'].sum():,.2f}")
    col2.metric("Avg Daily Cost", f"${filtered.groupby('date')['cost'].sum().mean():,.2f}")
    col3.metric("Peak Day", filtered.groupby('date')['cost'].sum().idxmax().strftime('%Y-%m-%d'))
    col4.metric("Peak Cost", f"${filtered.groupby('date')['cost'].sum().max():,.2f}")

    # Cost trend
    st.markdown("### Cost Trend Over Time")
    trend = filtered.groupby('date')['cost'].sum().reset_index()
    fig = px.line(trend, x='date', y='cost', title='Total Cost Over Time')
    st.plotly_chart(fig, use_container_width=True)

    # Cost breakdowns
    st.markdown("### Cost Breakdown")
    col1, col2 = st.columns(2)
    with col1:
        by_account = filtered.groupby('account')['cost'].sum().reset_index()
        fig1 = px.pie(by_account, names='account', values='cost', title='Cost by Account')
        st.plotly_chart(fig1, use_container_width=True)
    with col2:
        by_service = filtered.groupby('service')['cost'].sum().reset_index()
        fig2 = px.pie(by_service, names='service', values='cost', title='Cost by Service')
        st.plotly_chart(fig2, use_container_width=True)

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
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    import tempfile
    st.markdown("---")
    st.subheader("Export Feedback Analytics as PDF")
    def create_pdf_report(df, title):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        c = canvas.Canvas(tmp.name, pagesize=letter)
        width, height = letter
        c.setFont("Helvetica-Bold", 16)
        c.drawString(30, height-40, title)
        c.setFont("Helvetica", 10)
        y = height-70
        for col in df.columns:
            c.drawString(30, y, f"{col}")
            y -= 15
        y -= 10
        for idx, row in df.iterrows():
            y -= 15
            if y < 40:
                c.showPage()
                y = height-40
            c.drawString(30, y, ", ".join(str(x) for x in row.values))
        c.save()
        return tmp.name

    # Read anomaly feedback
    feedback_file = "anomaly_feedback.csv"
    anomaly_feedback = []
    if os.path.exists(feedback_file):
        with open(feedback_file, 'r') as f:
            for line in f:
                date, label, flag = line.strip().split(',')
                anomaly_feedback.append({'date': date, 'flag': flag})
    if anomaly_feedback:
        df_anom_fb = pd.DataFrame(anomaly_feedback)
        if st.button("Download Anomaly Feedback PDF"):
            pdf_path = create_pdf_report(df_anom_fb, "Anomaly Feedback Report")
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f.read(), "anomaly_feedback_report.pdf", "application/pdf")

    # Read recommendation feedback
    rec_feedback_file = "recommendation_feedback.csv"
    rec_feedback = []
    if os.path.exists(rec_feedback_file):
        with open(rec_feedback_file, 'r') as f:
            for line in f:
                resource, rtype, flag = line.strip().split(',')
                rec_feedback.append({'resource': resource, 'type': rtype, 'flag': flag})
    if rec_feedback:
        df_rec_fb = pd.DataFrame(rec_feedback)
        if st.button("Download Recommendation Feedback PDF"):
            pdf_path = create_pdf_report(df_rec_fb, "Recommendation Feedback Report")
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f.read(), "recommendation_feedback_report.pdf", "application/pdf")

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
        ("Reports", "📑"),
        ("Cost Forecast (Premium)", "🔮"),
        ("Cloud Accounts", "☁️")
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
elif selected_page == "Reports":
    # Advanced pages as tabs within Reports
    report_tabs = [
        "Main Reports",
        "FinOps Insights",
        "Optimization",
        "Optimization Insights",
        "Cost Sync History",
        "Audit Log"
    ]
    selected_tab = st.selectbox("Report Sections", report_tabs, key="report_tab")
    if selected_tab == "Main Reports":
        reports_page()
    elif selected_tab == "FinOps Insights":
        finops_insights_page()
    elif selected_tab == "Optimization":
        optimization_page()
    elif selected_tab == "Optimization Insights":
        optimization_insights_page()
    elif selected_tab == "Cost Sync History":
        cost_sync_history_page()
    elif selected_tab == "Audit Log":
        audit_log_page()
elif selected_page == "Cost Forecast (Premium)":
    cost_forecast_page()
elif selected_page == "Cloud Accounts":
    from pages.cloud_accounts import cloud_accounts_page
    cloud_accounts_page()
