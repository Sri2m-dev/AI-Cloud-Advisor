# Simple smoke-test for role normalization and route mapping

from auth.role_constants import normalize_role

# Mapping used in app_main routing
ROUTE_MAPPING = {
    "executive_dashboard": ["executive", "technical", "super_admin"],
    "operations_workspace": ["finance"],
}

TEST_ROLES = [
    "CTO",
    "engineer",
    "eng",
    "Finance",
    "finops",
    "admin",
    "root",
    "",
    None,
]

for t in TEST_ROLES:
    nr = normalize_role(t)
    route = None
    for page, allowed in ROUTE_MAPPING.items():
        if nr in allowed:
            route = page
            break
    print(f"Input: {t!r} -> Normalized: {nr!r} -> Route: {route}")
