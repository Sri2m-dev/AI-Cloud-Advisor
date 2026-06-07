from typing import Dict, Set

# Centralized permission matrix
PERMISSION_MATRIX: Dict[str, Set[str]] = {
    "Admin": {"approve_request", "reject_request", "reassign_request", "export_data"},
    "Manager": {"approve_request", "reject_request", "reassign_request"},
    "Analyst": {"export_data"},
    "super_admin": {"approve_request", "reject_request", "reassign_request", "export_data"},
    "executive": {"approve_request", "reject_request", "reassign_request", "export_data"},
    "technical": {"approve_request", "reject_request", "reassign_request", "export_data"},
}

def has_permission(role: str, action: str) -> bool:
    return action in PERMISSION_MATRIX.get(role, set())

