"""Data Source Control Tower Service for Nexora v1.1.

Provides a unified, provider-neutral operational read-model over all configured
tenant live data sources (AWS, Azure, M365), evaluating source health,
cadence-based freshness, execution history, and safe operational lifecycle actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from auth.authenticated_tenant import AuthenticatedTenantContext
from connector_orchestration.trigger import ConnectorTriggerType
from services.live_source_service import LiveSourceService, live_source_service


class SourceHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    NEVER_SYNCED = "NEVER_SYNCED"
    DISABLED = "DISABLED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class ControlTowerSourceView:
    source_id: str
    organization_id: str
    tenant_id: str
    provider: str
    source_type: str
    display_name: str
    connection_status: str
    active: bool
    validation_status: str
    health: SourceHealth
    freshness: FreshnessStatus
    last_sync_at: str | None
    last_success_at: str | None
    last_sync_status: str
    records_discovered: int
    records_ingested: int
    records_rejected: int
    schedule_enabled: bool
    cadence_seconds: int
    next_run_at: str | None
    safe_error_summary: str | None
    created_by: str
    created_at: str
    updated_at: str
    provenance_reference: str


@dataclass(frozen=True)
class ExecutionHistoryRecord:
    execution_id: str
    source_id: str
    trigger_type: str
    started_at: str | None
    completed_at: str | None
    status: str
    records_discovered: int
    records_ingested: int
    records_rejected: int
    safe_error_summary: str | None
    evidence_reference: str | None


class DataSourceControlTowerService:
    """Unified operational control plane over all tenant data sources."""

    def __init__(self, live_service: LiveSourceService | None = None, *, clock=None) -> None:
        self.live_service = live_service
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _get_service(self) -> LiveSourceService:
        if self.live_service is not None:
            return self.live_service
        return live_source_service()

    def _evaluate_freshness(
        self,
        last_success_at: str | None,
        schedule_enabled: bool,
        cadence_seconds: int,
        source_type: str,
        next_run_at: str | None = None,
    ) -> FreshnessStatus:
        if source_type == "uploaded_evidence":
            return FreshnessStatus.NOT_APPLICABLE
        if not last_success_at or not schedule_enabled or cadence_seconds <= 0:
            return FreshnessStatus.UNKNOWN

        try:
            success_dt = datetime.fromisoformat(last_success_at)
            expected_dt = datetime.fromisoformat(next_run_at) if next_run_at else None
        except (ValueError, TypeError):
            return FreshnessStatus.UNKNOWN

        now_dt = self.clock()
        if not success_dt.tzinfo or success_dt > now_dt:
            return FreshnessStatus.UNKNOWN
        if expected_dt is not None and not expected_dt.tzinfo:
            return FreshnessStatus.UNKNOWN
        # Freshness derived from expected cadence + bounded grace period
        grace = timedelta(seconds=min(3600, cadence_seconds // 2))
        deadline = success_dt + timedelta(seconds=cadence_seconds)
        if expected_dt is not None:
            deadline = min(deadline, expected_dt)
        if now_dt > deadline + grace:
            return FreshnessStatus.STALE
        return FreshnessStatus.FRESH

    def _evaluate_health(
        self,
        status: str,
        active: bool,
        last_sync_status: str,
        freshness: FreshnessStatus,
    ) -> SourceHealth:
        if status == "DISABLED":
            return SourceHealth.DISABLED
        if status in {"ERROR", "FAILED"} or last_sync_status == "FAILED":
            return SourceHealth.FAILED
        if last_sync_status == "NEVER_SYNCED":
            return SourceHealth.NEVER_SYNCED
        if status == "VALIDATING" or last_sync_status in {"RUNNING", "QUEUED"}:
            return SourceHealth.DEGRADED
        if not active:
            return SourceHealth.UNKNOWN
        if freshness == FreshnessStatus.STALE:
            return SourceHealth.STALE
        if (
            last_sync_status == "SUCCEEDED"
            and status == "ACTIVE"
            and freshness == FreshnessStatus.FRESH
        ):
            return SourceHealth.HEALTHY
        return SourceHealth.UNKNOWN

    def _execution_rows(self, context, source_id):
        """Read canonical runs with the same tie-breaker as source latest status."""
        service = self._get_service()
        service.authorize(context)
        with service.repository.transaction() as db:
            service.repository.source(db, context, source_id)
            return tuple(
                dict(row)
                for row in db.execute(
                    "SELECT * FROM connector_executions WHERE organization_id=? AND tenant_id=? "
                    "AND source_id=? ORDER BY queued_at DESC, rowid DESC LIMIT 100",
                    (context.organization_id, context.tenant_id, source_id),
                )
            )

    def list_unified_sources(
        self, context: AuthenticatedTenantContext
    ) -> tuple[ControlTowerSourceView, ...]:
        service = self._get_service()
        service.authorize(context)
        raw_sources = service.list_sources(context)

        unified_views: list[ControlTowerSourceView] = []

        for s in raw_sources:
            source_id = s["source_id"]
            provider = s["provider"]
            source_type = "saas_api" if provider == "m365" else "cloud_api"
            active = s["status"] == "ACTIVE"
            conn_status = s["status"]
            val_status = "READY" if s["status"] in {"READY", "ACTIVE"} else s["status"]

            # Get latest execution metrics
            executions = self._execution_rows(context, source_id)
            latest_exec = executions[0] if executions else None

            last_sync_status = (
                latest_exec["status"] if latest_exec else s.get("sync_status", "UNKNOWN")
            )
            last_sync_at = (
                latest_exec.get("completed_at") or latest_exec.get("started_at")
                if latest_exec
                else None
            )
            last_success_at = s.get("last_success_at")
            records_discovered = latest_exec.get("records_discovered", 0) if latest_exec else 0
            records_ingested = latest_exec.get("records_ingested", 0) if latest_exec else 0
            records_rejected = latest_exec.get("records_rejected", 0) if latest_exec else 0

            sched_enabled = bool(s.get("schedule_enabled", False))
            cadence = int(s.get("cadence_seconds") or 0)
            next_run = s.get("next_run_at")

            freshness = self._evaluate_freshness(
                last_success_at=last_success_at,
                schedule_enabled=sched_enabled,
                cadence_seconds=cadence,
                source_type=source_type,
                next_run_at=next_run,
            )

            health = self._evaluate_health(
                status=conn_status,
                active=active,
                last_sync_status=last_sync_status,
                freshness=freshness,
            )

            provenance = (
                latest_exec.get("evidence_reference") if latest_exec else None
            ) or f"source-instance:{source_id}"

            unified_views.append(
                ControlTowerSourceView(
                    source_id=source_id,
                    organization_id=s["organization_id"],
                    tenant_id=s["tenant_id"],
                    provider=provider,
                    source_type=source_type,
                    display_name=s["display_name"],
                    connection_status=conn_status,
                    active=active,
                    validation_status=val_status,
                    health=health,
                    freshness=freshness,
                    last_sync_at=last_sync_at,
                    last_success_at=last_success_at,
                    last_sync_status=last_sync_status,
                    records_discovered=records_discovered,
                    records_ingested=records_ingested,
                    records_rejected=records_rejected,
                    schedule_enabled=sched_enabled,
                    cadence_seconds=cadence,
                    next_run_at=next_run,
                    safe_error_summary=s.get("safe_error_summary"),
                    created_by=s.get("created_by", "system"),
                    created_at=s["created_at"],
                    updated_at=s["updated_at"],
                    provenance_reference=provenance,
                )
            )

        return tuple(unified_views)

    def get_source_detail(
        self, context: AuthenticatedTenantContext, source_id: str
    ) -> ControlTowerSourceView | None:
        sources = self.list_unified_sources(context)
        for s in sources:
            if s.source_id == source_id:
                return s
        return None

    def get_execution_history(
        self, context: AuthenticatedTenantContext, source_id: str
    ) -> tuple[ExecutionHistoryRecord, ...]:
        service = self._get_service()
        service.authorize(context)
        raw_execs = self._execution_rows(context, source_id)

        history: list[ExecutionHistoryRecord] = []
        for e in raw_execs:
            history.append(
                ExecutionHistoryRecord(
                    execution_id=e["execution_id"],
                    source_id=e["source_id"],
                    trigger_type=e["trigger_type"],
                    started_at=e.get("started_at"),
                    completed_at=e.get("completed_at"),
                    status=e["status"],
                    records_discovered=e.get("records_discovered", 0),
                    records_ingested=e.get("records_ingested", 0),
                    records_rejected=e.get("records_rejected", 0),
                    safe_error_summary=e.get("safe_error_summary"),
                    evidence_reference=e.get("evidence_reference"),
                )
            )
        return tuple(history)

    def trigger_manual_sync(
        self, context: AuthenticatedTenantContext, source_id: str, request_key: str
    ) -> dict[str, Any]:
        service = self._get_service()
        return service.sync(
            context, source_id, request_key=request_key, trigger=ConnectorTriggerType.MANUAL
        )

    def toggle_source_active(
        self, context: AuthenticatedTenantContext, source_id: str, active: bool
    ) -> None:
        service = self._get_service()
        service.set_active(context, source_id, active)
