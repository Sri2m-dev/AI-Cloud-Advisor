"""Canonical, domain-separated identities for document structure."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


def _canonical(value: Any) -> Any:
    if is_dataclass(value):
        return _canonical(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        ordered = sorted(value.items(), key=lambda pair: str(pair[0]))
        return {str(key): _canonical(item) for key, item in ordered}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported identity value: {type(value).__name__}")


def structural_fingerprint(domain: str, *values: Any) -> str:
    """Hash bounded structural values using stable canonical serialization."""
    if not domain or not domain.strip():
        raise ValueError("identity domain is required")
    payload = json.dumps(
        {"domain": domain, "values": _canonical(values)},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scoped_container_id(context, content_fingerprint: str) -> str:
    return "container-" + structural_fingerprint(
        "pue-011b.container.v1",
        context.organization_id,
        context.tenant_id,
        context.prospect_id,
        context.source_id,
        content_fingerprint,
    )[:32]


def scoped_document_id(context, container_id: str, structural_locator: str) -> str:
    return "document-" + structural_fingerprint(
        "pue-011b.document.v1",
        context.organization_id,
        context.tenant_id,
        context.prospect_id,
        context.source_id,
        container_id,
        structural_locator,
    )[:32]


def scoped_region_id(
    context, container_id: str, document_id: str | None, location, fingerprint: str
) -> str:
    return "region-" + structural_fingerprint(
        "pue-011b.region.v1",
        context.organization_id,
        context.tenant_id,
        context.prospect_id,
        context.source_id,
        container_id,
        document_id,
        location,
        fingerprint,
    )[:32]
