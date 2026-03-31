
import streamlit as st
import os

ENV = os.getenv("APP_ENV", "demo")



import streamlit as st
import os

ENV = os.getenv("APP_ENV", "demo")

import streamlit as st
import os

ENV = os.getenv("APP_ENV", "demo")



if ENV == "demo":
    from demo_ceo.app import main
    main()
else:
    from dashboards.ceo import show_dashboard
    show_dashboard()

# Instantiated once per script run (every Streamlit rerun).
# Must NOT be cached with @st.cache_resource — it renders a hidden HTML
# component and must execute in the active session's script context.
_cookie_ctrl = _CookieController() if _CookieController is not None else None


def _get_cookie_controller():
    return _cookie_ctrl


def _auth_cookie_expires_at():
    return datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=AUTH_COOKIE_DAYS)


def _auth_secret():
    return os.getenv("CLOUD_ADVISOR_CREDENTIAL_KEY") or "cloud-advisor-local-dev-secret"


def _format_plan_history_label(plan_def):
    history_days = plan_def.get("data_history_days")
    if history_days in {None, float("inf")}:
        return "Unlimited"
    return f"Last {int(history_days)} days"


def _query_param_value(name, default=None):
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value


def _clear_query_params(*keys):
    for key in keys:
        try:
            if key in st.query_params:
                del st.query_params[key]
        except Exception:
            pass


def _queue_billing_flash(level, message):
    st.session_state["billing_flash"] = {"level": level, "message": message}


def _render_billing_flash():
    flash = st.session_state.pop("billing_flash", None)
    if not flash:
        return
    getattr(st, flash.get("level", "info"), st.info)(flash.get("message", ""))


_TIGHT_PLAN_CHIP_PAGE = "AI Recommendations"


def _render_workspace_header(selected_page, plan_name):
    plan_label = str(plan_name or "Starter")
    selected_page_name = str(selected_page or "")
    header_class = (
        "saas-workspace-header saas-workspace-header--tight"
        if selected_page_name == _TIGHT_PLAN_CHIP_PAGE
        else "saas-workspace-header"
    )
    html_content = (
        "<style>"
        ".saas-workspace-header {display: flex; flex-direction: row; justify-content: space-between; align-items: center; width: 100%;}"
        ".saas-workspace-title {font-size: 2.8rem; font-weight: 700; margin-bottom: 0.5rem;}"
        ".saas-workspace-meta {font-size: 1.1rem; color: #444; margin-left: auto;}"
        "</style>"
        f"<div class='{header_class}'>"
        + ("<div class='saas-workspace-title'>Cloud Cost Dashboard</div>" if selected_page_name == 'Dashboard' else "")
        + (f"<div class='saas-workspace-meta'>Plan: {plan_label}</div>" if selected_page_name == 'Dashboard' else "")
        + "</div>"
    )
    st.markdown(html_content, unsafe_allow_html=True)


def _apply_plan_billing_history_limit(billing_df, username):
    session_username = st.session_state.get("username")
    plan_name = st.session_state.get("plan") if username and username == session_username else get_user_plan(username)
    plan_name = plan_name or "Starter"
    plan_def = get_plan_definition(plan_name)
    history_days = get_plan_billing_history_days(plan_name)
    scope_meta = {
        "plan_name": plan_name,
        "history_days": history_days,
        "history_label": _format_plan_history_label(plan_def),
        "window_start": None,
    }
    if billing_df.empty or history_days in {None, float("inf")}:
        return billing_df, scope_meta

    latest_date = billing_df["date"].max().normalize()
    window_start = latest_date - pd.Timedelta(days=int(history_days) - 1)
    scope_meta["window_start"] = window_start.date().isoformat()
    return billing_df[billing_df["date"] >= window_start].copy(), scope_meta


def _apply_authenticated_session(user_row):
    st.session_state.pop("logout_pending", None)
    st.session_state["authenticated"] = True
    st.session_state["username"] = user_row[0]
    st.session_state["role"] = user_row[2]
    st.session_state["company"] = user_row[3] if len(user_row) > 3 else None
    st.session_state["user_type"] = user_row[4] if len(user_row) > 4 else None
    st.session_state["plan"] = get_user_plan(user_row[0])


def _issue_auth_token(username):
    payload = {
        "sub": username,
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=AUTH_COOKIE_DAYS),
    }
    return jwt.encode(payload, _auth_secret(), algorithm="HS256")


def _set_auth_cookie(username):
    controller = _get_cookie_controller()
    if controller is None:
        return
    try:
        controller.set(
            AUTH_COOKIE_NAME,
            _issue_auth_token(username),
            max_age=AUTH_COOKIE_DAYS * 86400,
        )
    except Exception:
        pass


def _clear_auth_cookie():
    controller = _get_cookie_controller()
    if controller is None:
        return
    try:
        controller.set(AUTH_COOKIE_NAME, "", max_age=0)
    except Exception:
        pass
    try:
        controller.remove(AUTH_COOKIE_NAME)
    except Exception:
        pass


def _reset_authenticated_session(mark_logout_pending=False):
    for key in [
        "authenticated",
        "username",
        "role",
        "company",
        "user_type",
        "plan",
        "selected_page",
        "billing_checkout_url",
        "billing_portal_url",
        "processed_billing_session_id",
    ]:
        st.session_state.pop(key, None)
    st.session_state["authenticated"] = False
    if mark_logout_pending:
        st.session_state["logout_pending"] = True
    else:
        st.session_state.pop("logout_pending", None)


def _perform_logout():
    log_audit_event(st.session_state.get("username", "guest"), "logout")
    _clear_auth_cookie()
    _reset_authenticated_session(mark_logout_pending=True)
    _clear_query_params("billing_result", "session_id", "selected_page")


