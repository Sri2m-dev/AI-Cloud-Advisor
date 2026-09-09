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
from services.enterprise_spend_composition import (  # noqa: E402
    authenticated_tenant_context,
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
from shared.auth import require_role  # noqa: E402
from shared.currency import SUPPORTED_CURRENCIES, format_currency_amount  # noqa: E402
from shared.evidence_context import (  # noqa: E402
    activate_demo_workspace,
    activate_prospect_workspace,
    activate_tenant_workspace,
)
from shared.session import init_session  # noqa: E402
from shared.styles import configure_page  # noqa: E402
from universal_evidence.contracts import EvidenceAnalysisContext  # noqa: E402
from universal_evidence.financial.ui import render_financial_governance  # noqa: E402
from universal_evidence.persistence import LifecyclePersistenceError  # noqa: E402
from universal_evidence.pilot import (  # noqa: E402
    PilotAnalysisContext,
    admit_uploaded_evidence,
    get_pilot_service,
    render_dev_control,
    render_governed_measurement,
    render_governed_normalization,
    render_pue_stage12,
    render_semantic_governance,
)
from universal_evidence.pilot.dev_harness import (  # noqa: E402
    bootstrap_dev_pilot_session,
    harness_enabled,
    publish_active_prospect_scope,
)
from universal_evidence.pilot.production_render import (  # noqa: E402
    render_enterprise_context,
    render_reconciliation,
)
from universal_evidence.pilot.production_views import (  # noqa: E402
    build_enterprise_context,
    build_reconciliation_view,
)
from universal_evidence.product_closure import analyze_document_bundle  # noqa: E402
from universal_evidence.production_workflow import (  # noqa: E402
    activate_production_workflow,
    evidence_counts,
    load_configured_production_views,
    load_live_canonical_views,
    persist_document_closure,
    persist_production_workspace,
    resumable_production_workspaces,
    resume_document_closure,
    resume_production_workspace,
    upload_outcome,
)
from universal_evidence.security import (  # noqa: E402
    WorkflowAuthorizationContext,
    WorkspaceAuthorizationContext,
)


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
    activate_demo_workspace(st.session_state)
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
        "document_closure_result",
        "pue_pilot_context",
        "pue_dev_harness_active",
        "pue_shadow_analysis",
        "pue_shadow_request",
        "pue_upload_admission",
        "pue_upload_admission_error",
        "pue_local_pilot_stage",
        "pue_local_pilot_kill_switch",
        "pue_local_pilot_scope_fingerprint",
        "act005_result",
        "pue_enterprise_context_view",
        "pue_reconciliation_view",
        "pue_reconciliation_control",
    ):
        st.session_state.pop(key, None)


def _leave_active_workspace() -> None:
    """Return to source selection without deleting or replacing governed authority."""
    st.session_state.pop("analysis_start_path", None)


def _start_source_path(path: str) -> None:
    """Start a distinct presentation journey after the user selects its source."""
    _reset_journey()
    activate_tenant_workspace(st.session_state)
    st.session_state["analysis_start_path"] = path


def _prospect_pue_pilot_model(prospect_analysis):
    """Resolve an additive pilot model; never alter the legacy prospect result."""
    bootstrap_dev_pilot_session(st.session_state, prospect_analysis)
    context = st.session_state.get("pue_pilot_context")
    if not isinstance(context, PilotAnalysisContext):
        return None
    service = get_pilot_service()
    shadow_result = st.session_state.get("pue_shadow_analysis")
    request = st.session_state.get("pue_shadow_request")
    if shadow_result is None and request is not None:
        shadow_result = service.run_or_reuse_shadow(request)
        if shadow_result is not None:
            st.session_state["pue_shadow_analysis"] = shadow_result
    return service.experience(
        prospect_analysis=prospect_analysis,
        context=context,
        shadow_result=shadow_result,
    )


def _upload_pue_pilot_model(admission):
    return get_pilot_service().experience_upload(admission)


