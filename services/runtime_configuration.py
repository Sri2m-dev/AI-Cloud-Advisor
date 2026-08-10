"""Validation helpers for runtime repository composition."""

from __future__ import annotations

from urllib.parse import urlparse

_PLACEHOLDER_TOKENS = (
    "your-project",
    "replace-with",
    "example.supabase.co",
    "changeme",
    "placeholder",
)


def is_valid_supabase_configuration(url: str | None, key: str | None) -> bool:
    """Return true only for a usable-looking Supabase URL and credential."""
    normalized_url = str(url or "").strip()
    normalized_key = str(key or "").strip()
    combined = f"{normalized_url} {normalized_key}".casefold()
    if not normalized_url or not normalized_key:
        return False
    if any(token in combined for token in _PLACEHOLDER_TOKENS):
        return False
    parsed = urlparse(normalized_url)
    return parsed.scheme == "https" and bool(parsed.netloc)
