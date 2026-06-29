from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from core.connectors.base_connector import BaseConnector
from core.connectors.connector_health import ConnectorHealth
from core.connectors.connector_result import ConnectorResult, ConnectorRunStatus
from core.connectors.runtime.execution_run import (
    ConnectorExecutionRun,
    ConnectorExecutionStatus,
    ConnectorTriggerType,
)
from core.connectors.runtime.retry_policy import ConnectorRetryPolicy
from core.connectors.runtime.run_log import ConnectorLogLevel, ConnectorRunLog
from core.connectors.runtime.sync_checkpoint import ConnectorSyncCheckpoint
from repositories.connector_repository import ConnectorRepository
from repositories.connector_runtime_repository import ConnectorRuntimeRepository
from services.connector_service import ConnectorService


class ConnectorRuntimeService:
    def __init__(
        self,
        connector_service: ConnectorService | None = None,
        runtime_repository: ConnectorRuntimeRepository | None = None,
        connector_repository: ConnectorRepository | None = None,
    ):
        self.connector_repository = connector_repository or ConnectorRepository()
        self.connector_service = connector_service or ConnectorService(repository=self.connector_repository)
        self.runtime_repository = runtime_repository or ConnectorRuntimeRepository()

    def manual_run(
        self,
        connector: BaseConnector,
        operation: str,
        retry_policy: ConnectorRetryPolicy | None = None,
    ) -> ConnectorExecutionRun:
        return self.execute(connector, operation, ConnectorTriggerType.MANUAL.value, retry_policy)

    def execute(
        self,
        connector: BaseConnector,
        operation: str,
        trigger_type: str = ConnectorTriggerType.SCHEDULED.value,
        retry_policy: ConnectorRetryPolicy | None = None,
    ) -> ConnectorExecutionRun:
        policy = retry_policy or self.runtime_repository.default_retry_policy()
        run = ConnectorExecutionRun(
            connector_id=connector.connector_id,
            operation=operation,
            trigger_type=trigger_type,
            max_attempts=policy.max_attempts,
        )
        self.runtime_repository.save_run(run)
        self._log(run, ConnectorLogLevel.INFO.value, f"Queued {operation} run.")

        for attempt in range(1, policy.max_attempts + 1):
            run.attempt = attempt
            run.status = ConnectorExecutionStatus.RUNNING.value
            run.started_at = run.started_at or self._now()
            run.updated_at = self._now()
            self.runtime_repository.save_run(run)
            self._log(run, ConnectorLogLevel.INFO.value, f"Starting attempt {attempt}.")

            result = self._execute_operation(connector, operation)
            self.connector_repository.save_result(result)
            run.result_id = result.id
            run.message = result.message

            if result.status not in policy.retry_on_statuses:
                run.status = self._status_from_result(result)
                break

            if attempt < policy.max_attempts:
                run.status = ConnectorExecutionStatus.RETRYING.value
                self._log(
                    run,
                    ConnectorLogLevel.WARNING.value,
                    f"Attempt {attempt} failed; retry delay {policy.delay_for_attempt(attempt + 1)} seconds.",
                    {"errors": result.errors},
                )
                self.runtime_repository.save_run(run)
            else:
                run.status = ConnectorExecutionStatus.FAILED.value

        run.completed_at = self._now()
        run.updated_at = run.completed_at
        checkpoint = self.update_checkpoint(
            connector.connector_id,
            operation,
            records_processed=self._records_processed_for_result(result),
            metadata={"result_status": result.status},
        )
        run.checkpoint_id = checkpoint.id
        health = self.update_health_after_run(connector, run, result)
        run.health_id = health.id
        self.runtime_repository.save_run(run)
        self._log(run, ConnectorLogLevel.INFO.value, f"Completed with status {run.status}.")
        return run

    def due_schedules(self) -> list:
        now = self._now()
        return [
            schedule
            for schedule in self.connector_repository.list_schedules()
            if schedule.status == "Enabled" and (not schedule.next_run_at or schedule.next_run_at <= now)
        ]

    def update_checkpoint(
        self,
        connector_id: UUID | str,
        operation: str,
        cursor: str = "",
        high_watermark: str = "",
        records_processed: int = 0,
        metadata: dict | None = None,
    ) -> ConnectorSyncCheckpoint:
        existing = self.runtime_repository.get_checkpoint(connector_id, operation)
        checkpoint = existing or ConnectorSyncCheckpoint(UUID(str(connector_id)), operation)
        checkpoint.cursor = cursor or checkpoint.cursor
        checkpoint.high_watermark = high_watermark or self._now()
        checkpoint.records_processed += records_processed
        checkpoint.metadata.update(metadata or {})
        checkpoint.updated_at = self._now()
        return self.runtime_repository.save_checkpoint(checkpoint)

    def update_health_after_run(
        self,
        connector: BaseConnector,
        run: ConnectorExecutionRun,
        result: ConnectorResult,
    ) -> ConnectorHealth:
        health = connector.health_check()
        if result.status == ConnectorRunStatus.FAILED.value:
            health.score = min(health.score, 50.0)
            health.error_count += max(1, len(result.errors))
            health.last_error_at = self._now()
        else:
            health.last_success_at = self._now()
        health.metadata.update({"last_run_id": str(run.id), "last_operation": run.operation})
        self.connector_repository.save_health(health)
        entry = self.connector_repository.get_connector(connector.connector_id)
        if entry:
            entry.last_health_status = health.status
            if result.ok:
                entry.last_synced_at = self._now()
            self.connector_repository.register(entry)
        return health

    def run_logs(self, run_id: UUID | str) -> list[ConnectorRunLog]:
        return self.runtime_repository.list_logs(run_id)

    def _execute_operation(self, connector: BaseConnector, operation: str) -> ConnectorResult:
        operations = {
            "connect": connector.connect,
            "discover": connector.discover,
            "sync_entities": connector.sync_entities,
            "sync_relationships": connector.sync_relationships,
            "sync_metadata": connector.sync_metadata,
        }
        if operation not in operations:
            return ConnectorResult(
                connector.connector_id,
                operation,
                status=ConnectorRunStatus.FAILED.value,
                message=f"Unsupported connector operation: {operation}",
                errors=[f"Unsupported operation: {operation}"],
            )
        try:
            return operations[operation]()
        except Exception as exc:
            return ConnectorResult(
                connector.connector_id,
                operation,
                status=ConnectorRunStatus.FAILED.value,
                message=str(exc),
                errors=[str(exc)],
            )

    def _log(
        self,
        run: ConnectorExecutionRun,
        level: str,
        message: str,
        metadata: dict | None = None,
    ) -> ConnectorRunLog:
        return self.runtime_repository.append_log(
            ConnectorRunLog(
                run_id=run.id,
                connector_id=run.connector_id,
                operation=run.operation,
                level=level,
                message=message,
                metadata=metadata or {},
            )
        )

    @staticmethod
    def _status_from_result(result: ConnectorResult) -> str:
        if result.status == ConnectorRunStatus.SUCCESS.value:
            return ConnectorExecutionStatus.SUCCESS.value
        if result.status == ConnectorRunStatus.PARTIAL.value:
            return ConnectorExecutionStatus.PARTIAL.value
        if result.status == ConnectorRunStatus.SKIPPED.value:
            return ConnectorExecutionStatus.CANCELLED.value
        return ConnectorExecutionStatus.FAILED.value

    @staticmethod
    def _records_processed_for_result(result: ConnectorResult) -> int:
        return result.entities_synced + result.relationships_synced + result.metadata_records + result.events_published

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
