import streamlit as st

def cto_dashboard():
    st.subheader("Technical Overview")
    st.markdown("""
    - **Active Services:** EC2, RDS, S3  
    - **Regions:** ap-south-1, us-east-1  
    - **Instances Running:** 24  
    - **Idle Resources:** 6 instances  
    """)
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("Running Instances", "24")
    col2.metric("Idle Instances", "6")
    col3.metric("Avg CPU Utilization", "38%")
    st.markdown("### ⚙️ Optimization Opportunities")
    st.warning("Underutilized EC2 instances detected")
    st.info("RDS storage can be optimized")
    st.markdown("### 📊 Technical Metrics")
    col1, col2 = st.columns(2)
    with col1:
        st.write("CPU / Memory Graph")
    with col2:
        st.write("Network / Load Graph")
    st.success("🚀 Action: Rightsize EC2 + Enable autoscaling")