from finops_insights import generate_finops_insights

def render_finops_insights(service_cost, symbol):
    st.subheader("AI FinOps Insights")
    insights = generate_finops_insights(service_cost)
    if not insights:
        st.info("No optimization opportunities detected.")
        return
    for insight in insights:
        st.success(
            f"{insight['title']}\n\n"
            f"{insight['description']}\n\n"
            f"Estimated Savings: {symbol}{insight['savings']:,.0f} / year"
        )
def render_cost_forecast(df, symbol):

    import streamlit as st
    import pandas as pd

    st.markdown("## 📊 Cost Forecast")

    if "Month" not in df.columns:
        st.info("Monthly billing data required for forecasting.")
        return

    monthly_cost = (
        df.groupby("Month")["Cost"]
        .sum()
        .reset_index()
    )

    if len(monthly_cost) < 2:
        st.info("At least two months of data required for forecasting.")
        return

    # Sort months
    monthly_cost = monthly_cost.sort_values("Month")

    last_month_spend = monthly_cost.iloc[-1]["Cost"]
    prev_month_spend = monthly_cost.iloc[-2]["Cost"]

    growth_rate = (last_month_spend - prev_month_spend) / prev_month_spend

    forecast = last_month_spend * (1 + growth_rate)

    color = "#16a34a" if growth_rate > 0 else "#dc2626"

    st.markdown(
        f"""
        <div style="
            background:white;
            padding:22px;
            border-radius:14px;
            margin-top:10px;
            margin-bottom:20px;
            border-left:6px solid {color};
            box-shadow:0 6px 18px rgba(0,0,0,0.08);
        ">

        <div style="font-size:14px;color:#6b7280;margin-bottom:8px;">
            Projected Next Month Spend
        </div>

        <div style="font-size:32px;font-weight:800;">
            {symbol}{forecast:,.0f}
        </div>

        <div style="margin-top:8px;font-size:14px;color:{color};font-weight:600;">
            {'▲' if growth_rate > 0 else '▼'} {abs(growth_rate*100):.1f}% projected change
        </div>

        </div>
        """,
        unsafe_allow_html=True
    )
def render_cost_anomaly_detection(df, symbol):

    import streamlit as st
    import pandas as pd

    st.markdown("## 🔎 AI Cost Anomaly Detection")

    if "Month" not in df.columns:
        st.info("Monthly data required for anomaly detection.")
        return

    service_monthly = (
        df.groupby(["Month", "Service"])["Cost"]
        .sum()
        .reset_index()
    )

    months = sorted(service_monthly["Month"].unique())

    if len(months) < 2:
        st.info("At least two months of data required for anomaly detection.")
        return

    last_month = months[-1]
    prev_month = months[-2]

    current = service_monthly[service_monthly["Month"] == last_month]
    previous = service_monthly[service_monthly["Month"] == prev_month]

    merged = pd.merge(
        current,
        previous,
        on="Service",
        suffixes=("_current", "_previous")
    )

    merged["growth"] = (
        (merged["Cost_current"] - merged["Cost_previous"])
        / merged["Cost_previous"]
    ) * 100

    spikes = merged[merged["growth"] > 30]

    if spikes.empty:
        st.success("✅ No abnormal spend spikes detected.")
        return

    for _, row in spikes.iterrows():

        st.markdown(
            f"""
            <div style="
                background:white;
                padding:16px;
                border-radius:12px;
                margin-bottom:10px;
                border-left:5px solid #ef4444;
                box-shadow:0 4px 12px rgba(0,0,0,0.05);
            ">

            ⚠ <b>{row['Service']}</b> increased by 
            <b>{row['growth']:.1f}%</b> compared to last month.

            <br><br>

            Previous Month: {symbol}{row['Cost_previous']:,.0f}<br>
            Current Month: {symbol}{row['Cost_current']:,.0f}

            </div>
            """,
            unsafe_allow_html=True
        )
