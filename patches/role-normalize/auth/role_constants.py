# Central role constants and normalization helpers

ROLES = [
    "executive",
    "technical",
    "finance",
    "super_admin",
]

ROLE_ALIASES = {
    # Executive aliases
    "cto": "executive",
    "ceo": "executive",
    "cfo": "executive",
    "chief_technical_officer": "executive",
    "chief_executive_officer": "executive",
    # Technical aliases
    "eng": "technical",
    "engineer": "technical",
    "devops": "technical",
    "platform_engineer": "technical",
    # Finance aliases
    "finops": "finance",
    "finance_manager": "finance",
    # Admin aliases
    "admin": "super_admin",
    "root": "super_admin",
}


def normalize_role(role: str) -> str:
    """Return canonical role for a given role string.

    - Handles None and empty strings by returning empty string.
    - Strips whitespace and lowercases input.
    - Maps known aliases to canonical roles in `ROLES`.
    - Returns input if it's already a canonical role.
    """
    if not role:
        return ""
    r = role.strip().lower()
    if r in ROLES:
        return r
    return ROLE_ALIASES.get(r, r)
