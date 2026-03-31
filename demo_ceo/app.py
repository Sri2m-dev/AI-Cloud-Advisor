import streamlit as st
def main():
    st.set_page_config(layout="wide")

    st.markdown("### 🚀 Demo Mode")
    st.title("AI Cloud Advisor")
    st.caption("Executive Cost & Savings Report — March 2026")

    # -----------------------
    # EXECUTIVE SNAPSHOT
    # -----------------------
    st.subheader("1. Executive Snapshot")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Run Rate", "€42,300", "+8.7%")
    col2.metric("30-Day Outlook", "€44,000")
    col3.metric("90-Day Outlook", "€132,000")
    col4.metric("Savings Opportunity", "€8,300")

    st.info("Cloud operating cost is trending above baseline driven by compute and data platform scaling.")

    # -----------------------
    # COST DRIVERS
    # -----------------------
    st.subheader("2. Primary Cost Drivers")

    import pandas as pd

    drivers = pd.DataFrame({
        "Service": ["Compute", "Databases", "Storage", "Networking", "Analytics"],
        "Cloud": ["AWS", "Azure", "AWS", "AWS", "Azure"],
        "Cost (€)": [17800, 8900, 6200, 4100, 3300],
        "MoM Change": ["+14%", "+9%", "+5%", "+18%", "+11%"],
        "Cause": [
            "Oversized instances",
            "Over-provisioned DB",
            "No lifecycle policy",
            "Cross-region traffic",
            "Uncontrolled batch jobs"
        ]
    })

    st.dataframe(drivers, use_container_width=True)

    # -----------------------
    # SAVINGS
    # -----------------------
    st.subheader("3. Cost Reduction Opportunity")

    col1, col2, col3 = st.columns(3)

    col1.metric("No-disruption", "€5,200")
    col2.metric("Controlled Optimization", "€3,100")
    col3.metric("Total Savings", "€8,300")

    st.success("~20% cost reduction achievable without impacting business operations.")

    # -----------------------
    # BUSINESS UNIT
    # -----------------------
    st.subheader("4. Cost Ownership")

    bu = pd.DataFrame({
        "Business Unit": [
            "Product & Engineering",
            "Customer Operations",
            "Data & AI",
            "Shared / Platform",
            "Unowned"
        ],
        "Monthly (€)": [21600, 10200, 6800, 2500, 1200],
        "%": [51, 24, 16, 6, 3]
    })

    st.dataframe(bu, use_container_width=True)

    # -----------------------
    # PIPELINE
    # -----------------------
    st.subheader("5. Savings Pipeline")

    pipeline = pd.DataFrame({
        "Stage": ["Identified", "Accepted", "In Progress", "Realized"],
        "Monthly Value (€)": [8300, 6700, 4900, 2100],
        "Status": ["✅", "✅", "🟡", "✅"]
    })

    st.dataframe(pipeline, use_container_width=True)

    # -----------------------
    # CEO MESSAGE
    # -----------------------
    st.subheader("7. CEO Bottom Line")

    st.warning(
        "Cloud cost is increasing faster than business growth. "
        "However, ~€100K annual savings is achievable with low risk and clear ownership."
    )

if __name__ == "__main__":
    main()