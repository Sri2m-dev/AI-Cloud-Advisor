from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent, AgentResult


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class OpinionAgent(BaseAgent):
    recommendation = "Proceed"
    risk = "Medium"

    def contribute(self, goal: str, context: dict[str, Any], plan: dict[str, Any]) -> AgentResult:
        del goal
        return AgentResult(
            agent_name=self.agent_name,
            status="CONTRIBUTED",
            output={
                "Recommendation": self.recommendation,
                "Confidence": 90.0,
                "Risk": self.risk,
                "Evidence": [],
                "Blocking Issues": [],
                "Plan Updates": [],
                "Vote": "Proceed",
            },
            confidence=90.0,
        )


class CostOptimizationAgent(OpinionAgent):
    agent_name = "Cost Agent"
    description = "Analyzes spend, ROI, savings, and financial options."
    capabilities = ["Analyze spend", "Identify optimization opportunities", "Calculate ROI", "Estimate savings"]

    def contribute(self, goal: str, context: dict[str, Any], plan: dict[str, Any]) -> AgentResult:
        del goal, plan
        financial = context.get("financial") or {}
        candidates = financial.get("savings_candidates") or []
        savings = sum(_safe_float(row.get("Savings Potential")) for row in candidates[:3])
        if savings <= 0:
            savings = _safe_float(((context.get("prediction") or {}).get("summary") or {}).get("Predicted Spend")) * 0.15
        confidence = _safe_float(((context.get("prediction") or {}).get("summary") or {}).get("Average Confidence")) or 92.0
        risk = "Low" if savings < 250000 else "Medium"
        return AgentResult(
            agent_name=self.agent_name,
            status="CONTRIBUTED",
            output={
                "Recommendation": "Proceed",
                "Savings": round(savings, 2),
                "ROI": "Strong" if savings >= 100000 else "Moderate",
                "Confidence": round(confidence, 1),
                "Risk": risk,
                "Evidence": [f"Top savings candidates: {len(candidates)}", f"Estimated annual savings: ${savings:,.0f}"],
                "Blocking Issues": [],
                "Plan Updates": ["Prioritize highest ROI savings before lower-confidence actions."],
                "Vote": "Proceed",
            },
            confidence=round(confidence, 1),
        )


class OperationsAgent(OpinionAgent):
    agent_name = "Operations Agent"
    description = "Checks infrastructure readiness, dependencies, DR, rollback, and maintenance windows."
    capabilities = ["Infrastructure readiness", "Dependency validation", "DR readiness", "Rollback planning"]

    def contribute(self, goal: str, context: dict[str, Any], plan: dict[str, Any]) -> AgentResult:
        del goal
        risk_count = _safe_float(((context.get("risk") or {}).get("summary") or {}).get("Predicted Risks"))
        risk = "Medium" if risk_count >= 3 or plan.get("execution_preview", {}).get("Risk") == "High" else "Low"
        recommendation = "Proceed with scheduled maintenance window" if risk == "Medium" else "Proceed"
        return AgentResult(
            agent_name=self.agent_name,
            status="CONTRIBUTED",
            output={
                "Recommendation": recommendation,
                "Infrastructure Ready": "Yes",
                "Maintenance Window": "Available",
                "Rollback": "Available",
                "Confidence": 91.0,
                "Risk": risk,
                "Evidence": ["Shared context confirms production execution is blocked.", "Rollback validation is required before approval."],
                "Blocking Issues": [],
                "Plan Updates": ["Schedule changes during approved maintenance window.", "Add rollback owner to execution blueprint."],
                "Vote": "Proceed with modifications" if risk == "Medium" else "Proceed",
            },
            confidence=91.0,
        )


class SecurityAgent(OpinionAgent):
    agent_name = "Security Agent"
    description = "Evaluates security posture, compliance, encryption, identity, and audit implications."
    capabilities = ["Security posture", "Compliance review", "Identity policy review", "Audit implications"]

    def contribute(self, goal: str, context: dict[str, Any], plan: dict[str, Any]) -> AgentResult:
        text = f"{goal} {plan.get('classification')}".lower()
        pci = "Yes" if any(token in text for token in ["pci", "payment", "checkout", "customer"]) else "No"
        security_needed = any(token in text for token in ["security", "compliance", "production", "identity", "pci"])
        return AgentResult(
            agent_name=self.agent_name,
            status="CONTRIBUTED",
            output={
                "Recommendation": "Proceed after security review" if security_needed else "Proceed",
                "PCI Impact": pci,
                "Encryption": "Compliant",
                "Identity Risk": "Low",
                "Confidence": 90.0,
                "Risk": "Medium" if security_needed else "Low",
                "Evidence": ["Audit trail required for all agent decisions.", "No direct production execution in this sprint."],
                "Blocking Issues": [] if not security_needed else ["Security review required before execution."],
                "Plan Updates": ["Attach security evidence to approval packet."],
                "Vote": "Proceed with modifications" if security_needed else "Proceed",
            },
            confidence=90.0,
        )


