from .roles import require_jwt as _require_jwt, require_role as _require_role

def require_jwt():
    # Centralized wrapper for all JWT checks (add global logging, auditing, etc. here)
    return _require_jwt()

def require_role(allowed_roles):
    # Centralized wrapper for all RBAC checks (add global logging, auditing, etc. here)
    return _require_role(allowed_roles)
