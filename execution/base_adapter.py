from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AdapterResult:
    adapter: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class BaseExecutionAdapter:
    adapter_name = "base"
    enabled = False

    def execute_stage(self, stage: dict[str, Any], tasks: list[dict[str, Any]], context: dict[str, Any]) -> AdapterResult:
        del stage, tasks, context
        return AdapterResult(
            adapter=self.adapter_name,
            status="Execution Disabled",
            message="This adapter is registered but disabled.",
        )

    def validate(self, context: dict[str, Any]) -> AdapterResult:
        del context
        return AdapterResult(
            adapter=self.adapter_name,
            status="Validation Skipped",
            message="Adapter validation is disabled.",
        )

    def rollback(self, context: dict[str, Any]) -> AdapterResult:
        del context
        return AdapterResult(
            adapter=self.adapter_name,
            status="Rollback Disabled",
            message="Adapter rollback is disabled.",
        )
