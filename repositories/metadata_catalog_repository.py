from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core.metadata.data_quality import DataQualityAssessment
from core.metadata.lineage import LineageEdge
from core.metadata.metadata_record import MetadataRecord
from core.metadata.provenance import ProvenanceRecord


DEFAULT_METADATA_STORE = Path("data/metadata_catalog.json")


class MetadataCatalogRepository:
    def __init__(self, store_path: str | Path = DEFAULT_METADATA_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._metadata_records: dict[UUID, MetadataRecord] = {}
        self._lineage_edges: dict[UUID, LineageEdge] = {}
        self._quality_assessments: list[DataQualityAssessment] = []
        self._provenance_records: list[ProvenanceRecord] = []
        self._load()

    def save_metadata(self, record: MetadataRecord) -> MetadataRecord:
        record.touch()
        self._metadata_records[record.id] = record
        self._persist()
        return record

    def get_entity_metadata(self, entity_id: UUID | str) -> list[MetadataRecord]:
        resolved_id = UUID(str(entity_id))
        return sorted(
            [record for record in self._metadata_records.values() if record.entity_id == resolved_id],
            key=lambda record: record.sync_time,
            reverse=True,
        )

    def get_stale_entities(self, stale_after_days: int = 30) -> list[MetadataRecord]:
        return sorted(
            [
                record
                for record in self._metadata_records.values()
                if record.staleness_days >= stale_after_days or record.freshness_status == "Stale"
            ],
            key=lambda record: record.staleness_days,
            reverse=True,
        )

    def get_low_confidence_entities(self, threshold: float = 70.0) -> list[MetadataRecord]:
        return sorted(
            [record for record in self._metadata_records.values() if record.confidence_score < threshold],
            key=lambda record: record.confidence_score,
        )

    def save_lineage(self, edge: LineageEdge) -> LineageEdge:
        self._lineage_edges[edge.id] = edge
        self._persist()
        return edge

    def get_lineage_edges(self, entity_id: UUID | str | None = None) -> list[LineageEdge]:
        edges = list(self._lineage_edges.values())
        if entity_id:
            resolved_id = UUID(str(entity_id))
            edges = [
                edge
                for edge in edges
                if edge.source_entity_id == resolved_id or edge.target_entity_id == resolved_id
            ]
        return sorted(edges, key=lambda edge: edge.created_at, reverse=True)

    def save_quality_assessment(self, assessment: DataQualityAssessment) -> DataQualityAssessment:
        self._quality_assessments.append(assessment)
        self._persist()
        return assessment

    def get_latest_quality_assessment(self, entity_id: UUID | str) -> DataQualityAssessment | None:
        resolved_id = UUID(str(entity_id))
        assessments = [
            assessment
            for assessment in self._quality_assessments
            if assessment.entity_id == resolved_id
        ]
        if not assessments:
            return None
        return sorted(assessments, key=lambda assessment: assessment.assessed_at, reverse=True)[0]

    def save_provenance(self, record: ProvenanceRecord) -> ProvenanceRecord:
        self._provenance_records.append(record)
        self._persist()
        return record

    def get_provenance(self, entity_id: UUID | str) -> list[ProvenanceRecord]:
        resolved_id = UUID(str(entity_id))
        return sorted(
            [record for record in self._provenance_records if record.entity_id == resolved_id],
            key=lambda record: record.captured_at,
            reverse=True,
        )

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        payload = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        self._metadata_records = {
            UUID(item["id"]): MetadataRecord.from_dict(item)
            for item in payload.get("metadata_records", [])
        }
        self._lineage_edges = {
            UUID(item["id"]): LineageEdge.from_dict(item)
            for item in payload.get("lineage_edges", [])
        }
        self._quality_assessments = [
            DataQualityAssessment.from_dict(item)
            for item in payload.get("quality_assessments", [])
        ]
        self._provenance_records = [
            ProvenanceRecord.from_dict(item)
            for item in payload.get("provenance_records", [])
        ]

    def _persist(self) -> None:
        payload = {
            "metadata_records": [
                record.to_dict()
                for record in sorted(self._metadata_records.values(), key=lambda item: item.updated_at, reverse=True)
            ],
            "lineage_edges": [
                edge.to_dict()
                for edge in sorted(self._lineage_edges.values(), key=lambda item: item.created_at, reverse=True)
            ],
            "quality_assessments": [assessment.to_dict() for assessment in self._quality_assessments],
            "provenance_records": [record.to_dict() for record in self._provenance_records],
        }
        self.store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
