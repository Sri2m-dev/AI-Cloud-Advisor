"""Centralized RBAC role definitions and normalization helpers."""

ROLES = [
    "super_admin",
    "executive",
    "finance",
    "operations",
    "security",
    "technical",
    "auditor",
    "viewer",
]

ROLE_ALIASES = {
    "ceo": "executive",
    "cto": "technical",
    "cfo": "finance",
    "admin": "super_admin",
    "global_admin": "super_admin",
    "customer_admin": "super_admin",
    "finops": "finance",
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

CANONICAL_ROLES = set(ROLES)


def normalize_role(role: object) -> str:
    """Normalize a role alias into its canonical internal representation."""
    raw = str(role or "").strip()
    normalized = raw.lower()
    if normalized in CANONICAL_ROLES:
        return normalized
    return ROLE_ALIASES.get(normalized, normalized)

