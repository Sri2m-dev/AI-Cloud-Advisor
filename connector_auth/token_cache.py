"""Connector token cache."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock

from connector_auth.credentials import ConnectorAuthContext


@dataclass
class TokenCache:
    """Thread-safe in-memory token cache."""

    _tokens: dict[str, ConnectorAuthContext] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def get(self, cache_key: str) -> ConnectorAuthContext | None:
        with self._lock:
            context = self._tokens.get(cache_key)
            if context is None:
                return None
            if context.expires_at is not None and context.expires_at <= datetime.now(timezone.utc):
                self._tokens.pop(cache_key, None)
                return None
            return context

    def set(self, cache_key: str, context: ConnectorAuthContext) -> ConnectorAuthContext:
        with self._lock:
            self._tokens[cache_key] = context
            return context

    def clear(self, cache_key: str | None = None) -> None:
        with self._lock:
            if cache_key is None:
                self._tokens.clear()
            else:
                self._tokens.pop(cache_key, None)
