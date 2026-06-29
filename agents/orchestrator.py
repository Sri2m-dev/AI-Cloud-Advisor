from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from agents.context_manager import AgentContextManager
from agents.consensus_engine import ConsensusEngine
from agents.execution_manager import ExecutionManager
from agents.message_bus import AgentMessageBus
from agents.planner_agent import PlannerAgent
from agents.session_manager import AgentSessionManager
from agents.scorecard import AgentScorecard
from agents.specialist_agents import SPECIALIST_AGENT_CLASSES
from repositories.goal_repository import GoalRepository


class AgentOrchestrator:
    @staticmethod
    def plan_goal(
        goal: str,
        organization_id: str | None = None,
        created_by: str = "system",
        persist: bool = True,
    ) -> dict[str, Any]:
        context = AgentContextManager.build_context(goal, organization_id)
        result = AgentOrchestrator._build_plan_from_context(goal, context, created_by)
        if persist:
            GoalRepository.save_goal_plan(result)
        return result

    @staticmethod
    def _build_plan_from_context(goal: str, context: dict[str, Any], created_by: str = "system") -> dict[str, Any]:
        planner = PlannerAgent()
        plan = planner.create_plan(goal, context)
        validation = planner.validate(plan, context)
        blueprint = ExecutionManager.create_blueprint(plan, context)
        goal_id = str(uuid.uuid4())
        result = {
            "id": goal_id,
            "organization_id": context["organization_id"],
            "goal": goal,
            "classification": plan["classification"],
            "target": plan["target"],
            "status": "PLAN_READY" if validation["valid"] else "NEEDS_REVIEW",
            "created_by": created_by,
            "created_at": datetime.utcnow().isoformat(),
            "agents": plan["agents"],
            "tasks": plan["tasks"],
            "execution_preview": plan["execution_preview"],
            "execution_blueprint": blueprint,
            "validation": validation,
            "context_summary": AgentOrchestrator._context_summary(context),
        }
        return result

    @staticmethod
    def collaborate_on_goal(
        goal: str,
        organization_id: str | None = None,
        created_by: str = "system",
        persist: bool = True,
    ) -> dict[str, Any]:
        session = AgentSessionManager.start_session(goal, organization_id, created_by)
        context = session["context"]
        plan = AgentOrchestrator._build_plan_from_context(goal, context, created_by)
        goal_id = plan["id"]
        session["goal_id"] = goal_id
        bus = AgentMessageBus(goal_id)
        participants = [row["agent_name"] for row in plan.get("agents", [])]
        AgentSessionManager.mark_participants(session, participants)

        contributions: list[dict[str, Any]] = []
        for agent_name in participants:
            request = AgentOrchestrator._request_for(agent_name, plan)
            message = bus.route("Agent Orchestrator", agent_name, request, priority="High")
            contribution = AgentOrchestrator._agent_contribution(agent_name, goal, context, plan)
            bus.complete(message, contribution)
            contributions.append(contribution)

        consensus = ConsensusEngine.reach_consensus(contributions)
        consensus_message = bus.route("Reasoning Agent", "Consensus Engine", "Resolve agent votes into one enterprise recommendation", "High")
        bus.complete(consensus_message, consensus)

        unified_plan = AgentOrchestrator._unified_enterprise_plan(plan, contributions, consensus)
        scorecard = AgentScorecard.build(contributions, bus.messages)
        AgentSessionManager.complete(session, consensus["Consensus State"])
        result = {
            **plan,
            "status": consensus["Consensus State"],
            "collaboration_session": {
                key: value
                for key, value in session.items()
                if key != "context"
            },
            "participating_agents": participants,
            "messages": bus.messages,
            "agent_contributions": contributions,
            "consensus": consensus,
            "unified_enterprise_plan": unified_plan,
            "agent_scorecard": scorecard,
            "executive_summary": AgentOrchestrator._collaboration_summary(plan, consensus, contributions),
        }
        if persist:
            GoalRepository.save_goal_plan(result)
            GoalRepository.save_collaboration(result)
        return result

    @staticmethod
    def _context_summary(context: dict[str, Any]) -> dict[str, Any]:
        forecast_summary = (context.get("prediction") or {}).get("summary") or {}
        performance = (context.get("prediction_performance") or {}).get("prediction_health_score") or {}
        return {
            "asset_count": (context.get("knowledge_graph") or {}).get("asset_count", 0),
            "target_asset": (context.get("impact") or {}).get("target_asset"),
            "top_forecast_metric": forecast_summary.get("Top Forecast Metric"),
            "average_prediction_confidence": forecast_summary.get("Average Confidence"),
            "prediction_health_score": performance.get("Score"),
            "production_execution_allowed": False,
        }

    @staticmethod
    def _request_for(agent_name: str, plan: dict[str, Any]) -> str:
        requests = {
            "Planner Agent": "Confirm goal decomposition and sequencing.",
            "Cost Agent": "Analyze spend, ROI, savings, and financial options.",
            "Operations Agent": "Assess readiness, dependencies, maintenance windows, DR, and rollback.",
            "Security Agent": "Review security posture, compliance, identity, and audit implications.",
            "Governance Agent": "Evaluate policies, approval chain, segregation of duties, and CAB requirements.",
            "Simulation Agent": "Evaluate planning scenario, blast radius, and risk.",
            "Reasoning Agent": "Synthesize evidence, alternatives, and executive rationale.",
        }
        return requests.get(agent_name, f"Contribute to goal plan for {plan.get('target', 'enterprise target')}.")

    @staticmethod
    def _agent_contribution(agent_name: str, goal: str, context: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        if agent_name == "Planner Agent":
            return {
                "Agent": "Planner Agent",
                "Recommendation": "Proceed",
                "Confidence": plan.get("execution_preview", {}).get("Confidence", 90.0),
                "Risk": plan.get("execution_preview", {}).get("Risk", "Medium"),
                "Evidence": [f"{len(plan.get('tasks', []))} tasks created", f"Classification: {plan.get('classification')}"],
                "Blocking Issues": [],
                "Plan Updates": ["Use orchestrator-owned ordering and shared enterprise context."],
                "Vote": "Proceed",
            }
        agent_class = SPECIALIST_AGENT_CLASSES.get(agent_name)
        if not agent_class:
            return {
                "Agent": agent_name,
                "Recommendation": "Proceed",
                "Confidence": 85.0,
                "Risk": "Medium",
                "Evidence": ["No specialist implementation registered."],
                "Blocking Issues": [],
                "Plan Updates": [],
                "Vote": "Proceed",
            }
        result = agent_class().contribute(goal, context, plan)
        return {"Agent": result.agent_name, **result.output}

    @staticmethod
    def _unified_enterprise_plan(
        plan: dict[str, Any],
        contributions: list[dict[str, Any]],
        consensus: dict[str, Any],
    ) -> dict[str, Any]:
        plan_updates = [
            update
            for row in contributions
            for update in row.get("Plan Updates", [])
            if update
        ]
        blocking = consensus.get("Blocking Issues") or []
        blueprint = dict(plan.get("execution_blueprint") or {})
        blueprint["consensus"] = consensus
        blueprint["agent_updates"] = plan_updates
        blueprint["blocking_issues"] = blocking
        blueprint["execution_allowed"] = False
        return {
            "Goal": plan.get("goal"),
            "Classification": plan.get("classification"),
            "Target": plan.get("target"),
            "Enterprise Recommendation": consensus.get("Enterprise Recommendation"),
            "Expected Savings": (plan.get("execution_preview") or {}).get("Expected Savings", 0),
            "Business Risk": (plan.get("execution_preview") or {}).get("Risk", "Medium"),
            "Operational Risk": next((row.get("Risk") for row in contributions if row.get("Agent") == "Operations Agent"), "Medium"),
            "Security": next((row.get("Recommendation") for row in contributions if row.get("Agent") == "Security Agent"), "Approved"),
            "Governance": next((row.get("Recommendation") for row in contributions if row.get("Agent") == "Governance Agent"), "Approval required"),
            "Confidence": consensus.get("Confidence", 0),
            "Execution Blueprint": blueprint,
        }

    @staticmethod
    def _collaboration_summary(
        plan: dict[str, Any],
        consensus: dict[str, Any],
        contributions: list[dict[str, Any]],
    ) -> str:
        return (
            f"{len(contributions)} agents reviewed '{plan.get('goal')}'. "
            f"{consensus.get('Consensus State')} with recommendation: "
            f"{consensus.get('Enterprise Recommendation')} Confidence is {consensus.get('Confidence')}%."
        )
