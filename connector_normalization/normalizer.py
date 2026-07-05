"""Canonical normalization interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, Sequence

from connector_normalization.canonical_models import CanonicalEnterpriseRecord
from connector_sdk import ConnectorRecord


class CanonicalNormalizer(ABC):
    """Base class for converting connector records into canonical records."""

    normalizer_id: str
    supported_sources: tuple[str, ...] = ()
    supported_record_types: tuple[str, ...] = ()

    @abstractmethod
    def normalize(self, records: Sequence[ConnectorRecord]) -> Sequence[CanonicalEnterpriseRecord]:
        """Normalize connector records into canonical enterprise records."""

    def normalize_one(self, record: ConnectorRecord) -> CanonicalEnterpriseRecord:
        """Normalize a single connector record."""

        normalized = self.normalize([record])
        if not normalized:
            raise ValueError("Normalizer returned no canonical record.")
        return normalized[0]


class MappingNormalizer(CanonicalNormalizer):
    """Simple mapping-based normalizer for tests and lightweight adapters."""

    def __init__(self, normalizer_id: str, mapper: object) -> None:
        self.normalizer_id = normalizer_id
        self._mapper = mapper

    def normalize(self, records: Sequence[ConnectorRecord]) -> Sequence[CanonicalEnterpriseRecord]:
        return [self._mapper(record) for record in records]  # type: ignore[misc]
