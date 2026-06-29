from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from agents.context_manager import AgentContextManager


class AgentSessionManager:
    @staticmethod
    def start_session(goal: str, organization_id: str | None = None, created_by: str = "system") -> dict[str, Any]:
        context = AgentContextManager.build_context(goal, organization_id)
        session_id = str(uuid.uuid4())
        return {
            "id": session_id,
            "goal_id": str(uuid.uuid4()),
            "organization_id": context["organization_id"],
            "goal": goal,
            "created_by": created_by,
            "status": "Collaboration Started",
            "started_at": datetime.utcnow().isoformat(),
            "participants": [],
            "execution_state": "Context Ready",
            "retry_count": 0,
            "failures": [],
            "context": context,
        }

    @staticmethod
    def mark_participants(session: dict[str, Any], participants: list[str]) -> dict[str, Any]:
        session["participants"] = participants
        session["execution_state"] = "Agents Selected"
        return session

    @staticmethod
    def complete(session: dict[str, Any], status: str = "Consensus Reached") -> dict[str, Any]:
        session["status"] = status
        session["execution_state"] = status
        session["ended_at"] = datetime.utcnow().isoformat()
        return session
