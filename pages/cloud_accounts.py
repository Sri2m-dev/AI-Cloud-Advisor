import json

import pandas as pd
import streamlit as st

from database.db import get_account_limit, get_connected_account_count, list_cloud_accounts, list_sync_runs
from services.demo_environment import list_demo_scenarios, reset_demo_environment, seed_demo_environment
from services.cloud_account_service import CloudAccountSyncError, create_cloud_account, sync_cloud_account


PROVIDER_OPTIONS = ["AWS", "Azure", "GCP"]
WIZARD_STEPS = [
    "Choose provider",
    "Review readiness",
    "Enter credentials",
    "Connect account",
]

DEMO_SCENARIO_SIGNALS = {
    "healthy": [
        "Stable cloud account health across providers",
        "Low-risk recommendation set with minimal follow-up",
        "Clean billing history for baseline dashboard testing",
    ],
    "cost_spike": [
        "Accelerated spend in compute and analytics services",
        "Forecast risk item seeded for Dashboard and Recommendations",
        "Higher urgency recommendations for anomaly review",
    ],
    "waste_heavy": [
        "Oversized compute and storage-heavy usage patterns",
        "Optimization-focused recommendations with larger savings",
        "Useful for testing waste and rightsizing workflows",
    ],
    "governance_failure": [
        "Validation and policy failures across cloud accounts",
        "Governance and billing-export remediation items",
        "Useful for testing attention states in Cloud Operations",
    ],
    "mixed_failures": [
        "One healthy account plus governance and billing issues",
        "Forecast risk item seeded without opening Cost Forecast first",
        "Best end-to-end demo for dashboard and inbox testing",
    ],
}


def _wizard_defaults():
    return {
        "provider": "AWS",
        "role_arn": "",
        "external_id": "",
        "tenant_id": "",
        "client_id": "",
        "client_secret": "",
        "subscription_id": "",
        "gcp_json_bytes": None,
        "gcp_json_name": "",
        "gcp_billing_project_id": "",
        "gcp_billing_dataset": "",
        "gcp_billing_table": "",
        "gcp_billing_account_id": "",
    }


def _ensure_wizard_state():
    if "cloud_account_wizard" not in st.session_state:
        st.session_state["cloud_account_wizard"] = _wizard_defaults()
    if "cloud_account_wizard_step" not in st.session_state:
        st.session_state["cloud_account_wizard_step"] = 1


def _reset_wizard():
    st.session_state["cloud_account_wizard"] = _wizard_defaults()
    st.session_state["cloud_account_wizard_step"] = 1


def _provider_requirements(provider, wizard_state):
    if provider == "AWS":
        return [
            ("Role ARN provided", bool(wizard_state["role_arn"])),
            ("External ID provided", bool(wizard_state["external_id"])),
            ("Cross-account role is configured for Cost Explorer access", False),
        ]
    if provider == "Azure":
        return [
            ("Tenant ID provided", bool(wizard_state["tenant_id"])),
            ("Client ID provided", bool(wizard_state["client_id"])),
            ("Client secret provided", bool(wizard_state["client_secret"])),
            ("Subscription ID provided", bool(wizard_state["subscription_id"])),
            ("Service principal can query Azure Cost Management", False),
        ]
    return [
        ("Service account JSON uploaded", wizard_state["gcp_json_bytes"] is not None),
        ("Billing export project ID provided", bool(wizard_state["gcp_billing_project_id"])),
        ("Billing export dataset provided", bool(wizard_state["gcp_billing_dataset"])),
        ("Billing export table provided", bool(wizard_state["gcp_billing_table"])),
        ("Service account has BigQuery read access to the billing export dataset", False),
    ]


def _configured_requirement_count(requirements):
    return sum(1 for _, ready in requirements if ready)


def _render_provider_help(provider):
    if provider == "AWS":
        st.caption("Use a dedicated cross-account role with Cost Explorer permissions and a unique external ID.")
    elif provider == "Azure":
        st.caption("Use a service principal with Cost Management reader access on the target subscription.")
    else:
        st.caption("Use a GCP service account plus a BigQuery Cloud Billing export table for real cost sync.")
        with st.expander("GCP setup requirements", expanded=False):
            st.markdown(
                """
1. Enable Cloud Billing export to BigQuery in your GCP billing account.
2. Use the project, dataset, and table name created by that export.
3. Grant the uploaded service account BigQuery read access to that billing export dataset.
4. If the export table contains multiple billing accounts, optionally provide the billing account ID to filter the sync.
                """
            )


