from __future__ import annotations

from typing import Any

def resolve_organization_id(organization_id: str | None = None) -> str:
    resolved = str(organization_id or "").strip()
    if not resolved:
        raise ValueError("organization_id is required; implicit tenant fallback is disabled")
    return resolved


def require_organization_id(organization_id: str | None = None) -> str:
    return resolve_organization_id(organization_id)


def with_organization(rows: list[dict[str, Any]], organization_id: str) -> list[dict[str, Any]]:
    resolved = require_organization_id(organization_id)
    return [dict(row, organization_id=resolved) for row in rows]


def ensure_payload_organization(payload: dict[str, Any], organization_id: str | None = None) -> dict[str, Any]:
    resolved = require_organization_id(organization_id or payload.get("organization_id"))
    return dict(payload, organization_id=resolved)
