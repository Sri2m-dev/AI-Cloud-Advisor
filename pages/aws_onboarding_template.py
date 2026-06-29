from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.aws_onboarding_template_service import AWSOnboardingTemplateService


st.set_page_config(page_title="AWS Onboarding Template", layout="wide")


def _download_json(label: str, payload: dict, filename: str) -> None:
    st.download_button(
        label,
        data=AWSOnboardingTemplateService.to_json(payload),
        file_name=filename,
        mime="application/json",
        use_container_width=True,
    )


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)

    st.title("AWS Customer Onboarding Template")
    st.caption("IAM role, trust policy, and setup guide for connecting AWS to Nexora")

    st.subheader("1. Overview")
    st.info(
        "Use this template to create a read-only AWS role for Nexora. The role enables Cost Explorer, "
        "resource discovery, Compute Optimizer, and Trusted Advisor ingestion without manual data entry."
    )

    st.divider()
    st.subheader("2. Required IAM Permissions")
    permission_rows = AWSOnboardingTemplateService.get_permission_rows()
    st.dataframe(pd.DataFrame(permission_rows), use_container_width=True, hide_index=True)

    iam_policy = AWSOnboardingTemplateService.get_iam_policy()
    st.code(AWSOnboardingTemplateService.to_json(iam_policy), language="json")
    _download_json("Download IAM Permissions Policy", iam_policy, "nexora-aws-iam-policy.json")

    st.divider()
    st.subheader("3. Trust Policy")
    c1, c2 = st.columns(2)
    nexora_account_arn = c1.text_input("Nexora AWS Account ARN", value="<NEXORA_AWS_ACCOUNT_ARN>")
    external_id = c2.text_input("Customer External ID", value="<CUSTOMER_EXTERNAL_ID>")

    trust_policy = AWSOnboardingTemplateService.get_trust_policy(nexora_account_arn, external_id)
    st.code(AWSOnboardingTemplateService.to_json(trust_policy), language="json")
    _download_json("Download Trust Policy", trust_policy, "nexora-aws-trust-policy.json")

    st.divider()
    st.subheader("4. Step-by-step Setup")
    st.dataframe(pd.DataFrame(AWSOnboardingTemplateService.get_setup_steps()), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("5. Role ARN Configuration")
    st.dataframe(
        pd.DataFrame(AWSOnboardingTemplateService.get_role_configuration_fields()),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("6. Validate IAM Readiness")
        st.write("Open AWS Connector Setup and run AWS IAM Readiness using the Role ARN and External ID.")
        if st.button("Open AWS Connector Setup", use_container_width=True):
            st.switch_page("pages/aws_connector_setup.py")

    with right:
        st.subheader("7. Run First Sync")
        st.write("After readiness passes, run Preview AWS Sync, then Run AWS Sync to populate Nexora.")


if __name__ == "__main__":
    main()

