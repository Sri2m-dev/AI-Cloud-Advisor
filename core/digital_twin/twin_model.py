from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.digital_twin.twin_entity import TwinEntity
from core.digital_twin.twin_graph import TwinGraph
from core.digital_twin.twin_snapshot import TwinSnapshot
from core.digital_twin.twin_state import TwinLifecycle, TwinRefreshStatus, TwinState
from core.entities.entity import EnterpriseEntity, EntityRelationship, utc_now_iso


class TwinType(str, Enum):
    ENTERPRISE = "Enterprise"
    BUSINESS = "Business"
    TECHNOLOGY = "Technology"
    COST = "Cost"
    RISK = "Risk"
    OPERATIONAL = "Operational"
    EXECUTIVE = "Executive"


class TwinRefreshTrigger(str, Enum):
    MANUAL = "Manual"
    SCHEDULED = "Scheduled"
    CONNECTOR_TRIGGER = "Connector Trigger"
    EVENT_TRIGGER = "Event Trigger"
    WEBHOOK_TRIGGER = "Webhook Trigger"


@dataclass(frozen=True, slots=True)
class TwinRefreshPolicy:
    trigger: str = TwinRefreshTrigger.MANUAL.value
    enabled: bool = True
    interval_minutes: int | None = None
    source_system: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DigitalTwinModel:
    organization_id: UUID
    name: str = "Enterprise Digital Twin"
    id: UUID = field(default_factory=uuid4)
    twin_type: str = TwinType.ENTERPRISE.value
    twin_version: str = "1.0.0"
    supported_platform_version: str = "4.0"
    lifecycle: str = TwinLifecycle.DRAFT.value
    refresh_policies: list[TwinRefreshPolicy] = field(default_factory=lambda: [TwinRefreshPolicy()])
    entities: dict[UUID, TwinEntity] = field(default_factory=dict)
    relationships: list[EntityRelationship] = field(default_factory=list)
    snapshots: list[TwinSnapshot] = field(default_factory=list)
    state: TwinState | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        organization_id: UUID,
        entities: list[EnterpriseEntity] | None = None,
        relationships: list[EntityRelationship] | None = None,
        name: str = "Enterprise Digital Twin",
        twin_type: str = TwinType.ENTERPRISE.value,
    ) -> "DigitalTwinModel":
        model = cls(organization_id=organization_id, name=name, twin_type=twin_type)
        model.state = TwinState(model.id)
        if entities is not None:
            model.refresh(entities, relationships or [])
        return model

    def refresh(
        self,
        entities: list[EnterpriseEntity],
        relationships: list[EntityRelationship],
        refresh_source: str = TwinRefreshTrigger.MANUAL.value,
    ) -> TwinState:
        self.lifecycle = TwinLifecycle.SYNCHRONIZING.value
        for entity in entities:
            existing = self.entities.get(entity.id)
            if existing:
                existing.refresh_from_entity(entity)
            else:
                self.entities[entity.id] = TwinEntity.from_entity(entity)
        self.relationships = list(relationships)
        self.updated_at = utc_now_iso()
        if self.state is None:
            self.state = TwinState(self.id)
        health_components = self._health_components()
        self.state.mark_refreshed(
            entity_count=len(self.entities),
            relationship_count=len(self.relationships),
            health_score=self._health_score(health_components),
            freshness_score=100.0,
            refresh_source=refresh_source,
            health_components=health_components,
        )
        self.lifecycle = self.state.lifecycle
        return self.state

    def graph(self) -> TwinGraph:
        return TwinGraph.build(self.id, self.entities, self.relationships)

    def snapshot(self, name: str = "", description: str = "") -> TwinSnapshot:
        if self.state is None:
            self.state = TwinState(self.id)
        snapshot = TwinSnapshot(
            twin_id=self.id,
            state=self.state,
            graph=self.graph(),
            name=name or f"{self.name} Snapshot",
            description=description,
            twin_version=self.twin_version,
            state_version=self.state.state_version,
            graph_version=self.state.graph_version,
            metadata={
                "entity_count": len(self.entities),
                "relationship_count": len(self.relationships),
            },
        )
        self.snapshots.append(snapshot)
        self.state.snapshot_count = len(self.snapshots)
        return snapshot

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["organization_id"] = str(self.organization_id)
        payload["refresh_policies"] = [policy.to_dict() for policy in self.refresh_policies]
        payload["entities"] = [entity.to_dict() for entity in self.entities.values()]
        payload["relationships"] = [relationship.to_dict() for relationship in self.relationships]
        payload["snapshots"] = [snapshot.to_dict() for snapshot in self.snapshots]
        payload["state"] = self.state.to_dict() if self.state else None
        return payload

    def twin_metadata(self) -> dict[str, Any]:
        return {
            "twin_id": str(self.id),
            "twin_type": self.twin_type,
            "twin_version": self.twin_version,
            "state_version": self.state.state_version if self.state else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_refresh": self.state.last_refreshed_at if self.state else None,
            "refresh_source": self.state.refresh_source if self.state else None,
            "refresh_status": self.state.refresh_status if self.state else TwinRefreshStatus.NEVER_RUN.value,
            "snapshot_count": len(self.snapshots),
            "graph_version": self.state.graph_version if self.state else None,
            "twin_lifecycle": self.lifecycle,
            "health_score": self.state.health_score if self.state else None,
            "health_components": self.state.health_components if self.state else {},
        }

    def _health_components(self) -> dict[str, float]:
        if not self.entities:
            return {
                "applications": 100.0,
                "technology": 100.0,
                "risk": 100.0,
                "metadata": 100.0,
                "correlation": 100.0,
                "connector_health": 100.0,
            }
        application_entities = [entity for entity in self.entities.values() if entity.layer == "Application"]
        technology_entities = [entity for entity in self.entities.values() if entity.layer in {"Technology", "Cloud", "SaaS"}]
        risk_entities = [entity for entity in self.entities.values() if entity.layer == "Risk"]
        relationship_density = min(100.0, (len(self.relationships) / max(len(self.entities), 1)) * 50)
        source_coverage = (
            sum(1 for entity in self.entities.values() if entity.source_systems)
            / max(len(self.entities), 1)
        ) * 100
        return {
            "applications": self._average_health(application_entities),
            "technology": self._average_health(technology_entities),
            "risk": 100.0 - min(100.0, len(risk_entities) * 10.0),
            "metadata": round(source_coverage, 2),
            "correlation": round(relationship_density, 2),
            "connector_health": 100.0,
        }

    def _health_score(self, components: dict[str, float] | None = None) -> float:
        components = components or self._health_components()
        return round(sum(components.values()) / len(components), 2) if components else 100.0

    @staticmethod
    def _average_health(entities: list[TwinEntity]) -> float:
        if not entities:
            return 100.0
        return round(sum(entity.health_score for entity in entities) / len(entities), 2)

    def legacy_entity_health_score(self) -> float:
        if not self.entities:
            return 100.0
        entity_scores = [entity.health_score for entity in self.entities.values()]
        return round(sum(entity_scores) / len(entity_scores), 2)
