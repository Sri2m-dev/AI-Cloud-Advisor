from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from execution.adapter_registry import adapter_registry_rows, get_adapter
from repositories.safe_execution_repository import SafeExecutionRepository
from services.execution_event_bus import ExecutionEventBus
from services.governance_authorization_service import GovernanceAuthorizationService
from services.learning_engine import LearningEngine
from services.rollback_engine import RollbackEngine
from services.validation_engine import ValidationEngine
from services.workflow_builder_service import WorkflowBuilderService


EXECUTION_STATES = [
    "Draft",
    "Planned",
    "Governance Review",
    "Authorized",
    "Queued",
    "Executing",
    "Validating",
    "Completed",
    "Rolled Back",
    "Failed",
]

SAFETY_MODES = {
    "Simulation": "Nothing happens. Execution plan is only replayed as events.",
    "Mock": "Runs every engine step without real external API calls.",
    "Sandbox": "Reserved for approved test subscriptions. Disabled by default.",
    "Production": "Requires governance authorization, CAB, digital signature, time window, and policy validation.",
}


class SafeExecutionService:
    @staticmethod
    def request_execution(
        goal: str,
        organization_id: str | None = None,
        execution_mode: str = "Mock",
        adapter_name: str = "mock",
        created_by: str = "system",
        persist: bool = True,
        force_authorized: bool = False,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        blueprint = WorkflowBuilderService.build_from_goal(goal, org_id, created_by, persist=False)
        authorization = GovernanceAuthorizationService.evaluate_blueprint(blueprint, created_by=created_by, persist=False)
        return SafeExecutionService.execute_authorized_blueprint(
            blueprint,
            authorization,
            execution_mode=execution_mode,
            adapter_name=adapter_name,
            created_by=created_by,
            persist=persist,
            force_authorized=force_authorized,
        )

    @staticmethod
    def execute_authorized_blueprint(
        blueprint: dict[str, Any],
        authorization: dict[str, Any],
        execution_mode: str = "Mock",
        adapter_name: str = "mock",
        created_by: str = "system",
        persist: bool = True,
        force_authorized: bool = False,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(blueprint.get("organization_id"))
        job_id = str(uuid.uuid4())
        bus = ExecutionEventBus()
        workflow_id = blueprint.get("id") or job_id
        bus.emit("Execution Requested", workflow_id, {"mode": execution_mode, "adapter": adapter_name})
        gate = SafeExecutionService._authorization_gate(authorization, execution_mode, force_authorized)
        if not gate["allowed"]:
            bus.emit("Execution Blocked", workflow_id, gate)
            result = SafeExecutionService._blocked_result(job_id, org_id, workflow_id, blueprint, authorization, gate, execution_mode, adapter_name, bus.events)
            if persist:
                SafeExecutionRepository.save_execution(result)
                result["learning_outcome"] = LearningEngine.learn_from_execution(result, persist=True)
            else:
                result["learning_outcome"] = LearningEngine.learn_from_execution(result, persist=False)
            return result

        adapter = get_adapter(adapter_name)
        if not adapter.enabled or execution_mode in {"Sandbox", "Production"}:
            bus.emit("Adapter Disabled", workflow_id, {"adapter": adapter.adapter_name, "mode": execution_mode})
            result = SafeExecutionService._blocked_result(
                job_id,
                org_id,
                workflow_id,
                blueprint,
                authorization,
                {"allowed": False, "reason": f"{adapter.adapter_name} adapter execution disabled for {execution_mode} mode."},
                execution_mode,
                adapter_name,
                bus.events,
            )
            if persist:
                SafeExecutionRepository.save_execution(result)
                result["learning_outcome"] = LearningEngine.learn_from_execution(result, persist=True)
            else:
                result["learning_outcome"] = LearningEngine.learn_from_execution(result, persist=False)
            return result

        bus.emit("Execution Queued", workflow_id, {"status": "Queued"})
        stage_results = []
        tasks = blueprint.get("tasks", [])
        for stage in blueprint.get("stages", []):
            stage_tasks = [task for task in tasks if task.get("Stage") == stage.get("Name")]
            bus.emit("Stage Started", workflow_id, {"stage": stage.get("Name")})
            if execution_mode == "Simulation":
                adapter_result = {
                    "adapter": "simulation",
                    "status": "Completed",
                    "message": f"{stage.get('Name')} simulated without execution.",
                    "details": {"task_count": len(stage_tasks), "external_calls": 0},
                }
            else:
                adapter_result = adapter.execute_stage(stage, stage_tasks, {"execution_mode": execution_mode}).__dict__
            bus.emit("Stage Completed", workflow_id, {"stage": stage.get("Name"), "status": adapter_result["status"]})
            stage_results.append(
                {
                    "Stage": stage.get("Name"),
                    "Status": adapter_result["status"],
                    "Adapter": adapter_result["adapter"],
                    "Message": adapter_result["message"],
                    "Task Count": len(stage_tasks),
                },
            )

        bus.emit("Validation Started", workflow_id, {})
        adapter_validation = adapter.validate({"execution_mode": execution_mode, "validation": blueprint.get("validation", [])}).__dict__
        validation = ValidationEngine.validate_execution(blueprint, adapter_validation)
        bus.emit("Validation Passed", workflow_id, {"checks": len(validation)})
        rollback = RollbackEngine.rollback_if_required(blueprint, validation, adapter_validation)
        status = "Rolled Back" if rollback else "Completed"
        if rollback:
            bus.emit("Rollback Started", workflow_id, rollback)
            adapter.rollback({"execution_mode": execution_mode, "rollback": blueprint.get("rollback", [])})
            bus.emit("Rollback Completed", workflow_id, rollback)
        bus.emit("Execution Completed", workflow_id, {"status": status})
        result = {
            "id": job_id,
            "organization_id": org_id,
            "workflow_id": workflow_id,
            "goal": blueprint.get("goal"),
            "created_by": created_by,
            "created_at": datetime.utcnow().isoformat(),
            "execution_mode": execution_mode,
            "adapter": adapter.adapter_name if execution_mode != "Simulation" else "simulation",
            "status": status,
            "progress": 100,
            "authorization": {"Status": "AUTHORIZED", "Source": "Governance Authorization" if not force_authorized else "Forced test authorization"},
            "stages": stage_results,
            "validation_results": validation,
            "rollback_execution": rollback,
            "events": bus.events,
            "summary": SafeExecutionService._summary(status, blueprint, execution_mode, adapter_name, validation, rollback),
            "blueprint": blueprint,
        }
        if persist:
            SafeExecutionRepository.save_execution(result)
            result["learning_outcome"] = LearningEngine.learn_from_execution(result, persist=True)
        else:
            result["learning_outcome"] = LearningEngine.learn_from_execution(result, persist=False)
        return result

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        jobs = SafeExecutionRepository.list_jobs(organization_id)
        return {
            "jobs": jobs,
            "authorized_plans": [row for row in jobs if row.get("authorization_status") == "AUTHORIZED"],
            "queue": [row for row in jobs if row.get("status") == "Queued"],
            "running": [row for row in jobs if row.get("status") in {"Executing", "Validating"}],
            "completed": [row for row in jobs if row.get("status") == "Completed"],
            "rollbacks": [row for row in jobs if row.get("status") == "Rolled Back"],
            "history": jobs,
            "adapters": adapter_registry_rows(),
        }

    @staticmethod
    def _authorization_gate(authorization: dict[str, Any], execution_mode: str, force_authorized: bool) -> dict[str, Any]:
        if execution_mode == "Simulation":
            return {"allowed": True, "reason": "Simulation mode does not execute changes."}
        if force_authorized and execution_mode == "Mock":
            return {"allowed": True, "reason": "Mock execution authorized for verification."}
        if authorization.get("execution_status") != "AUTHORIZED":
            return {"allowed": False, "reason": authorization.get("execution_lock", {}).get("Reason", "Execution is not authorized.")}
        if authorization.get("execution_lock", {}).get("State") != "AUTHORIZED":
            return {"allowed": False, "reason": "Execution lock is not released."}
        if execution_mode == "Production":
            return {"allowed": False, "reason": "Production execution adapter is disabled in A.9.5."}
        return {"allowed": True, "reason": "Governance authorization verified."}

    @staticmethod
    def _blocked_result(
        job_id: str,
        org_id: str,
        workflow_id: str,
        blueprint: dict[str, Any],
        authorization: dict[str, Any],
        gate: dict[str, Any],
        execution_mode: str,
        adapter_name: str,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "id": job_id,
            "organization_id": org_id,
            "workflow_id": workflow_id,
            "goal": blueprint.get("goal"),
            "created_at": datetime.utcnow().isoformat(),
            "execution_mode": execution_mode,
            "adapter": adapter_name,
            "status": "Blocked",
            "progress": 0,
            "authorization": {"Status": authorization.get("execution_status", "NOT AUTHORIZED"), "Reason": gate.get("reason")},
            "stages": [],
            "validation_results": [],
            "rollback_execution": None,
            "events": events,
            "summary": {"Status": "Blocked", "Reason": gate.get("reason"), "Execution Performed": False},
            "blueprint": blueprint,
        }

    @staticmethod
    def _summary(
        status: str,
        blueprint: dict[str, Any],
        execution_mode: str,
        adapter_name: str,
        validation: list[dict[str, Any]],
        rollback: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "Status": status,
            "Goal": blueprint.get("goal"),
            "Execution Mode": execution_mode,
            "Adapter": adapter_name,
            "Stages": len(blueprint.get("stages", [])),
            "Validation Checks": len(validation),
            "Rollback": "Executed" if rollback else "Not Required",
            "External API Calls": 0,
            "Execution Performed": execution_mode == "Mock",
        }
