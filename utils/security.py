
ROLE_ACCESS = {
    "Leadership": ["Executive Dashboard"],
    "FinOps": ["Executive Dashboard", "Approval Center"],
    "CloudOps": ["Operations Workspace"],
    "Engineering": ["Technical Analytics"],
    "Governance": ["Audit Timeline", "SaaS Governance"],
    "Admin": ["*"]
}

def has_permission(role, workspace):
    if role == "Admin":
        return True
    allowed = ROLE_ACCESS.get(role, [])
    return "*" in allowed or workspace in allowed

