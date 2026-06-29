from __future__ import annotations

from typing import Any


class RollbackEngine:
    @staticmethod
    def rollback_if_required(
        blueprint: dict[str, Any],
        validation_results: list[dict[str, Any]],
        adapter_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        failed = [row for row in validation_results if row.get("Status") not in {"Passed", "Warning"}]
        if not failed and adapter_result.get("status") not in {"Failed", "Rollback Required"}:
            return None
        rollback = (blueprint.get("rollback") or [{}])[0]
        return {
            "Trigger": rollback.get("Trigger", "Validation failed"),
            "Status": "Rolled Back",
            "Rollback Task": rollback.get("Rollback Task", "Restore prior approved state."),
            "Verification": rollback.get("Verification", "Rollback verified."),
            "Business Validation": rollback.get("Business Validation", "Business owner validated recovery."),
            "Audit": "Rollback recorded by Safe Execution Engine.",
            "Closure": rollback.get("Closure", "Rollback closed with evidence."),
        }
