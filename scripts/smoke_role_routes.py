#!/usr/bin/env python3
"""Smoke test for role -> page routing (mirrors app_main.py logic).
Run: python scripts/smoke_role_routes.py
"""

try:
    from auth.role_constants import normalize_role
except Exception:
    import importlib.util
    import pathlib
    import sys

    repo_root = pathlib.Path(__file__).resolve().parent
    role_file = repo_root.joinpath("..", "auth", "role_constants.py").resolve()
    spec = importlib.util.spec_from_file_location("role_constants", str(role_file))
    role_mod = importlib.util.module_from_spec(spec)
    sys.modules["role_constants"] = role_mod
    spec.loader.exec_module(role_mod)
    normalize_role = role_mod.normalize_role


def route_for_role(role, authenticated=True):
    if not authenticated:
        return "pages/login.py"
    r = normalize_role(role)
    if r in [
        "executive",
        "technical",
        "super_admin",
    ]:
        return "pages/executive_dashboard.py"
    elif r in [
        "finance",
    ]:
        return "pages/operations_workspace.py"
    else:
        return "pages/login.py"


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
