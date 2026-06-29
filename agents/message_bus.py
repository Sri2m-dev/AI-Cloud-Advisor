from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any


class AgentMessageBus:
    def __init__(self, goal_id: str) -> None:
        self.goal_id = goal_id
        self.messages: list[dict[str, Any]] = []
        self.participants: list[str] = []

    def register(self, agent_name: str) -> None:
        if agent_name not in self.participants:
            self.participants.append(agent_name)

    def route(
        self,
        sender: str,
        recipient: str,
        request: str,
        priority: str = "Normal",
        status: str = "Pending",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.register(sender)
        self.register(recipient)
        message = {
            "id": str(uuid.uuid4()),
            "goal_id": self.goal_id,
            "sender": sender,
            "recipient": recipient,
            "request": request,
            "priority": priority,
            "status": status,
            "payload": payload or {},
            "created_at": datetime.utcnow().isoformat(),
            "sequence": len(self.messages) + 1,
        }
        self.messages.append(message)
        return message

    def complete(self, message: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        message["status"] = "Completed"
        message["response"] = response
        message["completed_at"] = datetime.utcnow().isoformat()
        return message