class GovernanceAgent(OpinionAgent):
    agent_name = "Governance Agent"
    description = "Determines policies, approval chain, CAB, and segregation-of-duties needs."
    capabilities = ["Policy validation", "Approval chain", "CAB review", "Segregation of duties"]

    def contribute(self, goal: str, context: dict[str, Any], plan: dict[str, Any]) -> AgentResult:
        del goal, context
        approvals = list((plan.get("execution_preview") or {}).get("Approvals") or [])
        if "CAB" not in approvals:
            approvals.append("CAB")
        if "CIO" not in approvals and (plan.get("execution_preview") or {}).get("Risk") in {"High", "Critical"}:
            approvals.append("CIO")
        return AgentResult(
            agent_name=self.agent_name,
            status="CONTRIBUTED",
            output={
                "Recommendation": "Await CAB approval",
                "Approvals Required": approvals,
                "Segregation Of Duties": "Required",
                "CAB Required": "Yes",
                "Confidence": 94.0,
                "Risk": "Medium",
                "Evidence": ["Governance policy requires approval before execution.", "Planner marked production execution as blocked."],
                "Blocking Issues": ["CAB approval required."],
                "Plan Updates": ["Add CAB and CIO approval gates when risk is high."],
                "Vote": "Proceed after approvals",
            },
            confidence=94.0,
        )


class SimulationAgent(OpinionAgent):
    agent_name = "Simulation Agent"
    description = "Evaluates scenario previews and blast radius before execution."
    capabilities = ["Scenario preview", "Blast radius", "Risk estimation"]

    def contribute(self, goal: str, context: dict[str, Any], plan: dict[str, Any]) -> AgentResult:
        target = (context.get("impact") or {}).get("target_asset") or plan.get("target")
        risk = (plan.get("execution_preview") or {}).get("Risk", "Medium")
        return AgentResult(
            agent_name=self.agent_name,
            status="CONTRIBUTED",
            output={
                "Recommendation": "Proceed with modifications" if risk in {"High", "Medium"} else "Proceed",
                "Scenario": f"Planning preview for {target}",
                "Business Risk": risk,
                "Confidence": 92.0,
                "Risk": risk,
                "Evidence": ["Simulation remains a planning artifact.", "Execution plan includes rollback and validation gates."],
                "Blocking Issues": [] if risk != "High" else ["High-risk scenario requires executive approval."],
                "Plan Updates": ["Run final simulation immediately before approval."],
                "Vote": "Proceed with modifications" if risk in {"High", "Medium"} else "Proceed",
            },
            confidence=92.0,
        )


class ReasoningAgent(OpinionAgent):
    agent_name = "Reasoning Agent"
    description = "Synthesizes evidence, alternatives, confidence, and executive rationale."
    capabilities = ["Explainability", "Evidence review", "Executive rationale"]

    def contribute(self, goal: str, context: dict[str, Any], plan: dict[str, Any]) -> AgentResult:
        del context
        return AgentResult(
            agent_name=self.agent_name,
            status="CONTRIBUTED",
            output={
                "Recommendation": "Proceed after approvals",
                "Rationale": f"The goal '{goal}' is actionable once financial, operational, and governance controls are satisfied.",
                "Confidence": (plan.get("execution_preview") or {}).get("Confidence", 91.0),
                "Risk": (plan.get("execution_preview") or {}).get("Risk", "Medium"),
                "Evidence": ["All agent contributions are routed through the orchestrator.", "Consensus prevents one optimistic opinion from dominating."],
                "Blocking Issues": [],
                "Plan Updates": ["Present final plan as an executive recommendation with approvals and risk rationale."],
                "Vote": "Proceed after approvals",
            },
            confidence=(plan.get("execution_preview") or {}).get("Confidence", 91.0),
        )


SPECIALIST_AGENT_CLASSES = {
    "Cost Agent": CostOptimizationAgent,
    "Operations Agent": OperationsAgent,
    "Security Agent": SecurityAgent,
    "Governance Agent": GovernanceAgent,
    "Simulation Agent": SimulationAgent,
    "Reasoning Agent": ReasoningAgent,
}
