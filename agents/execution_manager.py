from __future__ import annotations

from datetime import datetime
from typing import Any


class ExecutionManager:
    @staticmethod
    def create_blueprint(plan: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        preview = plan.get("execution_preview") or {}
        tasks = plan.get("tasks") or []
        return {
            "status": "PLAN_READY",
            "execution_allowed": False,
            "created_at": datetime.utcnow().isoformat(),
            "execution_plan": tasks,
            "approvals": preview.get("Approvals", []),
            "rollback": ExecutionManager._rollback(plan, context),
            "validation": ExecutionManager._validation(plan, context),
            "estimated_savings": preview.get("Expected Savings", 0),
            "risk": preview.get("Risk", "Medium"),
            "confidence": preview.get("Confidence", 0),
            "note": "A.9.1 produces an executable blueprint only. No production actions are executed.",
        }

    @staticmethod
    def _rollback(plan: dict[str, Any], context: dict[str, Any]) -> list[str]:
        target = plan.get("target") or (context.get("impact") or {}).get("target_asset") or "target asset"
        return [
            f"Snapshot current state for {target}.",
            "Preserve existing workflow and approval state.",
            "Define rollback owner before execution approval.",
            "Require validation evidence before closing the goal.",
        ]

    @staticmethod
    def _validation(plan: dict[str, Any], context: dict[str, Any]) -> list[str]:
        del context
        return [
            f"Confirm goal classification remains {plan.get('classification', 'Architecture')}.",
            "Validate forecast accuracy and prediction health before approval.",
            "Validate simulation risk and affected business services.",
            "Confirm all required approvals are complete.",
            "Confirm no production execution occurred during planning.",
        ]
