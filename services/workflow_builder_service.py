from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from agents.orchestrator import AgentOrchestrator
from connectors.common.tenant_guard import resolve_organization_id
from repositories.workflow_builder_repository import WorkflowBuilderRepository


WORKFLOW_STAGES = [
    ("Discovery", "Confirm scope, baseline, owners, and current-state evidence.", "Planner Agent"),
    ("Simulation", "Run scenario and impact previews before approvals.", "Simulation Agent"),
    ("Approval", "Prepare CAB package and collect required approval gates.", "Governance Agent"),
    ("Execution", "Document execution tasks for future approved implementation.", "Operations Agent"),
    ("Validation", "Validate cost, health, application, business-service, and KPI outcomes.", "Operations Agent"),
    ("Optimization", "Tune savings, risk controls, and follow-up recommendations.", "Cost Agent"),
    ("Closure", "Capture evidence, decisions, lessons, and final governance state.", "Reasoning Agent"),
]

WORKFLOW_TEMPLATES = [
    {
        "Name": "Cloud Cost Optimization",
        "Keywords": ["cloud", "aws", "azure", "cost", "spend", "reserved", "savings"],
        "Tasks": ["Analyze compute", "Analyze storage", "Analyze networking", "Run savings simulation", "Prepare CAB", "Validate savings"],
        "Duration Weeks": 6,
    },
    {
        "Name": "Oracle to PostgreSQL Migration",
        "Keywords": ["oracle", "postgres", "postgresql", "migration", "database"],
        "Tasks": ["Assess Oracle estate", "Map dependencies", "Design PostgreSQL target", "Run migration simulation", "Prepare CAB", "Validate cutover"],
        "Duration Weeks": 14,
    },
    {
        "Name": "SaaS License Optimization",
        "Keywords": ["saas", "license", "microsoft 365", "subscription", "unused"],
        "Tasks": ["Analyze active users", "Identify unused licenses", "Validate business owners", "Simulate removals", "Prepare CAB", "Validate access"],
        "Duration Weeks": 4,
    },
    {
        "Name": "Kubernetes Rightsizing",
        "Keywords": ["kubernetes", "k8s", "utilization", "cluster", "container"],
        "Tasks": ["Analyze cluster utilization", "Review workloads", "Simulate rightsizing", "Prepare maintenance window", "Prepare CAB", "Validate capacity"],
        "Duration Weeks": 8,
    },
    {
        "Name": "Disaster Recovery Testing",
        "Keywords": ["dr", "disaster", "recovery", "availability", "failover"],
        "Tasks": ["Identify critical services", "Validate RTO/RPO", "Run failover simulation", "Prepare CAB", "Execute test plan", "Validate recovery"],
        "Duration Weeks": 10,
    },
    {
        "Name": "Security Remediation",
        "Keywords": ["security", "compliance", "pci", "encryption", "identity"],
        "Tasks": ["Assess security finding", "Map controls", "Validate policy", "Prepare remediation plan", "Prepare CAB", "Validate audit evidence"],
        "Duration Weeks": 6,
    },
    {
        "Name": "Cloud Region Migration",
        "Keywords": ["region", "migration", "cloud region", "latency"],
        "Tasks": ["Assess source region", "Map workloads", "Simulate migration", "Prepare cutover", "Prepare CAB", "Validate region health"],
        "Duration Weeks": 12,
    },
]


