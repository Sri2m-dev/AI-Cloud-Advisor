from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core.digital_twin.business_twin import BusinessTwin


DEFAULT_BUSINESS_TWIN_STORE = Path("data/business_digital_twins.json")


class BusinessDigitalTwinRepository:
    def __init__(self, store_path: str | Path = DEFAULT_BUSINESS_TWIN_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._twins: dict[UUID, BusinessTwin] = {}
        self._load()

    def save(self, twin: BusinessTwin) -> BusinessTwin:
        self._twins[twin.id] = twin
        self._persist()
        return twin

    def get(self, twin_id: UUID | str) -> BusinessTwin | None:
        return self._twins.get(UUID(str(twin_id)))

    def latest_for_organization(self, organization_id: UUID | str) -> BusinessTwin | None:
        resolved_id = UUID(str(organization_id))
        matches = [twin for twin in self._twins.values() if twin.organization_id == resolved_id]
        if not matches:
            return None
        return sorted(matches, key=lambda twin: twin.generated_at, reverse=True)[0]

    def list_for_organization(self, organization_id: UUID | str) -> list[BusinessTwin]:
        resolved_id = UUID(str(organization_id))
        return sorted(
            [twin for twin in self._twins.values() if twin.organization_id == resolved_id],
            key=lambda twin: twin.generated_at,
            reverse=True,
        )

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        payload = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        self._twins = {
            UUID(item["id"]): BusinessTwin.from_dict(item)
            for item in payload.get("business_twins", [])
        }

    def _persist(self) -> None:
        payload = {
            "business_twins": [
                twin.to_dict()
                for twin in sorted(self._twins.values(), key=lambda item: item.generated_at, reverse=True)
            ]
        }
        self.store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
