from __future__ import annotations

from typing import Any


DEFAULT_POLICIES = [
    {
        "rule_name": "CAB approval for critical revenue systems",
        "category": "Governance",
        "condition": "risk_score >= 70 and revenue_exposure_per_day >= 1000000",
        "action": "Require CAB approval before execution.",
        "severity": "Critical",
    },
    {
        "rule_name": "Reject uneconomic migrations",
        "category": "Financial",
        "condition": "expected_savings < migration_cost",
        "action": "Reject or redesign the recommendation because migration cost exceeds expected savings.",
        "severity": "High",
    },
    {
        "rule_name": "Block automation for compliance exposure",
        "category": "Security",
        "condition": "compliance_risk >= 70",
        "action": "Block autonomous execution and route to security and compliance review.",
        "severity": "High",
    },
    {
        "rule_name": "Phase production migrations",
        "category": "Change",
        "condition": "production_applications >= 5",
        "action": "Use phased rollout: development, QA, then production.",
        "severity": "Medium",
    },
    {
        "rule_name": "Finance approval for material budget impact",
        "category": "Finance",
        "condition": "abs_budget_impact >= 100000",
        "action": "Require Finance approval because the budget impact is material.",
        "severity": "Medium",
    },
]


def evaluate_policies(
    context: dict[str, Any],
    configured_policies: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    facts = _facts(context)
    policies = configured_policies or DEFAULT_POLICIES
    applied = []
    for policy in policies:
        if not policy.get("enabled", True):
            continue
        condition = str(policy.get("condition") or "")
        matched = _matches(condition, facts)
        applied.append(
            {
                "Rule": policy.get("rule_name") or policy.get("Rule") or "Policy",
                "Category": policy.get("category") or "Governance",
                "Condition": condition,
                "Action": policy.get("action") or "Review required.",
                "Severity": policy.get("severity") or "Medium",
                "Matched": "Yes" if matched else "No",
            }
        )
    return applied


def _facts(context: dict[str, Any]) -> dict[str, float]:
    impact = context.get("impact") or {}
    simulation = context.get("simulation") or {}
    financial = simulation.get("financial_analysis") or impact.get("financial_impact") or {}
    risk = simulation.get("risk_analysis") or {}
    risk_summary = risk.get("summary") or {}
    impact_risk = impact.get("risk_analysis") or {}
    business = simulation.get("business_impact") or impact.get("business_impact") or {}
    return {
        "risk_score": _num(risk.get("score") or risk_summary.get("Risk Score") or impact.get("risk_score")),
        "revenue_exposure_per_day": _num(
            financial.get("Revenue Exposure Per Day")
            or financial.get("Estimated Revenue Risk Per Day")
        ),
        "expected_savings": _num(
            financial.get("Expected Annual Savings")
            or financial.get("Savings")
        ),
        "migration_cost": _num(financial.get("Migration Cost")),
        "compliance_risk": _num(impact_risk.get("Compliance Risk")),
        "production_applications": _num(business.get("Applications Impacted")),
        "abs_budget_impact": abs(_num(financial.get("Budget Impact"))),
    }


def _matches(condition: str, facts: dict[str, float]) -> bool:
    condition_key = condition.lower().replace(" ", "")
    checks = {
        "risk_score>=70andrevenue_exposure_per_day>=1000000": facts["risk_score"] >= 70
        and facts["revenue_exposure_per_day"] >= 1_000_000,
        "expected_savings<migration_cost": facts["expected_savings"] < facts["migration_cost"],
        "compliance_risk>=70": facts["compliance_risk"] >= 70,
        "production_applications>=5": facts["production_applications"] >= 5,
        "abs_budget_impact>=100000": facts["abs_budget_impact"] >= 100_000,
    }
    return checks.get(condition_key, False)


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
