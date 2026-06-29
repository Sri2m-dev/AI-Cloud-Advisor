from __future__ import annotations

import uuid
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class SafeExecutionRepository:
    @staticmethod
    def save_execution(execution: dict[str, Any]) -> bool:
        org_id = resolve_organization_id(execution.get("organization_id"))
        job_id = execution.get("id") or str(uuid.uuid4())
        ok = True
        ok = SafeExecutionRepository._insert(
            "execution_job",
            {
                "id": job_id,
                "organization_id": org_id,
                "workflow_id": execution.get("workflow_id"),
                "authorization_status": execution.get("authorization", {}).get("Status"),
                "execution_mode": execution.get("execution_mode"),
                "adapter_name": execution.get("adapter"),
                "status": execution.get("status"),
                "progress": execution.get("progress", 0),
                "execution_report": execution,
            },
        ) and ok
        ok = SafeExecutionRepository._insert(
            "execution_queue",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "job_id": job_id,
                "workflow_id": execution.get("workflow_id"),
                "queue_status": "Processed" if execution.get("status") in {"Completed", "Rolled Back", "Blocked"} else "Queued",
                "priority": execution.get("priority", "Normal"),
            },
        ) and ok
        for stage in execution.get("stages", []):
            ok = SafeExecutionRepository._insert(
                "execution_stage",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "job_id": job_id,
                    "workflow_id": execution.get("workflow_id"),
                    "stage_name": stage.get("Stage"),
                    "status": stage.get("Status"),
                    "adapter_name": stage.get("Adapter"),
                    "stage_payload": stage,
                },
            ) and ok
        for event in execution.get("events", []):
            ok = SafeExecutionRepository._insert(
                "execution_log",
                {
                    "id": event.get("id") or str(uuid.uuid4()),
                    "organization_id": org_id,
                    "job_id": job_id,
                    "workflow_id": execution.get("workflow_id"),
                    "event_type": event.get("event_type"),
                    "event_payload": event.get("payload", {}),
                    "sequence": event.get("sequence", 0),
                    "created_at": event.get("created_at"),
                },
            ) and ok
        for validation in execution.get("validation_results", []):
            ok = SafeExecutionRepository._insert(
                "validation_result",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "job_id": job_id,
                    "workflow_id": execution.get("workflow_id"),
                    "check_name": validation.get("Check"),
                    "status": validation.get("Status"),
                    "metric": validation.get("Metric"),
                    "result_payload": validation,
                },
            ) and ok
        if execution.get("rollback_execution"):
            rollback = execution["rollback_execution"]
            ok = SafeExecutionRepository._insert(
                "rollback_execution",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "job_id": job_id,
                    "workflow_id": execution.get("workflow_id"),
                    "trigger_name": rollback.get("Trigger"),
                    "status": rollback.get("Status"),
                    "rollback_payload": rollback,
                },
            ) and ok
        ok = SafeExecutionRepository._insert(
            "execution_result",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "job_id": job_id,
                "workflow_id": execution.get("workflow_id"),
                "status": execution.get("status"),
                "result_payload": execution.get("summary", {}),
            },
        ) and ok
        return ok

    @staticmethod
    def list_jobs(organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return SafeExecutionRepository._list("execution_job", organization_id, limit)

    @staticmethod
    def _insert(table_name: str, payload: dict[str, Any]) -> bool:
        try:
            supabase.table(table_name).insert(payload).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def _list(table_name: str, organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        try:
            return (
                supabase.table(table_name)
                .select("*")
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
        except Exception:
            return []
