from __future__ import annotations

from typing import Any

from execution.base_adapter import AdapterResult, BaseExecutionAdapter


class MockExecutionAdapter(BaseExecutionAdapter):
    adapter_name = "mock"
    enabled = True

    def execute_stage(self, stage: dict[str, Any], tasks: list[dict[str, Any]], context: dict[str, Any]) -> AdapterResult:
        mode = context.get("execution_mode", "Mock")
        return AdapterResult(
            adapter=self.adapter_name,
            status="Completed",
            message=f"{stage.get('Name', 'Stage')} completed in {mode} mode without external API calls.",
            details={
                "stage": stage.get("Name"),
                "task_count": len(tasks),
                "external_calls": 0,
                "mode": mode,
            },
        )

    def validate(self, context: dict[str, Any]) -> AdapterResult:
        return AdapterResult(
            adapter=self.adapter_name,
            status="Validation Ready",
            message="Mock validation completed using generated checklist.",
            details={"checks": len(context.get("validation", [])), "mode": context.get("execution_mode", "Mock")},
        )

    def rollback(self, context: dict[str, Any]) -> AdapterResult:
        return AdapterResult(
            adapter=self.adapter_name,
            status="Rollback Completed",
            message="Mock rollback completed without external API calls.",
            details={"rollback_steps": len(context.get("rollback", [])), "external_calls": 0},
        )
