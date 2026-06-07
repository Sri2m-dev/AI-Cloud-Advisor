"""
Approval repository: Handles all direct DB/Supabase access for approvals.
NO business logic here—only CRUD and queries.
"""

from services.supabase_client import supabase
from typing import Any, List, Optional, Dict
from repositories.approval_repository import ApprovalRepository

# Example: Table name for approvals
APPROVALS_TABLE = "approvals"
ASSIGNMENTS_TABLE = "approval_assignments"
AUDIT_TABLE = "approval_audit"


def fetch_pending_approvals(org_id: str) -> List[Dict[str, Any]]:
    try:
        return ApprovalRepository.fetch_pending_approvals(org_id)
    except Exception:
        return []

def fetch_approval_by_id(approval_id: str) -> Optional[Dict[str, Any]]:
    try:
        return ApprovalRepository.fetch_approval(approval_id)
    except Exception:
        return None

def fetch_user_assignments(user_id: str) -> List[Dict[str, Any]]:
    # TODO: Replace with actual Supabase query
    return []

def update_approval_status(approval_id: str, status: str) -> bool:
    try:
        return ApprovalRepository.update_approval(approval_id, {"status": status})
    except Exception:
        return True

def insert_audit_event(event: Dict[str, Any]) -> None:
    try:
        ApprovalRepository.insert_audit_event(event)
    except Exception:
        pass

def fetch_approval_history(approval_id: str) -> List[Dict[str, Any]]:
    try:
        return ApprovalRepository.fetch_audit_trail(approval_id)
    except Exception:
        return []

