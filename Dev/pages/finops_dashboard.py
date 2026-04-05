from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
from shared.queries import get_recommendations, get_usage_metrics
from shared.intelligence import generate_recommendations
from shared.aws_cost import get_aws_cost
from shared.supabase_client import get_supabase_client
from shared.nav import render_sidebar, render_header_bar, require_role
from services.ai_insights import explain_recommendation
from services.auto_optimization_engine import auto_optimize
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

require_role("FinOps")

# Sidebar
render_sidebar("FinOps Dashboard")
render_header_bar()

# Data
reco_df = get_recommendations(st.session_state["client_id"])
usage_df = get_usage_metrics(st.session_state["client_id"])
if not usage_df.empty and "cost" not in usage_df.columns and "utilization" in usage_df.columns:
    usage_df = usage_df.copy()
    usage_df["cost"] = usage_df["utilization"] * 0.5  # simple model
auto_reco = generate_recommendations(usage_df)
cost_data = load_cost_data()
cost_df = pd.DataFrame(cost_data)
supabase = get_supabase_client()

st.title("💼 FinOps Dashboard")
st.markdown("---")

# Recommendations
st.subheader("💡 Optimization Opportunities")
st.caption("Recommendation status flow: Pending → Approved → Completed")

if reco_df.empty or "title" not in reco_df.columns:
    st.info("No optimization opportunities found.")
else:
    reco_df = reco_df.copy()
    if "status" not in reco_df.columns:
        reco_df["status"] = "Pending"

    for i, row in reco_df.iterrows():
        recommendation_id = row.get("id")
        recommendation_title = row.get("title", f"Recommendation {i + 1}")
        status = str(row.get("status", "Pending") or "Pending").strip()
        normalized_status = status.lower()

        with st.container(border=True):
            st.write(f"💡 {recommendation_title}")

            details = []
            savings_value = row.get("savings")
            resource_name = row.get("resource")
            if pd.notna(resource_name):
                details.append(f"Resource: {resource_name}")
            if pd.notna(savings_value):
                try:
                    details.append(f"Estimated savings: ${float(savings_value):,.0f}/mo")
                except (TypeError, ValueError):
                    details.append(f"Estimated savings: {savings_value}")
            if details:
                st.caption(" • ".join(details))

            confidence = row.get("confidence")
            if pd.notna(confidence) and str(confidence).strip():
                st.caption(f"Confidence: {confidence}%")

            ai_explanation = row.get("ai_explanation")
            with st.expander("🤖 Why AI recommended this"):
                if pd.notna(ai_explanation) and str(ai_explanation).strip():
                    st.info(str(ai_explanation))
                else:
                    generated_reason = explain_recommendation(row)
                    st.info(generated_reason)

            if normalized_status in {"pending", "open"}:
                st.warning("Status: Pending")
                if st.button(f"Approve {i}", key=f"approve_{recommendation_id or i}"):
                    try:
                        supabase.table("recommendations") \
                            .update({"status": "Approved"}) \
                            .eq("id", recommendation_id) \
                            .execute()
                        st.success("Approved ✅")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Approval failed: {exc}")

            elif normalized_status == "approved":
                st.info("Status: Approved")
                if st.button(f"🚀 Apply Fix {i}", key=f"apply_fix_{recommendation_id or i}"):
                    try:
                        supabase.table("recommendations") \
                            .update({"status": "Completed"}) \
                            .eq("id", recommendation_id) \
                            .execute()

                        supabase.table("execution_logs").insert({
                            "recommendation_id": recommendation_id,
                            "action": recommendation_title,
                            "status": "Completed"
                        }).execute()

                        st.success("Execution Completed 🚀")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Execution failed: {exc}")

            elif normalized_status in {"completed", "success"}:
                st.success("✔ Optimization Applied")
            else:
                st.caption(f"Status: {status}")

try:
    logs = supabase.table("execution_logs").select("*").order("created_at", desc=True).execute()
    logs_df = pd.DataFrame(logs.data)
except Exception:
    logs_df = pd.DataFrame()

st.subheader("📜 Execution History")
if logs_df.empty:
    st.info("No execution logs available yet.")
else:
    st.dataframe(logs_df, use_container_width=True)

safe_mode = st.session_state.get("ai_safe_mode", True)
st.subheader("⚙️ Autonomous Optimization")

def run_auto_optimization():
    st.success("🤖 AI is analyzing your infrastructure...")
    with st.spinner("Running optimization engine..."):
        actions = auto_optimize(usage_df, safe_mode=safe_mode)

    if not actions:
        st.info("No optimization actions recommended right now.")
        return []

    for a in actions:
        st.info(f"{a['action']} → {a['resource']} ({a['status']})")
        try:
            supabase.table("execution_logs").insert({
                "recommendation_id": None,
                "action": a["action"],
                "status": a["status"]
            }).execute()
        except Exception:
            pass

    return actions

if st.button("Run Auto Optimization"):
    run_auto_optimization()

if st.session_state.get("auto_mode"):
    st.warning("⚠️ Autonomous mode active — actions triggered automatically")
    if not st.session_state.get("_auto_optimization_ran", False):
        run_auto_optimization()
        st.session_state["_auto_optimization_ran"] = True
else:
    st.session_state["_auto_optimization_ran"] = False

st.subheader("🤖 Auto Recommendations")

st.dataframe(pd.DataFrame(auto_reco))

# Simple prioritization
st.subheader("🔥 High Impact Savings")

if not reco_df.empty and "savings" in reco_df.columns:
    high_savings = reco_df[reco_df["savings"] > 1000]
    st.dataframe(high_savings)
else:
    st.info("No savings estimates available yet.")

st.subheader("💸 Cost Analysis")

if "cost" in cost_df.columns:
    high_cost = cost_df[cost_df["cost"] > 1000]
    st.dataframe(high_cost)
else:
    st.warning("⚠️ Cost data not available yet")

st.subheader("🧠 AI Explanation")

if not usage_df.empty:
    for _, row in usage_df.iterrows():
        explanation = explain_recommendation(row)
        resource_name = row.get("resource", "Unknown Resource")
        st.info(f"{resource_name} → {explanation}")
else:
    st.info("No usage data available for AI explanation.")

st.subheader("🤖 AI Copilot")
user_input = st.text_input("Ask about your cloud:", key="finops_copilot_input")

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
