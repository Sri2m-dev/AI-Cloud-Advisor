from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any


class ExecutionEventBus:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, event_type: str, workflow_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "workflow_id": workflow_id,
            "payload": payload or {},
            "created_at": datetime.utcnow().isoformat(),
            "sequence": len(self.events) + 1,
        }
        self.events.append(event)
        return event