def _restore_auth_session_from_cookie():
    if st.session_state.get("authenticated"):
        return
    if st.session_state.get("logout_pending"):
        return
    controller = _get_cookie_controller()
    if controller is None:
        return
    try:
        token = controller.get(AUTH_COOKIE_NAME)
    except Exception:
        return
    if not token:
        return
    try:
        payload = jwt.decode(token, _auth_secret(), algorithms=["HS256"])
        username = payload.get("sub")
        user = get_user(username)
        if not user:
            _clear_auth_cookie()
            return
        _apply_authenticated_session(user)
    except Exception:
        _clear_auth_cookie()

def predict_cost(cost_history):
    return predict_cost_months(cost_history, months_ahead=1)

def predict_cost_months(cost_history, months_ahead=1):
    X = np.arange(len(cost_history)).reshape(-1,1)
    y = np.array(cost_history)
    model = LinearRegression()
    model.fit(X, y)
    next_month = model.predict([[len(cost_history) + months_ahead - 1]])
    return next_month[0]


def _build_forecast_spike_recommendation(cost_series, forecast_value, forecast_period, model_choice):
    if forecast_value is None or cost_series is None or len(cost_series) < 7:
        return None

    recent_window = min(14, len(cost_series))
    recent_average = float(np.mean(cost_series[-recent_window:]))
    if recent_average <= 0:
        return None

    projected_change = float(forecast_value - recent_average)
    projected_change_ratio = projected_change / recent_average
    if projected_change_ratio < 0.10:
        return None

    priority = "high" if projected_change_ratio >= 0.25 else "medium"
    due_date = (datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=3)).isoformat()
    return {
        "title": f"Investigate {forecast_period}-month forecast spike",
        "description": (
            f"The {model_choice} forecast projects ${forecast_value:,.0f} versus a recent average of "
            f"${recent_average:,.0f}, a {projected_change_ratio:.0%} increase. Review demand drivers, "
            "capacity changes, and commitment coverage before month-end decisions."
        ),
        "resource": "shared:forecast-spike",
        "priority": priority,
        "estimated_savings": max(int(round(projected_change * 30)), 0),
        "due_date": due_date,
        "confidence_score": 0.88 if projected_change_ratio >= 0.25 else 0.74,
        "rationale": "The projected increase materially exceeds the recent cost baseline, so this is likely to affect next-month spend and planning decisions if left unexplained.",
        "effort_level": "low",
        "action_steps": [
            "Review the service-level contributors behind the recent trend change.",
            "Check whether the increase is expected demand, an anomaly, or a commitment coverage gap.",
            "Record the outcome before month-end forecast and budgeting decisions are finalized.",
        ],
        "recent_average": recent_average,
        "projected_change": projected_change,
        "projected_change_ratio": projected_change_ratio,
    }


def _get_analytics_connection():
    try:
        return get_pg_connection(), "PostgreSQL"
    except Exception:
        return get_db(), "SQLite"


@st.cache_data(ttl=20, show_spinner=False)
def _load_billing_data_frame():
    conn, _ = _get_analytics_connection()
    try:
        billing_df = pd.read_sql_query("SELECT account, date, service, cost FROM billing_data", conn)
    except Exception:
        billing_df = pd.DataFrame()
    finally:
        conn.close()
    return billing_df

