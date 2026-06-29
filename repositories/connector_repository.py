from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core.connectors.connector_config import ConnectorConfig
from core.connectors.connector_health import ConnectorHealth
from core.connectors.connector_registry import ConnectorRegistryEntry
from core.connectors.connector_result import ConnectorResult
from core.connectors.connector_scheduler import ConnectorSchedule


DEFAULT_CONNECTOR_STORE = Path("data/connector_platform.json")


class ConnectorRepository:
    def __init__(self, store_path: str | Path = DEFAULT_CONNECTOR_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._registry: dict[UUID, ConnectorRegistryEntry] = {}
        self._results: list[ConnectorResult] = []
        self._health: dict[UUID, ConnectorHealth] = {}
        self._schedules: dict[UUID, ConnectorSchedule] = {}
        self._load()

    def register(self, entry: ConnectorRegistryEntry) -> ConnectorRegistryEntry:
        self._registry[entry.connector_id] = entry
        self._persist()
        return entry

    def get_connector(self, connector_id: UUID | str) -> ConnectorRegistryEntry | None:
        return self._registry.get(UUID(str(connector_id)))

    def list_connectors(self, provider: str | None = None) -> list[ConnectorRegistryEntry]:
        entries = list(self._registry.values())
        if provider:
            entries = [entry for entry in entries if entry.config.provider == provider]
        return sorted(entries, key=lambda entry: entry.config.name.lower())

    def save_result(self, result: ConnectorResult) -> ConnectorResult:
        self._results.append(result)
        self._persist()
        return result

    def list_results(self, connector_id: UUID | str | None = None) -> list[ConnectorResult]:
        results = list(self._results)
        if connector_id:
            resolved_id = UUID(str(connector_id))
            results = [result for result in results if result.connector_id == resolved_id]
        return sorted(results, key=lambda result: result.completed_at, reverse=True)

    def save_health(self, health: ConnectorHealth) -> ConnectorHealth:
        self._health[health.connector_id] = health
        self._persist()
        return health

    def get_health(self, connector_id: UUID | str) -> ConnectorHealth | None:
        return self._health.get(UUID(str(connector_id)))

    def save_schedule(self, schedule: ConnectorSchedule) -> ConnectorSchedule:
        self._schedules[schedule.id] = schedule
        self._persist()
        return schedule

    def list_schedules(self, connector_id: UUID | str | None = None) -> list[ConnectorSchedule]:
        schedules = list(self._schedules.values())
        if connector_id:
            resolved_id = UUID(str(connector_id))
            schedules = [schedule for schedule in schedules if schedule.connector_id == resolved_id]
        return sorted(schedules, key=lambda schedule: schedule.operation)

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        payload = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        self._registry = {
            UUID(item["config"]["id"]): ConnectorRegistryEntry.from_dict(item)
            for item in payload.get("registry", [])
        }
        self._results = [ConnectorResult.from_dict(item) for item in payload.get("results", [])]
        self._health = {
            UUID(item["connector_id"]): ConnectorHealth.from_dict(item)
            for item in payload.get("health", [])
        }
        self._schedules = {
            UUID(item["id"]): ConnectorSchedule.from_dict(item)
            for item in payload.get("schedules", [])
        }

    def _persist(self) -> None:
        payload = {
            "registry": [entry.to_dict() for entry in self.list_connectors()],
            "results": [result.to_dict() for result in self.list_results()],
            "health": [health.to_dict() for health in self._health.values()],
            "schedules": [schedule.to_dict() for schedule in self.list_schedules()],
        }
        self.store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
