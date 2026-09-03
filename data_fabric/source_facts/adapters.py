"""Shared SourceFact adapters for API, CMDB, telemetry, and file evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Mapping

from connector_sdk import ConnectorRecord
from data_fabric.source_facts.models import FactType, Freshness, SourceFactInput


class ConnectorSourceFactAdapter:
    def adapt(self, records: Iterable[ConnectorRecord], mappings: Mapping[str, FactType]):
        facts = []
        for record in records:
            for field, fact_type in mappings.items():
                if field not in record.payload:
                    continue
                facts.append(
                    SourceFactInput(
                        source_record_id=record.source_id,
                        fact_type=fact_type,
                        subject_reference=str(record.payload.get("subject_id") or record.source_id),
                        predicate=field,
                        value=record.payload[field],
                        observed_at=record.observed_at,
                        source_schema_version=str(record.payload.get("schema_version", "1")),
                        freshness=Freshness.FRESH,
                        evidence_reference=f"connector:{record.source_id}",
                        provenance={"connector_entity_type": record.entity_type},
                    )
                )
        return tuple(facts)


class UniversalEvidenceSourceFactAdapter:
    def adapt(self, rows: Iterable[Mapping], mappings: Mapping[str, FactType], *, file_id: str):
        facts = []
        for ordinal, row in enumerate(rows, 1):
            source_id = str(row.get("source_record_id") or f"row-{ordinal}")
            subject = str(row.get("subject_reference") or source_id)
            for field, fact_type in mappings.items():
                if field not in row:
                    continue
                facts.append(
                    SourceFactInput(
                        source_id,
                        fact_type,
                        subject,
                        field,
                        row[field],
                        observed_at=datetime.now(timezone.utc),
                        freshness=Freshness.FRESH,
                        evidence_reference=f"file:{file_id}:row:{ordinal}",
                        provenance={"file_id": file_id, "row": ordinal},
                    )
                )
        return tuple(facts)


CloudApiSourceFactAdapter = ConnectorSourceFactAdapter
CmdbSourceFactAdapter = ConnectorSourceFactAdapter
TelemetrySourceFactAdapter = ConnectorSourceFactAdapter