def cost_forecast_page():
    st.title("Cost Forecast (Premium)")
    import optuna
    conn, backend_name = _get_analytics_connection()
    df = None
    try:
        df = pd.read_sql_query("SELECT date, SUM(cost) as total_cost FROM billing_data GROUP BY date ORDER BY date", conn)
    except Exception as e:
        st.error(f"Error loading cost history: {e}")
    finally:
        conn.close()

    if backend_name == "SQLite":
        # Only show this message to admin users
        user_role = st.session_state.get("role", "user")
        if user_role in ("admin", "global_admin"):  # adjust as needed for your admin roles
            st.caption("Using local SQLite data because PostgreSQL is not configured for this screen.")

    automl_best_params = st.session_state.get("forecast_automl_best_params", {})
    automl_best_score = st.session_state.get("forecast_automl_best_score")

    st.markdown("---")
    st.subheader("Automated Model Selection & Hyperparameter Tuning")
    if st.button("Run AutoML (Optuna)"):
        if df is None or df.empty:
            st.warning("Load billing data before running AutoML.")
            return
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
                    if ENV == "demo":
                        # Lightweight fallback for demo mode
                        return simple_forecast(y)
                    else:
                        from statsmodels.tsa.arima.model import ARIMA
                        model = ARIMA(y, order=(p,d,q))
                        fit = model.fit()
                        preds = fit.fittedvalues
                        return mean_absolute_error(y[max(d,1):], preds)
                except Exception:
                    return float('inf')
        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=20, show_progress_bar=False)
        st.session_state["forecast_automl_best_params"] = study.best_params
        st.session_state["forecast_automl_best_score"] = float(study.best_value)
        automl_best_params = study.best_params
        automl_best_score = float(study.best_value)

    if automl_best_params:
        best_model = automl_best_params.get("model", "Linear Regression")
        detail_parts = []
        if "seasonality_mode" in automl_best_params:
            detail_parts.append(f"Seasonality: {automl_best_params['seasonality_mode'].title()}")
        if {"p", "d", "q"}.issubset(automl_best_params):
            detail_parts.append(
                f"ARIMA order: ({automl_best_params['p']}, {automl_best_params['d']}, {automl_best_params['q']})"
            )
        details_text = " | ".join(detail_parts) if detail_parts else "Recommended settings applied below."
        score_suffix = f" with MAE={automl_best_score:.2f}" if automl_best_score is not None else ""
        st.success(f"Best model: {best_model}{score_suffix}")
        st.caption(details_text)

    if df is not None and not df.empty:
        st.markdown("## Cost History Trend")
        with st.expander("Show/Hide Cost History Chart", expanded=True):
            st.line_chart(df.set_index("date")["total_cost"])
        st.markdown("---")
        st.markdown("## Forecast Settings")
        model_options = ["Linear Regression", "Prophet", "ARIMA"]
        default_model = automl_best_params.get("model", "Linear Regression")
        col1, col2 = st.columns([2,1])
        with col1:
            model_choice = st.selectbox(
                "Select Forecast Model",
                model_options,
                index=model_options.index(default_model) if default_model in model_options else 0,
                help="Choose a forecasting algorithm. Prophet is best for seasonality, ARIMA for trends, Linear Regression for simplicity.",
            )
        with col2:
            forecast_period = st.number_input("Months to Forecast Ahead", min_value=1, max_value=12, value=1, help="How many months into the future to predict.")
        # --- Model hyperparameter controls ---
        arima_p = st.number_input("ARIMA p (AR)", min_value=0, max_value=5, value=int(automl_best_params.get("p", 1)), help="ARIMA autoregressive order.") if model_choice == "ARIMA" else 1
        arima_d = st.number_input("ARIMA d (I)", min_value=0, max_value=2, value=int(automl_best_params.get("d", 1)), help="ARIMA differencing order.") if model_choice == "ARIMA" else 1
        arima_q = st.number_input("ARIMA q (MA)", min_value=0, max_value=5, value=int(automl_best_params.get("q", 1)), help="ARIMA moving average order.") if model_choice == "ARIMA" else 1
        prophet_modes = ["additive", "multiplicative"]
        default_prophet_mode = automl_best_params.get("seasonality_mode", "additive")
        prophet_seasonality = st.selectbox(
            "Prophet Seasonality Mode",
            prophet_modes,
            index=prophet_modes.index(default_prophet_mode) if default_prophet_mode in prophet_modes else 0,
            help="Prophet seasonality mode.",
        ) if model_choice == "Prophet" else "additive"
        st.markdown("---")
        st.markdown("## Forecast Result")
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
            elif model_choice == "ARIMA":
                try:
                    if ENV == "demo":
                        # Lightweight fallback for demo mode
                        forecast_data = simple_forecast(df["total_cost"])
                        forecast_value = forecast_data.iloc[-1] if hasattr(forecast_data, 'iloc') else forecast_data[-1]
                        st.metric(label=f"ARIMA Forecast ({forecast_period} month(s) ahead)", value=f"${forecast_value:,.0f}", help="Demo mode: simple forecast.")
                    else:
                        from statsmodels.tsa.arima.model import ARIMA
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
                            st.plotly_chart(fig_resid, width="stretch")
                except Exception as e:
                    st.warning(f"ARIMA forecast error: {e}")
                    st.plotly_chart(plot_components_plotly(m, forecast_prophet), width="stretch")
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
                        st.plotly_chart(fig_resid, width="stretch")
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
                if ENV == "demo":
                    # Lightweight fallback for demo mode
                    return simple_forecast(train)
                else:
                    from statsmodels.tsa.arima.model import ARIMA
                    model = ARIMA(train, order=(arima_p, arima_d, arima_q))
                    fit = model.fit()
                    forecast = fit.forecast(steps=horizon)
                    return forecast.values
            mae_arima_cv = rolling_cv(arima_func, y_true)
            metrics_text += f"ARIMA MAE (CV): {mae_arima_cv:.2f}"
        except Exception:
            metrics_text += "ARIMA metrics: error"
        st.info(f"Model Performance (CV):\n{metrics_text}")

        forecast_recommendation = _build_forecast_spike_recommendation(
            y_true,
            forecast_value,
            forecast_period,
            model_choice,
        )
        if forecast_recommendation:
            st.warning(
                "Projected spend is materially above the recent baseline. Create a workflow item so the team can track and manage it."
            )
            insight_col1, insight_col2, insight_col3 = st.columns([1.1, 1.1, 1.6])
            insight_col1.metric("Recent Average", f"${forecast_recommendation['recent_average']:,.0f}")
            insight_col2.metric("Projected Increase", f"{forecast_recommendation['projected_change_ratio']:.0%}")
            if insight_col3.button("Create Forecast Recommendation", key=f"forecast_recommendation_{model_choice}_{forecast_period}", width="stretch"):
                recommendation_id = save_recommendation(
                    username=st.session_state.get("username", "guest"),
                    category="forecast",
                    title=forecast_recommendation["title"],
                    description=forecast_recommendation["description"],
                    source="cost_forecast",
                    resource=forecast_recommendation["resource"],
                    owner=st.session_state.get("username", "guest"),
                    priority=forecast_recommendation["priority"],
                    estimated_savings=forecast_recommendation["estimated_savings"],
                    due_date=forecast_recommendation["due_date"],
                    confidence_score=forecast_recommendation["confidence_score"],
                    rationale=forecast_recommendation["rationale"],
                    effort_level=forecast_recommendation["effort_level"],
                    action_steps=forecast_recommendation["action_steps"],
                )
                log_audit_event(
                    st.session_state.get("username", "guest"),
                    "create_forecast_recommendation",
                    f"recommendation_id={recommendation_id}, model={model_choice}, period={forecast_period}",
                )
                st.success("Forecast recommendation saved to the workflow inbox.")
            if insight_col3.button("Open AI Recommendations", key=f"forecast_open_recommendations_{model_choice}_{forecast_period}", width="stretch"):
                st.session_state["selected_page"] = "AI Recommendations"
                st.rerun()
        else:
            st.caption("No material forecast spike detected against the recent baseline.")

        # Downloadable forecast report
        if not forecast_data.empty:
            # Add header comment for user clarity
            header_comment = (
                '"# Column descriptions:\n'
                '# ds: Forecast date\n'
                '# yhat: Predicted (forecasted) value for the date\n'
                '# yhat_lower: Lower bound of the prediction interval\n'
                '# yhat_upper: Upper bound of the prediction interval\n\n"'
            )
            csv = (header_comment + forecast_data.to_csv(index=False)).encode('utf-8')
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
    else:
        st.info("Not enough data for forecast.")