def _build_payload_from_wizard(wizard_state):
    provider = wizard_state["provider"]
    return _account_payload(
        provider,
        wizard_state["role_arn"],
        wizard_state["external_id"],
        wizard_state["tenant_id"],
        wizard_state["client_id"],
        wizard_state["client_secret"],
        wizard_state["subscription_id"],
        wizard_state["gcp_json_bytes"],
        wizard_state["gcp_billing_project_id"],
        wizard_state["gcp_billing_dataset"],
        wizard_state["gcp_billing_table"],
        wizard_state["gcp_billing_account_id"],
    )


def _wizard_has_required_fields(wizard_state):
    return _required_fields_present(
        wizard_state["provider"],
        wizard_state["role_arn"],
        wizard_state["external_id"],
        wizard_state["tenant_id"],
        wizard_state["client_id"],
        wizard_state["client_secret"],
        wizard_state["subscription_id"],
        wizard_state["gcp_json_bytes"],
        wizard_state["gcp_billing_project_id"],
        wizard_state["gcp_billing_dataset"],
        wizard_state["gcp_billing_table"],
    )


def _render_step_status(current_step):
    columns = st.columns(len(WIZARD_STEPS))
    for index, label in enumerate(WIZARD_STEPS, start=1):
        if index < current_step:
            columns[index - 1].success(f"{index}. {label}")
        elif index == current_step:
            columns[index - 1].info(f"{index}. {label}")
        else:
            columns[index - 1].caption(f"{index}. {label}")


def _render_demo_environment_status():
    active_demo = st.session_state.get("active_demo_environment")
    if not active_demo:
        return

    st.success(
        f"Active demo scenario: {active_demo['label']}"
    )
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Seeded Accounts", active_demo.get("accounts", 0))
    metric_col2.metric("Billing Rows", active_demo.get("billing_rows", 0))
    metric_col3.metric("Workflow Items", active_demo.get("recommendations", 0))
    st.caption(active_demo.get("description", ""))
    action_col1, action_col2 = st.columns([1.2, 1.4])
    if action_col1.button("Open Dashboard", key="open_active_demo_dashboard", use_container_width=True):
        st.session_state["selected_page"] = "Dashboard"
        st.rerun()
    if action_col2.button("Open Recommendations", key="open_active_demo_recommendations", use_container_width=True):
        st.session_state["selected_page"] = "Recommendations"
        st.rerun()


def _account_payload(
    provider,
    role_arn,
    external_id,
    tenant_id,
    client_id,
    client_secret,
    subscription_id,
    gcp_json,
    gcp_billing_project_id,
    gcp_billing_dataset,
    gcp_billing_table,
    gcp_billing_account_id,
):
    if provider == "AWS":
        return {
            "account_name": role_arn,
            "account_identifier": role_arn,
            "credentials": {
                "role_arn": role_arn,
                "external_id": external_id,
            },
        }
    if provider == "Azure":
        return {
            "account_name": subscription_id,
            "account_identifier": subscription_id,
            "credentials": {
                "tenant_id": tenant_id,
                "client_id": client_id,
                "client_secret": client_secret,
                "subscription_id": subscription_id,
            },
        }

    gcp_data = json.loads(gcp_json.decode("utf-8"))
    account_identifier = gcp_billing_account_id or (
        f"{gcp_billing_project_id}:{gcp_billing_dataset}.{gcp_billing_table}"
    )
    account_name = gcp_data.get("project_id") or gcp_data.get("client_email", "gcp-account")
    return {
        "account_name": account_name,
        "account_identifier": account_identifier,
        "credentials": {
            "service_account_json": gcp_json.decode("utf-8"),
            "billing_project_id": gcp_billing_project_id,
            "billing_dataset": gcp_billing_dataset,
            "billing_table": gcp_billing_table,
            "billing_account_id": gcp_billing_account_id,
        },
    }


