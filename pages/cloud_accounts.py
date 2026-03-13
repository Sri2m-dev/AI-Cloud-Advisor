import streamlit as st

def cloud_accounts_page():
    st.title("Cloud Accounts")
    st.subheader("Connect your cloud account")

    provider = st.selectbox("Provider", ["AWS", "Azure", "GCP"], index=0)
    role_arn = st.text_input("Role ARN")
    external_id = st.text_input("External ID")

    if st.button("Connect Account"):
        if provider and role_arn and external_id:
            st.success(f"{provider} account connected successfully!")
        else:
            st.error("Please fill in all fields.")

if __name__ == "__main__":
    cloud_accounts_page()
