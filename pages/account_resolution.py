"""Governed account classification and approval workspace."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.cloud_account_registry_composition import cloud_account_registry_service
from services.enterprise_spend_composition import authenticated_tenant_context
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

configure_page(page_title="Account Resolution | Nexora", page_icon="search")
init_session()
require_role(
    ["super_admin", "client_admin", "executive", "cio", "finance", "operations", "auditor"]
)
context = authenticated_tenant_context(st.session_state)
service = cloud_account_registry_service()
render_enterprise_sidebar(
    st.session_state.get("role", "viewer"),
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Account Resolution"],
)


def content():
    dashboard = service.dashboard(context)
    classifications = dashboard["classifications"]
    metrics = st.columns(8)
    labels = (
        "Discovered Accounts",
        "Needs Review",
        "Resolved (Inferred)",
        "Resolved (Approved)",
        "Conflicted",
        "Quarantined Spend",
        "Provisionally Classified",
        "Governed Spend",
    )
    values = (
        dashboard["total"],
        dashboard["needs_review"],
        dashboard["resolved_inferred"],
        dashboard["resolved_approved"],
        dashboard["conflicted"],
        dashboard["quarantined_spend"],
        0,
        dashboard["resolved_spend"],
    )
    for column, label, value in zip(metrics, labels, values):
        column.metric(label, value)
    render_section(
        "Account Resolution",
        "Inference is provisional; approval and financial release remain separate boundaries.",
    )
    summaries = []
    for row in dashboard["accounts"]:
        results = classifications.get(str(row.get("account_id")), ())
        summaries.append(
            {
                "Account ID": row.get("account_id"),
                "Provider": row.get("provider"),
                "Spend": row.get("quarantined_spend", 0),
                "Inference Coverage": sum(result.inferred_value is not None for result in results),
                "Highest Confidence": max(
                    (result.confidence_score for result in results), default=0
                ),
                "Conflict Count": sum(result.conflict for result in results),
                "Lifecycle": row.get("resolution_status") or "DISCOVERED",
            }
        )
    st.dataframe(pd.DataFrame(summaries), use_container_width=True, hide_index=True)
    if not dashboard["accounts"]:
        return
    selected = st.selectbox(
        "Review account",
        dashboard["accounts"],
        format_func=lambda row: f"{row.get('provider', '').upper()} · {row.get('account_id')}",
    )
    results = classifications.get(str(selected.get("account_id")), ())
    if st.button("Load billing evidence and run inference"):
        results = service.classify_account(context, selected)
    tabs = st.tabs(
        [
            "Discovery Evidence",
            "Classification",
            "Business Mapping",
            "Financial Impact",
            "Approval History",
            "Audit History",
        ]
    )
    tabs[0].json(
        {
            key: selected.get(key)
            for key in (
                "source_import_id",
                "payer_account_id",
                "first_seen_at",
                "last_seen_at",
                "source_row_count",
                "quarantined_spend",
                "currency",
            )
        }
    )
    tabs[1].dataframe(
        pd.DataFrame(
            [
                {
                    "Field": result.field_name,
                    "Current Value": selected.get(result.field_name),
                    "Inferred Value": result.inferred_value or "UNKNOWN",
                    "Confidence": result.confidence_score,
                    "Evidence": len(result.evidence_ids),
                    "Status": result.inference_status,
                    "Approval": result.approval_status,
                    "Conflict": result.conflict,
                    "Review Reason": result.review_reason,
                }
                for result in results
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    tabs[2].write({result.field_name: result.inferred_value or "UNKNOWN" for result in results})
    tabs[3].write(
        {
            "Spend": selected.get("quarantined_spend", 0),
            "Policy": "Quarantine retained; provisional release disabled by default",
            "Allocation": "Not eligible before approval",
        }
    )
    tabs[4].info("High confidence never implies approval without tenant authority.")
    tabs[5].dataframe(
        service.repository.audit_history(context, selected["id"]) if selected.get("id") else []
    )


render_page(
    title="Account Resolution",
    description="Field-level classification, evidence review, and governed approval.",
    content=content,
)
