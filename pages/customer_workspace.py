# ruff: noqa: E402
from __future__ import annotations

import json
import sqlite3

import streamlit as st

from components.sidebar_navigation import render_sidebar_navigation
from services.customer_workflow_service import (
    CustomerWorkflowError,
    CustomerWorkflowService,
)
from services.enterprise_spend_composition import authenticated_tenant_context
from shared.session import init_session
from shared.styles import configure_page

configure_page(page_title="Customer Workspace | Nexora", page_icon="📁")
init_session()

from shared.auth import require_role

require_role(["client_admin", "executive", "cio", "finance", "auditor", "operations"])
role = str(st.session_state.get("role") or "")
render_sidebar_navigation(role)

st.title("Customer Workspace")
st.caption("Tenant-scoped evidence · bounded Ask · customer decisions and approvals")
st.info(
    "Customer decision approvals are business governance records. They do not execute "
    "privileged G08 owner operations."
)

try:
    authenticated = authenticated_tenant_context(st.session_state)
    service = CustomerWorkflowService.from_environment()
except (CustomerWorkflowError, PermissionError, RuntimeError) as error:
    st.error(f"Customer workspace is unavailable: {error}")
    st.stop()

try:
    workspaces = service.list_workspaces(authenticated)
except (CustomerWorkflowError, PermissionError, RuntimeError, sqlite3.Error) as error:
    st.error(f"Customer workspaces could not be loaded: {error}")
    st.stop()
with st.expander("Create a workspace", expanded=not workspaces):
    with st.form("customer_workspace_create"):
        workspace_name = st.text_input("Workspace name", max_chars=120)
        create_workspace = st.form_submit_button("Create workspace", type="primary")
    if create_workspace:
        try:
            created = service.create_workspace(authenticated, name=workspace_name)
            st.session_state["customer_workflow_workspace_id"] = created.workspace_id
            st.rerun()
        except (CustomerWorkflowError, PermissionError, RuntimeError, sqlite3.Error) as error:
            st.error(f"Workspace could not be created: {error}")

if not workspaces:
    st.info("Create a tenant workspace to begin uploading governed evidence.")
    st.stop()

workspace_ids = [event.workspace_id for event in workspaces]
labels = {
    event.workspace_id: str(event.payload.get("name") or event.workspace_id)
    for event in workspaces
}
preferred = st.session_state.get("customer_workflow_workspace_id")
default_index = workspace_ids.index(preferred) if preferred in workspace_ids else 0
workspace_id = st.selectbox(
    "Tenant workspace",
    workspace_ids,
    index=default_index,
    format_func=lambda value: labels.get(value, value),
)
st.session_state["customer_workflow_workspace_id"] = workspace_id

with st.expander("Upload evidence", expanded=True):
    with st.form("customer_evidence_upload", clear_on_submit=True):
        uploaded = st.file_uploader("CSV or XLSX cost evidence", type=["csv", "xlsx"])
        profile = st.selectbox(
            "Evidence profile",
            (
                "Generic technology-cost Excel/CSV",
                "AWS billing/CUR-derived CSV",
                "Azure cost export",
                "GCP billing export",
                "SaaS/license CSV or Excel",
                "Manual invoice/bill spreadsheet",
            ),
        )
        upload = st.form_submit_button("Validate and save evidence", type="primary")
    if upload:
        if uploaded is None:
            st.error("Choose a CSV or XLSX file before continuing.")
        else:
            try:
                evidence = service.upload_evidence(
                    authenticated,
                    workspace_id,
                    filename=uploaded.name,
                    content=uploaded.getvalue(),
                    input_profile=profile,
                )
                st.success(
                    f"Evidence validated and saved. Reference: {evidence.payload['evidence_id']}"
                )
            except (
                CustomerWorkflowError,
                PermissionError,
                ValueError,
                RuntimeError,
                sqlite3.Error,
            ) as error:
                st.error(f"Evidence was not admitted: {error}")

try:
    records = service.resume_workspace(authenticated, workspace_id)
except (CustomerWorkflowError, PermissionError, RuntimeError, sqlite3.Error) as error:
    st.error(f"Workspace records could not be resumed: {error}")
    st.stop()

