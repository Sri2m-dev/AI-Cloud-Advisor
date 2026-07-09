"""Canonical publisher abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from connector_normalization.canonical_models import CanonicalEnterpriseRecord


@dataclass(frozen=True)
class CanonicalPublishResult:
    published_count: int
    target: str
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    warnings: tuple[str, ...] = field(default_factory=tuple)


class CanonicalPublisher(ABC):
    """Storage-agnostic canonical record publisher."""

    @abstractmethod
    def publish(self, records: Sequence[CanonicalEnterpriseRecord]) -> CanonicalPublishResult:
        """Publish canonical records to an implementation-defined target."""


class InMemoryCanonicalPublisher(CanonicalPublisher):
    """In-memory publisher for smoke tests and local validation."""

    def __init__(self, target: str = "memory") -> None:
        self.target = target
        self.records: list[CanonicalEnterpriseRecord] = []

    def publish(self, records: Sequence[CanonicalEnterpriseRecord]) -> CanonicalPublishResult:
        self.records.extend(records)
        return CanonicalPublishResult(published_count=len(records), target=self.target)
