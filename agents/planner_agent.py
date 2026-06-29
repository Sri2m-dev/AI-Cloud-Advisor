from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent
from agents.registry import AgentRegistry


class PlannerAgent(BaseAgent):
    agent_name = "Planner Agent"
    description = "Converts business goals into delegated enterprise tasks."
    version = "1.0"
    capabilities = ["Goal decomposition", "Task sequencing", "Agent selection"]

    def understand_goal(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        classification = classify_goal(goal)
        target = (context.get("impact") or {}).get("target_asset", "Enterprise Portfolio")
        return {
            "goal": goal,
            "classification": classification,
            "target": target,
            "intent": goal_to_intent(goal),
        }

    def create_plan(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        understanding = self.understand_goal(goal, context)
        agents = AgentRegistry.select_agents(understanding["classification"], goal, context.get("organization_id"))
        tasks = build_tasks(goal, understanding, agents)
        estimates = estimate_goal(goal, understanding, context, agents)
        return {
            "goal": goal,
            "classification": understanding["classification"],
            "target": understanding["target"],
            "intent": understanding["intent"],
            "agents": agents,
            "tasks": tasks,
            "execution_preview": estimates,
            "confidence": estimates["Confidence"],
        }


def classify_goal(goal: str) -> str:
    text = str(goal or "").lower()
    if any(token in text for token in ["spend", "cost", "savings", "budget", "license", "saas"]):
        return "Financial"
    if any(token in text for token in ["dr", "availability", "uptime", "capacity", "kubernetes", "utilization"]):
        return "Operational"
    if any(token in text for token in ["security", "compliance", "pci", "risk"]):
        return "Security"
    if any(token in text for token in ["governance", "owner", "mapping", "quality score"]):
        return "Governance"
    if any(token in text for token in ["migration", "oracle", "modernize", "architecture"]):
        return "Migration"
    if any(token in text for token in ["optimize", "improve", "reduce", "remove"]):
        return "Optimization"
    return "Architecture"


def goal_to_intent(goal: str) -> str:
    text = str(goal or "").lower()
    if "reduce" in text:
        return "Reduce"
    if "improve" in text or "increase" in text:
        return "Improve"
    if "remove" in text or "decommission" in text:
        return "Remove"
    if "prepare" in text or "migration" in text:
        return "Prepare"
    return "Plan"


def build_tasks(goal: str, understanding: dict[str, Any], agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    classification = understanding["classification"]
    target = understanding["target"]
    templates = [
        ("Understand goal", "Planner Agent", f"Classify goal as {classification} and confirm target {target}."),
        ("Build context", "Planner Agent", "Collect graph, impact, prediction, workflow, and policy context."),
    ]
    if any(row["agent_name"] == "Cost Agent" for row in agents):
        templates += [
            ("Analyze cost", "Cost Agent", "Identify spend baseline, waste, budget exposure, and savings candidates."),
            ("Run predictions", "Cost Agent", "Estimate future spend and validate forecast confidence."),
        ]
    if any(row["agent_name"] == "Operations Agent" for row in agents):
        templates.append(("Assess operations", "Operations Agent", "Review availability, capacity, rollback, and validation gates."))
    if any(row["agent_name"] == "Security Agent" for row in agents):
        templates.append(("Review controls", "Security Agent", "Check compliance, risk, and security policy constraints."))
    templates += [
        ("Simulate outcome", "Simulation Agent", "Preview savings, risk, blast radius, and production impact."),
        ("Explain decision", "Reasoning Agent", "Build evidence, alternatives, confidence, and executive rationale."),
        ("Check policies", "Governance Agent", "Map required approvals and policy gates."),
        ("Create workflow blueprint", "Planner Agent", "Prepare reviewable execution plan without running production actions."),
    ]
    return [
        {
            "Task": index,
            "Name": name,
            "Agent": agent,
            "Description": description,
            "Status": "Planned",
        }
        for index, (name, agent, description) in enumerate(templates, start=1)
    ]


def estimate_goal(
    goal: str,
    understanding: dict[str, Any],
    context: dict[str, Any],
    agents: list[dict[str, Any]],
) -> dict[str, Any]:
    financial = context.get("financial") or {}
    savings_candidates = financial.get("savings_candidates") or []
    expected_savings = sum(float(row.get("Savings Potential") or 0) for row in savings_candidates[:3])
    if expected_savings <= 0 and any(token in str(goal).lower() for token in ["15", "20", "savings", "spend", "cost"]):
        predicted = ((context.get("prediction") or {}).get("summary") or {}).get("Predicted Spend", 0)
        expected_savings = float(predicted or 2_800_000) * 0.15
    risk_predictions = ((context.get("risk") or {}).get("summary") or {}).get("Predicted Risks", 0)
    confidence = ((context.get("prediction") or {}).get("summary") or {}).get("Average Confidence", 91)
    health = ((context.get("prediction_performance") or {}).get("prediction_health_score") or {}).get("Score", 88)
    confidence = round((float(confidence or 0) * 0.55) + (float(health or 0) * 0.45), 1)
    approvals = ["Business Owner", "Technology Owner", "Finance", "CAB"]
    if understanding["classification"] in {"Security", "Governance"}:
        approvals.append("Security")
    if expected_savings >= 250_000:
        approvals.append("CFO")
    risk = "High" if risk_predictions and risk_predictions >= 4 else "Medium" if expected_savings >= 250_000 else "Low"
    duration = 18 + max(len(agents) - 4, 0) * 4
    return {
        "Estimated Duration": f"{duration} Minutes",
        "Expected Savings": round(expected_savings, 2),
        "Risk": risk,
        "Approvals": approvals,
        "Confidence": confidence,
        "Production Execution": "Blocked in A.9.1",
    }
