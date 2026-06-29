from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import UUID

import pandas as pd
import streamlit as st

from auth.role_constants import normalize_role
from components.navigation.sidebar import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from core.connectors.base_connector import BaseConnector
from core.connectors.certification.certification_result import ConnectorCertificationStatus
from core.connectors.connector_health import ConnectorHealth, ConnectorHealthStatus
from core.connectors.connector_config import ConnectorConfig, ConnectorType
from core.connectors.connector_context import ConnectorContext
from core.connectors.connector_result import ConnectorResult, ConnectorRunStatus
from repositories.connector_certification_repository import ConnectorCertificationRepository
from repositories.connector_repository import ConnectorRepository
from repositories.connector_runtime_repository import ConnectorRuntimeRepository
from services.connector_service import ConnectorService
from services.connector_runtime_service import ConnectorRuntimeService


ALLOWED_ROLES = {"super_admin"}
ACTIVE_PAGE = "pages/connector_studio.py"


def _require_super_admin() -> None:
    role = normalize_role(st.session_state.get("role", ""))
    if role not in ALLOWED_ROLES:
        st.error("Connector Studio is available only to Super Admin users.")
        st.stop()


def _render_sidebar() -> None:
    role = normalize_role(st.session_state.get("role", "super_admin"))
    render_enterprise_sidebar(
        role,
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
        active_page=ACTIVE_PAGE,
    )


class StudioRuntimeConnector(BaseConnector):
    def connect(self) -> ConnectorResult:
        return ConnectorResult(self.connector_id, "connect", message="Connector Studio runtime handshake completed.")

    def discover(self) -> ConnectorResult:
        return ConnectorResult(self.connector_id, "discover", message="Connector discovery triggered from Connector Studio.")

    def sync_entities(self) -> ConnectorResult:
        return ConnectorResult(self.connector_id, "sync_entities", message="Entity sync triggered from Connector Studio.")

    def sync_relationships(self) -> ConnectorResult:
        return ConnectorResult(self.connector_id, "sync_relationships", message="Relationship sync triggered from Connector Studio.")

    def sync_metadata(self) -> ConnectorResult:
        return ConnectorResult(
            self.connector_id,
            "sync_metadata",
            status=ConnectorRunStatus.SUCCESS.value,
            message="Metadata sync triggered from Connector Studio.",
        )

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            self.connector_id,
            status=ConnectorHealthStatus.HEALTHY.value,
            score=95,
            message="Connector Studio runtime control completed successfully.",
        )


def _repositories() -> tuple[
    ConnectorRepository,
    ConnectorCertificationRepository,
    ConnectorRuntimeRepository,
    ConnectorService,
    ConnectorRuntimeService,
]:
    connector_repository = ConnectorRepository()
    runtime_repository = ConnectorRuntimeRepository()
    connector_service = ConnectorService(repository=connector_repository)
    return (
        connector_repository,
        ConnectorCertificationRepository(),
        runtime_repository,
        connector_service,
        ConnectorRuntimeService(connector_service, runtime_repository, connector_repository),
    )


