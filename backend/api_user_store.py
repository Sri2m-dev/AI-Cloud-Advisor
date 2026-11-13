"""Authoritative configured user records for the standalone API auth surface."""

import json
import os
from typing import Any


class APIUserStoreUnavailable(RuntimeError):
    """Raised when API user authorization records cannot be loaded."""


def load_api_users() -> dict[str, dict[str, Any]]:
    raw = os.getenv("API_USERS_JSON")
    if not raw:
        raise APIUserStoreUnavailable("API user authorization store is not configured")

    try:
        users = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise APIUserStoreUnavailable("API user authorization store is invalid") from exc

    if not isinstance(users, dict) or any(
        not isinstance(username, str) or not isinstance(record, dict)
        for username, record in users.items()
    ):
        raise APIUserStoreUnavailable("API user authorization store is invalid")

    return users


def is_api_user_active(record: dict[str, Any]) -> bool:
    return not (
        record.get("disabled") is True
        or record.get("enabled") is False
        or record.get("is_active") is False
        or str(record.get("status", "")).strip().lower()
        in {"disabled", "inactive", "removed"}
    )
