from __future__ import annotations

from typing import Any

from repositories.goal_repository import GoalRepository


DEFAULT_AGENTS = [
    {
        "agent_name": "Planner Agent",
        "description": "Decomposes business goals into enterprise tasks.",
        "version": "1.0",
        "status": "Production",
        "capabilities": ["Goal decomposition", "Task sequencing", "Agent selection"],
        "owner": "Enterprise AI",
        "enabled": True,
    },
    {
        "agent_name": "Cost Agent",
        "description": "Finds cost optimization, savings, and budget opportunities.",
        "version": "1.0",
        "status": "Approved",
        "capabilities": ["Cost optimization", "Savings estimation", "Budget analysis"],
        "owner": "FinOps",
        "enabled": True,
    },
    {
        "agent_name": "Simulation Agent",
        "description": "Runs non-production scenario previews for proposed changes.",
        "version": "1.0",
        "status": "Approved",
        "capabilities": ["Scenario execution", "Risk estimation", "Blast radius preview"],
        "owner": "Enterprise Architecture",
        "enabled": True,
    },
    {
        "agent_name": "Reasoning Agent",
        "description": "Explains recommendations with evidence, policies, and alternatives.",
        "version": "1.0",
        "status": "Approved",
        "capabilities": ["Explainability", "Evidence review", "Decision rationale"],
        "owner": "AI Governance",
        "enabled": True,
    },
    {
        "agent_name": "Governance Agent",
        "description": "Validates policy, approval, and compliance requirements.",
        "version": "1.0",
        "status": "Approved",
        "capabilities": ["Policy validation", "Approval mapping", "Compliance review"],
        "owner": "Governance",
        "enabled": True,
    },
    {
        "agent_name": "Operations Agent",
        "description": "Plans infrastructure, capacity, rollback, and validation steps.",
        "version": "1.0",
        "status": "Experimental",
        "capabilities": ["Infrastructure planning", "Rollback planning", "Validation gates"],
        "owner": "Operations",
        "enabled": True,
    },
    {
        "agent_name": "Security Agent",
        "description": "Reviews security exposure for planned enterprise changes.",
        "version": "1.0",
        "status": "Experimental",
        "capabilities": ["Security review", "Risk validation", "Control checks"],
        "owner": "Security",
        "enabled": True,
    },
]


class AgentRegistry:
    @staticmethod
    def list_agents(organization_id: str | None = None) -> list[dict[str, Any]]:
        rows = GoalRepository.list_agent_registry(organization_id)
        return rows or DEFAULT_AGENTS

    @staticmethod
    def enabled_agents(organization_id: str | None = None) -> list[dict[str, Any]]:
        return [row for row in AgentRegistry.list_agents(organization_id) if row.get("enabled", True)]

    @staticmethod
    def select_agents(classification: str, goal: str, organization_id: str | None = None) -> list[dict[str, Any]]:
        agents = AgentRegistry.enabled_agents(organization_id)
        required = ["Planner Agent", "Simulation Agent", "Reasoning Agent", "Governance Agent"]
        text = f"{classification} {goal}".lower()
        if any(token in text for token in ["cost", "spend", "savings", "license", "saas", "budget"]):
            required.insert(1, "Cost Agent")
        if any(token in text for token in ["availability", "dr", "capacity", "kubernetes", "production"]):
            required.insert(1, "Operations Agent")
        if any(token in text for token in ["security", "compliance", "pci", "risk"]):
            required.insert(1, "Security Agent")
        selected = []
        for name in required:
            match = next((row for row in agents if row.get("agent_name") == name), None)
            if match and match not in selected:
                selected.append(match)
        return selected
