import json
from datetime import date

import pandas as pd
import streamlit as st

from components.sidebar_navigation import render_sidebar_navigation
from database.db import supabase

role = st.session_state.get("role", "Unknown")
render_sidebar_navigation(role)

st.title("📤 Cost Upload Center")

st.markdown("""
Upload cost files from:

- AWS CUR
- Azure Cost Export
- GCP Billing Export
- SaaS Vendors
- MSP Invoices
""")

upload_type = st.selectbox(
    "Upload Type",
    [
        "AWS",
        "Azure",
        "GCP",
        "SaaS",
        "MSP"
    ]
)

uploaded_file = st.file_uploader(
    "Upload CSV",
    type=["csv"]
)

if uploaded_file:

    try:

        df = pd.read_csv(uploaded_file)

        st.success(
            f"{uploaded_file.name} loaded successfully."
        )

        st.subheader("Preview")

        st.dataframe(
            df.head(20),
            use_container_width=True
        )

        if upload_type == "AWS":

            service_col = None
            cost_col = None

            if "Service" in df.columns:
                service_col = "Service"

            if service_col is None:
                for col in df.columns:
                    if "service" in str(col).lower():
                        service_col = col
                        break

            preferred_cost_columns = [
                "Total Cost",
                "Cost",
                "Blended Cost",
                "Unblended Cost"
            ]

            for candidate in preferred_cost_columns:
                if candidate in df.columns:
                    cost_col = candidate
                    break

            if cost_col is None:
                for col in df.columns:
                    if "cost" in str(col).lower():
                        cost_col = col
                        break

            if service_col is None:
                st.error(
                    "Could not locate Service column."
                )
                st.stop()

            if cost_col is None:
                st.error(
                    "Could not locate Cost column."
                )
                st.stop()

            service_col = st.selectbox(
                "Service Column",
                df.columns,
                index=list(df.columns).index(
                    service_col
                )
            )

            cost_col = st.selectbox(
                "Cost Column",
                df.columns,
                index=list(df.columns).index(
                    cost_col
                )
            )

            st.info(
                f"Detected Service Column: {service_col}"
            )

            st.info(
                f"Detected Cost Column: {cost_col}"
            )

            grouped_df = (
                df.groupby(service_col)[cost_col]
                .sum()
                .reset_index()
            )

            st.info(
                f"Aggregated {len(df)} rows into "
                f"{len(grouped_df)} unique services."
            )

            if st.button(
                "Load Into Unified Cloud Costs"
            ):

                inserted = 0
                duplicates = 0
                failed = 0

                for _, row in grouped_df.iterrows():

                    try:

                        service_name = str(
                            row[service_col]
                        ).strip()

                        cost_value = pd.to_numeric(
                            row[cost_col],
                            errors="coerce"
                        )

                        if pd.isna(cost_value):
                            continue

                        existing = (
                            supabase
                            .table("unified_cloud_costs")
                            .select("id")
                            .eq("cloud", "aws")
                            .eq(
                                "account_name",
                                "aws-main"
                            )
                            .eq(
                                "service_name",
                                service_name
                            )
                            .eq(
                                "usage_date",
                                str(date.today())
                            )
                            .execute()
                        )

                        if existing.data:
                            duplicates += 1
                            continue

                        payload = {
                            "cloud": "aws",
                            "account_name": "aws-main",
                            "service_name": service_name,
                            "region": "global",
                            "resource_id": None,
                            "usage_date": str(
                                date.today()
                            ),
                            "usage_quantity": 0,
                            "cost": float(
                                cost_value
                            ),
                            "currency": "USD",
                            "environment": None,
                            "application": None,
                            "usage_hours": None,
                            "utilization": None,
                            "tags": {}
                        }

                        (
                            supabase
                            .table(
                                "unified_cloud_costs"
                            )
                            .insert(payload)
                            .execute()
                        )

                        inserted += 1

                    except Exception as e:

                        failed += 1

                        if failed <= 10:
                            st.error(
                                f"{service_name}: {e}"
                            )

                total_cost = (
                    pd.to_numeric(
                        df[cost_col],
                        errors="coerce"
                    )
                    .fillna(0)
                    .sum()
                )

                try:

                    (
                        supabase
                        .table("cost_uploads")
                        .insert(
                            {
                                "upload_type":
                                    upload_type,
                                "provider":
                                    upload_type,
                                "file_name":
                                    uploaded_file.name,
                                "billing_period":
                                    "Manual Upload",
                                "total_cost":
                                    float(total_cost),
                                "currency":
                                    "USD",
                                "uploaded_by":
                                    st.session_state.get(
                                        "user_email",
                                        "system"
                                    ),
                                "upload_status":
                                    "Uploaded"
                            }
                        )
                        .execute()
                    )

                except Exception as audit_error:

                    st.warning(
                        f"Audit logging failed: "
                        f"{audit_error}"
                    )

                st.success(
                    f"Inserted: {inserted} | "
                    f"Duplicates: {duplicates} | "
                    f"Failed: {failed}"
                )

        else:

            st.warning(
                "Azure, GCP, SaaS and MSP "
                "uploads are not yet implemented."
            )

    except Exception as e:

        st.error(
            f"Failed to process file: {e}"
        )
