from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AgentResult:
    agent_name: str
    status: str
    output: dict[str, Any]
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class BaseAgent:
    agent_name = "Base Agent"
    description = "Shared lifecycle for all Nexora agents."
    version = "1.0"
    capabilities: list[str] = []

    def understand_goal(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        return {"goal": goal, "context_available": bool(context)}

    def collect_context(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        return context

    def create_plan(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        return {"goal": goal, "tasks": []}

    def validate(self, plan: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return {"valid": True, "issues": [], "context_available": bool(context), "task_count": len(plan.get("tasks", []))}

    def execute(self, plan: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        validation = self.validate(plan, context)
        return AgentResult(
            agent_name=self.agent_name,
            status="PLANNED" if validation["valid"] else "NEEDS_REVIEW",
            output={"plan": plan, "validation": validation},
            confidence=plan.get("confidence", 0.0),
        )

    def learn(self, result: AgentResult, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "agent": self.agent_name,
            "status": result.status,
            "learning_mode": "passive",
            "context_keys": sorted(context.keys()),
        }