def inject_custom_css():
    with open(".streamlit/custom.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
inject_custom_css()

# -------------------
# SESSION STATE
# -------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
_restore_auth_session_from_cookie()

# -------------------
# LOGIN PAGE
# -------------------
def login_page():
    st.markdown("""
    <style>
    div[data-baseweb='input'] {
        max-width: 400px;
    }
    </style>
    """, unsafe_allow_html=True)
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = get_user(username)
        if user and password == user[1]:
            _apply_authenticated_session(user)
            _set_auth_cookie(user[0])
            log_audit_event(user[0], "login")
            show_toast(*TOAST_LOGIN_WELCOME)
            st.rerun()
        else:
            st.error("Invalid credentials")
    user_role = st.session_state.get("role", "user")
    if user_role not in ["global_admin", "client_admin", "premium", "user", "internal_user", "presenter", "admin"]:
        st.warning("You do not have access to this feature.")
        st.stop()
        st.session_state.update(authenticated=False)

# -------------------
# PAGE FUNCTIONS
# -------------------
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def create_pdf_report(df, title):
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    doc = SimpleDocTemplate(tmp.name, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=60, bottomMargin=40)
    styles = getSampleStyleSheet()
    elements = []
    # Title
    elements.append(Paragraph(f"<b>{title}</b>", styles['Title']))
    elements.append(Spacer(1, 18))
    # Table data
    table_data = [["Metric", "Value"]]
    for idx, row in df.iterrows():
        table_data.append([str(row[0]), str(row[1])])
    # Table style
    table = Table(table_data, colWidths=[180, 250])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f2f2f2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#222222')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
    ]))
    elements.append(table)
    doc.build(elements)
    return tmp.name


@st.cache_data(ttl=20, show_spinner=False)
def _cloud_operations_snapshot(username):
    accounts = list_cloud_accounts(username)
    sync_runs = list_sync_runs(username=username, limit=10)
    total_accounts = len(accounts)
    healthy_accounts = sum(1 for account in accounts if account.get("validation_status") == "validated")
    accounts_in_error = sum(
        1
        for account in accounts
        if account.get("status") == "error" or account.get("validation_status") == "error"
    )
    avg_health_score = round(
        sum(int(account.get("health_score") or 0) for account in accounts) / total_accounts,
        0,
    ) if total_accounts else 0
    return {
        "accounts": accounts,
        "sync_runs": sync_runs,
        "total_accounts": total_accounts,
        "healthy_accounts": healthy_accounts,
        "accounts_in_error": accounts_in_error,
        "avg_health_score": int(avg_health_score),
    }


def _scenario_account_deltas(snapshot_accounts, active_demo):
    if not active_demo:
        return []

    baseline_accounts = {
        account["account_name"]: account
        for account in get_demo_account_profiles("healthy")
    }
    delta_rows = []
    for account in snapshot_accounts:
        baseline = baseline_accounts.get(account.get("account_name"))
        if not baseline:
            continue
        current_health = int(account.get("health_score") or 0)
        baseline_health = int(baseline.get("details", {}).get("health_score") or 0)
        current_status = str(account.get("validation_status") or account.get("status") or "pending")
        baseline_status = str(baseline.get("details", {}).get("status") or "pending")
        current_issue = account.get("last_error") or account.get("validation_message") or "Healthy"
        if current_health == baseline_health and current_status == baseline_status and current_issue == "Healthy":
            continue
        delta_rows.append(
            {
                "Provider": account.get("provider", "").upper(),
                "Account": account.get("account_name", ""),
                "Healthy Baseline": f"{baseline_status.title()} / {baseline_health}",
                "Current State": f"{current_status.title()} / {current_health}",
                "Health Delta": current_health - baseline_health,
                "Primary Change": current_issue,
            }
        )
    return delta_rows


def _render_cloud_operations_summary(username, active_demo=None):
    snapshot = _cloud_operations_snapshot(username)
    st.markdown("---")
    st.subheader("Cloud Operations")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Connected Accounts", snapshot["total_accounts"])
    col2.metric("Healthy Accounts", snapshot["healthy_accounts"])
    col3.metric("Accounts Needing Attention", snapshot["accounts_in_error"])
    col4.metric("Average Health Score", f"{snapshot['avg_health_score']}/100")

    if snapshot["total_accounts"] == 0:
        st.info("No cloud accounts connected yet. Use Cloud Accounts to start the setup wizard and automatic sync.")
        return

    attention_accounts = [
        {
            "Provider": account.get("provider", "").upper(),
            "Account": account.get("account_name", ""),
            "Status": account.get("status", "pending"),
            "Validation": account.get("validation_status", "pending"),
            "Next Sync": account.get("next_sync_at") or "Not scheduled",
            "Issue": account.get("last_error") or account.get("validation_message") or "Healthy",
        }
        for account in snapshot["accounts"]
        if account.get("status") == "error" or account.get("validation_status") == "error"
    ]
    recent_runs = [
        {
            "Provider": run.get("provider", "").upper(),
            "Trigger": run.get("trigger_type", ""),
            "Status": run.get("status", ""),
            "Started": run.get("started_at", ""),
            "Records": f"{run.get('record_count') or 0:,}",
            "Error": run.get("error_message") or "",
        }
        for run in snapshot["sync_runs"][:5]
    ]
    delta_rows = _scenario_account_deltas(snapshot["accounts"], active_demo)

    left_col, right_col = st.columns([1.2, 1])
    with left_col:
        if active_demo and active_demo.get("key") != "healthy":
            st.markdown("#### Changed vs Healthy Baseline")
        else:
            st.markdown("#### Accounts Requiring Attention")

        if active_demo and active_demo.get("key") != "healthy" and delta_rows:
            st.dataframe(pd.DataFrame(delta_rows), width="stretch", hide_index=True)
        elif attention_accounts:
            st.dataframe(pd.DataFrame(attention_accounts), width="stretch", hide_index=True)
        else:
            st.success("All connected accounts are currently healthy.")
    with right_col:
        st.markdown("#### Recent Sync Activity")
        if recent_runs:
            st.dataframe(pd.DataFrame(recent_runs), width="stretch", hide_index=True)
        else:
            st.caption("No sync runs recorded yet.")


