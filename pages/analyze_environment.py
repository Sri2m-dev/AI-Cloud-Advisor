from __future__ import annotations

import os
import sys

import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from auth.connector_context import (  # noqa: E402
    get_current_organization_id,
    get_current_user_id,
)
from auth.role_constants import normalize_role  # noqa: E402
from components.navigation import render_enterprise_sidebar  # noqa: E402
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES  # noqa: E402
from services.aws_connector_service import AWSConnectorService  # noqa: E402
from services.azure_connector_service import AzureConnectorService  # noqa: E402
from services.demo_tenant_service import (  # noqa: E402
    demo_mode_enabled,
    is_demo_tenant,
    load_demo_tenant,
)
from services.prospect_data_intake_service import (  # noqa: E402
    DEFAULT_RETENTION_DAYS,
    PROSPECT_WATERMARK,
    SUPPORTED_PROFILES,
    ProspectIntakeError,
    confirm_analysis_currency,
    create_prospect_tenant,
    ingest_upload,
    prospect_encryption_key,
)
from shared.currency import SUPPORTED_CURRENCIES, format_currency_amount  # noqa: E402
from shared.auth import require_role  # noqa: E402
from shared.session import init_session  # noqa: E402
from shared.styles import configure_page  # noqa: E402


def _pipeline(title: str, stages: tuple[tuple[str, str], ...]) -> None:
    st.subheader(title)
    st.markdown(
        '<div class="nexora-process">'
        + "".join(
            '<div class="nexora-process-step ready">'
            f"<strong>{label}</strong><br><small>{detail}</small></div>"
            for label, detail in stages
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_certified_scope(items: tuple[str, ...]) -> None:
    st.caption("CERTIFIED DISCOVERY SCOPE")
    columns = st.columns(min(4, len(items)))
    for index, item in enumerate(items):
        columns[index % len(columns)].markdown(f"✓ {item}")


def _render_cloud_results(result: dict[str, object]) -> None:
    metrics = (
        ("Cloud accounts", result.get("accounts", 0)),
        ("Cost records", result.get("costs", 0)),
        ("Resources", result.get("resources", 0)),
        ("Discovered assets", result.get("assets_discovered", 0)),
        ("Recommendations", result.get("recommendations", 0)),
    )
    columns = st.columns(len(metrics))
    for column, (label, value) in zip(columns, metrics, strict=True):
        column.metric(label, f"{int(value or 0):,}")


def _open_demo(organization_id: str) -> None:
    load_demo_tenant(organization_id)
    st.switch_page("pages/welcome.py")


def _step_header(step: int, title: str, detail: str) -> None:
    st.caption(f"STEP {step} OF 4")
    st.subheader(title)
    st.write(detail)


def _reset_journey() -> None:
    for key in (
        "analysis_start_path",
        "environment_analysis_result",
        "prospect_analysis",
        "prospect_analysis_error",
    ):
        st.session_state.pop(key, None)


def _select_path(path: str) -> None:
    _reset_journey()
    st.session_state["analysis_start_path"] = path
    st.rerun()


configure_page(page_title="Analyze Your Environment | Nexora", page_icon="N")
init_session()
require_role(["executive", "finance", "sales_engineer", "client_admin", "super_admin"])
role = normalize_role(st.session_state.get("role", ""))
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Analyse Your Environment"],
)

st.markdown(
    """
    <section class="nexora-welcome-hero nexora-analysis-hero">
      <p class="nexora-eyebrow">ANALYZE YOUR ENVIRONMENT</p>
      <h1>Connect your technology estate in under five minutes.</h1>
      <p>How would you like to start? Choose a governed connection, upload real evidence,
      or explore the isolated Sample Enterprise. Unsupported conclusions remain UNKNOWN.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

connector_admin = role in {
    "executive",
    "sales_engineer",
    "client_admin",
    "super_admin",
}
upload_operator = role in {
    "executive",
    "sales_engineer",
    "finance",
    "client_admin",
    "super_admin",
}
organization_id = str(st.session_state.get("organization_id") or "")
demo_available = demo_mode_enabled() and is_demo_tenant(organization_id)
selected_path = st.session_state.get("analysis_start_path")
cloud_result = st.session_state.get("environment_analysis_result")
prospect_result = st.session_state.get("prospect_analysis")

if not selected_path:
    _step_header(1, "Choose a source", "Select one governed path to begin.")
action_specs = (
    (
        {
            "key": "aws",
            "color": "technology",
            "icon": "&#9729;",
            "title": "Connect AWS",
            "description": "Secure read-only connector",
        },
        {
            "key": "azure",
            "color": "technology",
            "icon": "&#9729;",
            "title": "Connect Azure",
            "description": "Secure read-only connector",
        },
        {
            "key": "upload",
            "color": "finance",
            "icon": "&#128196;",
            "title": "Upload Billing Files",
            "description": "CSV / CUR / Excel",
        },
        {
            "key": "demo",
            "color": "ai",
            "icon": "&#10022;",
            "title": "Explore Demo",
            "description": "Sample Enterprise product tour",
        },
    )
    if not selected_path
    else ()
)
actions = st.columns(len(action_specs)) if action_specs else []
for column, card in zip(actions, action_specs, strict=True):
    key = card["key"]
    with column:
        with st.container(border=True):
            st.markdown(
                f'<div class="nexora-start-icon {card["color"]}">{card["icon"]}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(f"### {card['title']}")
            st.write(card["description"])
            if key == "demo":
                st.markdown("**Fortune 500 retail enterprise**")
                st.caption(
                    "340 business services · 1,850 applications · 620 cloud accounts · "
                    "$214M governed spend"
                )
            label = {
                "aws": "Configure AWS →",
                "azure": "Configure Azure →",
                "upload": "Choose files →",
                "demo": "Launch Sample Enterprise →",
            }[key]
            if st.button(label, key=f"start_{key}", type="primary", use_container_width=True):
                if key == "demo" and demo_available:
                    _open_demo(organization_id)
                st.session_state["analysis_start_path"] = (
                    "demo_unavailable" if key == "demo" else key
                )
                st.rerun()
            if key in {"aws", "azure"}:
                st.caption("Authorization checked before live connection")
            elif key == "upload":
                st.caption("Consent checked before processing")
            else:
                st.caption("Isolated synthetic data · never customer data")

if selected_path and not cloud_result and not prospect_result:
    if st.button("← Choose another source", key="restart_analysis"):
        _reset_journey()
        st.rerun()

if selected_path in {"aws", "azure"} and not cloud_result:
    provider = "AWS" if selected_path == "aws" else "Microsoft Azure"
    _step_header(
        2,
        f"Connect {provider}",
        "Configure and verify the existing certified read-only connection.",
    )
    checks = (
        ("IAM role", "Billing", "Organizations", "Compute", "Storage")
        if selected_path == "aws"
        else ("Service principal", "Cost Management", "Subscriptions", "Resources", "Advisor")
    )
    with st.container(border=True):
        st.caption("READ-ONLY CONNECTION")
        st.subheader(f"Connect your {provider} environment")
        check_columns = st.columns(len(checks))
        for column, check in zip(check_columns, checks, strict=True):
            column.markdown(f"**&#10003; {check}**", unsafe_allow_html=True)
        st.caption("Estimated time: 2–3 minutes · no infrastructure changes")
        if not connector_admin:
            st.info(
                "Completing a live connection requires Sales Engineer, Client Administrator, "
                "or Super Administrator authorization."
            )
            st.caption("No cloud credentials have been collected or stored.")
            if demo_available and st.button(
                "Continue with Sample Enterprise",
                key=f"sample_{selected_path}",
                use_container_width=True,
            ):
                _open_demo(organization_id)
        elif selected_path == "aws":
            with st.form("guided_aws_connection"):
                connection_name = st.text_input("Connection name", value="Production AWS")
                st.radio("Authentication method", ("IAM Role (Certified)",))
                role_arn = st.text_input(
                    "Role ARN",
                    placeholder="arn:aws:iam::123456789012:role/NexoraReadOnlyRole",
                )
                external_id = st.text_input("External ID", type="password")
                region = st.selectbox(
                    "Region", ("us-east-1", "us-west-2", "eu-west-1", "ap-south-1")
                )
                form_actions = st.columns(2)
                test_aws = form_actions[0].form_submit_button(
                    "Test Connection", use_container_width=True
                )
                connect_aws = form_actions[1].form_submit_button(
                    "Start Discovery", type="primary", use_container_width=True
                )
                st.caption(
                    "Access Key and organization-wide authentication are not yet certified "
                    "for this live onboarding path."
                )
            _render_certified_scope(
                (
                    "Accounts and identity",
                    "Cost Explorer",
                    "EC2 and VPC",
                    "EBS-backed EC2 inventory",
                    "RDS",
                    "S3",
                    "Lambda",
                    "EKS",
                    "Compute Optimizer recommendations",
                )
            )
            if test_aws or connect_aws:
                with st.spinner("Verifying read-only AWS access..."):
                    connection = AWSConnectorService.test_connection(
                        role_arn or None,
                        external_id or None,
                        region,
                        organization_id=get_current_organization_id(),
                    )
                if connection.get("status") != "CONNECTED":
                    st.error("AWS could not verify the supplied read-only role.")
                else:
                    st.success("AWS connection verified.")
                    if connect_aws:
                        saved = AWSConnectorService.save_config(
                            get_current_organization_id(),
                            get_current_user_id(),
                            role_arn or None,
                            external_id or None,
                            region,
                        )
                        if saved.get("status") != "SAVED":
                            st.error("AWS configuration could not be saved.")
                        else:
                            _step_header(
                                3,
                                "Analyze environment",
                                "Only service-backed results are marked complete.",
                            )
                            with st.spinner(
                                "Discovering AWS accounts, costs, resources, and recommendations..."
                            ):
                                result = AWSConnectorService.sync_all(
                                    organization_id=get_current_organization_id()
                                )
                            st.session_state["environment_analysis_result"] = {
                                "provider": "AWS",
                                "connection_name": connection_name.strip() or "AWS",
                                **result,
                            }
                            st.rerun()
        else:
            with st.form("guided_azure_connection"):
                connection_name = st.text_input("Connection name", value="Production Azure")
                st.radio("Authentication method", ("Service Principal (Certified)",))
                tenant_id = st.text_input("Tenant ID")
                client_id = st.text_input("Client ID")
                client_secret = st.text_input("Client Secret", type="password")
                subscription_id = st.text_input("Subscription ID")
                form_actions = st.columns(2)
                test_azure = form_actions[0].form_submit_button(
                    "Test Connection", use_container_width=True
                )
                connect_azure = form_actions[1].form_submit_button(
                    "Start Discovery", type="primary", use_container_width=True
                )
                st.caption(
                    "Managed Identity and management-group onboarding are not yet certified "
                    "for this live onboarding path."
                )
            _render_certified_scope(
                (
                    "Subscription identity",
                    "Cost Management",
                    "Resource groups",
                    "Virtual machines",
                    "Storage accounts",
                    "Virtual networks",
                    "SQL databases",
                    "AKS clusters",
                    "Load balancers",
                )
            )
            if test_azure or connect_azure:
                with st.spinner("Verifying read-only Azure access..."):
                    connection = AzureConnectorService.test_connection(
                        tenant_id or None,
                        client_id or None,
                        client_secret or None,
                        subscription_id or None,
                        organization_id=get_current_organization_id(),
                    )
                if connection.get("status") != "CONNECTED":
                    st.error("Azure could not verify the supplied read-only identity.")
                else:
                    st.success("Azure connection verified.")
                    if connect_azure:
                        saved = AzureConnectorService.save_config(
                            get_current_organization_id(),
                            get_current_user_id(),
                            tenant_id or None,
                            client_id or None,
                            client_secret or None,
                            subscription_id or None,
                        )
                        if saved.get("status") != "SAVED":
                            st.error("Azure configuration could not be saved.")
                        else:
                            _step_header(
                                3,
                                "Analyze environment",
                                "Only service-backed results are marked complete.",
                            )
                            with st.spinner(
                                "Discovering Azure accounts, costs, resources, and "
                                "recommendations..."
                            ):
                                result = AzureConnectorService.sync_all(
                                    organization_id=get_current_organization_id()
                                )
                            st.session_state["environment_analysis_result"] = {
                                "provider": "Azure",
                                "connection_name": connection_name.strip() or "Azure",
                                **result,
                            }
                            st.rerun()

if selected_path == "upload" and not prospect_result:
    _step_header(
        2,
        "Upload billing evidence",
        "Provide authorized evidence for secure temporary analysis.",
    )
    with st.container(border=True):
        st.caption("GOVERNED FILE ANALYSIS")
        st.markdown("## Drop files here")
        st.write("Drag and drop or browse · AWS CUR · Azure Export · CSV · Excel")
        if not upload_operator:
            st.info(
                "Uploading production or prospect data requires Sales Engineer or Finance "
                "Operator authorization."
            )
            st.caption("No file has been selected, uploaded, or processed.")
            if demo_available and st.button(
                "Continue with Demo Dataset",
                key="sample_upload",
                use_container_width=True,
            ):
                _open_demo(organization_id)
        else:
            st.warning(PROSPECT_WATERMARK)
            with st.form("guided_prospect_upload"):
                prospect_name = st.text_input("Prospect organization name")
                consent = st.checkbox(
                    "I confirm authorization for temporary analysis and 30-day encrypted retention."
                )
                profile = st.selectbox("Input profile", SUPPORTED_PROFILES)
                upload = st.file_uploader(
                    "Drag and drop CSV or Excel evidence here, or browse files",
                    type=["csv", "xlsx"],
                )
                if upload is not None:
                    size_mb = len(upload.getvalue()) / (1024 * 1024)
                    st.success(f"{upload.name} · {size_mb:.2f} MB · ready for governed validation")
                st.caption(
                    "Accepted now: AWS CUR-derived CSV, Azure/GCP billing export, SaaS or "
                    "technology-cost CSV/XLSX. JSON and standalone ZIP are not yet supported."
                )
                run_upload = st.form_submit_button(
                    "Continue Analysis", type="primary", use_container_width=True
                )
            if run_upload:
                if upload is None:
                    st.error("Select a CSV or XLSX file before starting analysis.")
                else:
                    try:
                        _step_header(
                            3,
                            "Analyze uploaded evidence",
                            "Validation and normalization use the existing governed "
                            "intake service.",
                        )
                        actor = str(st.session_state.get("user_email") or "unknown")
                        key = prospect_encryption_key()
                        tenant = create_prospect_tenant(
                            prospect_name,
                            consent=consent,
                            actor=actor,
                            role=role,
                            retention_days=DEFAULT_RETENTION_DAYS,
                            key=key,
                        )
                        prospect_analysis = ingest_upload(
                            tenant,
                            profile=profile,
                            filename=upload.name,
                            content=upload.getvalue(),
                            actor=actor,
                            role=role,
                            key=key,
                        )
                        st.session_state["prospect_tenant"] = tenant
                        st.session_state["prospect_analysis"] = prospect_analysis
                        st.session_state["prospect_name"] = prospect_name.strip()
                        st.session_state.pop("prospect_analysis_error", None)
                        st.success(
                            "Evidence was scanned, validated, normalized, encrypted, and analyzed."
                        )
                        st.rerun()
                    except ProspectIntakeError as exc:
                        st.session_state["prospect_analysis_error"] = str(exc)
                        st.error(str(exc))

if selected_path == "demo_unavailable":
    st.info(
        "The Sample Enterprise is available only in an isolated demo workspace. Contact "
        "your Nexora representative for a guided assessment or demo workspace."
    )

cloud_result = st.session_state.get("environment_analysis_result")
if cloud_result:
    if cloud_result.get("status") == "SUCCESS":
        _step_header(
            4,
            "Executive brief ready",
            "The completed discovery results are ready for executive review.",
        )
        analysis_name = cloud_result.get("connection_name") or cloud_result.get("provider")
        _pipeline(
            f"{analysis_name} analysis complete",
            (
                ("Connection", "Verified"),
                ("Accounts", f"{cloud_result.get('accounts', 0):,} discovered"),
                ("Cost normalization", f"{cloud_result.get('costs', 0):,} records"),
                ("Resource discovery", f"{cloud_result.get('resources', 0):,} resources"),
                ("Technology inventory", "Persisted"),
                ("Relationship graph", "Persisted"),
                ("Recommendations", f"{cloud_result.get('recommendations', 0):,} findings"),
                ("Executive Brief", "Ready"),
            ),
        )
        st.subheader("Live discoveries")
        _render_cloud_results(cloud_result)
        st.page_link(
            "pages/welcome.py",
            label="Open Executive Operating System",
            use_container_width=True,
        )
        if st.button("Analyze another environment", key="restart_cloud_complete"):
            _reset_journey()
            st.rerun()
    else:
        st.error("Analysis failed. No discovery stage is marked complete.")

prospect_result = st.session_state.get("prospect_analysis")
if prospect_result and selected_path == "upload":
    if prospect_result.currency_resolution_required:
        _step_header(
            4,
            "Currency resolution required",
            "Currency could not be determined from the uploaded evidence."
            if prospect_result.currency_source != "MIXED_EVIDENCE"
            else "Multiple currencies were detected in the uploaded evidence.",
        )
        if prospect_result.currency_source == "MIXED_EVIDENCE":
            st.error(
                "Currencies detected: "
                + ", ".join(prospect_result.detected_currencies)
                + ". Monetary values have not been aggregated. Split the evidence by currency; "
                "FX conversion is not supported."
            )
        else:
            st.warning("Currency could not be determined from the uploaded evidence.")
            selected_currency = st.selectbox(
                "Currency", SUPPORTED_CURRENCIES, key="prospect_currency_selection"
            )
            currency_confirmed = st.checkbox(
                "I confirm that the selected currency applies to the uploaded evidence.",
                key="prospect_currency_confirmation",
            )
            if st.button("Confirm currency", type="primary", use_container_width=True):
                try:
                    resolved = confirm_analysis_currency(
                        st.session_state["prospect_tenant"],
                        analysis=prospect_result,
                        selected_currency=selected_currency,
                        confirmed=currency_confirmed,
                        actor=str(st.session_state.get("user_email") or "unknown"),
                        role=role,
                        key=prospect_encryption_key(),
                    )
                    st.session_state["prospect_analysis"] = resolved
                    st.rerun()
                except ProspectIntakeError as exc:
                    st.error(str(exc))
        st.stop()
    _step_header(
        4,
        "Prospect brief ready",
        "Validated evidence is ready for governed results, Ask Nexora, and reporting.",
    )
    _pipeline(
        "Uploaded evidence analysis complete",
        (
            ("Upload", "Encrypted"),
            ("Malware scan", "Passed"),
            ("Schema", "Validated"),
            ("Cost", "Normalized"),
            ("Evidence", f"{prospect_result.evidence_coverage:.1f}% coverage"),
            ("Prospect brief", "Ready"),
        ),
    )
    result_metrics = st.columns(4)
    result_metrics[0].metric(
        "Normalized spend",
        format_currency_amount(prospect_result.total_spend, prospect_result.currency),
    )
    result_metrics[1].metric("Evidence rows", f"{prospect_result.row_count:,}")
    result_metrics[2].metric("Evidence coverage", f"{prospect_result.evidence_coverage:.1f}%")
    result_metrics[3].metric(
        "Qualified opportunity",
        format_currency_amount(
            prospect_result.opportunity_evidence_qualified, prospect_result.currency
        ),
    )
    st.page_link(
        "pages/prospect_data_intake.py",
        label="Open Results, Ask Nexora, and Board Pack",
        use_container_width=True,
    )
    if st.button("Analyze another environment", key="restart_upload_complete"):
        _reset_journey()
        st.rerun()

if not selected_path:
    st.stop()

with st.expander("Learn more about supported evidence and secure processing"):
    st.write(
        "Supported uploads: AWS CUR-derived CSV, Azure and GCP billing exports, supported "
        "SaaS/license CSV or Excel, and generic technology-cost spreadsheets. PDF invoices "
        "are not yet supported."
    )
    st.caption("Coming Soon — additional certified enterprise connection paths")
    st.write(
        "Live connection is not yet certified for Google Cloud. Nexora does not simulate progress; "
        "unsupported mappings remain UNKNOWN."
    )
