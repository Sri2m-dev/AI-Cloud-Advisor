from __future__ import annotations

from typing import Any

from services.safe_execution_service import SafeExecutionService


class ExecutionManager:
    @staticmethod
    def queue(goal: str, organization_id: str | None = None, mode: str = "Mock") -> dict[str, Any]:
        return SafeExecutionService.request_execution(goal, organization_id, mode, persist=True)

    @staticmethod
    def pause(job: dict[str, Any]) -> dict[str, Any]:
        return {**job, "status": "Paused"}

    @staticmethod
    def resume(job: dict[str, Any]) -> dict[str, Any]:
        return {**job, "status": "Queued"}

    @staticmethod
    def retry(job: dict[str, Any]) -> dict[str, Any]:
        return {**job, "status": "Queued", "retry": True}

    @staticmethod
    def cancel(job: dict[str, Any]) -> dict[str, Any]:
        return {**job, "status": "Cancelled"}

    @staticmethod
    def rollback(job: dict[str, Any]) -> dict[str, Any]:
        return {**job, "status": "Rolled Back", "rollback_requested": True}