def _render_my_open_recommendations(username):
    workflow_items = list_recommendations(username=username, limit=50)
    role = st.session_state.get("role", "user")
    if role not in {"global_admin", "client_admin", "premium", "admin"}:
        workflow_items = [item for item in workflow_items if can_manage_recommendation(item, username, action="view")]
    open_items = [item for item in workflow_items if item.get("status") in {"new", "accepted", "snoozed"}]
    today = pd.Timestamp.now(tz="UTC").date()
    overdue_items = []
    assigned_items = []

    for item in open_items:
        due_date = item.get("due_date")
        if due_date:
            parsed_due_date = pd.to_datetime(due_date, errors="coerce")
            if not pd.isna(parsed_due_date) and parsed_due_date.date() < today:
                overdue_items.append(item)
        if item.get("owner") and item.get("owner") == username:
            assigned_items.append(item)

    st.markdown("---")
    header_col, action_col = st.columns([3, 1])
    header_col.subheader("My Open AI Recommendations")
    action_col.button(
        "Open AI Recommendations",
        key="dashboard_open_recommendations_inbox",
        width="stretch",
        on_click=lambda: st.session_state.update(selected_page="AI Recommendations"),
    )
    st.caption("Dashboard keeps this lightweight. Use AI Recommendations for full workflow management.")
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Open", len(open_items))
    metric_col2.metric("Assigned to Me", len(assigned_items))
    metric_col3.metric("Overdue", len(overdue_items))
    metric_col4.metric(
        "Open Savings",
        f"${sum(float(item.get('estimated_savings') or 0) for item in open_items):,.0f}",
    )

    if not open_items:
        st.caption("No open workflow recommendations right now.")
        return

    top_items = sorted(
        open_items,
        key=lambda item: (
            0 if item in overdue_items else 1,
            -float(item.get("estimated_savings") or 0),
        ),
    )[:3]
    summary_rows = []
    for item in top_items:
        summary_rows.append(
            {
                "Title": item.get("title"),
                "Status": item.get("status"),
                "Priority": str(item.get("priority") or "medium").title(),
                "Owner": item.get("owner") or "Unassigned",
                "Due": item.get("due_date") or "Not set",
                "Potential Savings": f"${float(item.get('estimated_savings') or 0):,.0f}",
            }
        )

    st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)


def _render_forecast_risk_summary(username):
    workflow_items = list_recommendations(username=username, source="cost_forecast", limit=20)
    role = st.session_state.get("role", "user")
    if role not in {"global_admin", "client_admin", "premium", "admin"}:
        workflow_items = [item for item in workflow_items if can_manage_recommendation(item, username, action="view")]

    open_items = [item for item in workflow_items if item.get("status") in {"new", "accepted", "snoozed"}]
    st.markdown("---")
    header_col, action_col = st.columns([3, 1])
    header_col.subheader("Forecast Risk")
    action_col.button(
        "Open Forecast",
        key="dashboard_open_cost_forecast",
        width="stretch",
        on_click=lambda: st.session_state.update(selected_page="Cost Forecast (Premium)"),
    )

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Open Forecast Risks", len(open_items))
    metric_col2.metric(
        "Potential Exposure",
        f"${sum(float(item.get('estimated_savings') or 0) for item in open_items):,.0f}",
    )
    metric_col3.metric(
        "High Priority",
        sum(1 for item in open_items if str(item.get("priority") or "").lower() == "high"),
    )

    if not open_items:
        st.caption("No open forecast risk workflow items right now. Create one from Cost Forecast when a material spike is detected.")
        return

    st.caption("Forecast spike recommendations created from Cost Forecast appear here for quick review.")
    top_items = sorted(
        open_items,
        key=lambda item: (
            0 if str(item.get("priority") or "").lower() == "high" else 1,
            item.get("due_date") or "9999-12-31",
        ),
    )[:3]
    summary_rows = [
        {
            "Title": item.get("title"),
            "Status": item.get("status"),
            "Priority": str(item.get("priority") or "medium").title(),
            "Owner": item.get("owner") or "Unassigned",
            "Due": item.get("due_date") or "Not set",
            "Potential Exposure": f"${float(item.get('estimated_savings') or 0):,.0f}",
        }
        for item in top_items
    ]
    st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)
    if st.button("Open Forecast Recommendations", key="dashboard_open_forecast_recommendations", width="stretch"):
        st.session_state["selected_page"] = "AI Recommendations"
        st.rerun()