def render_ai_insights(df, symbol):

    import streamlit as st
    import pandas as pd

    st.markdown("## 🧠 AI Cost Insights")

    service_summary = (
        df.groupby("Service")["Cost_Display"]
        .sum()
        .reset_index()
        .sort_values("Cost_Display", ascending=False)
    )

    total_spend = service_summary["Cost_Display"].sum()

    insights = []

    # Top cost driver insight
    top_service = service_summary.iloc[0]
    percent = (top_service["Cost_Display"] / total_spend) * 100

    insights.append(
        f"**{top_service['Service']}** accounts for **{percent:.1f}%** of total spend. "
        "Rightsizing or reserved capacity may reduce cost."
    )

    # EC2 insight
    if "Elastic Compute Cloud" in service_summary["Service"].values:
        insights.append(
            "EC2 usage suggests opportunity for **Savings Plans or Reserved Instances**."
        )

    # RDS insight
    if "Relational Database Service" in service_summary["Service"].values:
        insights.append(
            "Database workloads may benefit from **instance rightsizing and storage autoscaling**."
        )

    # CloudWatch insight
    if "AmazonCloudWatch" in service_summary["Service"].values:
        insights.append(
            "CloudWatch log costs may indicate **long retention periods**."
        )

    # Generic optimization insight
    insights.append(
        "Overall optimization potential is estimated at **~22% of cloud spend**."
    )

    for insight in insights:

        st.markdown(
            f"""
            <div style="
                background:white;
                padding:16px;
                border-radius:12px;
                margin-bottom:10px;
                border-left:5px solid #2563eb;
                box-shadow:0 4px 12px rgba(0,0,0,0.05);
            ">
            {insight}
            </div>
            """,
            unsafe_allow_html=True
        )
def render_savings_banner(summary, symbol):

    import streamlit as st

    annual_savings = summary["estimated_savings"] * 12
    coverage = (summary["estimated_savings"] / summary["total_spend"]) * 100
    top_service = summary["top_service"]

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(90deg,#ecfdf5,#d1fae5);
            padding:22px;
            border-radius:14px;
            margin-top:20px;
            margin-bottom:25px;
            border-left:6px solid #16a34a;
        ">

        <div style="font-size:16px;font-weight:600;color:#065f46;margin-bottom:14px;">
            💰 FinOps Optimization Summary
        </div>

        <div style="display:flex;justify-content:space-between">

            <div>
                <div style="font-size:13px;color:#047857;">Annual Savings Potential</div>
                <div style="font-size:24px;font-weight:800;color:#065f46;">
                    {symbol}{annual_savings:,.0f}
                </div>
            </div>

            <div>
                <div style="font-size:13px;color:#047857;">Optimization Coverage</div>
                <div style="font-size:22px;font-weight:700;color:#065f46;">
                    {coverage:.1f}%
                </div>
            </div>

            <div>
                <div style="font-size:13px;color:#047857;">Top Cost Driver</div>
                <div style="font-size:18px;font-weight:700;color:#065f46;">
                    {top_service}
                </div>
            </div>

        </div>

        </div>
        """,
        unsafe_allow_html=True
    )
import plotly.express as px
def render_cost_by_service(service_cost, symbol):
    chart_df = service_cost.head(10)
    fig = px.bar(
        chart_df,
        x="Cost",
        y="Service",
        orientation="h",
        text="Cost"
    )
    fig.update_layout(
        yaxis=dict(categoryorder="total ascending")
    )
    fig.update_traces(
        hovertemplate=f"%{{y}}<br>{symbol}%{{x:,.0f}}"
    )
    st.plotly_chart(fig, use_container_width=True)

import streamlit as st
import pandas as pd
import plotly.express as px

st.markdown("""
<style>

.snapshot-card{
    background:white;
    padding:20px;
    border-radius:10px;
}

.snapshot-title{
    font-size:14px;
}

.snapshot-value{
    font-size:28px;
    font-weight:700;
    color:#16a34a;
}

</style>
""", unsafe_allow_html=True)

def render_optimization_potential_card(symbol, optimization):
    import streamlit as st
    st.markdown(f"""
<div class="snapshot-card">
    <div class="snapshot-title">Optimization Potential</div>
    <div class="snapshot-value">
        {symbol}{optimization:,.0f}
    </div>
</div>
""", unsafe_allow_html=True)

def render_executive_snapshot(service_cost, symbol):
    total_spend = service_cost["Cost"].sum()
    top_service = service_cost.iloc[0]["Service"]
    optimization = total_spend * 0.15
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Total Monthly Spend",
        f"{symbol}{total_spend:,.0f}"
    )
    col2.metric(
        "Top Cost Driver",
        top_service
    )
    col3.metric(
        "Optimization Potential",
        f"{symbol}{optimization:,.0f}",
        "15%"
    )

def render_service_breakdown(df, symbol):
    st.markdown(
        "<h2 style='margin-bottom:10px;'>Cost by Service</h2>",
        unsafe_allow_html=True
    )


    service_cost = (
        df.groupby("Service")["Cost_Display"]
        .sum()
        .reset_index()
    )

    # remove total rows
    service_cost = service_cost[service_cost["Service"] != "Total"]

    # sort highest → lowest
    service_cost = service_cost.sort_values(
        by="Cost_Display",
        ascending=False
    )

    fig = px.bar(
        service_cost,
        x="Cost",
        y="Service",
        orientation="h",
        text="Cost"
    )

    fig.update_traces(
        texttemplate=f"{symbol}%{{x:,.0f}}"
    )

    fig.update_layout(
        yaxis=dict(autorange="reversed")
    )

    st.plotly_chart(fig, use_container_width=True)

def render_optimization_recommendations(df, symbol):
    with st.expander("Detailed Optimization Recommendations", expanded=False):

        service_summary = (
            df.groupby("Service")["Cost_Display"]
            .sum()
            .sort_values(ascending=False)
        )

        for service, cost in service_summary.head(5).items():

            if "Relational" in service or "RDS" in service:
                action = "Consider database rightsizing, storage autoscaling, and reserved instances."
            elif "Elastic Compute" in service or "EC2" in service:
                action = "Evaluate Savings Plans, instance rightsizing, and schedule non-production shutdown."
            elif "Simple Storage" in service or "S3" in service:
                action = "Implement lifecycle policies to move data to IA or Glacier tiers."
            elif "CloudWatch" in service:
                action = "Optimize log retention and remove unused custom metrics."
            elif "Data Transfer" in service:
                action = "Review cross-region traffic and enable CloudFront caching."
            else:
                action = "Review utilization metrics and evaluate commitment discounts."

            savings = cost * 0.22

            st.markdown(f"""
**{service}**

<span style="color:#111827;font-weight:600;">Current Spend:</span> {symbol}{cost:,.0f}  

<span style="color:#16a34a;font-weight:600;">Potential Savings:</span> {symbol}{savings:,.0f}

Recommendation: {action}

---
""", unsafe_allow_html=True)

def render_top_optimization_opportunities(df, symbol):
    st.markdown("## Top Optimization Opportunities")

    st.markdown("""
<style>

.op-card {
    background: white;
    padding: 18px;
    border-radius: 14px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:12px;
    border-left:5px solid #16a34a;
    transition: all 0.25s ease;
    cursor:pointer;
}

.op-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 28px rgba(0,0,0,0.12);
    border-left:5px solid #15803d;
}

