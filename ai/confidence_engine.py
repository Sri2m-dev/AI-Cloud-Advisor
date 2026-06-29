from __future__ import annotations

from typing import Any


def score_confidence(context: dict[str, Any], policies: list[dict[str, Any]]) -> dict[str, Any]:
    impact = context.get("impact") or {}
    simulation = context.get("simulation") or {}
    enterprise = context.get("enterprise") or {}
    quality = ((enterprise.get("quality") or {}).get("scores") or {})
    data_completeness = _bounded(
        (
            _presence(impact)
            + _presence(simulation)
            + _num(quality.get("overall", 75))
        )
        / 3
    )
    relationship_confidence = _bounded(_num((impact.get("graph_summary") or {}).get("Reasoning Readiness %") or 70))
    historical_accuracy = 82.0
    policy_coverage = _bounded((len([row for row in policies if row.get("Matched") == "Yes"]) / max(len(policies), 1)) * 100 + 55)
    simulation_accuracy = 90.0 if simulation else 65.0
    approval_completeness = _bounded(100 - (len(_missing_approval_status(context)) * 12))
    score = round(
        (data_completeness * 0.25)
        + (relationship_confidence * 0.20)
        + (historical_accuracy * 0.15)
        + (policy_coverage * 0.15)
        + (simulation_accuracy * 0.15)
        + (approval_completeness * 0.10),
        1,
    )
    reasons = []
    if data_completeness < 80:
        reasons.append("Some enterprise context is incomplete.")
    if relationship_confidence < 80:
        reasons.append("Knowledge graph relationship readiness is below target.")
    if approval_completeness < 90:
        reasons.append("One or more approvals remain unresolved.")
    if not reasons:
        reasons.append("Enterprise context, simulation, policy, and approval coverage are sufficient.")
    return {
        "Confidence": min(score, 100.0),
        "Data Completeness": round(data_completeness, 1),
        "Relationship Confidence": round(relationship_confidence, 1),
        "Historical Accuracy": historical_accuracy,
        "Policy Coverage": round(policy_coverage, 1),
        "Simulation Accuracy": simulation_accuracy,
        "Approval Completeness": round(approval_completeness, 1),
        "Reasons": reasons,
        "Missing Data": _missing_data(context),
        "Assumptions": _assumptions(context),
        "Data Freshness": "Current session context",
    }


def _presence(value: Any) -> float:
    return 100.0 if value else 0.0


def _missing_data(context: dict[str, Any]) -> list[str]:
    missing = []
    if not context.get("asset"):
        missing.append("Mapped asset")
    if not context.get("impact"):
        missing.append("Impact analysis")
    if not context.get("simulation"):
        missing.append("Simulation result")
    return missing


def _missing_approval_status(context: dict[str, Any]) -> list[str]:
    simulation = context.get("simulation") or {}
    approvals = simulation.get("approval_analysis") or (context.get("impact") or {}).get("approval_intelligence") or []
    return [row.get("Approver Role") or "Approval" for row in approvals if str(row.get("Status") or "").lower() in {"required", "conditional"}]


def _assumptions(context: dict[str, Any]) -> list[str]:
    simulation = context.get("simulation") or {}
    assumptions = simulation.get("assumptions") or {}
    return [f"{key}: {value}" for key, value in assumptions.items()] or ["No explicit scenario assumptions were required."]


def _bounded(value: Any) -> float:
    return max(0.0, min(_num(value), 100.0))


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