def _load_dashboard_billing_scope(username, active_demo=None):
    session_username = st.session_state.get("username")
    plan_name = st.session_state.get("plan") if username and username == session_username else get_user_plan(username)
    plan_name = plan_name or "Starter"
    plan_scope = {
        "plan_name": plan_name,
        "history_days": get_plan_billing_history_days(plan_name),
        "history_label": _format_plan_history_label(get_plan_definition(plan_name)),
        "window_start": None,
    }
    billing_df = _load_billing_data_frame().copy()

    if billing_df.empty:
        return pd.DataFrame(), active_demo.get("account_names", []) if active_demo else [], plan_scope

    billing_df["date"] = pd.to_datetime(billing_df["date"], errors="coerce")
    billing_df["cost"] = pd.to_numeric(billing_df["cost"], errors="coerce").fillna(0.0)
    billing_df = billing_df.dropna(subset=["date"])

    account_scope = []
    if active_demo and active_demo.get("account_names"):
        account_scope = active_demo["account_names"]
    else:
        account_scope = [account.get("account_name") for account in list_cloud_accounts(username) if account.get("account_name")]

    if account_scope:
        scoped_df = billing_df[billing_df["account"].isin(account_scope)].copy()
        if not scoped_df.empty:
            billing_df = scoped_df

    billing_df, plan_scope = _apply_plan_billing_history_limit(billing_df, username)
    return billing_df, account_scope, plan_scope


def _dashboard_summary_metrics(username, active_demo=None):
    billing_df, account_scope, _ = _load_dashboard_billing_scope(username, active_demo=active_demo)

    if billing_df.empty:
        return {
            "total_monthly_cost": 0.0,
            "total_monthly_delta": None,
            "forecast_next_month": 0.0,
            "forecast_delta": None,
            "potential_savings": 0.0,
            "idle_resources": 0,
            "account_names": account_scope,
        }

    if billing_df.empty:
        return {
            "total_monthly_cost": 0.0,
            "total_monthly_delta": None,
            "forecast_next_month": 0.0,
            "forecast_delta": None,
            "potential_savings": 0.0,
            "idle_resources": 0,
            "account_names": account_scope,
        }

    latest_date = billing_df["date"].max().normalize()
    recent_start = latest_date - pd.Timedelta(days=29)
    previous_start = latest_date - pd.Timedelta(days=59)
    previous_end = latest_date - pd.Timedelta(days=30)
    recent_df = billing_df[billing_df["date"] >= recent_start]
    previous_df = billing_df[(billing_df["date"] >= previous_start) & (billing_df["date"] <= previous_end)]

    total_monthly_cost = float(recent_df["cost"].sum())
    previous_monthly_cost = float(previous_df["cost"].sum()) if not previous_df.empty else None
    total_monthly_delta = None
    if previous_monthly_cost and previous_monthly_cost > 0:
        total_monthly_delta = ((total_monthly_cost - previous_monthly_cost) / previous_monthly_cost) * 100

    daily_totals = recent_df.groupby(recent_df["date"].dt.date)["cost"].sum().sort_index()
    recent_daily_average = float(daily_totals.mean()) if not daily_totals.empty else 0.0
    forecast_next_month = recent_daily_average * 30
    forecast_delta = None
    if total_monthly_cost > 0:
        forecast_delta = ((forecast_next_month - total_monthly_cost) / total_monthly_cost) * 100

    workflow_items = list_recommendations(username=username, limit=100)
    open_items = [item for item in workflow_items if item.get("status") in {"new", "accepted", "snoozed"}]
    potential_savings = float(sum(float(item.get("estimated_savings") or 0) for item in open_items))
    idle_resources = sum(
        1
        for item in open_items
        if str(item.get("category") or "").lower() in {"waste", "rightsizing", "storage", "compute"}
    )
    return {
        "total_monthly_cost": total_monthly_cost,
        "total_monthly_delta": total_monthly_delta,
        "forecast_next_month": forecast_next_month,
        "forecast_delta": forecast_delta,
        "potential_savings": potential_savings,
        "idle_resources": idle_resources,
        "account_names": account_scope,
    }


def _render_scenario_impact_summary(username, active_demo, summary_metrics):
    if not active_demo:
        return

    scenario_messages = {
        "healthy": {
            "title": "Stable demo baseline",
            "tone": "success",
            "points": [
                "Cloud accounts are healthy and syncing on schedule.",
                "Recommendation pressure should remain low.",
                "Use this scenario as the comparison point for the others.",
            ],
        },
        "cost_spike": {
            "title": "Spend acceleration detected",
            "tone": "warning",
            "points": [
                "Recent compute and analytics demand is driving a sharp cost increase.",
                "Forecast risk items should appear in AI Recommendations.",
                "Use this scenario to test anomaly review and month-end escalation workflows.",
            ],
        },
        "waste_heavy": {
            "title": "Optimization-heavy estate",
            "tone": "warning",
            "points": [
                "Idle or oversized resources should push potential savings up.",
                "Use this scenario to test rightsizing and cleanup workflows.",
                "Service mix should skew more heavily toward compute and storage.",
            ],
        },
        "governance_failure": {
            "title": "Operational control gaps present",
            "tone": "error",
            "points": [
                "Validation and policy failures should increase attention-required accounts.",
                "Billing-export and governance fixes should dominate recommendations.",
                "Use this scenario to test remediation tracking rather than pure cost savings.",
            ],
        },
        "mixed_failures": {
            "title": "Cross-functional triage scenario",
            "tone": "info",
            "points": [
                "One account is healthy while others require cost and governance follow-up.",
                "Forecast risk and operational issues should coexist in the same workflow queue.",
                "Use this scenario to test the full end-to-end operating model.",
            ],
        },
    }
    scenario_state = scenario_messages.get(active_demo.get("key"), scenario_messages["mixed_failures"])
    snapshot = _cloud_operations_snapshot(username)
    workflow_items = list_recommendations(username=username, limit=100)
    open_items = [item for item in workflow_items if item.get("status") in {"new", "accepted", "snoozed"}]
    high_priority_count = sum(1 for item in open_items if str(item.get("priority") or "").lower() == "high")
    forecast_risk_count = sum(1 for item in open_items if item.get("source") == "cost_forecast")

    st.markdown("---")
    st.subheader("Scenario Impact Summary")
    getattr(st, scenario_state["tone"])(scenario_state["title"])
    impact_col1, impact_col2, impact_col3 = st.columns(3)
    impact_col1.metric("Accounts Requiring Attention", snapshot["accounts_in_error"])
    impact_col2.metric("High-Priority AI Recommendations", high_priority_count)
    impact_col3.metric("Forecast Risk Items", forecast_risk_count)
    for point in scenario_state["points"]:
        st.caption(f"- {point}")
    st.caption(
        f"Current scenario monthly cost: ${summary_metrics['total_monthly_cost']:,.0f} across {len(summary_metrics['account_names'])} account(s)."
    )