def _table(rows: list[dict[str, Any]], empty: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info(empty)


def _latest_certifications(certification_repository: ConnectorCertificationRepository) -> dict[str, dict]:
    latest = {}
    for certification in certification_repository.list_certifications():
        connector_id = str(certification.connector_id)
        latest.setdefault(connector_id, certification.to_dict())
    return latest


def _registry_rows(
    connector_repository: ConnectorRepository,
    certification_repository: ConnectorCertificationRepository,
) -> list[dict[str, Any]]:
    certifications = _latest_certifications(certification_repository)
    rows = []
    for entry in connector_repository.list_connectors():
        health = connector_repository.get_health(entry.connector_id)
        certification = certifications.get(str(entry.connector_id), {})
        rows.append(
            {
                "Name": entry.config.name,
                "Provider": entry.config.provider,
                "Type": entry.config.connector_type,
                "Status": entry.status,
                "Enabled": entry.config.enabled,
                "Health": health.status if health else entry.last_health_status,
                "Health Score": health.score if health else "",
                "Certification": certification.get("status", "Pending"),
                "Certification Score": certification.get("score", ""),
                "Last Sync": entry.last_synced_at or "",
                "Last Discovery": entry.last_discovered_at or "",
                "Connector ID": str(entry.connector_id),
            }
        )
    return rows


def _health_rows(connector_repository: ConnectorRepository) -> list[dict[str, Any]]:
    rows = []
    for entry in connector_repository.list_connectors():
        health = connector_repository.get_health(entry.connector_id)
        rows.append(
            {
                "Connector": entry.config.name,
                "Provider": entry.config.provider,
                "Status": health.status if health else "Unknown",
                "Score": health.score if health else 0,
                "Message": health.message if health else "No health result published",
                "Errors": health.error_count if health else "",
                "Latency ms": health.latency_ms if health else "",
                "Checked": health.checked_at if health else "",
            }
        )
    return rows


def _certification_rows(certification_repository: ConnectorCertificationRepository) -> list[dict[str, Any]]:
    return [
        {
            "Connector ID": str(certification.connector_id),
            "Status": certification.status,
            "Score": certification.score,
            "Suite": certification.suite_name,
            "Summary": certification.summary,
            "Certified": certification.certified_at,
        }
        for certification in certification_repository.list_certifications()
    ]


def _schedule_rows(connector_repository: ConnectorRepository) -> list[dict[str, Any]]:
    rows = []
    connector_names = {
        entry.connector_id: entry.config.name
        for entry in connector_repository.list_connectors()
    }
    for schedule in connector_repository.list_schedules():
        rows.append(
            {
                "Connector": connector_names.get(schedule.connector_id, str(schedule.connector_id)),
                "Operation": schedule.operation,
                "Interval Minutes": schedule.interval_minutes,
                "Status": schedule.status,
                "Next Run": schedule.next_run_at or "",
                "Last Run": schedule.last_run_at or "",
            }
        )
    return rows


def _run_history_rows(connector_repository: ConnectorRepository) -> list[dict[str, Any]]:
    connector_names = {
        entry.connector_id: entry.config.name
        for entry in connector_repository.list_connectors()
    }
    return [
        {
            "Connector": connector_names.get(result.connector_id, str(result.connector_id)),
            "Operation": result.operation,
            "Status": result.status,
            "Entities": result.entities_synced,
            "Relationships": result.relationships_synced,
            "Metadata": result.metadata_records,
            "Events": result.events_published,
            "Errors": len(result.errors),
            "Completed": result.completed_at,
        }
        for result in connector_repository.list_results()
    ]


def _runtime_run_rows(
    connector_repository: ConnectorRepository,
    runtime_repository: ConnectorRuntimeRepository,
) -> list[dict[str, Any]]:
    connector_names = {
        entry.connector_id: entry.config.name
        for entry in connector_repository.list_connectors()
    }
    return [
        {
            "Run ID": str(run.id),
            "Connector": connector_names.get(run.connector_id, str(run.connector_id)),
            "Operation": run.operation,
            "Trigger": run.trigger_type,
            "Status": run.status,
            "Attempt": f"{run.attempt}/{run.max_attempts}",
            "Started": run.started_at or "",
            "Completed": run.completed_at or "",
            "Message": run.message,
        }
        for run in runtime_repository.list_runs()
    ]


def _run_log_rows(runtime_repository: ConnectorRuntimeRepository, run_id: str | None = None) -> list[dict[str, Any]]:
    logs = runtime_repository.list_logs(run_id) if run_id else runtime_repository.list_logs()
    return [
        {
            "Run ID": str(log.run_id),
            "Level": log.level,
            "Operation": log.operation,
            "Message": log.message,
            "Created": log.created_at,
        }
        for log in logs
    ]


def _checkpoint_rows(
    connector_repository: ConnectorRepository,
    runtime_repository: ConnectorRuntimeRepository,
) -> list[dict[str, Any]]:
    connector_names = {
        entry.connector_id: entry.config.name
        for entry in connector_repository.list_connectors()
    }
    checkpoints = sorted(runtime_repository._checkpoints.values(), key=lambda item: item.updated_at, reverse=True)
    return [
        {
            "Connector": connector_names.get(checkpoint.connector_id, str(checkpoint.connector_id)),
            "Operation": checkpoint.operation,
            "Cursor": checkpoint.cursor,
            "High Watermark": checkpoint.high_watermark,
            "Records Processed": checkpoint.records_processed,
            "Updated": checkpoint.updated_at,
        }
        for checkpoint in checkpoints
    ]


def _render_kpis(
    connector_repository: ConnectorRepository,
    certification_repository: ConnectorCertificationRepository,
) -> None:
    entries = connector_repository.list_connectors()
    health_rows = _health_rows(connector_repository)
    certifications = certification_repository.list_certifications()
    certified_ids = {
        certification.connector_id
        for certification in certifications
        if certification.status == ConnectorCertificationStatus.CERTIFIED.value
    }
    healthy = sum(1 for row in health_rows if row["Status"] == "Healthy")
    avg_health = (
        sum(float(row["Score"] or 0) for row in health_rows) / len(health_rows)
        if health_rows
        else 0
    )

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Connectors", len(entries))
    col2.metric("Healthy", healthy)
    col3.metric("Certified", len(certified_ids))
    col4.metric("Schedules", len(connector_repository.list_schedules()))
    col5.metric("Runs", len(connector_repository.list_results()))
    col6.metric("Avg Health", f"{avg_health:.1f}%")


def _render_registry(
    connector_repository: ConnectorRepository,
    certification_repository: ConnectorCertificationRepository,
) -> None:
    st.subheader("Connector Registry")
    _table(
        _registry_rows(connector_repository, certification_repository),
        "No connectors have been registered yet.",
    )


def _render_health(connector_repository: ConnectorRepository) -> None:
    st.subheader("Connector Health")
    _table(_health_rows(connector_repository), "No connector health results have been published yet.")


def _render_certification(certification_repository: ConnectorCertificationRepository) -> None:
    st.subheader("Certification Status")
    rows = _certification_rows(certification_repository)
    _table(rows, "No connector certifications have been recorded yet.")

    if rows:
        status_counts = Counter(row["Status"] for row in rows)
        st.subheader("Certification Distribution")
        _table(
            [{"Status": status, "Connectors": count} for status, count in sorted(status_counts.items())],
            "No certification distribution is available.",
        )


def _render_schedules(connector_repository: ConnectorRepository) -> None:
    st.subheader("Schedules")
    _table(_schedule_rows(connector_repository), "No connector schedules have been configured yet.")

    st.subheader("Schedule Status")
    due_count = sum(
        1
        for schedule in connector_repository.list_schedules()
        if schedule.status == "Enabled" and not schedule.next_run_at
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Configured", len(connector_repository.list_schedules()))
    col2.metric("Due Now", due_count)
    col3.metric("Paused", sum(1 for schedule in connector_repository.list_schedules() if schedule.status == "Paused"))


def _render_run_history(connector_repository: ConnectorRepository) -> None:
    st.subheader("Run History")
    _table(_run_history_rows(connector_repository), "No connector run history is available yet.")


def _render_runtime_controls(
    connector_repository: ConnectorRepository,
    runtime_repository: ConnectorRuntimeRepository,
    runtime_service: ConnectorRuntimeService,
) -> None:
    entries = connector_repository.list_connectors()
    st.subheader("Manual Run")
    if not entries:
        st.info("Register a connector before triggering runtime controls.")
        return

    labels = {f"{entry.config.name} | {entry.config.provider} | {entry.connector_id}": entry for entry in entries}
    selected_label = st.selectbox("Connector", list(labels))
    selected_entry = labels[selected_label]
    operation = st.selectbox(
        "Operation",
        ["connect", "discover", "sync_entities", "sync_relationships", "sync_metadata"],
    )
    context = ConnectorContext(selected_entry.config)
    connector = StudioRuntimeConnector(context)

    action_col, retry_col = st.columns(2)
    if action_col.button("Run Now", width="stretch"):
        run = runtime_service.manual_run(connector, operation)
        st.success(f"Run {run.id} completed with status {run.status}.")
        st.rerun()

    failed_runs = [
        run
        for run in runtime_repository.list_runs(selected_entry.connector_id)
        if run.status == "Failed"
    ]
    if failed_runs:
        retry_label = retry_col.selectbox("Failed Run", [f"{run.operation} | {run.id}" for run in failed_runs])
        retry_operation = retry_label.split("|", 1)[0].strip()
        if retry_col.button("Retry Failed Run", width="stretch"):
            run = runtime_service.manual_run(connector, retry_operation)
            st.success(f"Retry run {run.id} completed with status {run.status}.")
            st.rerun()
    else:
        retry_col.info("No failed runs are available to retry.")

    st.subheader("Runtime Runs")
    runtime_rows = _runtime_run_rows(connector_repository, runtime_repository)
    _table(runtime_rows, "No runtime execution runs have been recorded yet.")

    st.subheader("Run Logs")
    if runtime_rows:
        run_options = ["All"] + [row["Run ID"] for row in runtime_rows]
        selected_run = st.selectbox("Log Filter", run_options)
        _table(
            _run_log_rows(runtime_repository, None if selected_run == "All" else selected_run),
            "No logs are available for the selected run.",
        )
    else:
        st.info("No run logs are available yet.")

    st.subheader("Checkpoint Viewer")
    _table(_checkpoint_rows(connector_repository, runtime_repository), "No checkpoints have been recorded yet.")

    st.subheader("Last Run Health")
    health = connector_repository.get_health(selected_entry.connector_id)
    if health:
        st.json(health.to_dict())
    else:
        st.info("No health result has been published for this connector.")


def _render_source_systems(connector_repository: ConnectorRepository) -> None:
    rows = []
    provider_counts = Counter(entry.config.provider for entry in connector_repository.list_connectors())
    for provider, count in sorted(provider_counts.items()):
        entries = connector_repository.list_connectors(provider)
        latest_sync = max((entry.last_synced_at or "" for entry in entries), default="")
        rows.append(
            {
                "Provider": provider,
                "Connectors": count,
                "Enabled": sum(1 for entry in entries if entry.config.enabled),
                "Latest Sync": latest_sync,
            }
        )
    st.subheader("Source Systems")
    _table(rows, "No source systems are represented in the connector registry yet.")


def _render_admin_actions(service: ConnectorService) -> None:
    st.subheader("Register Connector")
    with st.form("connector_registration_form"):
        col1, col2, col3 = st.columns(3)
        name = col1.text_input("Name", value="")
        provider = col2.text_input("Provider", value="")
        connector_type = col3.selectbox("Type", [item.value for item in ConnectorType])
        col4, col5, col6 = st.columns(3)
        organization_id = col4.text_input("Organization ID", value="")
        auth_type = col5.selectbox("Auth", ["api_key", "oauth", "service_account", "aws", "azure"])
        interval = col6.number_input("Sync Interval", min_value=5, max_value=10080, value=60)
        submitted = st.form_submit_button("Register")
        if submitted:
            if not name.strip() or not provider.strip() or not organization_id.strip():
                st.error("Name, provider, and organization ID are required.")
                return
            try:
                config = ConnectorConfig(
                    name=name,
                    provider=provider,
                    connector_type=connector_type,
                    organization_id=UUID(organization_id),
                    auth_type=auth_type,
                    sync_interval_minutes=int(interval),
                )
                service.register_connector(config)
                service.schedule_connector(config.id, "sync_entities", int(interval))
                st.success("Connector registered.")
                st.rerun()
            except ValueError as exc:
                st.error(f"Invalid connector configuration: {exc}")


def render_section() -> None:
    (
        connector_repository,
        certification_repository,
        runtime_repository,
        connector_service,
        runtime_service,
    ) = _repositories()

    st.title("Connector Studio")
    st.caption("Program 2.5 - Connector Studio runtime controls and admin workspace")

    _render_kpis(connector_repository, certification_repository)
    tabs = st.tabs(["Registry", "Health", "Certification", "Schedules", "Run History", "Runtime Controls", "Source Systems", "Admin"])
    with tabs[0]:
        _render_registry(connector_repository, certification_repository)
    with tabs[1]:
        _render_health(connector_repository)
    with tabs[2]:
        _render_certification(certification_repository)
    with tabs[3]:
        _render_schedules(connector_repository)
    with tabs[4]:
        _render_run_history(connector_repository)
    with tabs[5]:
        _render_runtime_controls(connector_repository, runtime_repository, runtime_service)
    with tabs[6]:
        _render_source_systems(connector_repository)
    with tabs[7]:
        _render_admin_actions(connector_service)


def render_page() -> None:
    st.set_page_config(page_title="Connector Studio", layout="wide")
    _require_super_admin()
    _render_sidebar()
    render_section()


if __name__ == "__main__":
    render_page()
