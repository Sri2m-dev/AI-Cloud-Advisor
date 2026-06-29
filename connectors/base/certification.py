from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


CERTIFICATION_DOMAINS = (
    "organization",
    "billing",
    "inventory",
    "governance",
    "operations",
    "identity",
    "optimization",
)


class ConnectorCertification:
    @staticmethod
    def build(
        connector_name: str,
        version: str,
        authentication: str,
        status: str,
        records_synced: int,
        sync_duration: float,
        coverage: dict[str, bool],
        last_sync: str | None = None,
        next_sync: str | None = None,
        health_score: int | None = None,
        details: dict[str, Any] | None = None,
        required_domains: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        domains = required_domains or CERTIFICATION_DOMAINS
        complete_domains = sum(1 for domain in domains if coverage.get(domain, False))
        computed_health = round((complete_domains / len(domains)) * 100)
        return {
            "connector": connector_name,
            "version": version,
            "status": status,
            "authentication": authentication,
            "last_sync": last_sync or datetime.now(timezone.utc).isoformat(),
            "next_sync": next_sync,
            "records_synced": records_synced,
            "sync_duration": sync_duration,
            "coverage": {domain: bool(coverage.get(domain, False)) for domain in domains},
            "health_score": health_score if health_score is not None else computed_health,
            "certification_level": ConnectorCertification.level(coverage, domains),
            "certified_at": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }

    @staticmethod
    def level(coverage: dict[str, bool], domains: tuple[str, ...] | None = None) -> str:
        required = domains or CERTIFICATION_DOMAINS
        complete_domains = sum(1 for domain in required if coverage.get(domain, False))
        if complete_domains == len(required):
            return "Gold"
        if complete_domains >= 4:
            return "Silver"
        if complete_domains >= 2:
            return "Bronze"
        return "Uncertified"
