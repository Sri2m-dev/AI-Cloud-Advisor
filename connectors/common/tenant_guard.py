from __future__ import annotations

from typing import Any

from config import DEFAULT_ORG_ID


CONNECTOR_FALLBACK_ORG_ID = "27ebcb06-5941-4cd4-826f-96be73bddea5"
_cached_client_org_id: str | None = None


def resolve_organization_id(organization_id: str | None = None) -> str:
    if organization_id:
        return str(organization_id)

    client_org_id = _get_first_client_id()
    return client_org_id or CONNECTOR_FALLBACK_ORG_ID or DEFAULT_ORG_ID


def _get_first_client_id() -> str | None:
    global _cached_client_org_id

    if _cached_client_org_id:
        return _cached_client_org_id

    try:
        from services.supabase_client import supabase

        response = supabase.table("clients").select("id").limit(1).execute()
        rows = response.data or []
        if rows and rows[0].get("id"):
            _cached_client_org_id = str(rows[0]["id"])
            return _cached_client_org_id
    except Exception as exc:
        print("CLIENT ORGANIZATION FALLBACK LOAD FAILED:", exc)

    return None


def require_organization_id(organization_id: str | None = None) -> str:
    resolved = resolve_organization_id(organization_id)
    if not resolved:
        raise ValueError("organization_id is required for connector operations")
    return resolved


def with_organization(rows: list[dict[str, Any]], organization_id: str) -> list[dict[str, Any]]:
    resolved = require_organization_id(organization_id)
    return [dict(row, organization_id=resolved) for row in rows]


def ensure_payload_organization(payload: dict[str, Any], organization_id: str | None = None) -> dict[str, Any]:
    resolved = require_organization_id(organization_id or payload.get("organization_id"))
    return dict(payload, organization_id=resolved)
