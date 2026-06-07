"""Enterprise RBAC permissions helper."""

ROLE_PERMISSIONS = {
    "super_admin": ["all"],
    "executive": [
        "view_executive_dashboard",
        "view_financials",
        "view_risk",
    ],
    "operations": [
        "view_operations",
    ],
}


def has_permission(role: str, permission: str) -> bool:
    """Return True when a role has a given permission."""
    perms = ROLE_PERMISSIONS.get(str(role or "").lower(), [])
    return "all" in perms or permission in perms

