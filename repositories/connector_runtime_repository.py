from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core.connectors.runtime.execution_run import ConnectorExecutionRun
from core.connectors.runtime.retry_policy import ConnectorRetryPolicy
from core.connectors.runtime.run_log import ConnectorRunLog
from core.connectors.runtime.sync_checkpoint import ConnectorSyncCheckpoint


DEFAULT_CONNECTOR_RUNTIME_STORE = Path("data/connector_runtime.json")


class ConnectorRuntimeRepository:
    def __init__(self, store_path: str | Path = DEFAULT_CONNECTOR_RUNTIME_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._runs: dict[UUID, ConnectorExecutionRun] = {}
        self._logs: list[ConnectorRunLog] = []
        self._checkpoints: dict[tuple[UUID, str], ConnectorSyncCheckpoint] = {}
        self._retry_policies: dict[UUID, ConnectorRetryPolicy] = {}
        self._load()

    def save_run(self, run: ConnectorExecutionRun) -> ConnectorExecutionRun:
        self._runs[run.id] = run
        self._persist()
        return run

    def get_run(self, run_id: UUID | str) -> ConnectorExecutionRun | None:
        return self._runs.get(UUID(str(run_id)))

    def list_runs(self, connector_id: UUID | str | None = None) -> list[ConnectorExecutionRun]:
        runs = list(self._runs.values())
        if connector_id:
            resolved_id = UUID(str(connector_id))
            runs = [run for run in runs if run.connector_id == resolved_id]
        return sorted(runs, key=lambda run: run.created_at, reverse=True)

    def append_log(self, log: ConnectorRunLog) -> ConnectorRunLog:
        self._logs.append(log)
        self._persist()
        return log

    def list_logs(self, run_id: UUID | str | None = None) -> list[ConnectorRunLog]:
        logs = list(self._logs)
        if run_id:
            resolved_id = UUID(str(run_id))
            logs = [log for log in logs if log.run_id == resolved_id]
        return sorted(logs, key=lambda log: log.created_at)

    def save_checkpoint(self, checkpoint: ConnectorSyncCheckpoint) -> ConnectorSyncCheckpoint:
        self._checkpoints[(checkpoint.connector_id, checkpoint.operation)] = checkpoint
        self._persist()
        return checkpoint

    def get_checkpoint(self, connector_id: UUID | str, operation: str) -> ConnectorSyncCheckpoint | None:
        return self._checkpoints.get((UUID(str(connector_id)), operation))

    def save_retry_policy(self, policy: ConnectorRetryPolicy) -> ConnectorRetryPolicy:
        self._retry_policies[policy.id] = policy
        self._persist()
        return policy

    def default_retry_policy(self) -> ConnectorRetryPolicy:
        if not self._retry_policies:
            return self.save_retry_policy(ConnectorRetryPolicy())
        return sorted(self._retry_policies.values(), key=lambda policy: policy.name)[0]

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        payload = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        self._runs = {
            UUID(item["id"]): ConnectorExecutionRun.from_dict(item)
            for item in payload.get("runs", [])
        }
        self._logs = [ConnectorRunLog.from_dict(item) for item in payload.get("logs", [])]
        checkpoints = [
            ConnectorSyncCheckpoint.from_dict(item)
            for item in payload.get("checkpoints", [])
        ]
        self._checkpoints = {
            (checkpoint.connector_id, checkpoint.operation): checkpoint
            for checkpoint in checkpoints
        }
        self._retry_policies = {
            UUID(item["id"]): ConnectorRetryPolicy.from_dict(item)
            for item in payload.get("retry_policies", [])
        }

    def _persist(self) -> None:
        payload = {
            "runs": [run.to_dict() for run in self.list_runs()],
            "logs": [log.to_dict() for log in self._logs],
            "checkpoints": [checkpoint.to_dict() for checkpoint in self._checkpoints.values()],
            "retry_policies": [policy.to_dict() for policy in self._retry_policies.values()],
        }
        self.store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
