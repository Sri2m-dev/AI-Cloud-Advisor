"""Deterministic JSON-compatible serialization and hashing."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID

from data_fabric.foundation.exceptions import DataFabricValidationError


class DeterministicSerializer(ABC):
    """Interface for stable JSON-compatible Data Fabric serialization."""

    @abstractmethod
    def to_json_compatible(self, value: Any) -> Any:
        """Convert a value into deterministic JSON-compatible content."""

    @abstractmethod
    def dumps(self, value: Any) -> str:
        """Serialize a value with deterministic ordering and separators."""

    @abstractmethod
    def content_hash(self, value: Any) -> str:
        """Return a deterministic SHA-256 content hash."""


class DefaultDeterministicSerializer(DeterministicSerializer):
    """Default deterministic serializer for P3 contracts and plans."""

    def to_json_compatible(self, value: Any) -> Any:
        if is_dataclass(value):
            value = asdict(value)
        if isinstance(value, MappingProxyType):
            value = dict(value)
        if isinstance(value, Mapping):
            return {
                str(key): self.to_json_compatible(value[key])
                for key in sorted(value, key=lambda item: str(item))
            }
        if isinstance(value, tuple | list):
            return [self.to_json_compatible(item) for item in value]
        if isinstance(value, set | frozenset):
            converted = [self.to_json_compatible(item) for item in value]
            return sorted(converted, key=lambda item: json.dumps(item, sort_keys=True, default=str))
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise DataFabricValidationError("datetime values must be timezone-aware")
            return value.astimezone(timezone.utc).isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, UUID):
            return str(value)
        return value

    def dumps(self, value: Any) -> str:
        return json.dumps(
            self.to_json_compatible(value),
            sort_keys=True,
            separators=(",", ":"),
        )

    def content_hash(self, value: Any) -> str:
        return hashlib.sha256(self.dumps(value).encode("utf-8")).hexdigest()
