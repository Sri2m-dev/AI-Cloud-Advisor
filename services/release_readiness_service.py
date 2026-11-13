"""Readiness is unavailable until a reviewed evidence source is integrated.

The legacy persist argument is retained, but an unverified assessment is never
written as a certification record. This service performs no datastore access.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from nexora_release import RELEASE_VERSION

NOT_VERIFIED = "NOT_VERIFIED"


class ReleaseReadinessService:
    def __init__(self, organization_id: str | None = None) -> None:
        self.organization_id = resolve_organization_id(organization_id)

    def _base(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "score": None,
            "status": NOT_VERIFIED,
            "reason_code": "READINESS_EVIDENCE_UNAVAILABLE",
            "evidence": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def validate_release(self, persist: bool = True) -> dict[str, Any]:
        payload = self._base()
        payload.update(
            {
                "kpis": {
                    "Release Readiness": None,
                    "Release Status": NOT_VERIFIED,
                    "Version": RELEASE_VERSION,
                    "Known Blockers": None,
                },
                "checks": [
                    {"Check": name, "Score": None, "Status": NOT_VERIFIED}
                    for name in (
                        "Compile",
                        "Tests",
                        "Certification",
                        "Security",
                        "Performance",
                        "Compliance",
                        "Documentation",
                        "Release Notes",
                        "Migration",
                        "Rollback",
                        "Known Issues",
                    )
                ],
            }
        )
        return payload

    def validate_production_readiness(self, persist: bool = True) -> dict[str, Any]:
        payload = self._base()
        payload.update(
            {
                "kpis": {
                    "Production Ready": NOT_VERIFIED,
                    "Production Readiness": None,
                    "Blockers": None,
                },
                "domains": [
                    {"Domain": name, "Status": NOT_VERIFIED, "Score": None}
                    for name in (
                        "Infrastructure",
                        "Secrets",
                        "Configuration",
                        "Database",
                        "Storage",
                        "Queues",
                        "Monitoring",
                        "Logging",
                        "Alerting",
                        "Backups",
                        "Scaling",
                        "Certificates",
                        "RBAC",
                        "Tenants",
                    )
                ],
            }
        )
        return payload

    def version_1_readiness_report(self, persist: bool = True) -> dict[str, Any]:
        report = self._base()
        report.update(
            {
                "Version": RELEASE_VERSION,
                "Overall Readiness": None,
                "Platform": NOT_VERIFIED,
                "Connectors": NOT_VERIFIED,
                "Observability": NOT_VERIFIED,
                "Release Status": NOT_VERIFIED,
            }
        )
        for name in (
            "Security",
            "Compliance",
            "Performance",
            "Data Quality",
            "Knowledge Graph",
            "Digital Twin",
            "AI Trust",
            "DR Readiness",
            "Operational Readiness",
            "Production Readiness",
        ):
            report[name] = None
        return report
