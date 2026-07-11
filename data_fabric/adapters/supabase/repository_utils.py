"""Shared helpers for Supabase Data Fabric repository adapters."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from data_fabric.adapters.supabase.exceptions import SupabaseAdapterOperationError
from data_fabric.persistence.models import PageRequest, PageResult, RepositoryQuery


def single_row(response: Any) -> dict[str, Any]:
    data = getattr(response, "data", None) or []
    return data[0] if isinstance(data, list) else data


def optional_row(response: Any) -> dict[str, Any] | None:
    data = getattr(response, "data", None) or []
    if not data:
        return None
    return data[0]


def response_rows(response: Any) -> list[dict[str, Any]]:
    return list(getattr(response, "data", None) or [])


def ensure_inserted(response: Any, label: str) -> dict[str, Any]:
    row = single_row(response)
    if not row:
        raise SupabaseAdapterOperationError(f"{label} was not inserted")
    return row


def iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value is not None else None


def dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(str(value)).astimezone(timezone.utc)


def ratio_to_100(value: Any) -> float | None:
    if value is None:
        return None
    score = float(value)
    return score * 100.0 if score <= 1.0 else score


def score_to_ratio(value: Any) -> float:
    if value is None:
        return 1.0
    score = float(value)
    return score / 100.0 if score > 1.0 else score


def plain_mapping(value: Mapping[str, Any] | dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    return {str(key): plain_value(item) for key, item in dict(value).items()}


def plain_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return plain_mapping(value)
    if isinstance(value, tuple):
        return [plain_value(item) for item in value]
    if isinstance(value, list):
        return [plain_value(item) for item in value]
    if isinstance(value, set | frozenset):
        return sorted((plain_value(item) for item in value), key=str)
    if isinstance(value, datetime):
        return iso(value)
    return deepcopy(value)


def apply_query_filters(builder: Any, query: RepositoryQuery) -> Any:
    for field, value in query.filters.items():
        builder = builder.eq(field, value)
    for field, value in query.metadata_filters.items():
        builder = builder.eq(f"metadata->{field}", value)
    sort_field = sort_column(query.sort.field)
    builder = builder.order(sort_field, desc=query.sort.descending)
    return builder.range(query.page.offset, query.page.offset + query.page.limit - 1)


def sort_column(field: str) -> str:
    return {
        "record_id": "id",
        "snapshot_id": "snapshot_id",
        "event_id": "event_id",
        "provenance_id": "provenance_id",
    }.get(field, field)


def page_result(records: list[Any], query: RepositoryQuery) -> PageResult:
    return PageResult(tuple(records), len(records), query.page)


def default_page(page: PageRequest | None = None) -> PageRequest:
    return page or PageRequest()
