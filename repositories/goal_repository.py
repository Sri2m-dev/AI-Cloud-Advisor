from __future__ import annotations

import uuid
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class GoalRepository:
    @staticmethod
    def save_goal_plan(plan: dict[str, Any]) -> bool:
        org_id = resolve_organization_id(plan.get("organization_id"))
        goal_id = plan.get("id") or str(uuid.uuid4())
        ok = True
        ok = GoalRepository._insert(
            "goal_registry",
            {
                "id": goal_id,
                "organization_id": org_id,
                "goal_text": plan.get("goal"),
                "classification": plan.get("classification"),
                "target_asset": plan.get("target"),
                "status": plan.get("status"),
                "confidence": (plan.get("execution_preview") or {}).get("Confidence", 0),
                "created_by": plan.get("created_by", "system"),
                "created_at": plan.get("created_at"),
            },
        ) and ok
        ok = GoalRepository._insert(
            "goal_execution_plan",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "goal_id": goal_id,
                "plan_payload": plan.get("execution_blueprint") or {},
                "estimated_savings": (plan.get("execution_preview") or {}).get("Expected Savings", 0),
                "risk": (plan.get("execution_preview") or {}).get("Risk", "Medium"),
                "approvals": (plan.get("execution_preview") or {}).get("Approvals", []),
                "status": "Review Ready",
            },
        ) and ok
        for task in plan.get("tasks", []):
            ok = GoalRepository._insert(
                "goal_task",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "goal_id": goal_id,
                    "task_number": task.get("Task"),
                    "task_name": task.get("Name"),
                    "agent_name": task.get("Agent"),
                    "description": task.get("Description"),
                    "status": task.get("Status", "Planned"),
                },
            ) and ok
        ok = GoalRepository._insert(
            "goal_history",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "goal_id": goal_id,
                "event_type": "PLAN_CREATED",
                "event_payload": plan,
                "created_by": plan.get("created_by", "system"),
            },
        ) and ok
        ok = GoalRepository._insert(
            "goal_status",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "goal_id": goal_id,
                "status": plan.get("status", "PLAN_READY"),
                "reason": "Execution blueprint created for review. Production execution remains disabled.",
                "created_by": plan.get("created_by", "system"),
            },
        ) and ok
        ok = GoalRepository._insert(
            "agent_session",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "goal_id": goal_id,
                "session_status": "Planning Complete",
                "started_by": plan.get("created_by", "system"),
                "ended_at": plan.get("created_at"),
            },
        ) and ok
        ok = GoalRepository._insert(
            "agent_plan",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "goal_id": goal_id,
                "agents": plan.get("agents", []),
                "tasks": plan.get("tasks", []),
                "status": plan.get("status", "PLAN_READY"),
            },
        ) and ok
        for agent in plan.get("agents", []):
            ok = GoalRepository._insert(
                "agent_execution_log",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "goal_id": goal_id,
                    "agent_name": agent.get("agent_name"),
                    "event_type": "SELECTED_FOR_PLAN",
                    "event_payload": {
                        "status": agent.get("status"),
                        "capabilities": agent.get("capabilities") or [],
                        "production_execution": False,
                    },
                },
            ) and ok
        return ok

    @staticmethod
    def list_goals(organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return GoalRepository._list("goal_registry", organization_id, limit)

    @staticmethod
    def list_execution_plans(organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return GoalRepository._list("goal_execution_plan", organization_id, limit)

    @staticmethod
    def list_agent_registry(organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return GoalRepository._list("agent_registry", organization_id, limit)

    @staticmethod
    def list_agent_logs(organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return GoalRepository._list("agent_execution_log", organization_id, limit)

    @staticmethod
    def save_collaboration(collaboration: dict[str, Any]) -> bool:
        org_id = resolve_organization_id(collaboration.get("organization_id"))
        goal_id = collaboration.get("id")
        session = collaboration.get("collaboration_session") or {}
        consensus = collaboration.get("consensus") or {}
        ok = True
        ok = GoalRepository._insert(
            "agent_collaboration_session",
            {
                "id": session.get("id") or str(uuid.uuid4()),
                "organization_id": org_id,
                "goal_id": goal_id,
                "goal_text": collaboration.get("goal"),
                "status": session.get("status") or collaboration.get("status"),
                "participating_agents": collaboration.get("participating_agents", []),
                "shared_context_summary": collaboration.get("context_summary") or {},
                "created_by": collaboration.get("created_by", "system"),
                "started_at": session.get("started_at"),
                "ended_at": session.get("ended_at"),
            },
        ) and ok
        for message in collaboration.get("messages", []):
            ok = GoalRepository._insert(
                "agent_messages",
                {
                    "id": message.get("id") or str(uuid.uuid4()),
                    "organization_id": org_id,
                    "goal_id": goal_id,
                    "sender": message.get("sender"),
                    "recipient": message.get("recipient"),
                    "request": message.get("request"),
                    "priority": message.get("priority", "Normal"),
                    "status": message.get("status", "Completed"),
                    "message_payload": message.get("payload") or {},
                    "response_payload": message.get("response") or {},
                    "sequence": message.get("sequence", 0),
                    "created_at": message.get("created_at"),
                    "completed_at": message.get("completed_at"),
                },
            ) and ok
        for contribution in collaboration.get("agent_contributions", []):
            decision_id = str(uuid.uuid4())
            ok = GoalRepository._insert(
                "agent_decisions",
                {
                    "id": decision_id,
                    "organization_id": org_id,
                    "goal_id": goal_id,
                    "agent_name": contribution.get("Agent"),
                    "recommendation": contribution.get("Recommendation"),
                    "confidence": contribution.get("Confidence", 0),
                    "risk": contribution.get("Risk"),
                    "evidence": contribution.get("Evidence") or [],
                    "blocking_issues": contribution.get("Blocking Issues") or [],
                    "decision_payload": contribution,
                },
            ) and ok
            ok = GoalRepository._insert(
                "agent_votes",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "goal_id": goal_id,
                    "agent_name": contribution.get("Agent"),
                    "vote": contribution.get("Vote") or contribution.get("Recommendation"),
                    "confidence": contribution.get("Confidence", 0),
                    "reason": "; ".join(contribution.get("Evidence") or []),
                },
            ) and ok
        ok = GoalRepository._insert(
            "agent_consensus",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "goal_id": goal_id,
                "consensus_state": consensus.get("Consensus State"),
                "enterprise_recommendation": consensus.get("Enterprise Recommendation"),
                "confidence": consensus.get("Confidence", 0),
                "reason": consensus.get("Reason"),
                "agreements": consensus.get("Agreements", 0),
                "disagreements": consensus.get("Disagreements", 0),
                "blocking_issues": consensus.get("Blocking Issues") or [],
                "consensus_payload": consensus,
            },
        ) and ok
        ok = GoalRepository._insert(
            "collaboration_history",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "goal_id": goal_id,
                "event_type": "CONSENSUS_REACHED",
                "event_payload": collaboration,
                "created_by": collaboration.get("created_by", "system"),
            },
        ) and ok
        for row in collaboration.get("agent_scorecard", []):
            ok = GoalRepository._insert(
                "agent_scorecard",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "goal_id": goal_id,
                    "agent_name": row.get("Agent"),
                    "recommendation_acceptance_rate": row.get("Recommendation Acceptance Rate", 0),
                    "prediction_accuracy": row.get("Prediction Accuracy", 0),
                    "average_confidence": row.get("Average Confidence", 0),
                    "average_execution_time": row.get("Average Execution Time"),
                    "contribution_frequency": row.get("Contribution Frequency", 0),
                    "historical_success_rate": row.get("Historical Success Rate", 0),
                },
            ) and ok
        return ok

    @staticmethod
    def list_collaboration_sessions(organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return GoalRepository._list("agent_collaboration_session", organization_id, limit)

    @staticmethod
    def list_agent_messages(organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return GoalRepository._list("agent_messages", organization_id, limit)

    @staticmethod
    def list_agent_decisions(organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return GoalRepository._list("agent_decisions", organization_id, limit)

    @staticmethod
    def list_agent_consensus(organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return GoalRepository._list("agent_consensus", organization_id, limit)

    @staticmethod
    def _insert(table_name: str, payload: dict[str, Any]) -> bool:
        try:
            supabase.table(table_name).insert(payload).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def _list(table_name: str, organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        try:
            return (
                supabase.table(table_name)
                .select("*")
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
        except Exception:
            return []
