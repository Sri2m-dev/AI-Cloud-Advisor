from auth.guards import normalize_role, require_role as require_guard_role
from auth.guards import require_auth

def has_role(*roles):
    """
    Returns True if the current user has one of the specified roles.
    Usage: if has_role('admin', 'manager'):
    """
    user = require_auth()
    role = normalize_role(user.get("role"))
    return role in {normalize_role(candidate) for candidate in roles}

def require_role(*roles):
    """
    Call at the top of a page to enforce role access.
    Shows a warning and stops execution if the user does not have the required role.
    """
    return require_guard_role(roles)