def _render_dashboard_charts(username, active_demo=None):
    billing_df, account_scope, plan_scope = _load_dashboard_billing_scope(username, active_demo=active_demo)
    if billing_df.empty:
        return

    st.markdown("---")
    st.subheader("Scenario Spend View")
    if plan_scope["history_days"] not in {None, float("inf")}:
        st.caption(
            f"{plan_scope['plan_name']} includes {plan_scope['history_label'].lower()} of billing history in this view."
        )
    chart_col1, chart_col2 = st.columns([1.4, 1])

    daily_totals = (
        billing_df.groupby(billing_df["date"].dt.date)["cost"]
        .sum()
        .reset_index(name="cost")
        .rename(columns={"date": "Date", "cost": "Daily Cost"})
    )
    service_mix = (
        billing_df.groupby("service", as_index=False)["cost"]
        .sum()
        .sort_values("cost", ascending=False)
        .head(6)
        .rename(columns={"service": "Service", "cost": "Cost"})
    )

    with chart_col1:
        trend_fig = px.line(
            daily_totals,
            x="Date",
            y="Daily Cost",
            markers=True,
            title="Daily spend trend",
        )
        trend_fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=320)
        st.plotly_chart(trend_fig, width="stretch")

    with chart_col2:
        mix_fig = px.bar(
            service_mix,
            x="Cost",
            y="Service",
            orientation="h",
            title="Top cost drivers",
        )
        mix_fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=320, yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(mix_fig, width="stretch")

    scope_text = ", ".join(account_scope) if account_scope else "all connected accounts"
    st.caption(f"Charts are scoped to: {scope_text}")


def _seed_dashboard_recommendations(username):
    recommendations = [
        {
            "category": "cost-governance",
            "title": "Review untagged cloud spend",
            "description": "Some resources are missing cost allocation tags, which makes ownership and showback harder.",
            "source": "dashboard",
            "resource": "shared:untagged-spend",
            "estimated_savings": 600,
            "priority": "medium",
            "confidence_score": 0.8,
            "rationale": "Tagging gaps degrade cost attribution and usually block later optimization work from being assigned cleanly.",
            "effort_level": "medium",
            "action_steps": [
                "List the highest-spend untagged resources by account.",
                "Apply the minimum required ownership and cost-center tags.",
                "Re-check showback quality after the next sync completes.",
            ],
        },
        {
            "category": "waste",
            "title": "Investigate idle resources with no recent demand",
            "description": "Idle resources are contributing avoidable spend and should be rightsized, scheduled, or removed.",
            "source": "dashboard",
            "resource": "shared:idle-resources",
            "estimated_savings": 1750,
            "priority": "high",
            "confidence_score": 0.86,
            "rationale": "Idle-resource findings usually translate into direct savings quickly once ownership and shutdown windows are agreed.",
            "effort_level": "medium",
            "action_steps": [
                "Confirm which idle assets are truly non-production or safe to schedule down.",
                "Choose delete, resize, or schedule actions per resource group.",
                "Track the realized savings after the cleanup is completed.",
            ],
        },
        {
            "category": "forecast",
            "title": "Validate next-month forecast variance drivers",
            "description": "Recent trend changes suggest a forecast uplift that should be reviewed before month-end commitment decisions.",
            "source": "dashboard",
            "resource": "shared:forecast-variance",
            "estimated_savings": 900,
            "priority": "medium",
            "confidence_score": 0.76,
            "rationale": "Forecast variance is not automatically waste, but it is a strong planning signal when trend changes persist.",
            "effort_level": "low",
            "action_steps": [
                "Compare the latest trend to the prior two-week baseline.",
                "Check whether the uplift is tied to known launches, renewals, or anomalies.",
                "Capture a finance-ready explanation for the expected variance.",
            ],
        },
    ]
    for item in recommendations:
        save_recommendation(
            username=username,
            category=item["category"],
            title=item["title"],
            description=item["description"],
            source=item["source"],
            resource=item["resource"],
            estimated_savings=item["estimated_savings"],
            priority=item["priority"],
            confidence_score=item["confidence_score"],
            rationale=item["rationale"],
            effort_level=item["effort_level"],
            action_steps=item["action_steps"],
        )
    return len(recommendations)


def _seed_ai_advisor_recommendations(username):
    from services.recommendation_workflow import seed_ai_advisor_recommendations

    return seed_ai_advisor_recommendations(username)

