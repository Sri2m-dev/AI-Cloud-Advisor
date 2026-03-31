import streamlit as st
st.set_page_config(layout="wide")
print("CEO DASHBOARD FILE:", __file__)
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.aws_cost import get_cost_data

def show_demo_dashboard():

    # 1. HEADER
    st.markdown("""
    # ☁️ AI Cloud Advisor
    """)
    st.caption("Executive Cost Optimization Dashboard")
    st.markdown("---")

    # 2. KPI CARDS (Styled)
    col1, col2, col3, col4 = st.columns(4)

    def kpi_card(title, value, subtitle, gradient):
        st.markdown(f"""
        <div style="
            background: {gradient};
            padding: 20px;
            border-radius: 14px;
            color: white;
            height: 120px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        ">
            <div style="font-size:13px; opacity:0.85;">{title}</div>
            <div style="font-size:28px; font-weight:700; margin-top:6px;">{value}</div>
            <div style="font-size:12px; opacity:0.8; margin-top:4px;">{subtitle}</div>
        </div>
        """, unsafe_allow_html=True)

    with col1:
        kpi_card("Monthly Spend", "$6,500", "Current Month", "linear-gradient(135deg, #2F6F91, #4FA3D1)")
    with col2:
        kpi_card("Yearly Projection", "$78,000", "Forecast", "linear-gradient(135deg, #6F42C1, #9B6DFF)")
    with col3:
        kpi_card("Top Service", "Amazon EC2", "76% of spend", "linear-gradient(135deg, #1F9D8A, #38C6A8)")
    with col4:
        kpi_card("Savings Opportunity", "$3,294", "Potential Optimization", "linear-gradient(135deg, #2EA44F, #6EE7B7)")

    # Spacing after KPI cards
    st.markdown("<br>", unsafe_allow_html=True)

    # Improved Alerts
    st.markdown("""
    <div style="
        background:#FFF3CD;
        padding:12px;
        border-radius:8px;
        margin-bottom:8px;
    ">
    ⚠️ High spend detected in <b>EC2</b>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="
        background:#E7F3FF;
        padding:12px;
        border-radius:8px;
    ">
    💡 Amazon EC2 is your highest cost contributor
    </div>
    """, unsafe_allow_html=True)

    # Space before charts and cost breakdown header
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("## 📊 Cost Breakdown")

    # ...existing code for data...
    df = get_cost_data(demo=True)
    if df.empty:
        st.warning("No cost data available")
        return

    # 5. CHARTS (ONLY ONE BLOCK)
    service_df = df.groupby("service")["cost"].sum().reset_index().rename(columns={"service": "Service", "cost": "Cost"})
    fig_bar = px.bar(
        service_df,
        x="Service",
        y="Cost",
        text="Cost",
        color="Cost",
        color_continuous_scale="Blues"
    )
    fig_bar.update_traces(
        texttemplate='$%{text:,.0f}',
        textposition='outside'
    )
    fig_bar.update_layout(
        title="Top Cost Drivers",
        xaxis_title="Service",
        yaxis_title="Cost ($)",
        showlegend=False,
        height=350,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    trend_df = df.groupby("date")["cost"].sum().reset_index().rename(columns={"date": "Date", "cost": "Cost"})
    threshold = trend_df["Cost"].mean() * 1.3
    trend_df["Anomaly"] = trend_df["Cost"] > threshold
    fig_line = px.line(
        trend_df,
        x="Date",
        y="Cost",
        markers=True
    )
    fig_line.data[0].name = "Actual Cost"
    fig_line.data[0].line.color = "#1f77b4"
    fig_line.add_scatter(
        x=trend_df[trend_df["Anomaly"]]["Date"],
        y=trend_df[trend_df["Anomaly"]]["Cost"],
        mode='markers',
        marker=dict(color='red', size=10),
        name="Anomaly"
    )
    fig_line.update_traces(
        mode="lines+markers+text",
        text=[f"${v:,.0f}" for v in trend_df["Cost"]],
        textposition="top center",
        hovertemplate="Date: %{x}<br>Cost: $%{y:,.0f}"
    )
    fig_line.update_layout(
        title="Spending Trend (Last 3 Months)",
        yaxis_title="Cost ($)",
        legend=dict(
            orientation="h",
            y=1.1,
            x=1,
            xanchor="right"
        ),
        height=350,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    trend_df["Optimized"] = trend_df["Cost"] * 0.85
    fig_line.add_scatter(
        x=trend_df["Date"],
        y=trend_df["Optimized"],
        mode='lines+markers+text',
        text=[f"${v:,.0f}" for v in trend_df["Optimized"]],
        textposition="bottom center",
        line=dict(dash='dash', color='green'),
        name="Optimized Cost"
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top Cost Drivers")
        st.plotly_chart(fig_bar, use_container_width=True, key="bar_chart")
    with col2:
        st.subheader("Spending Trend (Last 3 Months)")
        st.plotly_chart(fig_line, use_container_width=True, key="line_chart")

    # --- Enterprise Bar Chart (Top Cost Drivers) ---
    service_df = df.groupby("service")["cost"].sum().reset_index().rename(columns={"service": "Service", "cost": "Cost"})
    fig_bar = px.bar(
        service_df,
        x="Service",
        y="Cost",
        text="Cost",
        color="Cost",
        color_continuous_scale="Blues"
    )
    fig_bar.update_traces(
        texttemplate='$%{text:,.0f}',
        textposition='outside'
    )
    fig_bar.update_layout(
        title="Top Cost Drivers",
        xaxis_title="Service",
        yaxis_title="Cost ($)",
        showlegend=False,
        height=400,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    # ...existing code for charts and columns remains...

    # --- Multi-Cloud Breakdown (Pie Chart) ---
    cloud_map = {
        "Amazon EC2": "AWS",
        "Amazon S3": "AWS",
        "Amazon RDS": "AWS",
        "Azure VM": "Azure",
        "Azure Blob": "Azure",
        "BigQuery": "GCP"
    }
    df["Cloud"] = df["service"].map(cloud_map)
    cloud_df = df.groupby("Cloud")["cost"].sum().reset_index().dropna()
    fig_pie = px.pie(
        cloud_df,
        names="Cloud",
        values="cost",
        title="Multi-Cloud Spend Distribution"
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    # --- Smart Insight ---
    if not cloud_df.empty:
        top_cloud = cloud_df.sort_values("cost", ascending=False).iloc[0]
        st.markdown(f"""
    <div style="background:#E3F2FD;padding:12px;border-radius:8px">
    {'💡'} {top_cloud['Cloud']} is contributing the highest cloud spend.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    ceo_dashboard()