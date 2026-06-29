from __future__ import annotations

from typing import Any


class ValidationEngine:
    @staticmethod
    def validate_execution(blueprint: dict[str, Any], adapter_validation: dict[str, Any]) -> list[dict[str, Any]]:
        checks = blueprint.get("validation", [])
        rows = []
        for check in checks:
            rows.append(
                {
                    "Check": check.get("Check"),
                    "Metric": check.get("Metric"),
                    "Status": "Passed",
                    "Evidence": f"{check.get('Success Criteria')} Verified in mock mode.",
                    "Owner": check.get("Owner"),
                },
            )
        rows.append(
            {
                "Check": "Adapter Validation",
                "Metric": adapter_validation.get("adapter"),
                "Status": "Passed" if adapter_validation.get("status") in {"Validation Ready", "Completed"} else "Needs Review",
                "Evidence": adapter_validation.get("message"),
                "Owner": "Execution Engine",
            },
        )
        return rows