class WorkflowBuilderService:
    @staticmethod
    def build_from_goal(
        goal: str,
        organization_id: str | None = None,
        created_by: str = "system",
        persist: bool = True,
    ) -> dict[str, Any]:
        collaboration = AgentOrchestrator.collaborate_on_goal(goal, organization_id, created_by, persist=False)
        return WorkflowBuilderService.build_from_collaboration(collaboration, created_by=created_by, persist=persist)

    @staticmethod
    def build_from_collaboration(
        collaboration: dict[str, Any],
        created_by: str = "system",
        persist: bool = True,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(collaboration.get("organization_id"))
        template = WorkflowBuilderService.select_template(collaboration.get("goal", ""))
        stages = WorkflowBuilderService._stages()
        tasks = WorkflowBuilderService._tasks(collaboration, template)
        dependencies = WorkflowBuilderService._dependencies(tasks)
        approvals = WorkflowBuilderService._approvals(collaboration)
        rollback = WorkflowBuilderService._rollback(collaboration)
        validation = WorkflowBuilderService._validation(collaboration)
        duration = WorkflowBuilderService._duration(template, tasks)
        workflow_id = str(uuid.uuid4())
        blueprint = {
            "id": workflow_id,
            "organization_id": org_id,
            "goal_id": collaboration.get("id"),
            "goal": collaboration.get("goal"),
            "status": "Blueprint Ready",
            "created_by": created_by,
            "created_at": datetime.utcnow().isoformat(),
            "template": template,
            "stages": stages,
            "tasks": tasks,
            "dependencies": dependencies,
            "approvals": approvals,
            "rollback": rollback,
            "validation": validation,
            "estimated_duration": duration,
            "business_risk": (collaboration.get("unified_enterprise_plan") or {}).get("Business Risk", "Medium"),
            "confidence": (collaboration.get("consensus") or {}).get("Confidence", 92.0),
            "execution_enabled": False,
            "executive_summary": WorkflowBuilderService._summary(collaboration, template, tasks, approvals, duration),
            "source_consensus": collaboration.get("consensus", {}),
            "source_collaboration": {
                "participating_agents": collaboration.get("participating_agents", []),
                "recommendation": (collaboration.get("consensus") or {}).get("Enterprise Recommendation"),
            },
        }
        if persist:
            WorkflowBuilderRepository.save_blueprint(blueprint)
        return blueprint

    @staticmethod
    def get_templates() -> list[dict[str, Any]]:
        return WORKFLOW_TEMPLATES

    @staticmethod
    def select_template(goal: str) -> dict[str, Any]:
        text = str(goal or "").lower()
        scored = []
        for template in WORKFLOW_TEMPLATES:
            score = sum(1 for token in template["Keywords"] if token in text)
            scored.append((score, template))
        best = max(scored, key=lambda item: item[0])
        return dict(best[1] if best[0] > 0 else WORKFLOW_TEMPLATES[0])

    @staticmethod
    def _stages() -> list[dict[str, Any]]:
        return [
            {
                "Stage": index,
                "Name": name,
                "Description": description,
                "Owner": owner,
                "Status": "Planned",
            }
            for index, (name, description, owner) in enumerate(WORKFLOW_STAGES, start=1)
        ]

    @staticmethod
    def _tasks(collaboration: dict[str, Any], template: dict[str, Any]) -> list[dict[str, Any]]:
        base_tasks = list(template.get("Tasks", []))
        stage_map = ["Discovery", "Discovery", "Simulation", "Approval", "Execution", "Validation"]
        tasks = []
        for index, name in enumerate(base_tasks, start=1):
            stage = stage_map[min(index - 1, len(stage_map) - 1)]
            tasks.append(
                {
                    "id": str(uuid.uuid4()),
                    "Task": index,
                    "Name": name,
                    "Stage": stage,
                    "Description": WorkflowBuilderService._task_description(name, collaboration),
                    "Owner": WorkflowBuilderService._owner_for_stage(stage),
                    "Estimated Duration": "3 Business Days" if stage != "Execution" else "5 Business Days",
                    "Dependencies": [] if index == 1 else [base_tasks[index - 2]],
                    "Success Criteria": WorkflowBuilderService._success_criteria(name, stage),
                    "Rollback Action": WorkflowBuilderService._rollback_action(stage),
                },
            )
        closing = [
            ("Confirm approval packet", "Approval"),
            ("Document future execution controls", "Execution"),
            ("Validate business KPIs", "Validation"),
            ("Capture lessons learned", "Closure"),
        ]
        for name, stage in closing:
            index = len(tasks) + 1
            tasks.append(
                {
                    "id": str(uuid.uuid4()),
                    "Task": index,
                    "Name": name,
                    "Stage": stage,
                    "Description": WorkflowBuilderService._task_description(name, collaboration),
                    "Owner": WorkflowBuilderService._owner_for_stage(stage),
                    "Estimated Duration": "2 Business Days",
                    "Dependencies": [tasks[-1]["Name"]] if tasks else [],
                    "Success Criteria": WorkflowBuilderService._success_criteria(name, stage),
                    "Rollback Action": WorkflowBuilderService._rollback_action(stage),
                },
            )
        return tasks

    @staticmethod
    def _dependencies(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        dependencies = []
        for task in tasks:
            for dependency in task.get("Dependencies", []):
                dependencies.append(
                    {
                        "Task": task["Name"],
                        "Depends On": dependency,
                        "Type": "Sequential",
                        "Reason": "Prevents invalid execution order.",
                    },
                )
        return dependencies

    @staticmethod
    def _approvals(collaboration: dict[str, Any]) -> list[dict[str, Any]]:
        preview = collaboration.get("execution_preview") or {}
        governance = next(
            (row for row in collaboration.get("agent_contributions", []) if row.get("Agent") == "Governance Agent"),
            {},
        )
        roles = list(preview.get("Approvals") or [])
        roles += list(governance.get("Approvals Required") or [])
        ordered = ["Business Owner", "Application Owner", "Technology Owner", "Security", "Finance", "CAB", "CIO"]
        roles = [role for role in ordered if role in set(roles + ordered[:3])]
        return [
            {
                "Approver Role": role,
                "Approver": "Assigned during CAB intake",
                "Stage": "Approval",
                "Required": True,
                "Policy Reason": WorkflowBuilderService._approval_reason(role),
            }
            for role in roles
        ]

    @staticmethod
    def _rollback(collaboration: dict[str, Any]) -> list[dict[str, Any]]:
        target = collaboration.get("target") or "target environment"
        return [
            {
                "Trigger": "Health degradation",
                "Rollback Task": f"Restore previous approved configuration for {target}.",
                "Verification": "Application and infrastructure health return to baseline.",
                "Business Validation": "Business owner confirms service recovery.",
                "Closure": "Attach rollback evidence to workflow package.",
            },
            {
                "Trigger": "Cost or KPI regression",
                "Rollback Task": "Pause rollout and restore prior cost-control settings.",
                "Verification": "Cost, CPU, memory, and error-rate checks are stable.",
                "Business Validation": "Finance and service owner approve recovery state.",
                "Closure": "Create follow-up optimization action.",
            },
        ]

    @staticmethod
    def _validation(collaboration: dict[str, Any]) -> list[dict[str, Any]]:
        del collaboration
        return [
            {"Check": "CPU", "Metric": "Utilization", "Success Criteria": "No sustained saturation above threshold.", "Owner": "Operations"},
            {"Check": "Cost", "Metric": "Daily spend", "Success Criteria": "Spend trend aligns with approved forecast.", "Owner": "Finance"},
            {"Check": "Health", "Metric": "Service health", "Success Criteria": "No critical health regressions.", "Owner": "Operations"},
            {"Check": "Applications", "Metric": "Error rate", "Success Criteria": "Application errors remain within baseline.", "Owner": "Application Owner"},
            {"Check": "Business Services", "Metric": "Availability", "Success Criteria": "Critical business services remain available.", "Owner": "Business Owner"},
            {"Check": "Incidents", "Metric": "Incident count", "Success Criteria": "No major incident caused by workflow.", "Owner": "Service Desk"},
            {"Check": "KPIs", "Metric": "Business KPI", "Success Criteria": "Executive KPI remains stable or improves.", "Owner": "CIO"},
        ]

    @staticmethod
    def _duration(template: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
        weeks = int(template.get("Duration Weeks") or max(4, round(len(tasks) / 2)))
        return f"{weeks} Weeks"

    @staticmethod
    def _summary(
        collaboration: dict[str, Any],
        template: dict[str, Any],
        tasks: list[dict[str, Any]],
        approvals: list[dict[str, Any]],
        duration: str,
    ) -> str:
        consensus = collaboration.get("consensus") or {}
        return (
            f"Execution Blueprint Ready using the {template.get('Name')} template. "
            f"The workflow contains 7 stages, {len(tasks)} tasks, {len(approvals)} approval gates, "
            f"rollback and validation plans, and an estimated duration of {duration}. "
            f"Consensus recommendation: {consensus.get('Enterprise Recommendation', 'Proceed after approval')} "
            "Production execution remains disabled."
        )

    @staticmethod
    def _task_description(name: str, collaboration: dict[str, Any]) -> str:
        target = collaboration.get("target") or "enterprise target"
        return f"{name} for {target} using shared agent consensus and enterprise context."

    @staticmethod
    def _owner_for_stage(stage: str) -> str:
        return {
            "Discovery": "Planner Agent",
            "Simulation": "Simulation Agent",
            "Approval": "Governance Agent",
            "Execution": "Operations Agent",
            "Validation": "Operations Agent",
            "Optimization": "Cost Agent",
            "Closure": "Reasoning Agent",
        }.get(stage, "Planner Agent")

    @staticmethod
    def _success_criteria(name: str, stage: str) -> str:
        return f"{stage} task '{name}' is complete with evidence attached and no unresolved blockers."

    @staticmethod
    def _rollback_action(stage: str) -> str:
        if stage in {"Execution", "Validation"}:
            return "Restore prior approved state and run business validation."
        return "Return workflow to prior review gate."

    @staticmethod
    def _approval_reason(role: str) -> str:
        return {
            "Business Owner": "Business impact acceptance.",
            "Application Owner": "Application readiness and dependency ownership.",
            "Technology Owner": "Technical change ownership.",
            "Security": "Security and compliance control validation.",
            "Finance": "Savings, budget, and ROI validation.",
            "CAB": "Enterprise change governance.",
            "CIO": "Executive approval for material or high-risk change.",
        }.get(role, "Required enterprise approval.")
