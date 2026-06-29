from __future__ import annotations

import hashlib
from typing import Any


class ConnectorNormalizer:
    @staticmethod
    def normalize_record(connector_name: str, record: dict[str, Any]) -> dict[str, Any]:
        source_id = str(record.get("id") or record.get("asset_id") or record.get("resource_id") or record.get("name") or "")
        stable_key = hashlib.sha256(f"{connector_name}:{source_id}:{record.get('type', '')}".encode()).hexdigest()[:24]
        return {
            "fabric_key": stable_key,
            "source_system": connector_name,
            "source_record_id": source_id or stable_key,
            "entity_type": record.get("entity_type") or record.get("type") or record.get("asset_type") or "Unknown",
            "display_name": record.get("name") or record.get("asset_name") or record.get("technology_name") or source_id or stable_key,
            "normalized_payload": record,
            "quality_score": ConnectorNormalizer.quality_score(record),
        }

    @staticmethod
    def normalize_records(connector_name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [ConnectorNormalizer.normalize_record(connector_name, record) for record in records]

    @staticmethod
    def quality_score(record: dict[str, Any]) -> int:
        required = ["id", "name", "type"]
        present = sum(1 for field in required if record.get(field) or record.get({"id": "asset_id", "name": "asset_name", "type": "asset_type"}[field]))
        return round((present / len(required)) * 100)
