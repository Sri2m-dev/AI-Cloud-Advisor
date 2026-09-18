"""Production GA navigation contract tests.

These tests protect the curated Nexora product navigation without changing
the underlying authorization registry or persona landing-page contracts.
"""

from pathlib import Path

from components.navigation.sidebar import (
    SECTION_ORDER,
    SIMPLIFIED_ROLE_NAVIGATION,
    build_persona_navigation_items,
)
from components.sidebar_navigation import (
    DEFAULT_ROLE_PAGE,
    PAGE_PATHS,
    ROLE_PAGES,
)


CANONICAL_SECTION_ORDER = [
    "Home",
    "Ask Nexora",
    "Executive",
    "Technology",
    "Financial",
    "SaaS",
    "Operations",
    "Governance",
    "Data & Integrations",
    "Administration",
]


GA_PERSONA_COUNTS = {
    "super_admin": 39,
    "client_admin": 26,
    "operations": 15,
    "auditor": 13,
}


CURRENT_DEFAULT_ROLE_PAGES = {
    "super_admin": "pages/executive_dashboard.py",
    "client_admin": "pages/executive_command_center.py",
    "operations": "pages/operations_workspace.py",
    "auditor": "pages/audit_timeline.py",
}


def _configured_pages(role: str) -> list[str]:
    return [
        item["page_label"]
        for item in SIMPLIFIED_ROLE_NAVIGATION[role]
    ]


def _configured_sections(role: str) -> list[str]:
    return [
        item["section"]
        for item in SIMPLIFIED_ROLE_NAVIGATION[role]
    ]


def test_production_ga_section_order_is_canonical():
    assert SECTION_ORDER == CANONICAL_SECTION_ORDER


def test_ga_personas_exist_with_expected_curated_counts():
    for role, expected_count in GA_PERSONA_COUNTS.items():
        assert role in SIMPLIFIED_ROLE_NAVIGATION
        assert len(SIMPLIFIED_ROLE_NAVIGATION[role]) == expected_count


def test_ga_persona_routes_are_registered():
    registered = set(PAGE_PATHS)

    for role in GA_PERSONA_COUNTS:
        pages = _configured_pages(role)
        missing = [
            page
            for page in pages
            if page not in registered
        ]

        assert not missing, (role, missing)


def test_ga_persona_routes_remain_within_rbac_authority():
    for role in GA_PERSONA_COUNTS:
        authorized = set(ROLE_PAGES[role])
        pages = _configured_pages(role)

        unauthorized = [
            page
            for page in pages
            if page not in authorized
        ]

        assert not unauthorized, (role, unauthorized)


def test_ga_persona_routes_do_not_duplicate_destinations():
    for role in GA_PERSONA_COUNTS:
        pages = _configured_pages(role)

        assert len(pages) == len(set(pages)), role


def test_ga_persona_sections_use_only_canonical_taxonomy():
    canonical_sections = set(CANONICAL_SECTION_ORDER)

    for role in GA_PERSONA_COUNTS:
        sections = _configured_sections(role)

        unknown = [
            section
            for section in sections
            if section not in canonical_sections
        ]

        assert not unknown, (role, unknown)


def test_ask_nexora_is_first_class_for_ga_personas():
    for role in GA_PERSONA_COUNTS:
        items = SIMPLIFIED_ROLE_NAVIGATION[role]

        assert len(items) >= 2
        assert items[0]["section"] == "Home"

        assert items[1]["label"] == "Ask Nexora"
        assert items[1]["page_label"] == "Enterprise AI Copilot"
        assert items[1]["section"] == "Ask Nexora"


def test_enterprise_ai_copilot_is_registered_and_authorized():
    assert "Enterprise AI Copilot" in PAGE_PATHS

    for role in GA_PERSONA_COUNTS:
        assert "Enterprise AI Copilot" in ROLE_PAGES[role]


def test_persona_builder_resolves_complete_ga_navigation():
    for role, expected_count in GA_PERSONA_COUNTS.items():
        navigation = build_persona_navigation_items(
            role=role,
            page_paths=PAGE_PATHS,
        )

        assert len(navigation) == 1

        children = navigation[0]["children"]

        assert len(children) == expected_count

        resolved_pages = [
            child["page"]
            for child in children
        ]

        expected_pages = [
            PAGE_PATHS[item["page_label"]]
            for item in SIMPLIFIED_ROLE_NAVIGATION[role]
        ]

        assert resolved_pages == expected_pages


def test_super_admin_uses_curated_product_surface():
    configured_pages = _configured_pages("super_admin")

    assert len(configured_pages) == GA_PERSONA_COUNTS["super_admin"]
    assert len(configured_pages) < len(ROLE_PAGES["super_admin"])


def test_persona_builder_returns_empty_for_unconfigured_role():
    navigation = build_persona_navigation_items(
        role="__production_ga_unconfigured_role__",
        page_paths=PAGE_PATHS,
    )

    assert navigation == []


def test_current_ga_default_role_pages_are_unchanged():
    for role, expected_path in CURRENT_DEFAULT_ROLE_PAGES.items():
        assert DEFAULT_ROLE_PAGE[role] == expected_path


def test_current_ga_default_role_page_files_exist():
    repository_root = Path(__file__).resolve().parents[1]

    for role, relative_path in CURRENT_DEFAULT_ROLE_PAGES.items():
        path = repository_root / relative_path

        assert path.is_file(), (role, str(path))


def test_role_pages_remain_authorization_superset_of_ga_personas():
    for role in GA_PERSONA_COUNTS:
        configured = set(_configured_pages(role))
        authorized = set(ROLE_PAGES[role])

        assert configured <= authorized


def test_existing_simplified_personas_are_preserved():
    for role in (
        "executive",
        "cio",
        "finance",
        "technical",
        "sales_engineer",
    ):
        assert role in SIMPLIFIED_ROLE_NAVIGATION
        assert SIMPLIFIED_ROLE_NAVIGATION[role]


def test_ga_navigation_does_not_remove_registered_routes():
    # The curated product surface is presentation-only.
    # The underlying PAGE_PATHS registry remains substantially broader.
    assert len(PAGE_PATHS) > GA_PERSONA_COUNTS["super_admin"]


def test_renderer_no_longer_special_cases_super_admin():
    repository_root = Path(__file__).resolve().parents[1]
    sidebar_path = repository_root / "components" / "navigation" / "sidebar.py"

    source = sidebar_path.read_text(encoding="utf-8")

    assert 'if normalized_role == "super_admin":' not in source


def test_renderer_preserves_persona_first_and_full_navigation_fallback():
    repository_root = Path(__file__).resolve().parents[1]
    sidebar_path = repository_root / "components" / "navigation" / "sidebar.py"

    source = sidebar_path.read_text(encoding="utf-8")

    persona_call = (
        "navigation_items = build_persona_navigation_items("
        "role=normalized_role, page_paths=page_paths or {})"
    )

    fallback_call = (
        "navigation_items = build_navigation_items("
        "page_paths=page_paths or {}, role_pages=role_pages or {})"
    )

    assert persona_call in source
    assert fallback_call in source

    assert source.index(persona_call) < source.index(fallback_call)
