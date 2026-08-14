#!/usr/bin/env python3
"""Smoke test for canonical role-to-page routing used by app_main.py.
Run: python scripts/smoke_role_routes.py
"""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from auth.role_constants import normalize_role  # noqa: E402
from components.sidebar_navigation import DEFAULT_ROLE_PAGE  # noqa: E402


def route_for_role(role, authenticated=True):
    if not authenticated:
        return "pages/login.py"
    return DEFAULT_ROLE_PAGE.get(normalize_role(role), "pages/login.py")


if __name__ == "__main__":
    roles = [
        "executive",
        "cto",
        "technical",
        "finance",
        "finops",
        "super_admin",
        "operations",
        "admin",
        "ceo",
        "engineer",
        "unknown",
        "",
    ]

    print("Authenticated=True")
    for role in roles:
        print(f"{role!r:10} -> {route_for_role(role, authenticated=True)}")

    print("\nAuthenticated=False")
    for role in roles[:5]:
        print(f"{role!r:10} -> {route_for_role(role, authenticated=False)}")
