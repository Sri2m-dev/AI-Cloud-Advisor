from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from repositories.governance_repository import GovernanceRepository
from services.workflow_builder_service import WorkflowBuilderService


POLICY_FILE = Path(__file__).resolve().parents[1] / "governance_policies" / "default_governance_policies.json"


class GovernanceAuthorizationService:
    @staticmethod
    def evaluate_goal(
        goal: str,
        organization_id: str | None = None,
        created_by: str = "system",
        persist: bool = True,
    ) -> dict[str, Any]:
        blueprint = WorkflowBuilderService.build_from_goal(goal, organization_id, created_by, persist=False)
        return GovernanceAuthorizationService.evaluate_blueprint(blueprint, created_by=created_by, persist=persist)

    @staticmethod
    def evaluate_blueprint(
        blueprint: dict[str, Any],
        created_by: str = "system",
        persist: bool = True,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(blueprint.get("organization_id"))
        policy = GovernanceAuthorizationService._select_policy(blueprint)
        policy_validation = GovernanceAuthorizationService._policy_validation(blueprint, policy)
        approvals = GovernanceAuthorizationService._required_approvals(blueprint, policy)
        cab_readiness = GovernanceAuthorizationService._cab_readiness(blueprint, approvals, policy_validation)
        risk_matrix = GovernanceAuthorizationService._risk_matrix(blueprint, policy_validation, cab_readiness)
        readiness = GovernanceAuthorizationService._governance_score(policy_validation, approvals, cab_readiness, risk_matrix)
        execution_lock = GovernanceAuthorizationService._execution_lock(readiness, approvals, policy_validation, cab_readiness)
        execution_status = "AUTHORIZED" if execution_lock["State"] == "AUTHORIZED" else "NOT AUTHORIZED"
        review = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "workflow_id": blueprint.get("id"),
            "goal": blueprint.get("goal"),
            "created_by": created_by,
            "created_at": datetime.utcnow().isoformat(),
            "blueprint_revision": "1.0",
            "policy": policy,
            "governance_score": readiness,
            "execution_status": execution_status,
            "required_approvals": approvals,
            "pending_approvals": [row for row in approvals if row.get("Status") != "Approved"],
            "policy_validation": policy_validation,
            "policy_violations": [row for row in policy_validation if row.get("Status") == "Fail"],
            "cab_readiness": cab_readiness,
            "risk_matrix": risk_matrix,
            "execution_lock": execution_lock,
            "executive_authorization": GovernanceAuthorizationService._executive_authorization(execution_status, readiness),
            "audit_timeline": GovernanceAuthorizationService._audit_timeline(blueprint, policy_validation, execution_lock),
            "executive_summary": GovernanceAuthorizationService._summary(execution_status, readiness, approvals, cab_readiness),
            "blueprint": blueprint,
        }
        if persist:
            GovernanceRepository.save_authorization(review)
        return review

    @staticmethod
    def decide_approval(
        approval_request_id: str,
        decision: str,
        decision_by: str,
        comments: str = "",
        conditions: list[str] | None = None,
        evidence: list[str] | None = None,
        organization_id: str | None = None,
        review_id: str | None = None,
        blueprint_revision: str = "1.0",
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        payload = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "approval_request_id": approval_request_id,
            "review_id": review_id,
            "decision": decision,
            "decision_by": decision_by,
            "comments": comments,
            "conditions": conditions or [],
            "evidence": evidence or [],
            "blueprint_revision": blueprint_revision,
            "digital_signature": GovernanceAuthorizationService._signature(
                approval_request_id,
                decision,
                decision_by,
                comments,
                blueprint_revision,
            ),
            "created_at": datetime.utcnow().isoformat(),
        }
        GovernanceRepository.save_approval_decision(payload)
        return payload

    @staticmethod
    def lock_execution(
        workflow_id: str,
        reason: str,
        organization_id: str | None = None,
        review_id: str | None = None,
        unlock_conditions: list[str] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "id": str(uuid.uuid4()),
            "organization_id": resolve_organization_id(organization_id),
            "review_id": review_id,
            "workflow_id": workflow_id,
            "lock_state": "LOCKED",
            "reason": reason,
            "unlock_conditions": unlock_conditions or [reason],
            "created_at": datetime.utcnow().isoformat(),
        }
        GovernanceRepository.save_execution_lock(payload)
        return payload

    @staticmethod
    def unlock_execution(
        workflow_id: str,
        authorized_by: str,
        organization_id: str | None = None,
        review_id: str | None = None,
        reason: str = "All governance authorization gates passed.",
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        lock = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "review_id": review_id,
            "workflow_id": workflow_id,
            "lock_state": "AUTHORIZED",
            "reason": reason,
            "unlock_conditions": [],
            "created_at": datetime.utcnow().isoformat(),
        }
        authorization = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "review_id": review_id,
            "workflow_id": workflow_id,
            "authorization_status": "AUTHORIZED",
            "authorized": True,
            "authorized_by": authorized_by,
            "authorization_reason": reason,
            "created_at": datetime.utcnow().isoformat(),
        }
        GovernanceRepository.save_execution_lock(lock)
        GovernanceRepository.save_execution_authorization(authorization)
        return {"execution_lock": lock, "execution_authorization": authorization}

    @staticmethod
    def _load_policies() -> dict[str, Any]:
        try:
            return json.loads(POLICY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"version": "fallback", "policies": []}

    @staticmethod
    def _select_policy(blueprint: dict[str, Any]) -> dict[str, Any]:
        policies = GovernanceAuthorizationService._load_policies().get("policies", [])
        text = f"{blueprint.get('goal', '')} {(blueprint.get('template') or {}).get('Name', '')}".lower()
        scored = []
        for policy in policies:
            score = sum(1 for token in policy.get("keywords", []) if token in text)
            scored.append((score, policy))
        if not scored:
            return {
                "name": "Default Enterprise Change",
                "required_approvals": ["Business Owner", "Technology Owner", "Finance", "CAB"],
                "conditions": {"rollback_required": True, "simulation_required": True, "validation_required": True, "dr_readiness_min": 80},
                "execution_window": {"allowed": ["Approved maintenance window"]},
            }
        return max(scored, key=lambda item: item[0])[1]

    @staticmethod
    def _policy_validation(blueprint: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
        conditions = policy.get("conditions", {})
        checks = [
            ("Business Policies", True, "Business approval path generated."),
            ("Security Policies", any(row.get("Approver Role") == "Security" for row in blueprint.get("approvals", [])), "Security approval is present."),
            ("Compliance Policies", len(blueprint.get("validation", [])) >= 5, "Validation controls cover compliance evidence."),
            ("Financial Policies", any(row.get("Approver Role") == "Finance" for row in blueprint.get("approvals", [])), "Finance approval is present."),
            ("Operational Policies", bool(blueprint.get("rollback")) and bool(blueprint.get("dependencies")), "Rollback and dependencies are present."),
            ("Architecture Policies", len(blueprint.get("stages", [])) >= 7, "Seven-stage enterprise workflow is present."),
            ("Rollback Required", bool(blueprint.get("rollback")) if conditions.get("rollback_required") else True, "Rollback plan required by policy."),
            ("Simulation Required", any(row.get("Name") == "Simulation" for row in blueprint.get("stages", [])) if conditions.get("simulation_required") else True, "Simulation stage required by policy."),
            ("Validation Required", bool(blueprint.get("validation")) if conditions.get("validation_required") else True, "Validation checklist required by policy."),
        ]
        rows = []
        for category, passed, evidence in checks:
            rows.append(
                {
                    "Policy": f"{policy.get('name', 'Enterprise Policy')} - {category}",
                    "Category": category,
                    "Status": "Pass" if passed else "Fail",
                    "Evidence": evidence,
                    "Severity": "High" if not passed else "Info",
                },
            )
        return rows

    @staticmethod
    def _required_approvals(blueprint: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
        existing = {row.get("Approver Role"): row for row in blueprint.get("approvals", [])}
        roles = []
        for role in policy.get("required_approvals", []):
            if role not in roles:
                roles.append(role)
        for role in existing:
            if role not in roles:
                roles.append(role)
        due = (datetime.utcnow() + timedelta(days=3)).date().isoformat()
        return [
            {
                "Approver Role": role,
                "Approver": existing.get(role, {}).get("Approver") or "Unassigned",
                "Status": "Pending",
                "Decision Options": ["Support", "Approve", "Reject", "Request Changes", "Delegate", "Escalate", "Conditional Approval"],
                "Policy Reason": existing.get(role, {}).get("Policy Reason") or f"{role} required by governance-as-code policy.",
                "Due Date": due,
            }
            for role in roles
        ]

    @staticmethod
    def _cab_readiness(
        blueprint: dict[str, Any],
        approvals: list[dict[str, Any]],
        policy_validation: list[dict[str, Any]],
    ) -> dict[str, Any]:
        checklist = [
            ("Simulation", any(row.get("Name") == "Simulation" for row in blueprint.get("stages", []))),
            ("Rollback", bool(blueprint.get("rollback"))),
            ("Validation", bool(blueprint.get("validation"))),
            ("Approvals", len(approvals) >= 4),
            ("Risk", blueprint.get("business_risk") in {"Low", "Medium", "High"}),
            ("Dependencies", bool(blueprint.get("dependencies"))),
            ("Documentation", bool(blueprint.get("executive_summary"))),
            ("Business Impact", bool(blueprint.get("goal"))),
            ("Policy Validation", not any(row.get("Status") == "Fail" for row in policy_validation)),
        ]
        rows = [{"Item": name, "Status": "Complete" if complete else "Missing"} for name, complete in checklist]
        missing = [name for name, complete in checklist if not complete]
        score = round((len(checklist) - len(missing)) / len(checklist) * 100, 1)
        return {
            "Score": score,
            "CAB Ready": "YES" if score >= 95 and not missing else "NO",
            "Missing Items": missing,
            "Checklist": rows,
        }

    @staticmethod
    def _risk_matrix(blueprint: dict[str, Any], policies: list[dict[str, Any]], cab: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"Risk": "Business Risk", "Level": blueprint.get("business_risk", "Medium"), "Mitigation": "Business Owner approval and KPI validation."},
            {"Risk": "Policy Violations", "Level": "High" if any(row.get("Status") == "Fail" for row in policies) else "Low", "Mitigation": "Resolve failed policy checks before authorization."},
            {"Risk": "CAB Readiness", "Level": "Low" if cab.get("Score", 0) >= 95 else "Medium", "Mitigation": "Complete missing CAB checklist items."},
            {"Risk": "Execution Risk", "Level": "Controlled", "Mitigation": "Execution remains locked until all gates pass."},
        ]

    @staticmethod
    def _governance_score(
        policies: list[dict[str, Any]],
        approvals: list[dict[str, Any]],
        cab: dict[str, Any],
        risks: list[dict[str, Any]],
    ) -> float:
        policy_score = 100 - (len([row for row in policies if row.get("Status") == "Fail"]) * 12)
        approval_score = 100 - (len([row for row in approvals if row.get("Status") != "Approved"]) * 6)
        risk_penalty = len([row for row in risks if row.get("Level") in {"High", "Critical"}]) * 8
        score = (max(policy_score, 0) * 0.35) + (max(approval_score, 0) * 0.25) + (cab.get("Score", 0) * 0.30) + ((100 - risk_penalty) * 0.10)
        return round(max(min(score, 100), 0), 1)

    @staticmethod
    def _execution_lock(readiness: float, approvals: list[dict[str, Any]], policies: list[dict[str, Any]], cab: dict[str, Any]) -> dict[str, Any]:
        blockers = []
        pending = [row.get("Approver Role") for row in approvals if row.get("Status") != "Approved"]
        if pending:
            blockers.append(f"Pending approvals: {', '.join(pending)}")
        failures = [row.get("Policy") for row in policies if row.get("Status") == "Fail"]
        if failures:
            blockers.append(f"Policy violations: {', '.join(failures)}")
        if cab.get("CAB Ready") != "YES":
            blockers.append(f"CAB not ready: {', '.join(cab.get('Missing Items') or ['Checklist incomplete'])}")
        if readiness < 95:
            blockers.append("Governance readiness below authorization threshold")
        return {
            "State": "AUTHORIZED" if not blockers else "LOCKED",
            "Reason": "All governance gates passed." if not blockers else "; ".join(blockers),
            "Unlock Conditions": blockers,
        }

    @staticmethod
    def _executive_authorization(status: str, score: float) -> dict[str, Any]:
        return {
            "Status": status,
            "Authorized By": "Pending Executive Authorization" if status != "AUTHORIZED" else "Executive Authorization Gate",
            "Reason": "Executive authorization requires all governance gates to pass." if status != "AUTHORIZED" else "Ready for controlled execution in a future sprint.",
            "Governance Score": score,
        }

    @staticmethod
    def _audit_timeline(blueprint: dict[str, Any], policies: list[dict[str, Any]], lock: dict[str, Any]) -> list[dict[str, Any]]:
        now = datetime.utcnow().isoformat()
        return [
            {"Time": blueprint.get("created_at"), "Event": "Workflow blueprint generated", "Actor": blueprint.get("created_by", "system")},
            {"Time": now, "Event": f"{len(policies)} policy checks evaluated", "Actor": "Governance Engine"},
            {"Time": now, "Event": f"Execution {lock.get('State')}", "Actor": "Execution Lock"},
        ]

    @staticmethod
    def _summary(status: str, score: float, approvals: list[dict[str, Any]], cab: dict[str, Any]) -> str:
        if status != "AUTHORIZED":
            pending = [row["Approver Role"] for row in approvals if row.get("Status") != "Approved"]
            missing = cab.get("Missing Items") or []
            reasons = pending[:3] + missing[:3]
            return f"Execution Status: NOT AUTHORIZED. Governance score is {score}%. Reason: {', '.join(reasons) or 'governance gates pending'}."
        return f"Execution Status: AUTHORIZED. Governance score is {score}% and all authorization gates passed."

    @staticmethod
    def _signature(*parts: str) -> str:
        raw = "|".join(str(part or "") for part in parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
