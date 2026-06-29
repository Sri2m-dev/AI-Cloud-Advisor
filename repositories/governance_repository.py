from __future__ import annotations

import uuid
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class GovernanceRepository:
    @staticmethod
    def save_authorization(review: dict[str, Any]) -> bool:
        org_id = resolve_organization_id(review.get("organization_id"))
        review_id = review.get("id") or str(uuid.uuid4())
        ok = True
        ok = GovernanceRepository._insert(
            "governance_review",
            {
                "id": review_id,
                "organization_id": org_id,
                "workflow_id": review.get("workflow_id"),
                "goal_text": review.get("goal"),
                "governance_score": review.get("governance_score", 0),
                "cab_readiness": review.get("cab_readiness", {}).get("Score", 0),
                "execution_status": review.get("execution_status"),
                "review_payload": review,
            },
        ) and ok
        for policy in review.get("policy_validation", []):
            ok = GovernanceRepository._insert(
                "policy_validation",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "review_id": review_id,
                    "policy_name": policy.get("Policy"),
                    "policy_category": policy.get("Category"),
                    "status": policy.get("Status"),
                    "evidence": policy.get("Evidence"),
                    "severity": policy.get("Severity"),
                },
            ) and ok
        for request in review.get("required_approvals", []):
            request_id = str(uuid.uuid4())
            ok = GovernanceRepository._insert(
                "approval_request",
                {
                    "id": request_id,
                    "organization_id": org_id,
                    "review_id": review_id,
                    "workflow_id": review.get("workflow_id"),
                    "approver_role": request.get("Approver Role"),
                    "approver": request.get("Approver"),
                    "status": request.get("Status", "Pending"),
                    "policy_reason": request.get("Policy Reason"),
                    "due_date": request.get("Due Date"),
                },
            ) and ok
        cab = review.get("cab_readiness", {})
        ok = GovernanceRepository._insert(
            "cab_review",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "review_id": review_id,
                "workflow_id": review.get("workflow_id"),
                "readiness_score": cab.get("Score", 0),
                "cab_ready": cab.get("CAB Ready") == "YES",
                "missing_items": cab.get("Missing Items", []),
                "checklist": cab.get("Checklist", []),
                "status": "Ready" if cab.get("CAB Ready") == "YES" else "Needs Remediation",
            },
        ) and ok
        ok = GovernanceRepository._insert(
            "execution_lock",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "review_id": review_id,
                "workflow_id": review.get("workflow_id"),
                "lock_state": review.get("execution_lock", {}).get("State", "LOCKED"),
                "reason": review.get("execution_lock", {}).get("Reason"),
                "unlock_conditions": review.get("execution_lock", {}).get("Unlock Conditions", []),
            },
        ) and ok
        ok = GovernanceRepository._insert(
            "execution_authorization",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "review_id": review_id,
                "workflow_id": review.get("workflow_id"),
                "authorization_status": review.get("execution_status"),
                "authorized": review.get("execution_status") == "AUTHORIZED",
                "authorized_by": review.get("executive_authorization", {}).get("Authorized By"),
                "authorization_reason": review.get("executive_authorization", {}).get("Reason"),
                "authorization_payload": review.get("executive_authorization", {}),
            },
        ) and ok
        return ok

    @staticmethod
    def save_approval_decision(decision: dict[str, Any]) -> bool:
        org_id = resolve_organization_id(decision.get("organization_id"))
        decision_id = decision.get("id") or str(uuid.uuid4())
        ok = GovernanceRepository._insert(
            "approval_decision",
            {
                "id": decision_id,
                "organization_id": org_id,
                "approval_request_id": decision.get("approval_request_id"),
                "review_id": decision.get("review_id"),
                "decision": decision.get("decision"),
                "decision_by": decision.get("decision_by"),
                "comments": decision.get("comments"),
                "conditions": decision.get("conditions", []),
                "evidence": decision.get("evidence", []),
                "blueprint_revision": decision.get("blueprint_revision", "1.0"),
            },
        )
        if decision.get("digital_signature"):
            ok = GovernanceRepository._insert(
                "digital_signature",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "approval_decision_id": decision_id,
                    "signed_by": decision.get("decision_by"),
                    "signature_hash": decision.get("digital_signature"),
                    "signature_payload": decision,
                    "blueprint_revision": decision.get("blueprint_revision", "1.0"),
                },
            ) and ok
        if decision.get("comments"):
            ok = GovernanceRepository._insert(
                "approval_comments",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "approval_request_id": decision.get("approval_request_id"),
                    "review_id": decision.get("review_id"),
                    "comment_by": decision.get("decision_by"),
                    "comment_text": decision.get("comments"),
                    "evidence": decision.get("evidence", []),
                },
            ) and ok
        return ok

    @staticmethod
    def save_execution_lock(lock: dict[str, Any]) -> bool:
        org_id = resolve_organization_id(lock.get("organization_id"))
        return GovernanceRepository._insert(
            "execution_lock",
            {
                "id": lock.get("id") or str(uuid.uuid4()),
                "organization_id": org_id,
                "review_id": lock.get("review_id"),
                "workflow_id": lock.get("workflow_id"),
                "lock_state": lock.get("lock_state", "LOCKED"),
                "reason": lock.get("reason"),
                "unlock_conditions": lock.get("unlock_conditions", []),
            },
        )

    @staticmethod
    def save_execution_authorization(authorization: dict[str, Any]) -> bool:
        org_id = resolve_organization_id(authorization.get("organization_id"))
        return GovernanceRepository._insert(
            "execution_authorization",
            {
                "id": authorization.get("id") or str(uuid.uuid4()),
                "organization_id": org_id,
                "review_id": authorization.get("review_id"),
                "workflow_id": authorization.get("workflow_id"),
                "authorization_status": authorization.get("authorization_status", "NOT AUTHORIZED"),
                "authorized": authorization.get("authorized", False),
                "authorized_by": authorization.get("authorized_by"),
                "authorization_reason": authorization.get("authorization_reason"),
                "authorization_payload": authorization,
            },
        )

    @staticmethod
    def list_governance_reviews(organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return GovernanceRepository._list("governance_review", organization_id, limit)

    @staticmethod
    def list_approval_requests(organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return GovernanceRepository._list("approval_request", organization_id, limit)

    @staticmethod
    def _insert(table_name: str, payload: dict[str, Any]) -> bool:
        try:
            supabase.table(table_name).insert(payload).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def _list(table_name: str, organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
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
