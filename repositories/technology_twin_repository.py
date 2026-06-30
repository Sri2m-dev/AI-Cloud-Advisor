from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core.digital_twin.technology import InfrastructureLayer, TechnologyTwin


DEFAULT_TECHNOLOGY_TWIN_STORE = Path("data/technology_digital_twins.json")


class TechnologyTwinRepository:
    def __init__(self, store_path: str | Path = DEFAULT_TECHNOLOGY_TWIN_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._twins: dict[UUID, TechnologyTwin] = {}
        self._load()

    def save(self, twin: TechnologyTwin) -> TechnologyTwin:
        self._twins[twin.id] = twin
        self._persist()
        return twin

    def get(self, twin_id: UUID | str) -> TechnologyTwin | None:
        return self._twins.get(UUID(str(twin_id)))

    def latest_for_organization(self, organization_id: UUID | str) -> TechnologyTwin | None:
        resolved_id = UUID(str(organization_id))
        twins = [twin for twin in self._twins.values() if twin.organization_id == resolved_id]
        if not twins:
            return None
        return sorted(twins, key=lambda twin: twin.generated_at, reverse=True)[0]

    def list_for_organization(self, organization_id: UUID | str) -> list[TechnologyTwin]:
        resolved_id = UUID(str(organization_id))
        return sorted(
            [twin for twin in self._twins.values() if twin.organization_id == resolved_id],
            key=lambda twin: twin.generated_at,
            reverse=True,
        )

    def get_infrastructure_layer(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
    ) -> InfrastructureLayer | None:
        twin = self.latest_for_organization(organization_id)
        if not twin:
            return None
        node = twin.nodes.get(UUID(str(technology_id)))
        return node.infrastructure_layer if node else None

    def save_infrastructure_layer(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
        layer: InfrastructureLayer,
    ) -> TechnologyTwin:
        twin = self.latest_for_organization(organization_id)
        if not twin:
            raise KeyError(f"Technology twin not found for organization: {organization_id}")
        node = twin.nodes.get(UUID(str(technology_id)))
        if not node:
            raise KeyError(f"Technology node not found: {technology_id}")
        node.infrastructure_layer = layer
        twin.refresh()
        return self.save(twin)

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        payload = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        self._twins = {
            UUID(item["id"]): TechnologyTwin.from_dict(item)
            for item in payload.get("technology_twins", [])
        }

    def _persist(self) -> None:
        payload = {
            "technology_twins": [
                twin.to_dict()
                for twin in sorted(self._twins.values(), key=lambda item: item.generated_at, reverse=True)
            ]
        }
        self.store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