.op-title {
    font-size:16px;
    font-weight:600;
    color:#111827;
}

.op-value {
    font-size:18px;
    font-weight:700;
    color:#16a34a;
}

</style>
""", unsafe_allow_html=True)

    service_summary = (
        df.groupby("Service")["Cost_Display"]
        .sum()
        .sort_values(ascending=False)
    )

    for service, cost in service_summary.head(5).items():

        if "Relational" in service or "RDS" in service:
            title = "🗄️ Database Optimization"
        elif "Elastic Compute" in service or "EC2" in service:
            title = "⚡ EC2 Savings Plans"
        elif "Simple Storage" in service or "S3" in service:
            title = "📦 S3 Lifecycle Policy"
        else:
            title = "💡 Cost Optimization"

        savings = cost * 0.22

        st.markdown(f"""
        <div class="op-card">
            <div class="op-title">{title}</div>
            <div class="op-value">{symbol}{savings:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)

def render_monthly_trend(df, symbol):

    if "Date" not in df.columns:
        st.markdown("## Monthly Cost Trend")
        st.info("Monthly trend unavailable — no date column found.")
        return
    if "Month" not in df.columns:
        st.markdown("## Monthly Cost Trend")
        st.info("Monthly trend unavailable – no date column found in the uploaded CSV.")
        return

    st.markdown("## Monthly Cost Trend")

    monthly_cost = (
        df.groupby("Month")["Cost"]
        .sum()
        .reset_index()
        .sort_values("Month")
    )

    fig = px.line(
        monthly_cost,
        x="Month",
        y="Cost",
        markers=True
    )

    fig.update_traces(
        line=dict(color="#2563eb", width=3),
        marker=dict(size=8),
        hovertemplate=f"{symbol}%{{y:,.0f}}"
    )

    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        yaxis_title="",
        xaxis_title=""
    )

    st.plotly_chart(fig, use_container_width=True)

