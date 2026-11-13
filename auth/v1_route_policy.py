"""V1 page registration policy derived from the approved M0 route catalogue."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path

from auth.role_constants import normalize_role

_CATALOGUE = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "release"
    / "nexora-v1-m0-2026-11-07"
    / "route_catalogue.csv"
)
_CUSTOMER_WORKFLOW_ROLES = frozenset(
    {"client_admin", "executive", "cio", "finance", "operations", "auditor"}
)
_REQUIRED_V1_M0_PAGES = frozenset(
    {
        "pages/login.py",
        "pages/logout.py",
        "pages/approval_center.py",
        "pages/reports.py",
    }
)
_CUSTOMER_WORKFLOW_PAGES = frozenset(
    {
        "pages/customer_workspace.py",
        "pages/approval_center.py",
        "pages/reports.py",
    }
)


def _normalize_path(page_path: str) -> str:
    return str(page_path or "").replace("\\", "/").lstrip("./")


@lru_cache(maxsize=1)
def route_catalogue() -> dict[str, dict[str, str]]:
    try:
        with _CATALOGUE.open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
    except OSError as error:
        raise RuntimeError("The approved V1 route catalogue is unavailable") from error
    if not rows or not {"path", "navigation_labels", "scope"}.issubset(rows[0]):
        raise RuntimeError("The approved V1 route catalogue is invalid")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        path = _normalize_path(row.get("path", ""))
        if not path or path in result:
            raise RuntimeError("The approved V1 route catalogue has an invalid path")
        result[path] = row
    return result


def is_v1_page_allowed(
    page_path: str,
    role: str,
    *,
    page_paths: Mapping[str, str],
    role_pages: Mapping[str, Sequence[str]],
) -> bool:
    path = _normalize_path(page_path)
    normalized_role = normalize_role(role)
    if not normalized_role:
        return False
    if path == "pages/logout.py":
        return True
    if path in _CUSTOMER_WORKFLOW_PAGES:
        return normalized_role in _CUSTOMER_WORKFLOW_ROLES
    return path in _REQUIRED_V1_M0_PAGES


def allowed_page_specs(
    role: str,
    *,
    page_paths: Mapping[str, str],
    role_pages: Mapping[str, Sequence[str]],
) -> list[tuple[str, str]]:
    normalized_role = normalize_role(role)
    labels = list(role_pages.get(normalized_role, ()))
    if normalized_role in _CUSTOMER_WORKFLOW_ROLES:
        labels.extend(("Customer Workspace", "Approvals", "Reports"))

    pages: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label in labels:
        path = _normalize_path(page_paths.get(label, ""))
        if (
            path
            and path not in seen
            and is_v1_page_allowed(
                path,
                normalized_role,
                page_paths=page_paths,
                role_pages=role_pages,
            )
        ):
            pages.append((label, path))
            seen.add(path)
    pages.append(("Logout", "pages/logout.py"))
    return pages