def _required_fields_present(
    provider,
    role_arn,
    external_id,
    tenant_id,
    client_id,
    client_secret,
    subscription_id,
    gcp_json,
    gcp_billing_project_id,
    gcp_billing_dataset,
    gcp_billing_table,
):
    if provider == "AWS":
        return bool(role_arn and external_id)
    if provider == "Azure":
        return bool(tenant_id and client_id and client_secret and subscription_id)
    return bool(gcp_json is not None and gcp_billing_project_id and gcp_billing_dataset and gcp_billing_table)


def cloud_accounts_page():
    _ensure_wizard_state()
    st.title("☁️ Cloud Accounts")
    st.subheader("Connect a cloud account once and let the platform sync cost data automatically.")
    st.caption("Saved accounts are encrypted at rest and scheduled for automatic background cost sync.")
    _render_demo_environment_status()

    username = st.session_state.get("username", "guest")
    current_plan = st.session_state.get("plan", "Starter")
    account_limit = get_account_limit(current_plan)
    connected_accounts = get_connected_account_count(username)

    st.info(
        f"Connected accounts: {connected_accounts} / "
        f"{account_limit if account_limit != float('inf') else 'Unlimited'}"
    )
    if account_limit != float('inf'):
        st.progress(min(connected_accounts / max(account_limit, 1), 1.0))
    else:
        st.progress(1.0)

    st.markdown("---")
    demo_scenarios = list_demo_scenarios()
    scenario_keys = [item["key"] for item in demo_scenarios]
    scenario_map = {item["key"]: item for item in demo_scenarios}
    selected_scenario = st.selectbox(
        "Demo scenario",
        scenario_keys,
        index=scenario_keys.index("mixed_failures") if "mixed_failures" in scenario_keys else 0,
        format_func=lambda key: scenario_map[key]["label"],
        help="Choose the type of seeded environment you want to test.",
        key="demo_environment_scenario",
    )
    st.caption(scenario_map[selected_scenario]["description"])
    st.markdown("**What this scenario changes**")
    for signal in DEMO_SCENARIO_SIGNALS.get(selected_scenario, []):
        st.caption(f"- {signal}")

    demo_col1, demo_col2, demo_col3 = st.columns([1.2, 1.2, 2.3])
    if demo_col1.button("Load Demo Environment", use_container_width=True):
        max_demo_accounts = account_limit if account_limit != float('inf') else 3
        seed_summary = seed_demo_environment(
            username,
            max_accounts=max_demo_accounts,
            scenario=selected_scenario,
        )
        st.session_state["active_demo_environment"] = {
            "key": selected_scenario,
            "label": scenario_map[selected_scenario]["label"],
            "description": scenario_map[selected_scenario]["description"],
            "accounts": seed_summary["accounts"],
            "account_names": seed_summary.get("account_names", []),
            "providers": seed_summary.get("providers", []),
            "billing_rows": seed_summary["billing_rows"],
            "recommendations": seed_summary["recommendations"],
        }
        st.success(
            f"{scenario_map[selected_scenario]['label']} loaded: "
            f"{seed_summary['accounts']} account(s), "
            f"{seed_summary['billing_rows']} billing rows, "
            f"{seed_summary['recommendations']} recommendations."
        )
        st.rerun()
    if demo_col2.button("Reset Demo Environment", use_container_width=True):
        reset_summary = reset_demo_environment(username)
        st.session_state.pop("active_demo_environment", None)
        st.success(
            "Demo environment cleared: "
            f"{reset_summary['accounts']} account(s), "
            f"{reset_summary['billing_rows']} billing rows, "
            f"{reset_summary['sync_runs']} sync run(s), "
            f"{reset_summary['recommendations']} recommendation(s)."
        )
        st.rerun()
    demo_col3.caption(
        "Seeds scenario-specific mock cloud accounts, sync runs, billing history, and recommendations so you can test the full app without live credentials."
    )

    if connected_accounts >= account_limit:
        st.warning(
            f"Your plan allows up to {account_limit} cloud account(s).\n\n"
            "Upgrade for more linked accounts and automation."
        )
        if st.button("Open Billing"):
            st.session_state["page"] = "billing"
            st.rerun()
        return

    wizard_state = st.session_state["cloud_account_wizard"]
    wizard_step = st.session_state["cloud_account_wizard_step"]
    requirements = _provider_requirements(wizard_state["provider"], wizard_state)
    configured_count = _configured_requirement_count(requirements)

    st.markdown("---")
    st.markdown("### Account Setup Wizard")
    st.progress(wizard_step / len(WIZARD_STEPS))
    _render_step_status(wizard_step)

    with st.container(border=True):
        if wizard_step == 1:
            st.markdown("#### Step 1: Choose your provider")
            selected_provider = st.selectbox(
                "Cloud provider",
                PROVIDER_OPTIONS,
                index=PROVIDER_OPTIONS.index(wizard_state["provider"]),
            )
            wizard_state["provider"] = selected_provider
            _render_provider_help(selected_provider)
            st.info("You can change the provider later before connecting the account.")
            col1, col2 = st.columns([1, 1])
            if col1.button("Continue", use_container_width=True):
                st.session_state["cloud_account_wizard_step"] = 2
                st.rerun()
            if col2.button("Reset", use_container_width=True):
                _reset_wizard()
                st.rerun()

        elif wizard_step == 2:
            st.markdown("#### Step 2: Review readiness")
            _render_provider_help(wizard_state["provider"])
            st.info(
                f"Configured items: {configured_count} / {len(requirements)}. "
                "Missing provider-side permissions can still block validation even after credentials are entered."
            )
            for requirement_label, is_ready in requirements:
                if is_ready:
                    st.success(requirement_label)
                else:
                    st.warning(requirement_label)
            col1, col2 = st.columns([1, 1])
            if col1.button("Back", use_container_width=True):
                st.session_state["cloud_account_wizard_step"] = 1
                st.rerun()
            if col2.button("Continue to credentials", use_container_width=True):
                st.session_state["cloud_account_wizard_step"] = 3
                st.rerun()

        elif wizard_step == 3:
            st.markdown("#### Step 3: Enter credentials")
            provider = wizard_state["provider"]
            if provider == "AWS":
                wizard_state["role_arn"] = st.text_input("Role ARN", value=wizard_state["role_arn"])
                wizard_state["external_id"] = st.text_input("External ID", value=wizard_state["external_id"])
            elif provider == "Azure":
                wizard_state["tenant_id"] = st.text_input("Tenant ID", value=wizard_state["tenant_id"])
                wizard_state["client_id"] = st.text_input("Client ID", value=wizard_state["client_id"])
                wizard_state["client_secret"] = st.text_input(
                    "Client Secret",
                    type="password",
                    value=wizard_state["client_secret"],
                )
                wizard_state["subscription_id"] = st.text_input(
                    "Subscription ID",
                    value=wizard_state["subscription_id"],
                )
            else:
                uploaded_file = st.file_uploader("Service Account JSON", type=["json"])
                if uploaded_file is not None:
                    wizard_state["gcp_json_bytes"] = uploaded_file.read()
                    wizard_state["gcp_json_name"] = uploaded_file.name
                if wizard_state["gcp_json_name"]:
                    st.caption(f"Loaded file: {wizard_state['gcp_json_name']}")
                wizard_state["gcp_billing_project_id"] = st.text_input(
                    "Billing Export Project ID",
                    value=wizard_state["gcp_billing_project_id"],
                )
                wizard_state["gcp_billing_dataset"] = st.text_input(
                    "Billing Export Dataset",
                    value=wizard_state["gcp_billing_dataset"],
                )
                wizard_state["gcp_billing_table"] = st.text_input(
                    "Billing Export Table",
                    value=wizard_state["gcp_billing_table"],
                )
                wizard_state["gcp_billing_account_id"] = st.text_input(
                    "Billing Account ID (Optional)",
                    value=wizard_state["gcp_billing_account_id"],
                )
            col1, col2 = st.columns([1, 1])
            if col1.button("Back", use_container_width=True):
                st.session_state["cloud_account_wizard_step"] = 2
                st.rerun()
            if col2.button("Review connection", use_container_width=True):
                st.session_state["cloud_account_wizard_step"] = 4
                st.rerun()

        else:
            st.markdown("#### Step 4: Review and connect")
            provider = wizard_state["provider"]
            requirements = _provider_requirements(provider, wizard_state)
            configured_count = _configured_requirement_count(requirements)
            st.write(f"Provider: {provider}")
            st.write(f"Readiness: {configured_count} / {len(requirements)} items configured")

            if _wizard_has_required_fields(wizard_state):
                try:
                    payload = _build_payload_from_wizard(wizard_state)
                    review_frame = pd.DataFrame(
                        [
                            {"Field": "Account name", "Value": payload["account_name"]},
                            {"Field": "Account identifier", "Value": payload["account_identifier"]},
                            {"Field": "Credential fields", "Value": len(payload["credentials"])},
                        ]
                    )
                    st.dataframe(review_frame, use_container_width=True, hide_index=True)
                    st.success("Required fields are present. The platform will validate and start sync after connection.")
                except json.JSONDecodeError:
                    st.error("The uploaded GCP JSON file could not be parsed. Upload a valid service account file.")
                    payload = None
            else:
                payload = None
                st.error("Some required fields are still missing. Go back and complete the credential step.")

            col1, col2, col3 = st.columns([1, 1, 1])
            if col1.button("Back", use_container_width=True):
                st.session_state["cloud_account_wizard_step"] = 3
                st.rerun()
            if col2.button("Start over", use_container_width=True):
                _reset_wizard()
                st.rerun()
            if col3.button("Save and Start Sync", use_container_width=True, disabled=payload is None):
                try:
                    result = create_cloud_account(
                        username=username,
                        provider=provider,
                        account_name=payload["account_name"],
                        account_identifier=payload["account_identifier"],
                        credentials=payload["credentials"],
                    )
                    st.success("Cloud account saved securely. Cost sync started successfully.")
                    if result["preview"]:
                        st.write("Connection preview:")
                        preview = result["preview"]
                        if isinstance(preview[0], dict):
                            st.dataframe(pd.DataFrame(preview), use_container_width=True)
                        else:
                            st.write(preview)
                    _reset_wizard()
                    st.rerun()
                except (CloudAccountSyncError, json.JSONDecodeError) as exc:
                    st.error(f"Unable to save and sync this account: {exc}")

    st.markdown("---")
    st.markdown("### Connected Accounts")
    accounts = list_cloud_accounts(username)
    if not accounts:
        st.info("No cloud accounts connected yet.")
        return

    for account in accounts:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{account['provider'].upper()}** - {account['account_name']}")
                st.caption(f"Identifier: {account['account_identifier']}")
                st.write(f"Status: {account['status']}")
                st.write(
                    f"Validation: {account.get('validation_status', 'pending')}"
                    f" | Health score: {account.get('health_score', 0)}/100"
                )
                if account.get("last_synced_at"):
                    st.write(f"Last sync: {account['last_synced_at']}")
                if account.get("next_sync_at"):
                    st.write(f"Next sync: {account['next_sync_at']}")
                if account.get("coverage_start") or account.get("coverage_end"):
                    st.write(
                        f"Coverage: {account.get('coverage_start', 'N/A')} to {account.get('coverage_end', 'N/A')}"
                    )
                if account.get("last_sync_record_count") is not None:
                    st.write(f"Last sync records: {account.get('last_sync_record_count', 0)}")
                if account.get("validation_message"):
                    st.caption(account["validation_message"])
                if account.get("last_error"):
                    st.error(account["last_error"])
                recent_runs = list_sync_runs(cloud_account_id=account["id"], limit=3)
                if recent_runs:
                    with st.expander("Recent sync runs", expanded=False):
                        st.dataframe(pd.DataFrame(recent_runs), use_container_width=True, hide_index=True)
            with col2:
                if st.button("Sync now", key=f"sync_account_{account['id']}", use_container_width=True):
                    try:
                        sync_cloud_account(account["id"], trigger_type="manual")
                        st.success("Sync completed successfully.")
                        st.rerun()
                    except CloudAccountSyncError as exc:
                        st.error(f"Sync failed: {exc}")


if __name__ == "__main__":
    cloud_accounts_page()