def render_cost_spike_detector(df, symbol):
    st.markdown("## ⚠ Cost Spike Detector")

    if "Month" not in df.columns:
        st.info("Cost spike detection requires monthly billing data.")
        return

    monthly_service_cost = (
        df.groupby(["Month", "Service"])["Cost"]
        .sum()
        .reset_index()
    )

    pivot = monthly_service_cost.pivot(
        index="Service",
        columns="Month",
        values="Cost"
    ).fillna(0)

    if pivot.shape[1] < 2:
        st.info("Not enough monthly data to detect spikes.")
        return

    months = list(pivot.columns)

    last_month = months[-1]
    spikes = []

    for service in pivot.index:
        previous = pivot.loc[service, months[-2]] if len(months) > 1 else 0
        current = pivot.loc[service, last_month]
        if previous == 0:
            continue
        change_pct = ((current - previous) / previous) * 100
        if change_pct > 30:   # spike threshold
            spikes.append({
                "service": service,
                "increase": current - previous,
                "pct": change_pct
            })

    if not spikes:
        st.success("No abnormal cost spikes detected.")
        return

    for spike in spikes:
        st.warning(
            f"""
**{spike['service']}**

Increase: **{symbol}{spike['increase']:,.0f}**

Growth: **{spike['pct']:.1f}% vs last month**
"""
        )

def render_cost_distribution(df, symbol, total_spend):

    st.markdown(
        "<h2 style='white-space:nowrap;'>Spend Distribution</h2>",
        unsafe_allow_html=True
    )

    service_summary = (
        df.groupby("Service")["Cost"]
        .sum()
        .reset_index()
        .sort_values("Cost", ascending=False)
    )

    top_services = service_summary.head(6)

    others_cost = service_summary.iloc[6:]["Cost"].sum()

    if others_cost > 0:
        others_row = pd.DataFrame({
            "Service": ["Others"],
            "Cost": [others_cost]
        })
        top_services = pd.concat([top_services, others_row])

    # Wider donut column
    col1, col2 = st.columns([3, 1])

    fig = px.pie(
        top_services,
        values="Cost",
        names="Service",
        hole=0.6
    )

    fig.update_traces(
        textinfo="percent",
        textposition="inside"
    )

    fig.update_layout(
        showlegend=False,
        height=500,  # increase donut size
        margin=dict(t=0, b=0, l=40, r=0),
        annotations=[
            dict(
                text=f"{symbol}{total_spend:,.0f}<br>Total Spend",
                showarrow=False,
                font=dict(size=20)
            )
        ]
    )

    with col1:
        st.markdown("<div style='margin-top:-40px'>", unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div style='margin-top:20px'>", unsafe_allow_html=True)
        for service in top_services["Service"]:
            st.markdown(
                f"<div style='margin-bottom:10px;'>• {service}</div>",
                unsafe_allow_html=True
            )
        st.markdown("</div>", unsafe_allow_html=True)

def render_finops_score(df):
    import streamlit as st
    st.markdown("## FinOps Health Score")
    total_services = df["Service"].nunique()
    total_spend = df["Cost"].sum()
    # Simple scoring logic
    score = 50
    if total_services > 5:
        score += 10
    if total_spend > 100000:
        score += 10
    if total_services > 8:
        score += 10
    score = min(score, 100)
    if score >= 80:
        level = "Optimized"
    elif score >= 60:
        level = "Moderate Optimization"
    else:
        level = "High Optimization Potential"
    st.metric("FinOps Score", f"{score}/100")
    st.progress(score / 100)
    st.caption(level)

def render_cloud_waste_detection(df, symbol):
    import streamlit as st
    with st.expander("☁ Cloud Waste Detection", expanded=False):
        service_cost = df.groupby("Service")["Cost_Display"].sum().sort_values(ascending=False)
        total_spend = service_cost.sum()
        low_spend = service_cost[service_cost < (total_spend * 0.05)]
        high_spend = service_cost[service_cost > (total_spend * 0.25)]
        waste_items = []
        for svc in low_spend.index:
            waste_items.append(f"⚠ **{svc}** may indicate idle resources.")
        for svc in high_spend.index:
            waste_items.append(f"💰 **{svc}** is a major cost driver — optimization recommended.")
        if len(waste_items) == 0:
            st.success("No obvious waste patterns detected.")
        else:
            for item in waste_items:
                st.markdown(item)
