"""Canonical record deduplication support."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Sequence

from connector_normalization import CanonicalEnterpriseRecord


class DeduplicationStrategy(str, Enum):
    PRIMARY_KEY = "primary_key"
    NATURAL_KEY = "natural_key"
    HASH = "hash"
    EXTERNAL_ID = "external_id"
    COMPOSITE_KEY = "composite_key"


@dataclass(frozen=True)
class DeduplicationKey:
    strategy: DeduplicationStrategy
    value: str


class DeduplicationEngine:
    """Generates deduplication keys and removes duplicates from batches."""

    def key_for(self, record: CanonicalEnterpriseRecord, strategy: DeduplicationStrategy = DeduplicationStrategy.PRIMARY_KEY) -> DeduplicationKey:
        if strategy == DeduplicationStrategy.PRIMARY_KEY:
            return DeduplicationKey(strategy, record.record_id)
        if strategy == DeduplicationStrategy.EXTERNAL_ID:
            return DeduplicationKey(strategy, f"{record.source_system}:{record.source_id}")
        if strategy == DeduplicationStrategy.NATURAL_KEY:
            return DeduplicationKey(strategy, f"{record.record_type.value}:{record.name}:{record.source_system}")
        if strategy == DeduplicationStrategy.COMPOSITE_KEY:
            return DeduplicationKey(strategy, f"{record.record_type.value}:{record.source_system}:{record.source_id}:{record.organization_id or ''}")
        payload = f"{record.record_type.value}:{record.source_system}:{record.source_id}:{record.name}:{record.provider_metadata}"
        return DeduplicationKey(strategy, sha256(payload.encode("utf-8")).hexdigest())

    def deduplicate(
        self,
        records: Sequence[CanonicalEnterpriseRecord],
        strategy: DeduplicationStrategy = DeduplicationStrategy.PRIMARY_KEY,
    ) -> list[CanonicalEnterpriseRecord]:
        seen: set[str] = set()
        deduped: list[CanonicalEnterpriseRecord] = []
        for record in records:
            key = self.key_for(record, strategy).value
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)
        return deduped