def _financial_context():
    if not str(os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB") or "").strip():
        return None
    return authenticated_tenant_context(st.session_state)


def _render_upload_pue(admission):
    closure = st.session_state.get("document_closure_result")
    if closure is not None:
        st.markdown("### Evidence overview")
        metrics = st.columns(4)
        metrics[0].metric("Source files", len(closure.documents))
        metrics[1].metric("Representations", closure.representation_count)
        metrics[2].metric("Business documents", closure.business_document_count)
        metrics[3].metric("Analysis status", "COMPLETE · AUTOMATIC")
        st.caption("Scope: Current prospect · Governed Document Intelligence")
        st.success("Document Intelligence completed successfully.")
        licenses = st.columns(4)
        licenses[0].metric("Purchased licenses", closure.purchased_licenses)
        licenses[1].metric("Assigned licenses", closure.assigned_licenses)
        licenses[2].metric("Unassigned licenses", closure.unassigned_licenses)
        licenses[3].metric("Access entitlements", closure.access_entitlements)
        st.warning(
            "Savings remain UNKNOWN. No optimization amount is inferred without governed "
            "price, currency, and eligibility evidence."
        )
        st.dataframe(
            [
                {
                    "Document": item.filename,
                    "Type": item.container_type,
                    "Regions": item.region_count,
                    "Invoice representations": item.financial_representation_count,
                    "Purchased": item.purchased_licenses,
                    "Assigned": item.assigned_licenses,
                    "Unassigned": item.unassigned_licenses,
                    "Access": item.access_entitlements,
                }
                for item in closure.documents
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("### Financial documents")
        grouped = {}
        for item in closure.financial_documents:
            grouped.setdefault(item["business_document_id"], []).append(item)
        financial_rows = []
        for business_document_id, representations in grouped.items():
            preferred = next(
                (item for item in representations if item["total_due"] is not None),
                representations[0],
            )
            states = {state for item in representations for state in item["reconciliations"]}
            currencies = {
                currency
                for item in representations
                for currency in item["currencies"]
                if item["currency_governed"]
            }
            financial_rows.append(
                {
                    "Document": business_document_id,
                    "Evidence": " + ".join(
                        sorted(
                            {
                                item["filename"].rsplit(".", 1)[-1].upper()
                                for item in representations
                            }
                        )
                    ),
                    "Representations": len(representations),
                    "Detail/Subtotal": preferred["detail_total"],
                    "Tax": preferred["tax"],
                    "Total Due": preferred["total_due"],
                    "Currency": next(iter(currencies)) if len(currencies) == 1 else "UNKNOWN",
                    "Reconciliation": "Reconciled"
                    if states == {"RECONCILED"}
                    else "Review required",
                }
            )
        st.dataframe(financial_rows, use_container_width=True, hide_index=True)
        with st.expander("Technical provenance"):
            st.json(list(closure.financial_documents))
        st.caption("Unresolved: " + ", ".join(closure.unknowns))
        st.info(
            "Document Intelligence completed automatically. Manual review is only required "
            "for a material conflict; unresolved non-critical facts remain UNKNOWN."
        )
        return
    records, fields = evidence_counts(admission)
    st.markdown("### Evidence overview")
    summary = st.columns(4)
    summary[0].metric("Evidence", admission.original_filename)
    summary[1].metric("Detail records", f"{records:,}")
    summary[2].metric("Fields discovered", f"{fields:,}")
    summary[3].metric("Analysis status", "Review required")
    st.caption("Scope: Current prospect · Uploaded evidence")
    render_pue_stage12(st, _upload_pue_pilot_model(admission))
    render_semantic_governance(st, admission)
    render_governed_normalization(st, admission)
    render_governed_measurement(st, admission)
    render_financial_governance(
        st,
        admission,
        context=_financial_context(),
        actor_id=str(st.session_state.get("user_email") or "unknown"),
        actor_role=role,
    )
    _render_enterprise_workflow(admission)


def _render_enterprise_workflow(admission):
    durable = None
    try:
        durable = load_configured_production_views(admission)
    except LifecyclePersistenceError:
        st.error(
            "Enterprise workflow state is temporarily unavailable. "
            "No stale or inferred context has been displayed."
        )
        return
    if durable is not None:
        durable_context, durable_reconciliation = durable
        st.session_state["pue_enterprise_context_view"] = (
            admission.fingerprint,
            durable_context,
        )
        st.session_state["pue_reconciliation_view"] = (
            admission.fingerprint,
            durable_reconciliation,
        )
    elif st.session_state.get("pue_enterprise_context_view") is None:
        try:
            live_context, live_reconciliation = load_live_canonical_views(
                st.session_state, admission, role=role
            )
        except (PermissionError, RuntimeError, ValueError):
            st.error(
                "Enterprise context is temporarily unavailable. "
                "No stale or inferred context has been displayed."
            )
            return
        st.session_state["pue_enterprise_context_view"] = (
            admission.fingerprint,
            live_context,
        )
        st.session_state["pue_reconciliation_view"] = (
            admission.fingerprint,
            live_reconciliation,
        )
    context = _scoped_production_view(
        "pue_enterprise_context_view",
        admission,
        build_enterprise_context(()),
    )
    reconciliation = _scoped_production_view(
        "pue_reconciliation_view",
        admission,
        build_reconciliation_view(),
    )
    control = _scoped_production_view("pue_reconciliation_control", admission, None)
    controls = None
    authorization = None
    if isinstance(control, tuple) and len(control) == 2:
        service, proposals = control
        controls = (service, {item.proposal_fingerprint: item for item in proposals})
        try:
            authorization = WorkflowAuthorizationContext.from_authenticated(
                authenticated_tenant_context(st.session_state),
                prospect_id=admission.scope.prospect_id,
                analysis_id=admission.scope.analysis_id,
            )
        except PermissionError:
            # An incomplete authenticated boundary can never enable mutation controls.
            controls = None
    render_enterprise_context(st, context)
    render_reconciliation(
        st,
        reconciliation,
        controls=controls,
        authorization=authorization,
    )


def _scoped_production_view(key, admission, empty):
    stored = st.session_state.get(key)
    if not isinstance(stored, tuple) or len(stored) != 2:
        return empty
    fingerprint, model = stored
    return model if fingerprint == admission.fingerprint else empty


def _render_dev_pilot_control(admission=None, prospect_analysis=None):
    if admission is not None:
        return render_dev_control(st, admission)
    if admission is None and prospect_analysis is not None:
        publish_active_prospect_scope(prospect_analysis)
    if harness_enabled() and st.button(
        "Apply local PUE pilot control",
        key="apply_local_pue_pilot_control",
    ):
        st.rerun()


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
active_upload_admission = st.session_state.get("pue_upload_admission")

if selected_path and (cloud_result or prospect_result or active_upload_admission):
    if st.button("← Choose another source", key="leave_active_workspace"):
        _leave_active_workspace()
        st.rerun()

if not selected_path:
    _step_header(1, "Choose a source", "Select one governed path to begin.")
    try:
        workspace_authorization = WorkspaceAuthorizationContext.from_authenticated(
            authenticated_tenant_context(st.session_state)
        )
        resumable_workspaces = resumable_production_workspaces(workspace_authorization)
    except (PermissionError, RuntimeError):
        resumable_workspaces = ()
    if resumable_workspaces:
        with st.container(border=True):
            st.subheader("Resume governed analysis")
            st.write("Continue retained evidence governance without uploading the source again.")
            if len(resumable_workspaces) == 1:
                selected_workspace = resumable_workspaces[0]
            else:
                selected_workspace = st.selectbox(
                    "Analysis",
                    resumable_workspaces,
                    format_func=lambda item: (
                        f"{item.prospect_name} — {item.filename} — "
                        f"{item.governed_mapping_count} governed mappings"
                    ),
                    key="pue_resume_workspace",
                )
            st.caption(
                f"{selected_workspace.record_count:,} records · "
                f"{selected_workspace.field_count:,} fields · tenant-scoped"
            )
            if st.button(
                "Resume existing analysis",
                key="resume_governed_analysis",
                type="primary",
            ):
                try:
                    admission, tenant, prospect_name, _profile = resume_production_workspace(
                        selected_workspace,
                        authorization=workspace_authorization,
                    )
                    try:
                        closure, _files = resume_document_closure(
                            selected_workspace, authorization=workspace_authorization
                        )
                        st.session_state["document_closure_result"] = closure
                    except Exception:  # noqa: BLE001 - older single-file workspaces remain valid
                        st.session_state.pop("document_closure_result", None)
                    st.session_state["analysis_start_path"] = "upload"
                    st.session_state["pue_upload_admission"] = admission
                    st.session_state["prospect_tenant"] = tenant
                    st.session_state["prospect_name"] = prospect_name
                    activate_prospect_workspace(
                        st.session_state,
                        expected_fingerprint=admission.fingerprint,
                    )
                    st.session_state["pue_upload_admission_error"] = (
                        "Governed analysis resumed from encrypted retained evidence. "
                        "No file was uploaded again."
                    )
                    st.rerun()
                except Exception:  # noqa: BLE001 - resume fails closed at the UI boundary
                    st.error(
                        "The selected governed analysis could not be safely resumed. "
                        "No other workspace was substituted."
                    )
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
                _start_source_path("demo_unavailable" if key == "demo" else key)
                st.rerun()
            if key in {"aws", "azure"}:
                st.caption("Authorization checked before live connection")
            elif key == "upload":
                st.caption("Consent checked before processing")
            else:
                st.caption("Isolated synthetic data · never customer data")

if (
    selected_path
    and not cloud_result
    and not prospect_result
    and not st.session_state.get("pue_upload_admission")
):
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

if (
    selected_path == "upload"
    and not prospect_result
    and not st.session_state.get("pue_upload_admission")
):
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
                    "Drag and drop CSV, Excel, or PDF evidence here, or browse files",
                    type=["csv", "xlsx", "pdf"],
                    accept_multiple_files=True,
                )
                if upload:
                    size_mb = sum(len(item.getvalue()) for item in upload) / (1024 * 1024)
                    st.success(
                        f"{len(upload)} files · {size_mb:.2f} MB · ready for governed validation"
                    )
                st.caption(
                    "Accepted now: AWS CUR-derived CSV, Azure/GCP billing export, SaaS or "
                    "technology-cost CSV/XLSX, and native-text PDF invoices. Scanned PDF is "
                    "not supported. JSON and standalone ZIP are not yet supported."
                )
                run_upload = st.form_submit_button(
                    "Continue Analysis", type="primary", use_container_width=True
                )
            if run_upload:
                if not upload:
                    st.error("Select at least one CSV, XLSX, or PDF file before starting analysis.")
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
                        bundle = tuple((item.name, item.getvalue()) for item in upload)
                        primary_name, content = next(
                            (
                                item
                                for item in bundle
                                if item[0].lower().endswith((".csv", ".xlsx"))
                            ),
                            bundle[0],
                        )
                        st.session_state["prospect_tenant"] = tenant
                        st.session_state["prospect_name"] = prospect_name.strip()
                        try:
                            authenticated = authenticated_tenant_context(st.session_state)
                            workspace_authorization = (
                                WorkspaceAuthorizationContext.from_authenticated(authenticated)
                            )
                            admission = admit_uploaded_evidence(
                                tenant,
                                filename=primary_name,
                                content=content,
                                tenant_context=authenticated,
                            )
                            persist_production_workspace(
                                admission,
                                prospect_tenant=tenant,
                                prospect_name=prospect_name.strip(),
                                input_profile=profile,
                                authorization=workspace_authorization,
                            )
                            closure_context = EvidenceAnalysisContext(
                                admission.scope.analysis_id,
                                admission.source_id,
                                admission.scope.prospect_id,
                                admission.scope.organization_id,
                                admission.scope.tenant_id,
                            )
                            closure = analyze_document_bundle(context=closure_context, files=bundle)
                            persist_document_closure(
                                admission,
                                closure,
                                prospect_tenant=tenant,
                                files=bundle,
                                input_profile=profile,
                                authorization=workspace_authorization,
                            )
                            st.session_state["document_closure_result"] = closure
                            st.session_state["pue_upload_admission"] = admission
                            activate_prospect_workspace(
                                st.session_state,
                                expected_fingerprint=admission.fingerprint,
                            )
                            activate_production_workflow(admission)
                            st.session_state.pop("pue_upload_admission_error", None)
                        except Exception:  # noqa: BLE001 - shadow admission is isolated
                            st.session_state.pop("pue_upload_admission", None)
                            st.session_state["pue_upload_admission_error"] = (
                                "Additional governed evidence analysis is temporarily unavailable."
                            )
                        if primary_name.lower().endswith((".csv", ".xlsx")):
                            try:
                                prospect_analysis = ingest_upload(
                                    tenant,
                                    profile=profile,
                                    filename=primary_name,
                                    content=content,
                                    actor=actor,
                                    role=role,
                                    key=key,
                                )
                                st.session_state["prospect_analysis"] = prospect_analysis
                                st.session_state.pop("prospect_analysis_error", None)
                            except ProspectIntakeError as exc:
                                st.session_state.pop("prospect_analysis", None)
                                st.session_state["prospect_analysis_error"] = str(exc)
                        else:
                            st.session_state.pop("prospect_analysis", None)
                            st.session_state["prospect_analysis_error"] = (
                                "Legacy billing compatibility is unavailable for PDF-only "
                                "evidence; Document Intelligence completed successfully."
                            )
                        st.success(
                            "Document Intelligence scanned, encrypted, interpreted, and "
                            "analyzed the evidence."
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
upload_admission = st.session_state.get("pue_upload_admission")
if prospect_result and selected_path == "upload":
    _render_dev_pilot_control(upload_admission, prospect_result)
    pue_pilot_model = (
        _upload_pue_pilot_model(upload_admission)
        if upload_admission is not None
        else _prospect_pue_pilot_model(prospect_result)
    )
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
        render_pue_stage12(st, pue_pilot_model)
        if upload_admission is not None and st.session_state.get("document_closure_result") is None:
            render_semantic_governance(st, upload_admission)
            render_governed_normalization(st, upload_admission)
            render_governed_measurement(st, upload_admission)
            render_financial_governance(
                st,
                upload_admission,
                context=_financial_context(),
                actor_id=str(st.session_state.get("user_email") or "unknown"),
                actor_role=role,
            )
            _render_enterprise_workflow(upload_admission)
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
    render_pue_stage12(st, pue_pilot_model)
    if upload_admission is not None and st.session_state.get("document_closure_result") is None:
        render_semantic_governance(st, upload_admission)
        render_governed_normalization(st, upload_admission)
        render_governed_measurement(st, upload_admission)
        render_financial_governance(
            st,
            upload_admission,
            context=_financial_context(),
            actor_id=str(st.session_state.get("user_email") or "unknown"),
            actor_role=role,
        )
        _render_enterprise_workflow(upload_admission)
    st.page_link(
        "pages/prospect_data_intake.py",
        label="Open Results, Ask Nexora, and Board Pack",
        use_container_width=True,
    )
    if st.button("Analyze another environment", key="restart_upload_complete"):
        _reset_journey()
        st.rerun()

if upload_admission is not None and prospect_result is None and selected_path == "upload":
    outcome = upload_outcome(
        admission=upload_admission,
        legacy_error=st.session_state.get("prospect_analysis_error"),
    )
    st.success(outcome.message)
    if outcome.compatibility_notice:
        if st.session_state.get("document_closure_result") is None:
            st.info(outcome.compatibility_notice)
    _render_upload_pue(upload_admission)

if (
    upload_admission is not None
    and prospect_result is None
    and st.session_state.get("pue_upload_admission_error")
    and selected_path == "upload"
):
    st.info(str(st.session_state["pue_upload_admission_error"]))

if (
    prospect_result is not None
    and st.session_state.get("pue_upload_admission_error")
    and selected_path == "upload"
):
    st.info(str(st.session_state["pue_upload_admission_error"]))

if not selected_path:
    st.stop()

with st.expander("Learn more about supported evidence and secure processing"):
    st.write(
        "Supported uploads: AWS CUR-derived CSV, Azure and GCP billing exports, supported "
        "SaaS/license CSV or Excel, generic technology-cost spreadsheets, and native-text "
        "PDF invoices. Scanned-image PDFs remain unsupported."
    )
    st.caption("Coming Soon — additional certified enterprise connection paths")
    st.write(
        "Live connection is not yet certified for Google Cloud. Nexora does not simulate progress; "
        "unsupported mappings remain UNKNOWN."
    )