evidence_records = records["evidence"]
if evidence_records:
    st.subheader("Validated evidence")
    st.dataframe(
        [
            {
                "Evidence reference": row["payload"]["evidence_id"],
                "File": row["payload"]["filename"],
                "Validation": row["payload"]["validation_status"],
                "SHA-256": row["payload"]["source_sha256"],
                "Uploaded": row["occurred_at"],
            }
            for row in evidence_records
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No evidence has been saved in this workspace.")

if evidence_records:
    evidence_by_id = {
        row["event_id"]: row for row in evidence_records
    }
    with st.form("customer_workspace_ask"):
        selected_evidence_id = st.selectbox(
            "Evidence source",
            list(evidence_by_id),
            format_func=lambda value: evidence_by_id[value]["payload"]["filename"],
        )
        question = st.text_input(
            "Ask a bounded question about this evidence",
            placeholder="How many evidence records are present?",
            max_chars=1000,
        )
        ask_submitted = st.form_submit_button("Ask Nexora")
    if ask_submitted:
        try:
            answer = service.ask(
                authenticated,
                workspace_id,
                evidence_id=selected_evidence_id,
                question=question,
            )
            if answer.payload["state"] == "GROUNDED":
                st.success(answer.payload["answer"])
            else:
                st.warning(answer.payload["answer"])
            for reference in answer.payload["evidence_references"]:
                st.caption(
                    f"Evidence: {reference['filename']} · "
                    f"SHA-256 {reference['sha256']} · "
                    f"record {reference['record_id']}"
                )
            st.rerun()
        except (
            CustomerWorkflowError,
            PermissionError,
            ValueError,
            RuntimeError,
            sqlite3.Error,
        ) as error:
            st.error(f"Ask could not use this evidence: {error}")

ask_records = [
    row for row in records["asks"] if row["payload"].get("state") == "GROUNDED"
]
if records["asks"]:
    st.subheader("Ask history")
    for row in records["asks"]:
        payload = row["payload"]
        st.markdown(f"**{payload['question']}**")
        if payload["state"] == "GROUNDED":
            st.write(payload["answer"])
        else:
            st.warning(payload["answer"])
        for reference in payload["evidence_references"]:
            st.caption(
                f"Evidence: {reference['filename']} · "
                f"SHA-256 {reference['sha256']} · "
                f"record {reference['record_id']}"
            )
if ask_records:
    st.subheader("Create a customer decision")
    with st.form("customer_decision_create"):
        selected_ask_id = st.selectbox(
            "Grounded Ask response",
            [row["event_id"] for row in ask_records],
            format_func=lambda value: next(
                row["payload"]["question"] for row in ask_records if row["event_id"] == value
            ),
        )
        decision_text = st.text_input("Decision", max_chars=500)
        decision_rationale = st.text_area("Rationale", max_chars=2000)
        create_decision = st.form_submit_button("Save decision")
    if create_decision:
        try:
            decision = service.create_decision(
                authenticated,
                workspace_id,
                ask_id=selected_ask_id,
                decision=decision_text,
                rationale=decision_rationale,
            )
            st.success(f"Decision saved: {decision.payload['decision_id']}")
            st.rerun()
        except (
            CustomerWorkflowError,
            PermissionError,
            ValueError,
            RuntimeError,
            sqlite3.Error,
        ) as error:
            st.error(f"Decision was not saved: {error}")

decision_records = records["decisions"]
existing_requests = [
    event
    for event in records["approvals"]
    if event["event_type"] == "APPROVAL_REQUESTED"
]
approved_decision_ids = {
    event["payload"]["approval"]["subject_id"] for event in existing_requests
}
unrequested_decisions = [
    row
    for row in decision_records
    if row["payload"]["decision_id"] not in approved_decision_ids
]
if unrequested_decisions:
    st.subheader("Request customer approval")
    with st.form("customer_approval_request"):
        selected_decision_id = st.selectbox(
            "Decision to submit",
            [row["payload"]["decision_id"] for row in unrequested_decisions],
            format_func=lambda value: next(
                row["payload"]["decision"]
                for row in unrequested_decisions
                if row["payload"]["decision_id"] == value
            ),
        )
        approval_reason = st.text_area("Approval request reason", max_chars=2000)
        request_approval = st.form_submit_button("Submit for approval")
    if request_approval:
        try:
            created_approval = service.request_approval(
                authenticated,
                workspace_id,
                decision_id=selected_decision_id,
                reason=approval_reason,
            )
            st.success(f"Approval request submitted: {created_approval.payload['approval_id']}")
            st.rerun()
        except (
            CustomerWorkflowError,
            PermissionError,
            ValueError,
            RuntimeError,
            sqlite3.Error,
        ) as error:
            st.error(f"Approval request was not saved: {error}")

for request_event in existing_requests:
    approval = dict(request_event["payload"]["approval"])
    transitions = [
        event["payload"]
        for event in records["approvals"]
        if event["event_type"] == "APPROVAL_TRANSITIONED"
        and event["payload"]["approval_id"] == request_event["payload"]["approval_id"]
    ]
    history = [item["history"] for item in transitions]
    if transitions:
        approval = dict(transitions[-1]["approval"])
    st.markdown(f"**Approval {approval['request_id']} — {approval['state']}**")
    st.caption(
        f"Decision: {request_event['payload']['approval']['requested_action']} · "
        f"Current approver: {approval['current_approver_role']}"
    )
    if approval["state"] in {"PENDING", "ESCALATED"}:
        expected = (
            "executive" if approval["current_approver_role"] == "ceo"
            else approval["current_approver_role"]
        )
        if authenticated.role == expected and authenticated.user_id != approval["requesting_actor"]:
            with st.form(f"approval_transition_{approval['request_id']}"):
                target = st.selectbox(
                    "Customer approval action",
                    ("APPROVED", "REJECTED"),
                    key=f"approval_target_{approval['request_id']}",
                )
                reason = st.text_input(
                    "Decision reason",
                    key=f"approval_reason_{approval['request_id']}",
                )
                transition = st.form_submit_button("Record approval decision")
            if transition:
                try:
                    changed = service.transition_approval(
                        authenticated,
                        workspace_id,
                        approval_id=approval["request_id"],
                        target=target,
                        reason=reason,
                    )
                    st.success(f"Approval state recorded: {changed.payload['approval']['state']}")
                    st.rerun()
                except (
                    CustomerWorkflowError,
                    PermissionError,
                    ValueError,
                    RuntimeError,
                    sqlite3.Error,
                ) as error:
                    st.error(f"Approval decision was not recorded: {error}")
        else:
            st.info(
                f"This step is reserved for a different "
                f"{approval['current_approver_role']} approver."
            )
    if history:
        st.json(history)
    if approval["state"] == "APPROVED":
        if st.button(
            "Create evidence-linked export",
            key=f"export_{approval['request_id']}",
        ):
            try:
                exported = service.export_evidence(
                    authenticated,
                    workspace_id,
                    approval_id=approval["request_id"],
                )
                st.session_state["active_customer_export"] = exported.payload["package"]
                st.rerun()
            except (
                CustomerWorkflowError,
                PermissionError,
                ValueError,
                RuntimeError,
                sqlite3.Error,
            ) as error:
                st.error(f"Evidence export was not created: {error}")

if st.session_state.get("active_customer_export"):
    export_package = st.session_state["active_customer_export"]
    st.download_button(
        "Download evidence-linked decision package",
        data=json.dumps(export_package, indent=2, sort_keys=True),
        file_name=f"nexora-evidence-export-{export_package['export_id']}.json",
        mime="application/json",
    )

if records["exports"]:
    st.subheader("Evidence export history")
    for row in records["exports"]:
        package = row["payload"]["package"]
        st.caption(
            f"Export {package['export_id']} · created {row['occurred_at']} · "
            f"approval {package['approval']['request_id']}"
        )
        st.download_button(
            "Download saved evidence-linked package",
            data=json.dumps(package, indent=2, sort_keys=True),
            file_name=f"nexora-evidence-export-{package['export_id']}.json",
            mime="application/json",
            key=f"saved_export_{package['export_id']}",
        )
