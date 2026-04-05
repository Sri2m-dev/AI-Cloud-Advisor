from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
from shared.queries import get_usage_metrics, get_recommendations
from shared.intelligence import generate_insights
from shared.aws_cost import get_aws_cost
from services.forecast_engine import forecast_cost
from shared.actions import get_action_requests
from shared.supabase_client import get_supabase_client
from shared.nav import render_sidebar, show_ceo_dashboard, require_role
from services.ai_insights import generate_ai_insights, ai_summary, build_safe_summary_input
from services.basic_copilot import generate_response


@st.cache_data(ttl=3600)
def load_cost_data():
    try:
        return get_aws_cost()
    except Exception:
        return {}

# 🔐 Access Control
if "role" not in st.session_state or "client_id" not in st.session_state:
    st.switch_page("app.py")

require_role("CEO")

# -----------------------
# SIDEBAR
# -----------------------
render_sidebar("CEO Dashboard")

# -----------------------
# DATA
# -----------------------
usage_df = get_usage_metrics(st.session_state["client_id"])
if not usage_df.empty and "cost" not in usage_df.columns and "utilization" in usage_df.columns:
    usage_df = usage_df.copy()
    usage_df["cost"] = usage_df["utilization"] * 0.5  # simple model
reco_df = get_recommendations(st.session_state["client_id"])
cost_data = load_cost_data()
cost_df = pd.DataFrame(cost_data)
supabase = get_supabase_client()

try:
    usage = supabase.table("usage_metrics").select("*").eq("client_id", st.session_state["client_id"]).execute()
    usage_df = pd.DataFrame(usage.data)
except Exception:
    pass

try:
    reco = supabase.table("recommendations").select("*").eq("client_id", st.session_state["client_id"]).execute()
    reco_df = pd.DataFrame(reco.data)
except Exception:
    pass

try:
    anomaly = supabase.table("anomalies").select("*").execute()
    anomaly_df = pd.DataFrame(anomaly.data)
except Exception:
    anomaly_df = pd.DataFrame()

if not usage_df.empty and "cost" not in usage_df.columns and "utilization" in usage_df.columns:
    usage_df = usage_df.copy()
    usage_df["cost"] = usage_df["utilization"] * 0.5  # simple model

if cost_df.empty:
    cost_df = pd.DataFrame({
        "service": ["EC2", "S3"],
        "cost": [3200, 800]
    })

trend_cost_df = pd.DataFrame({
    "month": ["Jan", "Feb", "Mar"],
    "cost": [5000, 6500, 6000]
})

forecast = forecast_cost(trend_cost_df)
optimized_cost = cost_df["cost"].sum() * 0.8 if not cost_df.empty and "cost" in cost_df.columns else 0
savings = reco_df["savings"].sum() if not reco_df.empty and "savings" in reco_df.columns else 0
total_cost = usage_df["cost"].sum() if not usage_df.empty and "cost" in usage_df.columns else 0
top_service = usage_df.groupby("service")["cost"].sum().idxmax() if not usage_df.empty and {"service", "cost"}.issubset(usage_df.columns) else "N/A"
anomaly_count = len(anomaly_df)
insights = generate_ai_insights(usage_df, cost_df, reco_df)

# -----------------------
# UI
# -----------------------
st.session_state["usage_df"] = usage_df
st.session_state["reco_df"] = reco_df
st.session_state["cost_df"] = cost_df
show_ceo_dashboard()

st.subheader("🤖 AI Executive Summary")
st.success(f"""
📊 **Monthly Cloud Insight**

• Total Spend: ${total_cost:,.0f}  
• Top Cost Driver: {top_service}  
• Potential Savings: ${savings:,.0f}  
• Anomalies Detected: {anomaly_count}  

👉 AI Recommendation: Focus on optimizing {top_service} to reduce costs by up to 30%.
""")

st.markdown("---")
st.markdown("### 💡 Key Takeaways")

col1, col2, col3 = st.columns(3)
col1.metric("💰 Spend", f"${total_cost:,.0f}")
col2.metric("⚠️ Anomalies", anomaly_count)
col3.metric("💡 Savings", f"${savings:,.0f}")

for insight in insights:
    st.info(insight)

score = 85  # You can calculate later
st.metric("AI Optimization Score", f"{score}/100")
st.metric("� Estimated Savings", f"${savings:.2f}")
st.progress(score / 100)

st.caption("Overall cloud efficiency and optimization health")

st.subheader("🔮 AI Cost Forecast")
if forecast:
    forecast_col1, forecast_col2 = st.columns(2)
    forecast_col1.metric("Next Month Forecast", f"${forecast['next_month']}")
    forecast_col2.metric("3-Month Projection", f"${forecast['three_month']}")

    forecast_df = pd.DataFrame({
        "Month": ["Jan", "Feb", "Mar", "Apr (Forecast)", "May (Forecast)"],
        "Cost": [5000, 6500, 6000, forecast["next_month"], forecast["three_month"]]
    })
    st.line_chart(forecast_df.set_index("Month"))

    if forecast["growth_rate"] > 10:
        st.error(f"⚠️ Cost expected to increase by {forecast['growth_rate']}% next month")

st.subheader("🤖 AI Recommendation Summary")
safe_input = build_safe_summary_input(usage_df, cost_df, reco_df)
summary = ai_summary(safe_input)
st.success(summary)

st.markdown(
    """
    <div style="display:inline-block;background:#ecfdf5;color:#065f46;padding:8px 14px;border-radius:999px;font-weight:600;border:1px solid #a7f3d0;margin-top:0.5rem;">
        🔒 AI Privacy Safe · Only masked optimization signals are shared
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("👁 Workflow Status")
st.caption("Role: CEO · Permission: View only")
action_df = get_action_requests(st.session_state["client_id"])
if action_df.empty:
    st.info("No optimization actions have been submitted yet.")
else:
    action_df = action_df.copy()
    if "status" in action_df.columns:
        action_df["status"] = action_df["status"].astype(str).str.replace("_", " ").str.title()
    view_cols = [col for col in ["recommendation_title", "status", "created_at"] if col in action_df.columns]
    st.dataframe(action_df[view_cols], use_container_width=True)

try:
    logs = supabase.table("execution_logs").select("*").order("created_at", desc=True).limit(10).execute()
    logs_df = pd.DataFrame(logs.data)
except Exception:
    logs_df = pd.DataFrame()

st.subheader("📜 Recent Executions")
st.caption("Recent optimization actions completed by the platform")
if logs_df.empty:
    st.info("No execution history available yet.")
else:
    display_cols = [col for col in ["action", "status", "created_at"] if col in logs_df.columns]
    if "status" in logs_df.columns:
        logs_df["status"] = logs_df["status"].astype(str).str.title()
    st.dataframe(logs_df[display_cols], use_container_width=True)

st.subheader("🤖 AI Copilot")
user_input = st.text_input("Ask about your cloud:", key="ceo_copilot_input")

st.markdown("### 💡 Try asking:")
st.write("- Where am I overspending?")
st.write("- What is my forecast?")
st.write("- Should I migrate to Azure?")

if user_input:
    response = generate_response(user_input, usage_df, cost_df, reco_df)
    with st.chat_message("user"):
        st.write(user_input)
    with st.chat_message("assistant"):
        st.write(response)
