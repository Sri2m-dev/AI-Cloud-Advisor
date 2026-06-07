import streamlit as st
from core.supabase_client import supabase

# =====================================================
# PAGE HEADER
# =====================================================

st.title("☁️ Cloud Connections")

# =====================================================
# CONNECTION TEST
# =====================================================

try:
    result = (
        supabase
        .table("cloud_connections")
        .select("*")
        .limit(5)
        .execute()
    )

    st.success("Supabase Connected")

except Exception as e:
    st.error(f"Database Connection Error: {e}")
    st.stop()

# =====================================================
# TABS
# =====================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Connections",
        "AWS",
        "Azure",
        "GCP",
    ]
)

# =====================================================
# CONNECTION LIST
# =====================================================

with tab1:

    st.subheader("Existing Cloud Connections")

    try:
        result = (
            supabase
            .table("cloud_connections")
            .select("*")
            .execute()
        )

        if result.data:
            st.dataframe(
                result.data,
                use_container_width=True
            )
        else:
            st.info(
                "No cloud connections configured."
            )

    except Exception as e:
        st.error(str(e))

# =====================================================
# AWS
# =====================================================

with tab2:

    st.subheader("Add AWS Account")

    account_name = st.text_input(
        "Account Name",
        key="aws_account_name"
    )

    account_id = st.text_input(
        "AWS Account ID",
        key="aws_account_id"
    )

    role_arn = st.text_input(
        "Role ARN",
        key="aws_role_arn"
    )

    external_id = st.text_input(
        "External ID",
        key="aws_external_id"
    )

    if st.button(
        "Add AWS Account",
        key="add_aws"
    ):

        try:

            (
                supabase
                .table("cloud_connections")
                .insert(
                    {
                        "provider": "AWS",
                        "account_name": account_name,
                        "account_id": account_id,
                        "role_arn": role_arn,
                        "external_id": external_id,
                        "status": "Pending",
                    }
                )
                .execute()
            )

            st.success(
                "AWS account added successfully."
            )

        except Exception as e:
            st.error(str(e))

# =====================================================
# AZURE
# =====================================================

with tab3:

    st.subheader("Add Azure Subscription")

    tenant_id = st.text_input(
        "Tenant ID",
        key="azure_tenant_id"
    )

    subscription_id = st.text_input(
        "Subscription ID",
        key="azure_subscription_id"
    )

    client_id = st.text_input(
        "Client ID",
        key="azure_client_id"
    )

    if st.button(
        "Add Azure Subscription",
        key="add_azure"
    ):

        try:

            (
                supabase
                .table("cloud_connections")
                .insert(
                    {
                        "provider": "Azure",
                        "tenant_id": tenant_id,
                        "subscription_id": subscription_id,
                        "account_id": client_id,
                        "status": "Pending",
                    }
                )
                .execute()
            )

            st.success(
                "Azure subscription added successfully."
            )

        except Exception as e:
            st.error(str(e))

# =====================================================
# GCP
# =====================================================

with tab4:

    st.subheader("Add GCP Project")

    project_id = st.text_input(
        "Project ID",
        key="gcp_project_id"
    )

    if st.button(
        "Add GCP Project",
        key="add_gcp"
    ):

        try:

            (
                supabase
                .table("cloud_connections")
                .insert(
                    {
                        "provider": "GCP",
                        "project_id": project_id,
                        "status": "Pending",
                    }
                )
                .execute()
            )

            st.success(
                "GCP project added successfully."
            )

        except Exception as e:
            st.error(str(e))