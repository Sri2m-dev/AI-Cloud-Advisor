import plotly.express as px
import streamlit as st
import plotly.express as px

def render_executive_snapshot(summary, symbol):
    st.markdown("## Executive Snapshot")

    total_spend = summary["total_spend"]
    top_service = summary["top_service"]
    estimated_savings = summary["estimated_savings"]

    savings_pct = 0
    if total_spend > 0:
        savings_pct = (estimated_savings / total_spend) * 100

    if savings_pct >= 20:
        badge_color = "#16a34a"
    elif savings_pct >= 10:
        badge_color = "#d97706"
    else:
        badge_color = "#dc2626"

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div style="background:white;padding:25px;border-radius:16px;
                    box-shadow:0 8px 20px rgba(0,0,0,0.05);
                    border-left:6px solid #2563eb;height:150px;">
            <div style="font-size:14px;color:#6b7280;font-weight:600;">
                Total Monthly Spend
            </div>
            <div style="font-size:24px;font-weight:700;margin-top:20px;">
                {symbol}{total_spend:,.0f}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background:white;padding:25px;border-radius:16px;
                    box-shadow:0 8px 20px rgba(0,0,0,0.05);
                    border-left:6px solid #2563eb;height:150px;">
            <div style="font-size:14px;color:#6b7280;font-weight:600;">
                Top Cost Driver
            </div>
            <div style="font-size:20px;font-weight:700;margin-top:20px;">
                {top_service}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="background:white;padding:25px;border-radius:16px;
                    box-shadow:0 8px 20px rgba(0,0,0,0.05);
                    border-left:6px solid #2563eb;height:150px;">
            <div style="font-size:14px;color:#6b7280;font-weight:600;">
                Optimization Potential
            </div>
            <div style="font-size:24px;font-weight:700;margin-top:20px;">
                {symbol}{estimated_savings:,.0f}
                <span style="background:{badge_color};
                             color:white;
                             padding:4px 10px;
                             border-radius:12px;
                             font-size:12px;
                             margin-left:10px;">
                    {savings_pct:.1f}%
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_service_breakdown(df, symbol):
    st.markdown("## Cost by Service")

    service_summary = (
        df.groupby("Service")["Cost"]
        .sum()
        .reset_index()
        .sort_values("Cost", ascending=False)
    )

    fig = px.bar(
        service_summary.head(10),
        x="Service",
        y="Cost",
        text_auto=True
    )

    fig.update_traces(
        texttemplate=f"{symbol}%{{y:,.0f}}",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_title=f"Cost ({symbol})",
        xaxis_title="",
        uniformtext_minsize=8,
        uniformtext_mode="hide"
    )

    st.plotly_chart(fig, use_container_width=True)
