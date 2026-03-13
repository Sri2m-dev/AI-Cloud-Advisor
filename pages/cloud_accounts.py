import streamlit as st

def cloud_accounts_page():
    st.title("Cloud Accounts")
    st.subheader("Connect your cloud account")

    provider = st.selectbox("Provider", ["AWS", "Azure", "GCP"], index=0)

    if provider == "AWS":
        role_arn = st.text_input("Role ARN")
        external_id = st.text_input("External ID")
    elif provider == "Azure":
        tenant_id = st.text_input("Tenant ID")
        client_id = st.text_input("Client ID")
        client_secret = st.text_input("Client Secret", type="password")
        subscription_id = st.text_input("Subscription ID")
    elif provider == "GCP":
        st.info("Upload your GCP Service Account JSON file.")
        gcp_json = st.file_uploader("Service Account JSON", type="json")

    if st.button("Connect Account"):
        if provider == "AWS":
            if role_arn and external_id:
                from services.aws_connector import assume_role, get_cost_explorer_client
                try:
                    temp_creds = assume_role(role_arn, external_id)
                    if temp_creds:
                        ce_client = get_cost_explorer_client(temp_creds)
                        response = ce_client.get_cost_and_usage(
                            TimePeriod={
                                "Start": "2026-01-01",
                                "End": "2026-03-13"
                            },
                            Granularity="MONTHLY",
                            Metrics=["UnblendedCost"]
                        )
                        results = []
                        for r in response["ResultsByTime"]:
                            results.append({
                                "month": r["TimePeriod"]["Start"],
                                "cost": float(r["Total"]["UnblendedCost"]["Amount"])
                            })
                        st.success("AWS account connected successfully!")
                        st.write("Cost Explorer Results:", results)
                    else:
                        st.error("Failed to assume role. Check ARN and External ID.")
                except Exception as e:
                    st.error(f"AWS authentication failed: {e}")
            else:
                st.error("Please fill in all fields.")
        elif provider == "Azure":
            if tenant_id and client_id and client_secret and subscription_id:
                from services.azure_connector import get_azure_resource_groups
                try:
                    resource_groups = get_azure_resource_groups(tenant_id, client_id, client_secret, subscription_id)
                    st.success("Azure account connected successfully!")
                    st.write("Resource Groups:", resource_groups)
                except Exception as e:
                    st.error(f"Azure authentication failed: {e}")
            else:
                st.error("Please fill in all fields.")
        elif provider == "GCP":
            if gcp_json:
                from services.gcp_connector import list_gcp_buckets
                try:
                    buckets = list_gcp_buckets(gcp_json.read())
                    st.success("GCP account connected successfully!")
                    st.write("Buckets:", buckets)
                except Exception as e:
                    st.error(f"GCP authentication failed: {e}")
            else:
                st.error("Please upload your Service Account JSON file.")

if __name__ == "__main__":
    cloud_accounts_page()