def dashboard_page():
    # Example: Fetch cost data from FastAPI backend
    st.markdown("### API Demo: Cost Data from Backend")
    cost_data = get_cost_data()
    if cost_data:
        st.json(cost_data)

    anomaly_feedback = []
    rec_feedback = []
    df_anom_fb = None
    df_rec_fb = None
    filtered = None
    anomalies = None
    recs = None
    username = st.session_state.get("username", "guest")
    active_demo = st.session_state.get("active_demo_environment")
    if active_demo:
        st.info(
            f"Demo scenario active: {active_demo['label']} | "
            f"Accounts: {active_demo.get('accounts', 0)} | "
            f"Billing rows: {active_demo.get('billing_rows', 0)} | "
            f"Workflow items: {active_demo.get('recommendations', 0)}"
        )
        st.caption(active_demo.get("description", ""))
    summary_metrics = _dashboard_summary_metrics(username, active_demo=active_demo)
    _render_scenario_impact_summary(username, active_demo, summary_metrics)
    _render_dashboard_charts(username, active_demo=active_demo)
    _render_cloud_operations_summary(username, active_demo=active_demo)
    _render_my_open_recommendations(username)
    _render_forecast_risk_summary(username)
    col1, col2, col3, col4 = st.columns(4)
    total_monthly_delta_text = (
        f"{summary_metrics['total_monthly_delta']:+.1f}% vs prior 30d"
        if summary_metrics["total_monthly_delta"] is not None
        else "No prior baseline"
    )
    forecast_delta_text = (
        f"{summary_metrics['forecast_delta']:+.1f}% vs recent month"
        if summary_metrics["forecast_delta"] is not None
        else "Awaiting baseline"
    )
    savings_delta_text = f"{len(summary_metrics['account_names'])} account(s) in scope"
    idle_delta_text = "Needs action" if summary_metrics["idle_resources"] else "Under control"
    col1.metric("Total Monthly Cost", f"${summary_metrics['total_monthly_cost']:,.0f}", total_monthly_delta_text)
    col2.metric("Forecast Next Month", f"${summary_metrics['forecast_next_month']:,.0f}", forecast_delta_text)
    col3.metric("Potential Savings", f"${summary_metrics['potential_savings']:,.0f}", savings_delta_text)
    col4.metric("Idle Resources", f"{summary_metrics['idle_resources']}", idle_delta_text)
    if summary_metrics["account_names"]:
        st.caption("Dashboard metrics are currently scoped to: " + ", ".join(summary_metrics["account_names"]))

    action_col1, action_col2 = st.columns([1.2, 3])
    if action_col1.button("Generate Recommendations", key="dashboard_generate_recommendations", width="stretch"):
        dashboard_count = _seed_dashboard_recommendations(username)
        ai_count = len(_seed_ai_advisor_recommendations(username))
        st.success(f"AI Recommendations refreshed with {dashboard_count + ai_count} workflow items.")
        st.session_state["selected_page"] = "AI Recommendations"
        st.rerun()
    action_col2.caption("Create a fresh set of workflow items from dashboard signals and AI advisor heuristics.")

    st.markdown("---")
    show_legacy_lab = st.toggle(
        "Show legacy feedback and model lab",
        value=False,
        key="dashboard_show_legacy_lab",
        help="Reveals older experimental feedback, retraining, and AutoML panels that are not scenario-specific.",
    )
    if not show_legacy_lab:
        st.caption("Legacy feedback, retraining, and experimental model panels are hidden by default so the scenario-driven dashboard stays focused.")
        return

    # --- Scheduled Report Emails (manual trigger for demo) ---
    st.subheader("Email Feedback Analytics")
    st.caption("Set SMTP env: YAGMAIL_USER, YAGMAIL_PASSWORD")
    st.markdown("""
    <style>
    div[data-baseweb='input'] {
        max-width: 400px;
    }
    </style>
    """, unsafe_allow_html=True)
    import yagmail
    col1, col2 = st.columns([1,4])
    with col1:
        email_to = st.text_input("Recipient Email", "your@email.com", key="email_input_compact")
        send_btn = st.button("Send Email", key="send_email_compact", width="stretch")
    if send_btn:
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
        st.write
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
    anomaly_feedback_file = "anomaly_feedback.csv"
    if os.path.exists(anomaly_feedback_file):
        # ...existing code for anomaly feedback...
        pass

    # Recommendation feedback analytics
    rec_feedback_file = "recommendation_feedback.csv"
    rec_feedback = []
    st.write("NEW VERSION DEPLOYED")
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
    import plotly.express as px
    st.write("Unified Cloud Cost Analytics Dashboard")

    # Load data
    conn, _ = _get_analytics_connection()
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
    st.plotly_chart(fig_tag, width="stretch")
    st.dataframe(by_tag.rename(columns={'cost': 'Total Cost'}))

    st.markdown("### Cost Breakdown by User")
    by_user = filtered.groupby('user')['cost'].sum().reset_index()
    fig_user = px.bar(by_user, x='user', y='cost', text='cost', title='Cost by User')
    st.plotly_chart(fig_user, width="stretch")
    st.dataframe(by_user.rename(columns={'cost': 'Total Cost'}))

    st.markdown("### Cost Breakdown by Project")
    by_project = filtered.groupby('project')['cost'].sum().reset_index()
    fig_proj = px.bar(by_project, x='project', y='cost', text='cost', title='Cost by Project')
    st.plotly_chart(fig_proj, width="stretch")
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
    st.plotly_chart(fig_mo, width="stretch")
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
        st.plotly_chart(fig_anom, width="stretch")
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
    st.plotly_chart(fig, width="stretch")

    # Cost breakdowns
    st.markdown("### Cost Breakdown")
    col1, col2 = st.columns(2)
    with col1:
        by_account = filtered.groupby('account')['cost'].sum().reset_index()
        fig1 = px.pie(by_account, names='account', values='cost', title='Cost by Account')
        st.plotly_chart(fig1, width="stretch")
    with col2:
        by_service = filtered.groupby('service')['cost'].sum().reset_index()
        fig2 = px.pie(by_service, names='service', values='cost', title='Cost by Service')
        st.plotly_chart(fig2, width="stretch")

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
admin_pages = {"Access Management"} if is_company_admin_role(current_role) or is_global_admin_role(current_role) else set()
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
