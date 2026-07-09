"""In-memory provenance tracker implementation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from data_fabric.lineage.exceptions import LineageValidationError
from data_fabric.lineage.interfaces import ProvenanceTracker


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """Source authority and derivation context for one canonical object."""

    id: str
    source_system: str
    source_identifier: str
    organization_id: str
    collection_method: str
    entity_id: str | None = None
    relationship_id: str | None = None
    connector_version: str | None = None
    normalization_rule: str | None = None
    identity_resolution_rule: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class InMemoryProvenanceTracker(ProvenanceTracker):
    """Non-persistent reference tracker for provenance records."""

    def __init__(self) -> None:
        self._records: list[ProvenanceRecord] = []

    def record_provenance(self, record: ProvenanceRecord) -> ProvenanceRecord:
        self._validate_record(record)
        stored = deepcopy(record)
        self._records.append(stored)
        return deepcopy(stored)

    def trace_provenance_by_source(
        self,
        source_system: str,
        source_identifier: str,
    ) -> list[ProvenanceRecord]:
        return [
            deepcopy(record)
            for record in self._records
            if record.source_system == source_system
            and record.source_identifier == source_identifier
        ]

    def explain_entity_origin(self, entity_id: str) -> str:
        records = [record for record in self._records if record.entity_id == entity_id]
        if not records:
            return f"No provenance recorded for entity {entity_id}."
        record = sorted(records, key=lambda item: item.captured_at)[0]
        return (
            f"Entity {entity_id} is derived from {record.source_system}/"
            f"{record.source_identifier} using {record.collection_method}."
        )

    def explain_relationship_origin(self, relationship_id: str) -> str:
        records = [
            record for record in self._records if record.relationship_id == relationship_id
        ]
        if not records:
            return f"No provenance recorded for relationship {relationship_id}."
        record = sorted(records, key=lambda item: item.captured_at)[0]
        return (
            f"Relationship {relationship_id} is derived from {record.source_system}/"
            f"{record.source_identifier} using {record.collection_method}."
        )

    @staticmethod
    def _validate_record(record: ProvenanceRecord) -> None:
        required = {
            "id": record.id,
            "source_system": record.source_system,
            "source_identifier": record.source_identifier,
            "organization_id": record.organization_id,
            "collection_method": record.collection_method,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise LineageValidationError(
                f"Provenance record is missing required field(s): {', '.join(missing)}"
            )
        if not record.entity_id and not record.relationship_id:
            raise LineageValidationError(
                "Provenance record requires entity_id or relationship_id"
            )
