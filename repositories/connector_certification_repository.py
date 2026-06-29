from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core.connectors.certification.certification_result import ConnectorCertificationResult
from core.connectors.certification.health_policy import ConnectorHealthAssessment, ConnectorHealthPolicy


DEFAULT_CONNECTOR_CERTIFICATION_STORE = Path("data/connector_certification.json")


class ConnectorCertificationRepository:
    def __init__(self, store_path: str | Path = DEFAULT_CONNECTOR_CERTIFICATION_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._certifications: list[ConnectorCertificationResult] = []
        self._health_assessments: list[ConnectorHealthAssessment] = []
        self._policies: dict[UUID, ConnectorHealthPolicy] = {}
        self._load()

    def save_certification(self, result: ConnectorCertificationResult) -> ConnectorCertificationResult:
        self._certifications.append(result)
        self._persist()
        return result

    def latest_certification(self, connector_id: UUID | str) -> ConnectorCertificationResult | None:
        resolved_id = UUID(str(connector_id))
        matches = [result for result in self._certifications if result.connector_id == resolved_id]
        if not matches:
            return None
        return sorted(matches, key=lambda result: result.certified_at, reverse=True)[0]

    def list_certifications(self, connector_id: UUID | str | None = None) -> list[ConnectorCertificationResult]:
        results = list(self._certifications)
        if connector_id:
            resolved_id = UUID(str(connector_id))
            results = [result for result in results if result.connector_id == resolved_id]
        return sorted(results, key=lambda result: result.certified_at, reverse=True)

    def save_health_assessment(self, assessment: ConnectorHealthAssessment) -> ConnectorHealthAssessment:
        self._health_assessments.append(assessment)
        self._persist()
        return assessment

    def latest_health_assessment(self, connector_id: UUID | str) -> ConnectorHealthAssessment | None:
        resolved_id = UUID(str(connector_id))
        matches = [assessment for assessment in self._health_assessments if assessment.connector_id == resolved_id]
        if not matches:
            return None
        return sorted(matches, key=lambda assessment: assessment.assessed_at, reverse=True)[0]

    def save_policy(self, policy: ConnectorHealthPolicy) -> ConnectorHealthPolicy:
        self._policies[policy.id] = policy
        self._persist()
        return policy

    def default_policy(self) -> ConnectorHealthPolicy:
        if not self._policies:
            return self.save_policy(ConnectorHealthPolicy())
        return sorted(self._policies.values(), key=lambda policy: policy.created_at)[0]

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        payload = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        self._certifications = [
            ConnectorCertificationResult.from_dict(item)
            for item in payload.get("certifications", [])
        ]
        self._health_assessments = [
            ConnectorHealthAssessment.from_dict(item)
            for item in payload.get("health_assessments", [])
        ]
        self._policies = {
            UUID(item["id"]): ConnectorHealthPolicy.from_dict(item)
            for item in payload.get("policies", [])
        }

    def _persist(self) -> None:
        payload = {
            "certifications": [result.to_dict() for result in self.list_certifications()],
            "health_assessments": [assessment.to_dict() for assessment in self._health_assessments],
            "policies": [policy.to_dict() for policy in self._policies.values()],
        }
        self.store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
