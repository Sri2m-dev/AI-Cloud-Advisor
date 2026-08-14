from __future__ import annotations

import inspect
from pathlib import Path

from components.executive_experience import WORKSPACES
from components.sidebar_navigation import EXECUTIVE_EXPERIENCE_PAGES, PAGE_PATHS, ROLE_PAGES


def test_rt1_through_rt8_are_composed():
    assert tuple(WORKSPACES) == (
        "command",
        "ceo",
        "cio",
        "cfo",
        "architect",
        "operations",
        "finops",
        "board",
    )


def test_every_workspace_is_role_gated_and_uses_canonical_pages():
    for workspace in WORKSPACES.values():
        assert workspace.roles
        assert workspace.surfaces
        for surface in workspace.surfaces:
            assert surface.page in PAGE_PATHS.values()
            assert surface.page.startswith("pages/")


def test_navigation_matches_workspace_entitlements():
    for role, labels in EXECUTIVE_EXPERIENCE_PAGES.items():
        assert set(labels).issubset(ROLE_PAGES[role])
        assert all(label in PAGE_PATHS for label in labels)


def test_surface_visibility_can_be_intersected_with_existing_rbac():
    reverse_paths = {path: label for label, path in PAGE_PATHS.items()}
    for workspace in WORKSPACES.values():
        for role in workspace.roles:
            allowed = frozenset(PAGE_PATHS[label] for label in ROLE_PAGES.get(role, ()))
            visible = tuple(item for item in workspace.surfaces if item.page in allowed)
            assert all(reverse_paths[item.page] in ROLE_PAGES[role] for item in visible)


def test_p5_composition_has_no_domain_or_persistence_dependency():
    import components.executive_experience as module

    source = inspect.getsource(module).lower()
    for forbidden in ("repositories", "sqlite", "sqlalchemy", "supabase", "openai"):
        assert forbidden not in source


def test_workspace_pages_delegate_to_shared_tenant_guard():
    root = Path(__file__).parents[2]
    for page in EXECUTIVE_EXPERIENCE_PAGES["super_admin"]:
        source = (root / PAGE_PATHS[page]).read_text(encoding="utf-8")
        assert "run_executive_workspace" in source
