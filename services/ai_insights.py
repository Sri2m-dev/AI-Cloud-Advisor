import os


def ai_summary(text):
    fallback = "Based on current usage patterns, optimizing EC2 instances can reduce costs by 20–30%."

    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return fallback

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a FinOps assistant. Summarize only cloud cost optimization insights. "
                        "Never include client names, IDs, emails, or other sensitive data."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content or fallback
    except Exception:
        return fallback


def build_safe_summary_input(usage_df, cost_df, reco_df):
    total_cost = 0.0
    underutilized_count = 0
    potential_savings = 0.0
    recommendation_count = 0 if reco_df is None else len(reco_df)

    if cost_df is not None and not cost_df.empty and "cost" in cost_df.columns:
        total_cost = float(cost_df["cost"].fillna(0).sum())

    if usage_df is not None and not usage_df.empty and "utilization" in usage_df.columns:
        underutilized_count = int((usage_df["utilization"] < 40).sum())
        if total_cost == 0 and "cost" in usage_df.columns:
            total_cost = float(usage_df["cost"].fillna(0).sum())

    if reco_df is not None and not reco_df.empty and "savings" in reco_df.columns:
        potential_savings = float(reco_df["savings"].fillna(0).sum())

    return f"""
Summarize cost optimization insights only for an executive dashboard.
Do not mention any client names, IDs, emails, regions, or sensitive raw records.

Total monthly cost: ${total_cost:,.2f}
Underutilized resources: {underutilized_count}
Potential savings identified: ${potential_savings:,.2f}
Recommendation count: {recommendation_count}

Provide a concise 2-3 sentence summary with business impact.
""".strip()


def explain_recommendation(row):
    util = row.get("utilization", 0)

    if util < 30:
        return "This resource is underutilized (<30%), indicating over-provisioning."
    elif util > 85:
        return "This resource is overutilized (>85%), which may impact performance."
    else:
        return "Resource is within optimal utilization range."


def generate_ai_insights(usage_df, cost_df, reco_df):
    insights = []

    safe_mode = True
    try:
        import streamlit as st

        safe_mode = st.session_state.get("ai_safe_mode", True)
    except Exception:
        pass

    if safe_mode:
        insights.append("🔐 AI running in SAFE MODE (no sensitive data shared)")

    # 1. High cost detection
    if not cost_df.empty and "cost" in cost_df.columns:
        total_cost = cost_df["cost"].sum()
        if total_cost > 5000:
            insights.append(f"⚠️ High monthly spend detected: ${total_cost}")

    # 2. Low utilization
    if not usage_df.empty and "utilization" in usage_df.columns:
        low_util = usage_df[usage_df["utilization"] < 40]
        if not low_util.empty:
            insights.append(f"💡 {len(low_util)} resources are underutilized")

    # 3. Recommendations summary
    if not reco_df.empty:
        savings = reco_df["savings"].sum() if "savings" in reco_df.columns else 0
        insights.append(f"💰 Potential savings identified: ${savings}")

    # 4. Default fallback
    if not insights:
        insights.append("✅ Infrastructure looks optimized")

    return insights
