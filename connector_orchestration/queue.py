"""Connector orchestration queue contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4

from connector_orchestration.trigger import ConnectorTrigger
from connector_runtime import ConnectorExecutionPolicy


class QueueState(str, Enum):
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass(frozen=True)
class ConnectorQueueItem:
    queue_id: str = field(default_factory=lambda: str(uuid4()))
    connector_id: str = ""
    trigger: ConnectorTrigger = field(default_factory=ConnectorTrigger)
    policy: ConnectorExecutionPolicy = field(default_factory=ConnectorExecutionPolicy)
    state: QueueState = QueueState.WAITING
    attempt: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def with_state(self, state: QueueState, *, attempt: int | None = None) -> "ConnectorQueueItem":
        return ConnectorQueueItem(
            queue_id=self.queue_id,
            connector_id=self.connector_id,
            trigger=self.trigger,
            policy=self.policy,
            state=state,
            attempt=self.attempt if attempt is None else attempt,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata=self.metadata,
        )


class ConnectorQueueManager:
    """In-memory queue manager for connector orchestration."""

    def __init__(self) -> None:
        self._items: dict[str, ConnectorQueueItem] = {}

    def enqueue(self, connector_id: str, trigger: ConnectorTrigger, policy: ConnectorExecutionPolicy | None = None) -> ConnectorQueueItem:
        item = ConnectorQueueItem(connector_id=connector_id, trigger=trigger, policy=policy or ConnectorExecutionPolicy())
        self._items[item.queue_id] = item
        return item

    def dequeue_next(self) -> ConnectorQueueItem | None:
        waiting = [item for item in self._items.values() if item.state in {QueueState.WAITING, QueueState.RETRYING}]
        if not waiting:
            return None
        item = sorted(waiting, key=lambda candidate: candidate.created_at)[0]
        running = item.with_state(QueueState.RUNNING)
        self._items[item.queue_id] = running
        return running

    def mark(self, queue_id: str, state: QueueState, *, attempt: int | None = None) -> ConnectorQueueItem | None:
        item = self._items.get(queue_id)
        if item is None:
            return None
        updated = item.with_state(state, attempt=attempt)
        self._items[queue_id] = updated
        return updated

    def list_items(self, state: QueueState | None = None) -> list[ConnectorQueueItem]:
        items = list(self._items.values())
        if state is None:
            return items
        return [item for item in items if item.state == state]
