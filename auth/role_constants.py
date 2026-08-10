"""Centralized RBAC role definitions and normalization helpers."""

ROLES = [
    "super_admin",
    "client_admin",
    "executive",
    "cio",
    "finance",
    "operations",
    "security",
    "technical",
    "auditor",
    "viewer",
]

ROLE_ALIASES = {
    "ceo": "executive",
    "cio": "cio",
    "cto": "cio",
    "cfo": "finance",
    "admin": "super_admin",
    "administrator": "super_admin",
    "executive": "executive",
    "global_admin": "super_admin",
    "superadmin": "super_admin",
    "customer_admin": "client_admin",
    "customeradmin": "client_admin",
    "client_admin": "client_admin",
    "customer_owner": "client_admin",
    "org_admin": "client_admin",
    "organization_admin": "client_admin",
    "finance": "finance",
    "finops": "finance",
    "finopsmanager": "finance",
    "viewer": "viewer",
    "auditor": "auditor",
    "leadership": "executive",
    "approval": "executive",
    "technical": "technical",
    "saas": "operations",
    "msp": "operations",
    "cloudops": "operations",
    "cloud_ops": "operations",
    "engineering": "technical",
    "engineer": "technical",
    "governance": "security",
}

ALLOWED_ROLES = {
    "super_admin",
    "client_admin",
    "executive",
    "cio",
    "technical",
    "finance",
}

CANONICAL_ROLES = set(ROLES)


def normalize_role(role: object) -> str:
    """Normalize a role alias into its canonical internal representation."""
    raw = str(role or "").strip()
    normalized = raw.lower()
    if normalized in CANONICAL_ROLES:
        return normalized
    return ROLE_ALIASES.get(normalized, normalized)

