from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from uuid import UUID

from core.entities.entity import EnterpriseEntity
from core.metadata.data_quality import DataQualityAssessment
from core.metadata.lineage import LineageEdge
from core.metadata.metadata_record import FreshnessStatus, MetadataRecord
from core.metadata.provenance import ProvenanceRecord
from repositories.entity_repository import EntityRepository
from repositories.metadata_catalog_repository import MetadataCatalogRepository


class MetadataCatalogService:
    def __init__(
        self,
        metadata_repository: MetadataCatalogRepository | None = None,
        entity_repository: EntityRepository | None = None,
    ):
        self.metadata_repository = metadata_repository or MetadataCatalogRepository()
        self.entity_repository = entity_repository or EntityRepository()

    def register_source_metadata(
        self,
        entity_id: UUID | str,
        source_system: str,
        sync_time: str | datetime,
        confidence_score: float = 100.0,
        source_record_id: str = "",
        source_uri: str = "",
        steward_id: UUID | str | None = None,
        metadata: dict | None = None,
    ) -> MetadataRecord:
        entity = self._get_entity(entity_id)
        sync_time_text = self._normalize_timestamp(sync_time)
        staleness_days = self._age_days(sync_time_text)
        freshness_score = self._freshness_score(staleness_days)
        provenance = self.metadata_repository.save_provenance(
            ProvenanceRecord(
                entity_id=entity.id,
                organization_id=entity.organization_id,
                source_system=source_system.strip(),
                source_record_id=source_record_id,
                source_uri=source_uri,
                operation="sync",
                actor_id=UUID(str(steward_id)) if steward_id else None,
                metadata=metadata or {},
            )
        )
        record = MetadataRecord(
            entity_id=entity.id,
            organization_id=entity.organization_id,
            source_system=source_system.strip(),
            sync_time=sync_time_text,
            steward_id=UUID(str(steward_id)) if steward_id else None,
            owner_id=entity.owner_id,
            confidence_score=self._bounded(confidence_score),
            completeness_score=self._entity_completeness(entity),
            freshness_score=freshness_score,
            source_coverage=self._source_coverage(entity),
            owner_coverage=100.0 if entity.owner_id else 0.0,
            relationship_coverage=self._relationship_coverage(entity.id),
            lineage_depth=self._lineage_depth(entity.id),
            staleness_days=staleness_days,
            freshness_status=self._freshness_status(staleness_days).value,
            provenance_id=provenance.id,
            metadata=metadata or {},
        )
        return self.metadata_repository.save_metadata(record)

    def record_lineage(
        self,
        source_entity_id: UUID | str,
        target_entity_id: UUID | str,
        transformation: str,
        source_system: str = "metadata_catalog",
        confidence_score: float = 100.0,
        metadata: dict | None = None,
    ) -> LineageEdge:
        source = self._get_entity(source_entity_id)
        target = self._get_entity(target_entity_id)
        edge = LineageEdge(
            source_entity_id=source.id,
            target_entity_id=target.id,
            organization_id=target.organization_id,
            transformation=transformation.strip(),
            source_system=source_system.strip(),
            confidence_score=self._bounded(confidence_score),
            metadata=metadata or {},
        )
        return self.metadata_repository.save_lineage(edge)

    def assess_data_quality(self, entity_id: UUID | str) -> DataQualityAssessment:
        entity = self._get_entity(entity_id)
        records = self.metadata_repository.get_entity_metadata(entity.id)
        latest = records[0] if records else None
        staleness_days = latest.staleness_days if latest else self._age_days(entity.updated_at)
        assessment = DataQualityAssessment(
            entity_id=entity.id,
            organization_id=entity.organization_id,
            completeness_score=self._entity_completeness(entity),
            freshness_score=latest.freshness_score if latest else self._freshness_score(staleness_days),
            confidence_score=self._average([record.confidence_score for record in records], default=75.0),
            lineage_depth=self._lineage_depth(entity.id),
            source_coverage=self._source_coverage(entity),
            owner_coverage=100.0 if entity.owner_id else 0.0,
            relationship_coverage=self._relationship_coverage(entity.id),
            staleness_days=staleness_days,
            freshness_status=self._freshness_status(staleness_days).value,
            issues=self._quality_issues(entity, records, staleness_days),
            metadata={
                "source_systems": sorted({record.source_system for record in records}),
                "metadata_record_count": len(records),
            },
        )
        return self.metadata_repository.save_quality_assessment(assessment)

    def get_entity_metadata(self, entity_id: UUID | str) -> dict:
        entity = self._get_entity(entity_id)
        return {
            "entity": entity.to_dict(),
            "metadata_records": [record.to_dict() for record in self.metadata_repository.get_entity_metadata(entity.id)],
            "latest_quality": (
                latest.to_dict()
                if (latest := self.metadata_repository.get_latest_quality_assessment(entity.id))
                else None
            ),
            "provenance": [record.to_dict() for record in self.metadata_repository.get_provenance(entity.id)],
        }

    def get_lineage_graph(self, entity_id: UUID | str) -> dict:
        root = self._get_entity(entity_id)
        edges = self.metadata_repository.get_lineage_edges(root.id)
        entity_ids = {root.id}
        for edge in edges:
            entity_ids.add(edge.source_entity_id)
            entity_ids.add(edge.target_entity_id)
        nodes = []
        for node_id in sorted(entity_ids, key=str):
            entity = self.entity_repository.get_entity(node_id)
            nodes.append(
                {
                    "id": str(node_id),
                    "display_name": entity.display_name if entity else "Unknown",
                    "entity_type": entity.entity_type if entity else "Unknown",
                }
            )
        return {
            "root_entity_id": str(root.id),
            "nodes": nodes,
            "edges": [edge.to_dict() for edge in edges],
        }

    def get_stale_entities(self, stale_after_days: int = 30) -> list[MetadataRecord]:
        return self.metadata_repository.get_stale_entities(stale_after_days)

    def get_low_confidence_entities(self, threshold: float = 70.0) -> list[MetadataRecord]:
        return self.metadata_repository.get_low_confidence_entities(threshold)

    def _get_entity(self, entity_id: UUID | str) -> EnterpriseEntity:
        entity = self.entity_repository.get_entity(entity_id)
        if not entity:
            raise KeyError(f"Entity not found: {entity_id}")
        return entity

    def _relationship_coverage(self, entity_id: UUID) -> float:
        return 100.0 if self.entity_repository.get_relationships(entity_id) else 0.0

    def _lineage_depth(self, entity_id: UUID) -> int:
        edges = self.metadata_repository.get_lineage_edges()
        adjacency: dict[UUID, list[UUID]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source_entity_id, []).append(edge.target_entity_id)
        visited = {entity_id}
        queue: deque[tuple[UUID, int]] = deque([(entity_id, 0)])
        depth = 0
        while queue:
            current_id, current_depth = queue.popleft()
            depth = max(depth, current_depth)
            for next_id in adjacency.get(current_id, []):
                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, current_depth + 1))
        return depth

    @staticmethod
    def _entity_completeness(entity: EnterpriseEntity) -> float:
        checks = [
            bool(entity.display_name.strip()),
            bool(entity.entity_type.strip()),
            bool(entity.organization_id),
            bool(entity.owner_id),
            bool(entity.description.strip()),
            bool(entity.tags),
            bool(entity.source_systems),
        ]
        return round((sum(checks) / len(checks)) * 100, 2)

    @staticmethod
    def _source_coverage(entity: EnterpriseEntity) -> float:
        if not entity.source_systems:
            return 0.0
        return round(min(100.0, len(entity.source_systems) * 25.0), 2)

    @staticmethod
    def _freshness_score(staleness_days: int) -> float:
        if staleness_days <= 1:
            return 100.0
        if staleness_days <= 7:
            return 90.0
        if staleness_days <= 30:
            return 70.0
        if staleness_days <= 90:
            return 40.0
        return 10.0

    @staticmethod
    def _freshness_status(staleness_days: int) -> FreshnessStatus:
        if staleness_days < 0:
            return FreshnessStatus.UNKNOWN
        if staleness_days <= 7:
            return FreshnessStatus.CURRENT
        if staleness_days <= 30:
            return FreshnessStatus.WARNING
        return FreshnessStatus.STALE

    @staticmethod
    def _age_days(timestamp: str) -> int:
        try:
            parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except ValueError:
            return 999
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - parsed).days

    @staticmethod
    def _normalize_timestamp(value: str | datetime) -> str:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _average(values: list[float], default: float) -> float:
        return round(sum(values) / len(values), 2) if values else default

    @staticmethod
    def _bounded(value: float) -> float:
        return round(max(0.0, min(100.0, float(value))), 2)

    def _quality_issues(
        self,
        entity: EnterpriseEntity,
        records: list[MetadataRecord],
        staleness_days: int,
    ) -> list[str]:
        issues = []
        if not records:
            issues.append("No metadata records registered")
        if not entity.owner_id:
            issues.append("Owner is missing")
        if not entity.source_systems:
            issues.append("Source system coverage is missing")
        if not self.entity_repository.get_relationships(entity.id):
            issues.append("Relationship coverage is missing")
        if staleness_days > 30:
            issues.append("Metadata is stale")
        if records and self._average([record.confidence_score for record in records], default=100.0) < 70:
            issues.append("Confidence is below enterprise threshold")
        return issues
